# AlgoBattle Arena — Deploy to Cloudflare

> **For a 24/7 production judge, skip straight to [`vps-setup.md`](./vps-setup.md)**
> (Option A: free/cheap VPS + Docker + named tunnel — recommended for a real event).

## Architecture

```
Browser ──▶ Cloudflare Worker (algobattle-arena.dakshx.workers.dev)
                ├─ serves static frontend (Assets)
                ├─ /health, /api/leaderboard, /api/submissions (KV — always on)
                └─ /api/* → cloudflared tunnel → judge backend
                                                     ├─ Your machine (dev)
                                                     └─ VPS + Docker (prod)
```

**Why this shape:** Cloudflare Workers **cannot run Python/C++ compilers or subprocesses** — no sandbox executes on the edge. So the judge runs where it can (your machine / a small VPS) and the Worker securely proxies `/api/*` to it through a tunnel. The frontend is 100% static on Cloudflare's CDN, and the leaderboard persists in Workers KV.

---

## 1. Build the frontend

```bash
cd backend
source .venv/bin/activate
python sandbox/deploy/build_frontend.py
# → writes sandbox/deploy/public/index.html with problems injected
```

## 2. Start the judge backend locally

```bash
python sandbox/web_arena.py
# → FastAPI on http://127.0.0.1:8080
```

Verify: `curl http://127.0.0.1:8080/health`

## 3. Expose it with a Cloudflare Tunnel

```bash
# Install cloudflared (macOS)
brew install cloudflared

# Start a quick tunnel (no account needed)
cloudflared tunnel --url http://127.0.0.1:8080
# → prints: https://judge-xxxx.trycloudflare.com
```

Keep that terminal running. The URL is your **backend origin**.

## 4. Deploy the Worker (API proxy)

```bash
cd sandbox/deploy/worker
npm i -g wrangler
wrangler login

# Point the Worker at your tunnel
wrangler secret put TUNNEL_URL
# paste: https://judge-xxxx.trycloudflare.com

# Deploy
wrangler deploy
# → your worker at https://algobattle-arena.<your-subdomain>.workers.dev
```

## 5. Deploy the frontend to Cloudflare Pages

```bash
cd sandbox/deploy
wrangler pages deploy public --project-name algobattle-arena
# → your site at https://algobattle-arena.pages.dev
```

The frontend calls `/api/*` on **its own origin** (Pages). To make that reach the Worker, add a redirect/function:

```bash
# Pages Functions proxy (single file, no build step):
mkdir -p public/functions/api
cp ../worker/index.js public/functions/api/[[path]].js
```

Or simpler — set the Worker as the site's custom domain and have Pages serve through it (recommended for a single origin).

---

## Quick dev flow (no Cloudflare at all)

```bash
python sandbox/web_arena.py        # backend on :8080
open http://127.0.0.1:8080          # full arena served by FastAPI
```

---

## Files

| Path | Purpose |
|------|---------|
| `deploy/worker/index.js` | Cloudflare Worker — serves frontend + proxies `/api/*` |
| `deploy/worker/wrangler.toml` | Worker config |
| `deploy/public/index.html` | Static frontend (built) |
| `deploy/build_frontend.py` | Injects problems into the HTML |
| `deploy/vps-setup.md` | Production VPS + Docker + named tunnel guide |
| `../Dockerfile` | Judge Docker image (FastAPI + Python/C++/Java) |
| `../requirements.txt` | Python deps for the image |

## Security notes

- The tunnel exposes your judge to the internet — add auth in the Worker (check a bearer token) before going public.
- For real production, run the backend on a VPS with Docker (`backend/sandbox/Dockerfile`) + cgroups, not your laptop.
- `cloudflared quick tunnels` expire; use a **named tunnel** for persistence: `cloudflared tunnel create judge && cloudflared tunnel route dns judge judge.yourdomain.com`.

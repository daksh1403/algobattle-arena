# Run AlgoBattle in GitHub Codespaces — free, no credit card

Codespaces gives you a cloud Linux box (2 cores, 8GB, 120 core-hours/month
free with a GitHub account). It's perfect for **running the judge during a
live demo/event** — no VPS, no card, and your Mac can stay asleep.

## One click

1. Open the repo: `https://github.com/daksh1403/algobattle`
2. Green **Code ▾ → Codespaces → Create codespace on main**
3. Wait ~1 min for the container to build (`.devcontainer` auto-runs)
4. In the terminal:
   ```bash
   cd backend && source .venv/bin/activate
   python sandbox/web_arena.py
   ```
5. Codespaces shows **Forwarded Port 8080** — open it in the browser, or
   make it **Public** (ports panel → right-click → Port Visibility → Public)
   to get a URL anyone can hit.

## Connect the deployed site (optional, for a live demo)

```bash
# in Codespaces terminal
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o cloudflared
chmod +x cloudflared
./cloudflared tunnel --url http://127.0.0.1:8080
# → copy the https://xxx.trycloudflare.com URL
```

Then from your Mac:

```bash
cd backend/sandbox/deploy/worker
wrangler secret put TUNNEL_URL    # paste the trycloudflare URL
```

Now `algobattle-arena.dakshx.workers.dev` judges from the Codespaces box.

## Caveats

- Codespaces **stops when idle** (default 30 min) — fine for a demo session,
  not for 24/7. Restart it for the event and it resumes with all data
  (the `arena_data.json` lives in the repo's working copy).
- Keep the codespace for the event; delete it after.

## Alternative: run the same script anywhere

`backend/sandbox/deploy/setup-vps.sh` does the same for a real VPS or a
Codespaces container:

```bash
bash backend/sandbox/deploy/setup-vps.sh --codespaces   # in Codespaces
bash backend/sandbox/deploy/setup-vps.sh                # on a VPS
```

# AlgoBattle VPS Deployment — Option A (recommended)

Move the judge backend off your laptop onto a cheap/free VPS so the site
judges **24/7** without a local tunnel. The Cloudflare Worker (frontend +
KV leaderboard) stays as-is; only the sandbox moves.

```
Browser → Cloudflare Worker (algobattle-arena.dakshx.workers.dev)
              ├─ static frontend (Assets)
              ├─ /health, /api/leaderboard, /api/submissions (KV — always on)
              └─ /api/* → named tunnel → VPS: Docker algobattle-judge
```

## 1. Get a VPS

| Provider | Spec | Cost |
|----------|------|------|
| Oracle Cloud Free Tier | 2× ARM cores, 1 GB RAM, 50 GB disk | **Free forever** |
| Hetzner CX22 | 2× vCPU, 4 GB RAM | ~€4/mo |
| DigitalOcean | 1 vCPU, 1 GB RAM | $6/mo |
| GDG/college lab server | anything with Docker | $0 |

Minimum: 2 CPU cores, 1 GB RAM (g++ and javac need headroom), Ubuntu 22.04.

## 2. On the VPS — install Docker

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# log out and back in
```

## 3. Get the judge image onto the VPS

**Option A (easiest): build on the VPS**

```bash
# copy the backend folder up (from your Mac)
rsync -avz --exclude .venv --exclude __pycache__ --exclude deploy \
  /path/to/backend/sandbox user@VPS_IP:/opt/algobattle/sandbox

# on the VPS
cd /opt/algobattle/sandbox
docker build -t algobattle-judge -f Dockerfile .
```

**Option B: push to a registry (GitHub Container Registry / Docker Hub)**

```bash
# from your Mac — build & push
docker build -t ghcr.io/YOUR_USER/algobattle-judge -f sandbox/Dockerfile backend
docker push ghcr.io/YOUR_USER/algobattle-judge
# on the VPS
docker pull ghcr.io/YOUR_USER/algobattle-judge
```

## 4. Run the judge

```bash
docker run -d --restart=always --name algobattle-judge \
  -p 8080:8080 \
  -v algobattle-data:/data \
  algobattle-judge

# verify
curl http://127.0.0.1:8080/health
# → {"status":"ok","app":"algobattle","sandbox":"online"}
```

The leaderboard file persists in the `algobattle-data` volume (survives
container restarts/recreations).

## 5. Create a persistent named tunnel (one-time)

```bash
# on the VPS
cloudflared tunnel login
cloudflared tunnel create judge
# → creates credentials and prints a tunnel ID (e.g. abc123-...)

# add DNS route (needs a domain on Cloudflare; or use the .cfargotunnel.com URL)
cloudflared tunnel route dns judge judge.yourdomain.com

# config file ~/.cloudflared/config.yml
tunnel: abc123-...
credentials-file: /home/USER/.cloudflared/abc123-....json

ingress:
  - hostname: judge.yourdomain.com
    service: http://127.0.0.1:8080
  - service: http_status:404

# run as a service (survives reboots)
sudo cloudflared service install
```

If you don't have a domain on Cloudflare, you can still get a **stable**
URL by running the tunnel without a hostname and reading the
`*.cfargotunnel.com` URL from `cloudflared tunnel list` — it does not
rotate like quick tunnels.

## 6. Point the Worker at the VPS (one-time)

```bash
cd backend/sandbox/deploy/worker
wrangler secret put TUNNEL_URL
# paste: https://judge.yourdomain.com   (or the .cfargotunnel.com URL)
```

Done. The site now judges 24/7. Verify:

```bash
curl https://algobattle-arena.dakshx.workers.dev/health   # worker online
curl https://judge.yourdomain.com/health                  # judge online
```

## 7. Optional hardening

- **Firewall**: only allow 22 (SSH) and 443 (tunnel) — the tunnel reaches
  the judge via localhost, so you don't need 8080 open publicly:
  ```bash
  sudo ufw allow 22/tcp
  sudo ufw allow 443/tcp
  sudo ufw enable
  ```
- **Resource limits**: Docker already isolates CPU/memory per run via
  `RLIMIT_*` in the sandbox. Add a container cap for safety:
  ```bash
  docker run -d --restart=always --name algobattle-judge \
    -p 8080:8080 --memory 1g --cpus 2 \
    -v algobattle-data:/data \
    algobattle-judge
  ```
- **Backups**: the only state is `/data/arena_data.json` (volume). Snapshot
  it or `docker cp` it periodically.

## Known container quirks (already handled)

- **Java JVM in containers**: the JVM reserves ~1GB+ of *virtual* address
  space on startup (compressed class space) even with a small heap. The
  sandbox gives Java a 2GB `RLIMIT_AS` while capping the heap with
  `-Xmx256m -XX:MaxMetaspaceSize=128m -XX:ReservedCodeCacheSize=64m`, so
  real memory stays ~35MB but the JVM doesn't die with "Could not reserve
  enough space".
- **g++ / javac under load**: compiled languages get a 10s wall budget
  (Python gets 3s) so compile contention doesn't produce false TLEs.
- **HEALTHCHECK** runs `/health` every 30s; the container shows `healthy`
  in `docker ps` when the judge is ready.

## Rollback / local dev

The system works identically with the local tunnel:

```bash
python3 sandbox/web_arena.py            # local judge on :8080
cloudflared tunnel --url http://127.0.0.1:8080
wrangler secret put TUNNEL_URL          # point at the quick tunnel URL
```

#!/usr/bin/env bash
# AlgoBattle judge — one-command setup for a fresh Ubuntu server OR GitHub
# Codespaces. Installs Docker (server), pulls the judge image, runs it,
# and prints the tunnel command.
#
# Usage:
#   On a VPS:        bash setup-vps.sh
#   In Codespaces:   bash setup-vps.sh --codespaces   (no Docker needed)
set -e

MODE="${1:-server}"
PORT="${PORT:-8080}"
ADMIN_KEY="${ADMIN_KEY:-gdg-admin-2026}"
IMAGE="${IMAGE:-ghcr.io/daksh1403/algobattle-judge:latest}"

echo "==> AlgoBattle judge setup (mode: $MODE)"

if [ "$MODE" = "codespaces" ]; then
  echo "==> Codespaces mode: compilers + deps only (already have Docker)"
  sudo apt-get update -qq
  sudo apt-get install -y -qq g++ openjdk-17-jdk-headless >/dev/null 2>&1 || true
  cd backend
  [ -d .venv ] || python3 -m venv .venv
  source .venv/bin/activate
  pip install -q -r sandbox/requirements.txt
  echo ""
  echo "Start the judge:  python sandbox/web_arena.py"
  echo "Then open the forwarded port ${PORT} in Codespaces."
  exit 0
fi

# ---- server mode ----
echo "==> Installing Docker..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sh
  sudo usermod -aG docker "$USER" || true
fi

echo "==> Pulling judge image: $IMAGE"
docker pull "$IMAGE"

echo "==> Starting judge on port $PORT"
docker rm -f algobattle-judge >/dev/null 2>&1 || true
docker run -d --restart=always --name algobattle-judge \
  -p "$PORT:8080" --memory 1g --cpus 2 \
  -v algobattle-data:/data \
  -e ADMIN_KEY="$ADMIN_KEY" \
  "$IMAGE"

echo ""
echo "==> Verify:"
echo "  curl http://127.0.0.1:${PORT}/health"
echo ""
echo "==> Persistent tunnel (run once, survives reboots):"
echo "  cloudflared tunnel login"
echo "  cloudflared tunnel create judge"
echo "  cloudflared tunnel route dns judge judge.yourdomain.com   # if you have a domain"
echo "  sudo cloudflared service install"
echo ""
echo "Then from your Mac:  wrangler secret put TUNNEL_URL"

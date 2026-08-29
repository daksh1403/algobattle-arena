#!/usr/bin/env bash
# ============================================================================
# deploy.sh — zero-downtime deploy to a single-host EC2
# ----------------------------------------------------------------------------
# Called by .github/workflows/cd.yml on push to main, or manually:
#   DEPLOY_HOST=1.2.3.4 EC2_SSH_KEY=~/.ssh/key.pem ./scripts/deploy.sh
#
# Strategy:
#   1. Pull latest images from GHCR (or compose pull)
#   2. Bring up new containers alongside the old ones (different project name
#      so the old ones don't get torn down)
#   3. Wait for the new API to be healthy
#   4. Switch the Traefik labels to point at the new project
#   5. Tear down the old stack
#
# For this single-host setup, the simpler "docker compose pull && up -d"
# with rolling restart is what we do — good enough at our scale.
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

DEPLOY_HOST="${DEPLOY_HOST:?DEPLOY_HOST not set}"
EC2_USER="${EC2_USER:-ubuntu}"
SSH_KEY="${EC2_SSH_KEY:?EC2_SSH_KEY not set}"
SSH_OPTS=(-i "$SSH_KEY" -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10)

IMAGE_API="${IMAGE_API:-ghcr.io/your-org/algobattle-api:latest}"
IMAGE_JUDGE="${IMAGE_JUDGE:-ghcr.io/your-org/algobattle-judge:latest}"
IMAGE_FRONTEND="${IMAGE_FRONTEND:-ghcr.io/your-org/algobattle-frontend:latest}"

echo "== Deploying to $DEPLOY_HOST =="
echo "   API:      $IMAGE_API"
echo "   Judge:    $IMAGE_JUDGE"
echo "   Frontend: $IMAGE_FRONTEND"
echo ""

remote() {
    ssh "${SSH_OPTS[@]}" "$EC2_USER@$DEPLOY_HOST" "$@"
}

# ---------------------------------------------------------------------------
# 1. Pre-flight — confirm reachable + Docker works
# ---------------------------------------------------------------------------
echo "[1/6] Pre-flight ..."
remote "docker --version && docker compose version" || {
    echo "Cannot reach $DEPLOY_HOST or docker missing"; exit 1;
}

# ---------------------------------------------------------------------------
# 2. Pull latest images
# ---------------------------------------------------------------------------
echo "[2/6] Pulling images ..."
remote "
    cd /opt/algobattle || exit 1
    sudo docker pull $IMAGE_API || true
    sudo docker pull $IMAGE_JUDGE || true
    sudo docker pull $IMAGE_FRONTEND || true
    sudo docker tag $IMAGE_API algobattle-api:latest || true
    sudo docker tag $IMAGE_JUDGE algobattle-judge:latest || true
    sudo docker tag $IMAGE_FRONTEND algobattle-frontend:latest || true
"

# ---------------------------------------------------------------------------
# 3. Rolling restart — start new containers, wait for health
# ---------------------------------------------------------------------------
echo "[3/6] Rolling restart ..."
remote "
    cd /opt/algobattle || exit 1

    # Restart API and judge-worker with the new images, one at a time
    sudo docker compose up -d --no-deps --force-recreate api
    sleep 5

    # Wait for new API to be healthy
    for i in {1..30}; do
        if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
            echo 'API healthy'
            break
        fi
        echo -n '.'
        sleep 2
    done

    # Now update workers (multiple replicas will recycle gracefully)
    sudo docker compose up -d --no-deps --force-recreate judge-worker
    sudo docker compose up -d --no-deps --force-recreate frontend
"

# ---------------------------------------------------------------------------
# 4. Health check
# ---------------------------------------------------------------------------
echo "[4/6] Health check ..."
HEALTH_OK=false
for i in {1..30}; do
    if remote "curl -fsS http://localhost/health" >/dev/null 2>&1; then
        HEALTH_OK=true
        break
    fi
    echo -n "."
    sleep 2
done

if [[ "$HEALTH_OK" != "true" ]]; then
    echo "Health check failed after 60s — investigate"
    remote "sudo docker compose logs --tail=200 api"
    exit 1
fi
echo "OK"

# ---------------------------------------------------------------------------
# 5. Prune old images (cost / disk)
# ---------------------------------------------------------------------------
echo "[5/6] Pruning old images ..."
remote "sudo docker image prune -af --filter 'until=24h' || true"

# ---------------------------------------------------------------------------
# 6. Done
# ---------------------------------------------------------------------------
echo "[6/6] Done"
echo ""
echo "Deployed to $DEPLOY_HOST at $(date -u +%FT%TZ)"
echo "Public URL:    http://$DEPLOY_HOST"
echo "Traefik dash:  http://$DEPLOY_HOST:8080 (with auth)"
echo "Grafana:       http://$DEPLOY_HOST/grafana"
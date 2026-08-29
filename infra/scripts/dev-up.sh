#!/usr/bin/env bash
# ============================================================================
# dev-up.sh — bring the full local stack up
# ----------------------------------------------------------------------------
# * Creates .env from .env.example if missing
# * Generates random secrets
# * Starts dev compose (postgres exposed, hot reload)
# ============================================================================
set -euo pipefail

cd "$(dirname "$0")/.."

# ----------------------------------------------------------------------------
# 1. .env
# ----------------------------------------------------------------------------
if [[ ! -f .env ]]; then
    echo "[dev-up] .env not found — copying from .env.example and generating secrets"
    cp .env.example .env
    # Generate strong random secrets
    POSTGRES_PASSWORD=$(openssl rand -hex 24)
    REDIS_PASSWORD=$(openssl rand -hex 24)
    SECRET_KEY=$(openssl rand -hex 32)
    JUDGE0_POSTGRES_PASSWORD=$(openssl rand -hex 24)
    JUDGE0_REDIS_PASSWORD=$(openssl rand -hex 24)
    JUDGE0_AUTH_TOKEN=$(openssl rand -hex 32)
    GRAFANA_ADMIN_PASSWORD=$(openssl rand -hex 16)

    sed -i.bak "s|change_me_postgres_password|$POSTGRES_PASSWORD|g"       .env
    sed -i.bak "s|change_me_redis_password|$REDIS_PASSWORD|g"               .env
    sed -i.bak "s|change_me_jwt_secret_at_least_32_chars_long|$SECRET_KEY|g" .env
    sed -i.bak "s|change_me_judge0_postgres_password|$JUDGE0_POSTGRES_PASSWORD|g" .env
    sed -i.bak "s|change_me_judge0_redis_password|$JUDGE0_REDIS_PASSWORD|g" .env
    sed -i.bak "s|change_me_judge0_internal_token|$JUDGE0_AUTH_TOKEN|g"   .env
    sed -i.bak "s|change_me_grafana_password|$GRAFANA_ADMIN_PASSWORD|g"    .env
    rm -f .env.bak
    echo "[dev-up] .env written. Back up the file — passwords are random."
fi

# ----------------------------------------------------------------------------
# 2. Compose
# ----------------------------------------------------------------------------
echo "[dev-up] Bringing up dev stack..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

# ----------------------------------------------------------------------------
# 3. Wait for API health
# ----------------------------------------------------------------------------
echo -n "[dev-up] Waiting for API health"
for i in {1..60}; do
    if curl -fsS http://localhost:8000/health >/dev/null 2>&1; then
        echo " — OK"
        break
    fi
    echo -n "."
    sleep 2
done

# ----------------------------------------------------------------------------
# 4. Done
# ----------------------------------------------------------------------------
echo ""
echo "============================================="
echo "Algobattle dev stack is up."
echo ""
echo "  App:        http://localhost:3000"
echo "  API:        http://localhost:8000"
echo "  Postgres:   localhost:5432 (user/pass in .env)"
echo "  Redis:      localhost:6379"
echo "  Adminer:    http://localhost:8081"
echo "  Mailhog:    http://localhost:8025"
echo "  Traefik:    http://localhost:8080"
echo "  Prometheus: http://localhost:9090"
echo "  Grafana:    http://localhost:3000 (admin / \$GRAFANA_ADMIN_PASSWORD)"
echo "============================================="
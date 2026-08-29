#!/usr/bin/env bash
# ============================================================================
# dev-down.sh — stop and remove the local stack
# ----------------------------------------------------------------------------
# Pass --volumes (or -v) to also remove named volumes (postgres data, etc).
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/.."

DOCKER_FLAGS=""
if [[ "${1:-}" =~ ^(-v|--volumes|--remove-volumes)$ ]]; then
    DOCKER_FLAGS="-v"
    echo "[dev-down] Removing volumes"
fi

echo "[dev-down] Stopping dev stack..."
docker compose -f docker-compose.yml -f docker-compose.dev.yml down $DOCKER_FLAGS --remove-orphans
docker compose -f judge0/docker-compose.judge0.yml --project-name algobattle-judge0 down $DOCKER_FLAGS --remove-orphans 2>/dev/null || true

echo "[dev-down] Done."
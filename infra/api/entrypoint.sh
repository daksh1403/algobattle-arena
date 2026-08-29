#!/bin/sh
# ============================================================================
# Algobattle API entrypoint
# ----------------------------------------------------------------------------
# Runs Alembic migrations then execs the CMD.
# In dev (target=dev), CMD is uvicorn --reload and we skip migrations.
# ============================================================================

set -e

# If first arg looks like uvicorn --reload, we're in dev — skip migrations.
case "$1" in
  uvicorn*) ;;
  *)
    echo "[entrypoint] Running database migrations..."
    if command -v alembic >/dev/null 2>&1; then
      alembic upgrade head || {
        echo "[entrypoint] WARNING: alembic upgrade failed — continuing. " \
             "Database may already be at head or unreachable."
      }
    else
      echo "[entrypoint] alembic not installed; skipping migrations."
    fi
    ;;
esac

echo "[entrypoint] Starting: $*"
exec "$@"
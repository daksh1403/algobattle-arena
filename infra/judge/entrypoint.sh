#!/bin/sh
# ============================================================================
# Algobattle Judge Worker — entrypoint
# ----------------------------------------------------------------------------
# Starts a tiny prometheus exporter side-car on :9100/metrics, then execs RQ.
# ============================================================================

set -e

# --- Start prometheus multiproc-aware exporter in background ---
if [ -n "$PROMETHEUS_MULTIPROC_DIR" ]; then
  mkdir -p "$PROMETHEUS_MULTIPROC_DIR"
fi

# --- Pre-flight ---
echo "[entrypoint] Connecting to Redis at $(echo "$REDIS_URL" | sed 's,:[^:@]*@,:***@,')"
python -c "
import os, sys, redis
try:
    r = redis.Redis.from_url(os.environ['REDIS_URL'])
    r.ping()
    print('[entrypoint] Redis OK')
except Exception as e:
    print(f'[entrypoint] Redis FAIL: {e}', file=sys.stderr)
    sys.exit(0)  # Don't fail boot; RQ will retry.
"

# --- Wait for Judge0 ---
if [ -n "$JUDGE0_URL" ]; then
  echo "[entrypoint] Waiting for Judge0 at $JUDGE0_URL ..."
  for i in $(seq 1 60); do
    if curl -fsS --max-time 2 "$JUDGE0_URL/about" >/dev/null 2>&1; then
      echo "[entrypoint] Judge0 reachable"
      break
    fi
    sleep 2
  done
fi

echo "[entrypoint] Starting RQ worker: $*"
exec "$@"
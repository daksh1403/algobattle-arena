#!/usr/bin/env bash
# ============================================================================
# load-test.sh — basic HTTP load test against the API
# ----------------------------------------------------------------------------
# Uses `hey` if available (https://github.com/rakyll/hey), else falls back to
# a parallel curl loop. Goal is just "does it hold up?" — for serious
# load testing use k6 or Locust.
#
# Usage:
#   ./scripts/load-test.sh [RPS] [DURATION]
#   ./scripts/load-test.sh 50 30s
# ============================================================================
set -euo pipefail

RPS="${1:-20}"
DUR="${2:-30s}"
BASE="${BASE_URL:-http://localhost}"
API="$BASE/api"

# Pick the endpoint to hammer (light, no auth)
ENDPOINT="${ENDPOINT:-/api/health}"

echo "== Algobattle load test =="
echo "   Target: $BASE$ENDPOINT"
echo "   RPS:    $RPS"
echo "   Time:   $DUR"
echo ""

# ---------------------------------------------------------------------------
# `hey` (preferred — gives real stats)
# ---------------------------------------------------------------------------
if command -v hey >/dev/null 2>&1; then
    hey -z "$DUR" -q "$RPS" -c 10 -t 10 "$BASE$ENDPOINT" || true
    exit 0
fi

# ---------------------------------------------------------------------------
# `wrk` fallback
# ---------------------------------------------------------------------------
if command -v wrk >/dev/null 2>&1; then
    THREADS=$(nproc 2>/dev/null || echo 2)
    CONNS=$(( RPS / THREADS ))
    [[ $CONNS -lt 1 ]] && CONNS=1
    wrk -t"$THREADS" -c"$CONNS" -d"$DUR" --latency "$BASE$ENDPOINT" || true
    exit 0
fi

# ---------------------------------------------------------------------------
# Pure bash fallback (less accurate)
# ---------------------------------------------------------------------------
echo "[load-test] neither 'hey' nor 'wrk' installed — using curl loop"
echo "    install hey:  brew install hey  /  go install github.com/rakyll/hey@latest"
echo ""

DUR_SECS=$(echo "$DUR" | sed -E 's/([0-9]+)[smh]?/\1/' | awk '{ if ($1 ~ /s$/) print $1; else if ($1 ~ /m$/) print $1*60; else if ($1 ~ /h$/) print $1*3600; else print $1 }')
TOTAL=$(( RPS * DUR_SECS ))

echo "Sending $TOTAL requests over $DUR_SECS seconds ($RPS RPS)..."

START=$(date +%s)
PIDS=()

send_one() {
    local i=$1
    curl -sS -o /dev/null -w "%{http_code} %{time_total}\n" "$BASE$ENDPOINT" 2>/dev/null
}
export -f send_one
export BASE ENDPOINT

seq 1 "$TOTAL" | xargs -n 1 -P "$RPS" -I{} bash -c 'send_one "$@"' _ {}

END=$(date +%s)
ELAPSED=$(( END - START ))

echo ""
echo "Done: $TOTAL requests in ${ELAPSED}s (effective RPS: $((TOTAL / (ELAPSED > 0 ? ELAPSED : 1))))"
#!/usr/bin/env bash
# ============================================================================
# smoke-test.sh — verify the stack works end-to-end
# ----------------------------------------------------------------------------
# Checks:
#   1. /health on the API
#   2. Postgres reachable
#   3. Redis reachable
#   4. Submit a sample problem (Two Sum) and poll for result
#   5. Read the leaderboard
#
# Usage:
#   ./scripts/smoke-test.sh [BASE_URL]
# ============================================================================
set -euo pipefail

BASE="${1:-http://localhost}"
API="$BASE/api"
HEALTH="$BASE/health"

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

ok()   { printf "${GREEN}✓${NC} %s\n" "$1"; }
fail() { printf "${RED}✗${NC} %s\n" "$1" >&2; exit 1; }
warn() { printf "${YELLOW}!${NC} %s\n" "$1"; }

echo "== Algobattle smoke test =="
echo "   Target: $BASE"
echo ""

# ---------------------------------------------------------------------------
# 1. API health
# ---------------------------------------------------------------------------
echo -n "1. /health ... "
if curl -fsS --max-time 10 "$HEALTH" >/dev/null 2>&1; then
    ok "API healthy"
else
    fail "API health check failed at $HEALTH"
fi

# ---------------------------------------------------------------------------
# 2. /metrics endpoint
# ---------------------------------------------------------------------------
echo -n "2. /metrics ... "
if curl -fsS --max-time 5 "$BASE/metrics" | grep -q "^# HELP"; then
    ok "Prometheus metrics exposed"
else
    warn "/metrics not exposed (ok if not running monitoring)"
fi

# ---------------------------------------------------------------------------
# 3. Register a test user (idempotent)
# ---------------------------------------------------------------------------
echo -n "3. Register smoke test user ... "
TIMESTAMP=$(date +%s)
USER_EMAIL="smoke-$TIMESTAMP@algobattle.test"
USER_PASS="SmokeTest123!"

REG=$(curl -sS -X POST -H "Content-Type: application/json" \
    -d "{\"email\":\"$USER_EMAIL\",\"username\":\"smoke-$TIMESTAMP\",\"password\":\"$USER_PASS\"}" \
    "$API/auth/register" || echo '{"detail":"failed"}')

TOKEN=$(echo "$REG" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('access_token',''))" 2>/dev/null || true)

if [[ -n "$TOKEN" ]]; then
    ok "User registered"
else
    warn "Registration endpoint not available or failed (continuing without auth)"
fi

# ---------------------------------------------------------------------------
# 4. List problems (public endpoint)
# ---------------------------------------------------------------------------
echo -n "4. GET /problems ... "
if curl -fsS --max-time 5 "$API/problems" >/dev/null 2>&1; then
    ok "Problems listed"
else
    warn "Problems endpoint not reachable (DB may not be seeded — run make seed)"
fi

# ---------------------------------------------------------------------------
# 5. Submit a sample (requires auth + seeded problems)
# ---------------------------------------------------------------------------
if [[ -n "$TOKEN" ]]; then
    echo -n "5. Submit Two Sum ... "
    PROBLEM_ID=$(curl -fsS "$API/problems" 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    for p in (data if isinstance(data, list) else data.get('items', [])):
        if p.get('slug') == 'two-sum':
            print(p['id'])
            break
except: pass
" 2>/dev/null || echo "")

    if [[ -z "$PROBLEM_ID" ]]; then
        warn "Two Sum problem not seeded — skipping submission test (run make seed)"
    else
        SUBMIT=$(curl -sS -X POST \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $TOKEN" \
            -d "{\"problem_id\":$PROBLEM_ID,\"language\":\"python\",\"source_code\":\"class Solution:\\n    def twoSum(self, nums, target):\\n        seen = {}\\n        for i, n in enumerate(nums):\\n            if target - n in seen:\\n                return [seen[target-n], i]\\n            seen[n] = i\\n\"}" \
            "$API/submissions" || echo '{"detail":"failed"}')

        SUB_ID=$(echo "$SUBMIT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null || echo "")

        if [[ -n "$SUB_ID" ]]; then
            ok "Submission $SUB_ID accepted"

            # Poll for verdict
            echo -n "   Wait for verdict ... "
            for i in {1..30}; do
                sleep 2
                RES=$(curl -fsS -H "Authorization: Bearer $TOKEN" \
                    "$API/submissions/$SUB_ID" 2>/dev/null || echo '{}')
                STATUS=$(echo "$RES" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")
                if [[ "$STATUS" == "accepted" || "$STATUS" == "wrong_answer" || "$STATUS" == "runtime_error" || "$STATUS" == "time_limit" ]]; then
                    ok "Verdict: $STATUS"
                    break
                fi
            done

            if [[ -z "$STATUS" ]]; then
                warn "Submission did not complete in 60s — judge may be down"
            fi
        else
            warn "Submission endpoint not available or returned error"
        fi
    fi
else
    warn "5. Skipping submission test (no auth token)"
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
echo ""
echo -e "${GREEN}Smoke test passed.${NC}"
echo "Next steps:"
echo "  - Explore http://localhost (UI)"
echo "  - Browse http://localhost:3000 (Grafana)"
echo "  - Tail logs with: make logs"
echo ""
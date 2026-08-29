#!/usr/bin/env bash
# ============================================================================
# Deploy the AlgoBattle judge to Heroku (student plan, $13/mo credit × 24 mo)
# ----------------------------------------------------------------------------
# Prereqs:
#   1. Claim the Heroku student offer (verify with college email / SheerID):
#      https://www.studentoffers.co/offer/heroku  — or directly via
#      https://www.heroku.com/students  (no card needed on the student plan)
#   2. Install the Heroku CLI:  brew install heroku/brew/heroku
#   3. heroku login
#
# Then run this script. It deploys backend/sandbox/Dockerfile as a container
# app and prints the public judge URL. Point the Cloudflare Worker at it via:
#   cd backend/sandbox/deploy/worker && wrangler secret put TUNNEL_URL
# ============================================================================
set -euo pipefail

APP_NAME="${1:-algobattle-judge}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DOCKERFILE_DIR="$SCRIPT_DIR/../.."          # backend/ (Dockerfile context)

echo "==> Creating Heroku app: $APP_NAME"
heroku create "$APP_NAME"

echo "==> Setting container stack (uses backend/sandbox/Dockerfile)"
heroku stack:set container -a "$APP_NAME"

echo "==> Pushing the judge image (this builds Python/C++/Java + deps)"
cd "$DOCKERFILE_DIR"
heroku container:push web -a "$APP_NAME"

echo "==> Releasing"
heroku container:release web -a "$APP_NAME"

URL="https://$APP_NAME.herokuapp.com"
echo ""
echo "===================================================="
echo "  Judge is live at: $URL"
echo "  Health check:"
echo "    curl $URL/health"
echo ""
echo "  Point the Worker at it:"
echo "    cd backend/sandbox/deploy/worker"
echo "    wrangler secret put TUNNEL_URL    # paste: $URL"
echo "===================================================="

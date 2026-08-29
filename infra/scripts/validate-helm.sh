#!/usr/bin/env bash
# ============================================================================
# validate-helm.sh — quick syntax + render check for the Helm chart
# ----------------------------------------------------------------------------
# Useful in CI before `helm install`. Doesn't require a running cluster.
# ============================================================================
set -euo pipefail
cd "$(dirname "$0")/../helm"

echo "== helm lint =="
helm lint .

echo ""
echo "== helm template (default values) =="
helm template algobattle . > /tmp/helm-render.yaml
echo "  → $(wc -l < /tmp/helm-render.yaml) lines"

echo ""
echo "== helm template (production values) =="
helm template algobattle . \
    --set image.registry=ghcr.io \
    --set api.replicaCount=3 \
    --set judge.replicaCount=5 \
    --set ingress.hosts[0].host=algobattle.example.com \
    > /tmp/helm-render-prod.yaml
echo "  → $(wc -l < /tmp/helm-render-prod.yaml) lines"

echo ""
echo "All good."
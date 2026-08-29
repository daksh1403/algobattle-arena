#!/usr/bin/env bash
# One-time setup inside the Codespaces container.
set -e

echo "==> Installing compilers (C++/Java) + Python deps..."
sudo apt-get update -qq
sudo apt-get install -y -qq g++ openjdk-17-jdk-headless >/dev/null 2>&1 || true

cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -q --upgrade pip
pip install -q -r sandbox/requirements.txt

echo ""
echo "================================================"
echo "  AlgoBattle Judge ready in Codespaces!"
echo "  Start it with:"
echo "    cd backend && source .venv/bin/activate"
echo "    python sandbox/web_arena.py"
echo "  Then open the forwarded port 8080."
echo "================================================"

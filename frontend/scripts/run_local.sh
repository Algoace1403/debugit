#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_DIR="$(dirname "$SCRIPT_DIR")"

echo "=== CI-Heal Agent — Frontend (local) ==="

cd "$FRONTEND_DIR"

# Install deps if needed
if [ ! -d "node_modules" ]; then
  echo "Installing dependencies..."
  npm install
fi

# Point at local backend
export VITE_API_URL="${VITE_API_URL:-http://127.0.0.1:8000}"
echo "VITE_API_URL=$VITE_API_URL"
echo "Starting Vite dev server..."
echo ""

exec npx vite --host 127.0.0.1

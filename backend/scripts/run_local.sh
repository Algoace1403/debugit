#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$BACKEND_DIR/venv"

echo "=== CI-Heal Agent — Backend (local) ==="

# Create venv if not exists
if [ ! -d "$VENV_DIR" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"

# Install / update deps
echo "Installing dependencies..."
pip install -q -r "$BACKEND_DIR/requirements.txt"

# Copy .env from example if not exists
if [ ! -f "$BACKEND_DIR/.env" ]; then
  echo ""
  echo "WARNING: No .env file found."
  echo "Copy .env.example and fill in your keys:"
  echo "  cp $BACKEND_DIR/.env.example $BACKEND_DIR/.env"
  echo ""
fi

# Ensure data directory exists
export DATA_DIR="${DATA_DIR:-/tmp/ci-heal-runs}"
mkdir -p "$DATA_DIR"

echo "Starting uvicorn on http://127.0.0.1:8000 ..."
echo "  DATA_DIR=$DATA_DIR"
echo ""

cd "$BACKEND_DIR"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

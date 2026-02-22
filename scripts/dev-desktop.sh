#!/usr/bin/env bash
# Dev script: launches CachiBot server + Electron window.
# Prerequisites:
#   - pip install -e .        (install cachibot in dev mode)
#   - cd frontend && npm ci   (install frontend deps)
#   - cd desktop && npm ci    (install Electron deps)
#
# Usage: bash scripts/dev-desktop.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cleanup() {
  echo "[dev] Shutting down..."
  kill $BACKEND_PID 2>/dev/null || true
}
trap cleanup EXIT

# Build frontend if dist doesn't exist
if [ ! -f "$ROOT_DIR/frontend/dist/index.html" ]; then
  echo "[dev] Building frontend..."
  cd "$ROOT_DIR/frontend"
  npm run build
fi

# Start CachiBot server
echo "[dev] Starting CachiBot server on port 5870..."
cd "$ROOT_DIR"
cachibot server --port 5870 &
BACKEND_PID=$!

# Wait for backend
sleep 3

# Launch Electron in dev mode
echo "[dev] Launching Electron..."
cd "$ROOT_DIR/desktop"
npx electron .

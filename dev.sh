#!/usr/bin/env bash
# Start CachiBot backend + frontend for development.
# Usage: bash dev.sh
#
# Prerequisites:
#   pip install -e .          (backend in dev mode)
#   cd frontend && npm install (frontend deps)

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Colors
CYAN='\033[0;36m'
GREEN='\033[0;32m'
DIM='\033[2m'
RESET='\033[0m'

cleanup() {
  echo ""
  echo -e "${CYAN}[dev]${RESET} Shutting down..."
  kill $BACKEND_PID 2>/dev/null || true
  kill $FRONTEND_PID 2>/dev/null || true
  wait $BACKEND_PID 2>/dev/null
  wait $FRONTEND_PID 2>/dev/null
  echo -e "${GREEN}[dev]${RESET} Done."
}
trap cleanup EXIT INT TERM

# Start backend
echo -e "${CYAN}[dev]${RESET} Starting backend on ${GREEN}http://127.0.0.1:6392${RESET}"
cd "$ROOT_DIR"
cachibot server --port 6392 --reload &
BACKEND_PID=$!

# Start frontend
echo -e "${CYAN}[dev]${RESET} Starting frontend on ${GREEN}http://localhost:5173${RESET}"
cd "$ROOT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!

echo ""
echo -e "${CYAN}[dev]${RESET} Both servers running. Press ${GREEN}Ctrl+C${RESET} to stop."
echo ""

# Wait for either process to exit
wait -n $BACKEND_PID $FRONTEND_PID 2>/dev/null || true

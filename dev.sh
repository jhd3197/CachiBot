#!/usr/bin/env bash
# CachiBot dev launcher.
#
# Usage:
#   bash dev.sh                # backend + frontend in browser (default)
#   bash dev.sh backend        # backend only
#   bash dev.sh frontend       # frontend only (Vite dev server)
#   bash dev.sh desktop        # backend + frontend + Electron
#   bash dev.sh all            # backend + frontend + browser + Electron

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-browser}"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
DIM='\033[2m'
RESET='\033[0m'

PIDS=()

cleanup() {
  echo ""
  echo -e "${CYAN}[dev]${RESET} Shutting down..."
  for pid in "${PIDS[@]}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${PIDS[@]}"; do wait "$pid" 2>/dev/null || true; done
  echo -e "${GREEN}[dev]${RESET} Done."
}
trap cleanup EXIT INT TERM

# --- Kill stale processes on required ports ---
kill_port() {
  local port=$1
  local pid
  pid=$(lsof -ti :"$port" 2>/dev/null || true)
  if [ -n "$pid" ]; then
    echo -e "${YELLOW}[dev]${RESET} Killing stale process on port $port (PID $pid)"
    kill -9 $pid 2>/dev/null || true
  fi
}

case "$MODE" in backend|browser|desktop|all) kill_port 6392 ;; esac
case "$MODE" in frontend|browser|desktop|all) kill_port 5173 ;; esac

# --- Backend ---
case "$MODE" in backend|browser|desktop|all)
  echo -e "${CYAN}[dev]${RESET} backend  -> ${GREEN}http://127.0.0.1:6392${RESET}"
  cd "$ROOT_DIR"
  cachibot server --port 6392 --reload &
  PIDS+=($!)
  ;; esac

# --- Frontend (Vite) ---
case "$MODE" in frontend|browser|desktop|all)
  echo -e "${CYAN}[dev]${RESET} frontend -> ${GREEN}http://localhost:5173${RESET}"
  cd "$ROOT_DIR/frontend"
  npm run dev &
  PIDS+=($!)
  ;; esac

# --- Electron ---
case "$MODE" in desktop|all)
  sleep 3
  echo -e "${CYAN}[dev]${RESET} electron -> ${GREEN}loading from Vite${RESET}"
  cd "$ROOT_DIR/desktop"
  ELECTRON_DEV_URL="http://localhost:5173" npx electron . &
  PIDS+=($!)
  ;; esac

echo -e "${DIM}[dev] Running ($MODE). Press Ctrl+C to stop.${RESET}"
echo ""

wait -n "${PIDS[@]}" 2>/dev/null || true

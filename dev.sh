#!/usr/bin/env bash
# CachiBot dev launcher.
#
# Usage:
#   bash dev.sh                # backend + frontend in browser (default)
#   bash dev.sh backend        # backend only
#   bash dev.sh frontend       # frontend only (Vite dev server)
#   bash dev.sh desktop        # backend + frontend + Electron
#   bash dev.sh all            # backend + frontend + browser + Electron
#   bash dev.sh watch-lint     # watch Python + TS files and lint on changes

set -e

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-browser}"

CYAN='\033[0;36m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
RED='\033[0;31m'
DIM='\033[2m'
RESET='\033[0m'

PIDS=()

# --- watch-lint mode ---
if [ "$MODE" = "watch-lint" ]; then
  PY_PATH="$ROOT_DIR/cachibot"
  TS_PATH="$ROOT_DIR/frontend/src"
  echo -e "${CYAN}[dev]${RESET} Watching for lint errors (Python + TypeScript)"
  echo -e "${DIM}[dev]   Python  : $PY_PATH${RESET}"
  echo -e "${DIM}[dev]   Frontend: $TS_PATH${RESET}"
  echo -e "${DIM}[dev] Press Ctrl+C to stop.${RESET}"
  echo ""

  run_all_lint() {
    local ts
    ts=$(date +%H:%M:%S)
    echo -e "${DIM}[$ts]${RESET} ${CYAN}Running linters...${RESET}"
    echo ""

    # --- Python: ruff check ---
    echo -e "  ${CYAN}Python (ruff check)${RESET}"
    if ruff check "$PY_PATH"; then
      echo -e "    ${GREEN}passed${RESET}"
    else
      echo -e "    ${RED}errors found${RESET}"
    fi

    # --- Python: ruff format (auto-fix) ---
    echo -e "  ${CYAN}Python (ruff format)${RESET}"
    if ruff format --check "$PY_PATH" 2>/dev/null; then
      echo -e "    ${GREEN}formatted${RESET}"
    else
      ruff format "$PY_PATH" 2>/dev/null
      echo -e "    ${YELLOW}reformatted${RESET}"
    fi

    # --- Frontend: ESLint ---
    echo -e "  ${CYAN}Frontend (eslint)${RESET}"
    if (cd "$ROOT_DIR/frontend" && npm run lint 2>/dev/null); then
      echo -e "    ${GREEN}passed${RESET}"
    else
      echo -e "    ${RED}errors found${RESET}"
    fi

    echo ""
  }

  run_all_lint

  # Try inotifywait (Linux/WSL), then fswatch (macOS), then poll
  if command -v inotifywait &>/dev/null; then
    while inotifywait -r -e modify,create,delete \
          --include '\.(py|ts|tsx)$' \
          "$PY_PATH" "$TS_PATH" 2>/dev/null; do
      sleep 0.5
      run_all_lint
    done
  elif command -v fswatch &>/dev/null; then
    fswatch -e ".*" -i "\\.py$" -i "\\.tsx?$" -r "$PY_PATH" "$TS_PATH" | while read -r _; do
      sleep 0.5
      run_all_lint
    done
  else
    echo -e "${YELLOW}[dev] No watcher found. Install inotify-tools or fswatch for live updates.${RESET}"
    echo -e "${YELLOW}[dev] Falling back to polling every 3s...${RESET}"
    LAST_HASH=""
    while true; do
      HASH=$(find "$PY_PATH" "$TS_PATH" \( -name '*.py' -o -name '*.ts' -o -name '*.tsx' \) -printf '%T@ %p\n' 2>/dev/null | md5sum | cut -d' ' -f1)
      if [ "$HASH" != "$LAST_HASH" ] && [ -n "$LAST_HASH" ]; then
        run_all_lint
      fi
      LAST_HASH="$HASH"
      sleep 3
    done
  fi
  exit 0
fi

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

case "$MODE" in backend|browser|desktop|all) kill_port 5870 ;; esac
case "$MODE" in frontend|browser|desktop|all) kill_port 5173 ;; esac

# --- Backend ---
case "$MODE" in backend|browser|desktop|all)
  echo -e "${CYAN}[dev]${RESET} backend  -> ${GREEN}http://127.0.0.1:5870${RESET}"
  cd "$ROOT_DIR"
  if [ -x "$ROOT_DIR/.venv/bin/cachibot" ]; then
    "$ROOT_DIR/.venv/bin/cachibot" server --port 5870 --reload &
  elif [ -x "$ROOT_DIR/.venv/Scripts/cachibot.exe" ]; then
    "$ROOT_DIR/.venv/Scripts/cachibot.exe" server --port 5870 --reload &
  else
    cachibot server --port 5870 --reload &
  fi
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

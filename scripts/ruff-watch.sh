#!/usr/bin/env bash
# Shortcut — delegates to the integrated dev launcher.
# Usage: ./scripts/ruff-watch.sh
exec "$(dirname "$0")/../dev.sh" watch-lint

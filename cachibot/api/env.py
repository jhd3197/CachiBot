"""Shared .env file helpers for API routes."""

from __future__ import annotations

import os
from pathlib import Path


def get_env_path() -> Path:
    """Return the .env path, respecting CACHIBOT_WORKSPACE (set by Electron/PyInstaller)."""
    ws = os.environ.get("CACHIBOT_WORKSPACE")
    return Path(ws) / ".env" if ws else Path.cwd() / ".env"

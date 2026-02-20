"""
Stale server process guard.

Writes a PID file on startup and removes it on clean shutdown.
On next startup, if a stale PID file exists, verifies process identity
and kills it before connecting to any platforms — preventing
TelegramConflictError from orphaned uvicorn children.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import signal
import subprocess
import sys
import time
from pathlib import Path

logger = logging.getLogger("cachibot.pid_guard")

PID_FILE = Path.home() / ".cachibot" / "server.pid"

_IDENTITY_NAMES = {"python", "python3", "python.exe", "python3.exe", "cachibot-server.exe"}


def _is_process_alive(pid: int) -> bool:
    """Check whether a process with the given PID exists."""
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _verify_identity_windows(pid: int) -> bool:
    """Verify the process is a Python/CachiBot process on Windows."""
    try:
        result = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        output = result.stdout.strip().lower()
        if "no tasks" in output or not output:
            return False
        # Image name is the first CSV field, e.g. "python.exe","12345",...
        for name in _IDENTITY_NAMES:
            if name in output:
                return True
        return False
    except Exception:
        return False


def _verify_identity_unix(pid: int) -> bool:
    """Verify the process is a Python/CachiBot process on Linux/macOS."""
    try:
        exe = os.readlink(f"/proc/{pid}/exe")
        exe_lower = exe.lower()
        return "python" in exe_lower or "cachibot" in exe_lower
    except OSError:
        pass
    # Fallback for macOS or systems without /proc
    try:
        result = subprocess.run(
            ["ps", "-p", str(pid), "-o", "comm="],
            capture_output=True,
            text=True,
            timeout=5,
        )
        comm = result.stdout.strip().lower()
        return "python" in comm or "cachibot" in comm
    except Exception:
        return False


def _verify_identity(pid: int) -> bool:
    """Verify the stale PID belongs to a Python/CachiBot process."""
    if platform.system() == "Windows":
        return _verify_identity_windows(pid)
    return _verify_identity_unix(pid)


def _kill_process(pid: int) -> None:
    """Kill a process (with tree kill on Windows)."""
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        except Exception as exc:
            logger.warning("taskkill failed for PID %d: %s", pid, exc)
    else:
        # SIGTERM first, then SIGKILL if needed
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError:
            return
        # Wait up to 3s for graceful exit before SIGKILL
        for _ in range(30):
            time.sleep(0.1)
            if not _is_process_alive(pid):
                return
        try:
            os.kill(pid, signal.SIGKILL)
        except OSError:
            pass


def kill_stale_server() -> None:
    """Kill a stale server process if one exists from a previous crash."""
    try:
        data = json.loads(PID_FILE.read_text())
        pid = data["pid"]
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        return

    if pid == os.getpid():
        # PID file points to ourselves (shouldn't happen, but be safe)
        return

    if not _is_process_alive(pid):
        logger.debug("Stale PID file found (PID %d already dead), cleaning up", pid)
        PID_FILE.unlink(missing_ok=True)
        return

    if not _verify_identity(pid):
        logger.debug(
            "PID %d exists but is not a Python/CachiBot process, removing stale PID file", pid
        )
        PID_FILE.unlink(missing_ok=True)
        return

    logger.warning("Killing stale server process (PID %d)", pid)
    _kill_process(pid)

    # Wait up to 5s for the process to exit
    for _ in range(50):
        time.sleep(0.1)
        if not _is_process_alive(pid):
            break
    else:
        logger.error("Failed to kill stale server process (PID %d)", pid)

    PID_FILE.unlink(missing_ok=True)


def write_pid_file(port: int) -> None:
    """Write the current process PID file."""
    try:
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(
            json.dumps({"pid": os.getpid(), "exe": sys.executable, "port": port})
        )
    except Exception as exc:
        logger.warning("Failed to write PID file: %s", exc)


def remove_pid_file() -> None:
    """Remove the PID file on clean shutdown."""
    try:
        PID_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.warning("Failed to remove PID file: %s", exc)

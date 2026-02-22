"""Centralized Logging Configuration.

Sets up file-based rotating logs with secret masking for the entire app.
Console output is left to uvicorn's default handler — no duplicate streams.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from cachibot.services.secret_masking import SecretMaskingFilter

_LOG_DIR = Path.home() / ".cachibot" / "logs"
_LOG_FILE = _LOG_DIR / "cachibot.log"
_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_BACKUP_COUNT = 3
_FORMAT = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging() -> None:
    """Configure the root logger with a rotating file handler and secret masking.

    Safe to call multiple times — skips if already configured.
    """
    root = logging.getLogger()

    # Guard against duplicate setup
    if any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        return

    _LOG_DIR.mkdir(parents=True, exist_ok=True)

    file_handler = RotatingFileHandler(
        _LOG_FILE,
        maxBytes=_MAX_BYTES,
        backupCount=_BACKUP_COUNT,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATE_FORMAT))
    file_handler.addFilter(SecretMaskingFilter())

    root.addHandler(file_handler)

    # Also install secret masking on the root logger itself so console output
    # (uvicorn's handler) is masked too — replaces the old install_secret_masking() call.
    if not any(isinstance(f, SecretMaskingFilter) for f in root.filters):
        root.addFilter(SecretMaskingFilter())

    # Ensure root logger captures DEBUG+ so the file handler sees everything.
    # (uvicorn sets root to WARNING — we need to lower it for the file handler
    # without adding a console handler that would duplicate uvicorn's output.)
    if root.level > logging.DEBUG:
        root.setLevel(logging.DEBUG)

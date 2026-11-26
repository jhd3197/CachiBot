"""Per-bot controller tokens for the Vela computer container.

Vela reads its controller token only from the file named by
``VELA_CONTROLLER_TOKEN_FILE`` (default ``/run/secrets/vela-controller-token``)
and refuses a token from an environment variable. CachiBot therefore
generates one token per bot, stores it under its data dir and bind-mounts it
into the container read-only.

Permissions: the per-bot directory is 0700 (only the CachiBot user can open
it on the host) and the token file itself is 0644. That combination works on
Linux because the file is bind-mounted *by path*: inside the container the
mount resolves the inode directly, bypassing host directory traversal, so
the container's uid 10001 needs only the file's own read bit. Other host
users still cannot reach the file through the 0700 directory. Docker Desktop
on Windows/macOS does not enforce POSIX modes at all.

The token value never appears in docker argv, environment variables, logs
or API responses — only its host path does.
"""

from __future__ import annotations

import logging
import os
import re
import secrets
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILENAME = "controller-token"
TOKEN_BYTES = 48  # secrets.token_urlsafe(48) → 64 characters

_BOT_ID_RE = re.compile(r"[A-Za-z0-9_-]+")


class TokenManager:
    """Create and load per-bot controller token files."""

    def __init__(self, base_dir: Path | None = None) -> None:
        if base_dir is None:
            from cachibot.config import cachibot_data_dir

            base_dir = cachibot_data_dir() / "computers"
        self._base_dir = base_dir

    def token_path(self, bot_id: str) -> Path:
        """Host path of the bot's token file (validated against traversal)."""
        if not _BOT_ID_RE.fullmatch(bot_id):
            raise ValueError(f"invalid bot id for token storage: {bot_id!r}")
        return self._base_dir / bot_id / TOKEN_FILENAME

    def ensure_token(self, bot_id: str) -> str:
        """Return the bot's token, generating and persisting it on first use.

        The file is created 0644 via ``os.open`` (no race between create and
        chmod) inside the 0700 per-bot directory; see the module docstring
        for why that is safe with the bind mount.
        """
        directory = self.token_path(bot_id).parent
        directory.mkdir(parents=True, exist_ok=True)
        if sys.platform != "win32":
            # The base dir (0700) holds every bot's 0700 dir; only the token
            # file inside is group/other-readable (see module docstring).
            os.chmod(self._base_dir, 0o700)
            os.chmod(directory, 0o700)

        path = self.token_path(bot_id)
        if path.exists():
            token = path.read_text(encoding="utf-8").strip()
            if token:
                return token

        token = secrets.token_urlsafe(TOKEN_BYTES)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if sys.platform != "win32":
            flags |= os.O_NOFOLLOW
        try:
            fd = os.open(path, flags, 0o644)
        except FileExistsError:
            # Another task generated it first — read the winner's file.
            return path.read_text(encoding="utf-8").strip()
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(token)
                handle.write("\n")
        except BaseException:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
            raise
        return token

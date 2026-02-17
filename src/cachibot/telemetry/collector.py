"""Collect anonymous telemetry metrics.

NEVER collects: messages, API keys, passwords, emails, IPs, file paths,
or conversation content. Only aggregate counts and system metadata.
"""

import logging
import platform
import sys
import time
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Server start time (set on import)
_start_time = time.monotonic()


def collect_telemetry() -> dict:
    """Collect anonymous telemetry payload.

    Returns a dict with system metadata and aggregate usage counts.
    All data is anonymous — no PII, no message content, no keys.
    """
    from cachibot import __version__
    from cachibot.config import Config

    config = Config.load()

    # Determine database type from config
    db_url = config.database.url
    if db_url:
        if "postgresql" in db_url or "postgres" in db_url:
            db_type = "postgresql"
        elif "mysql" in db_url:
            db_type = "mysql"
        else:
            db_type = "other"
    else:
        db_type = "sqlite"

    uptime_seconds = int(time.monotonic() - _start_time)

    payload = {
        "app_version": __version__,
        "os_type": platform.system().lower(),
        "os_version": platform.release(),
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "db_type": db_type,
        "uptime_seconds": uptime_seconds,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    # Aggregate counts from database (best-effort, never fail)
    try:
        import asyncio

        counts = asyncio.get_event_loop().run_until_complete(_collect_db_counts())
        payload.update(counts)
    except Exception:
        # If we can't get DB counts (no running loop, etc.), that's fine
        try:
            import asyncio

            counts = asyncio.run(_collect_db_counts())
            payload.update(counts)
        except Exception:
            logger.debug("Could not collect DB counts for telemetry")

    return payload


async def _collect_db_counts() -> dict:
    """Collect aggregate counts from the database."""
    counts: dict = {}
    try:
        from cachibot.storage.db import get_session

        async with get_session() as session:
            from sqlalchemy import text

            # Total bots
            result = await session.execute(text("SELECT COUNT(*) FROM bots"))
            row = result.scalar()
            counts["bot_count"] = row or 0

            # Total messages (aggregate only)
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM messages"))
                row = result.scalar()
                counts["message_count"] = row or 0
            except Exception:
                counts["message_count"] = 0

            # Total users
            try:
                result = await session.execute(text("SELECT COUNT(*) FROM users"))
                row = result.scalar()
                counts["user_count"] = row or 0
            except Exception:
                counts["user_count"] = 0

            # Active connections count
            try:
                result = await session.execute(
                    text("SELECT COUNT(*) FROM connections WHERE status = 'connected'")
                )
                row = result.scalar()
                counts["active_connections"] = row or 0
            except Exception:
                counts["active_connections"] = 0

    except Exception:
        logger.debug("Could not query database for telemetry counts")

    return counts

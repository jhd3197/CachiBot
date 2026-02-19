"""Background telemetry scheduler.

Runs as an asyncio task during server lifespan. Checks every hour whether
it's time to send telemetry (>24h since last send). Non-blocking, all
errors silently caught.
"""

import asyncio
import logging
import os
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Check interval: every hour
_CHECK_INTERVAL_SECONDS = 3600
# Send interval: every 24 hours
_SEND_INTERVAL_SECONDS = 86400

_task: asyncio.Task[None] | None = None


async def start_telemetry_scheduler() -> None:
    """Start the background telemetry scheduler task."""
    global _task
    if _task is not None:
        return

    _task = asyncio.create_task(_scheduler_loop())
    logger.debug("Telemetry scheduler started")


async def stop_telemetry_scheduler() -> None:
    """Stop the background telemetry scheduler task."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.debug("Telemetry scheduler stopped")


async def _scheduler_loop() -> None:
    """Main scheduler loop — runs until cancelled."""
    # Initial send on startup (if eligible)
    await _maybe_send()

    while True:
        try:
            await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
            await _maybe_send()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Telemetry scheduler error (silent): %s", exc)


async def _maybe_send() -> None:
    """Send telemetry if enabled and enough time has elapsed."""
    try:
        # Respect env var
        if os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() in ("1", "true", "yes"):
            return

        from cachibot.config import Config

        config = Config.load()

        if not config.telemetry.enabled:
            return

        # Check if enough time has passed since last send
        if config.telemetry.last_sent:
            try:
                last_sent = datetime.fromisoformat(config.telemetry.last_sent)
                elapsed = (datetime.now(timezone.utc) - last_sent).total_seconds()
                if elapsed < _SEND_INTERVAL_SECONDS:
                    return
            except (ValueError, TypeError):
                pass  # Invalid timestamp — send anyway

        # Collect and send
        from cachibot.telemetry.collector import collect_telemetry
        from cachibot.telemetry.sender import send_telemetry

        payload = collect_telemetry()
        await send_telemetry(payload)

    except Exception as exc:
        logger.debug("Telemetry _maybe_send error (silent): %s", exc)

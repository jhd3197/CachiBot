"""Background terms-version checker.

Polls the cachibot.ai legal endpoint to detect terms-of-service updates.
Runs as an asyncio task during server lifespan. All errors silently caught
so offline / air-gapped setups are unaffected.
"""

import asyncio
import logging

logger = logging.getLogger(__name__)

# Check every 6 hours
_CHECK_INTERVAL_SECONDS = 6 * 3600

_TERMS_URL = "https://cachibot.ai/api/legal/terms"
_TIMEOUT_SECONDS = 10

_task: asyncio.Task[None] | None = None
_latest_terms: dict | None = None


async def start_terms_checker() -> None:
    """Start the background terms-version checker task."""
    global _task
    if _task is not None:
        return

    _task = asyncio.create_task(_checker_loop())
    logger.debug("Terms checker started")


async def stop_terms_checker() -> None:
    """Stop the background terms-version checker task."""
    global _task
    if _task is not None:
        _task.cancel()
        try:
            await _task
        except asyncio.CancelledError:
            pass
        _task = None
        logger.debug("Terms checker stopped")


def get_latest_terms_version() -> str:
    """Return the latest known terms version, or empty string if unknown."""
    if _latest_terms and "version" in _latest_terms:
        return _latest_terms["version"]
    return ""


async def _checker_loop() -> None:
    """Main checker loop — fetches on startup, then every 6 hours."""
    await _fetch_terms()

    while True:
        try:
            await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
            await _fetch_terms()
        except asyncio.CancelledError:
            break
        except Exception as exc:
            logger.debug("Terms checker loop error (silent): %s", exc)


async def _fetch_terms() -> None:
    """Fetch the current terms version from cachibot.ai."""
    global _latest_terms
    try:
        import httpx

        async with httpx.AsyncClient(timeout=_TIMEOUT_SECONDS) as client:
            resp = await client.get(_TERMS_URL)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and "version" in data:
                _latest_terms = data
                logger.debug("Terms version fetched: %s", data.get("version"))
    except Exception as exc:
        logger.debug("Terms fetch failed (silent): %s", exc)

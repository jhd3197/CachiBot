"""
Outbound Webhook Delivery Service

Delivers event payloads to registered webhooks with HMAC signing and retry logic.
All deliveries are fire-and-forget via asyncio.create_task.
"""

import asyncio
import hashlib
import hmac
import json
import logging
import time
from typing import Any

import httpx

from cachibot.storage.developer_repository import WebhookRepository

logger = logging.getLogger(__name__)

# Retry backoff delays in seconds
_RETRY_DELAYS = [1, 2, 4]

_wh_repo = WebhookRepository()


def emit_webhook_event(bot_id: str, event: str, payload: dict[str, Any]) -> None:
    """Fire-and-forget webhook delivery for a bot event.

    Safe to call from any async context. Silently does nothing if no event loop
    is running (e.g., CLI mode).
    """
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_deliver_event(bot_id, event, payload))
    except RuntimeError:
        pass


async def _deliver_event(bot_id: str, event: str, payload: dict[str, Any]) -> None:
    """Look up matching webhooks and deliver to each."""
    try:
        webhooks = await _wh_repo.get_active_webhooks_for_event(bot_id, event)
    except Exception:
        logger.warning("Failed to fetch webhooks for bot %s event %s", bot_id, event, exc_info=True)
        return

    for wh in webhooks:
        asyncio.create_task(_deliver_single(wh.id, wh.url, wh.secret, event, bot_id, payload))


async def _deliver_single(
    webhook_id: str,
    url: str,
    secret: str | None,
    event: str,
    bot_id: str,
    payload: dict[str, Any],
) -> None:
    """Deliver a payload to a single webhook with retries."""
    body = {
        "event": event,
        "bot_id": bot_id,
        "timestamp": time.time(),
        "data": payload,
    }
    body_bytes = json.dumps(body).encode()

    headers: dict[str, str] = {
        "Content-Type": "application/json",
        "X-CachiBot-Event": event,
    }

    if secret:
        sig = hmac.new(secret.encode(), body_bytes, hashlib.sha256).hexdigest()
        headers["X-CachiBot-Signature"] = sig

    for attempt, delay in enumerate(_RETRY_DELAYS):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, content=body_bytes, headers=headers)

            if resp.status_code < 400:
                await _wh_repo.record_success(webhook_id)
                return

            logger.warning(
                "Webhook %s delivery attempt %d returned %d",
                webhook_id,
                attempt + 1,
                resp.status_code,
            )
        except Exception as exc:
            logger.warning(
                "Webhook %s delivery attempt %d failed: %s",
                webhook_id,
                attempt + 1,
                exc,
            )

        if attempt < len(_RETRY_DELAYS) - 1:
            await asyncio.sleep(delay)

    # All retries exhausted
    logger.error("Webhook %s delivery failed after %d attempts", webhook_id, len(_RETRY_DELAYS))
    try:
        await _wh_repo.record_failure(webhook_id)
    except Exception:
        pass

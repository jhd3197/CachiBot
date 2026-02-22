"""
Viber Webhook Routes

Handles incoming webhook events from the Viber Bot API.
Provides a POST endpoint for message ingestion and event handling.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request

from cachibot.services.platform_manager import get_platform_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/viber", tags=["webhooks"])


@router.post("/{connection_id}")
async def handle_webhook(connection_id: str, request: Request) -> dict[str, str]:
    """Handle incoming Viber webhook events.

    Reads the raw body and X-Viber-Content-Signature header, then delegates
    signature validation and event processing to the Viber adapter.

    Args:
        connection_id: The CachiBot connection ID.
        request: The incoming FastAPI request.

    Returns:
        A simple acknowledgement dict.
    """
    # Read raw body for signature validation
    raw_body = await request.body()

    # Get signature header
    signature = request.headers.get("X-Viber-Content-Signature", "")
    if not signature:
        logger.warning(f"Viber webhook: missing signature for connection {connection_id}")
        raise HTTPException(status_code=403, detail="Missing signature")

    # Parse JSON payload
    try:
        body: dict[str, Any] = await request.json()
    except Exception:
        logger.error(f"Viber webhook: invalid JSON for {connection_id}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Get the adapter from the platform manager
    manager = get_platform_manager()
    adapter = manager.get_adapter(connection_id)

    if not adapter:
        logger.warning(f"Viber webhook: no active adapter for connection {connection_id}")
        raise HTTPException(status_code=404, detail="No active adapter for this connection")

    # Delegate processing to the adapter
    from cachibot.services.adapters.viber import ViberAdapter

    if not isinstance(adapter, ViberAdapter):
        logger.error(f"Viber webhook: adapter for {connection_id} is not a ViberAdapter")
        raise HTTPException(status_code=400, detail="Connection is not a Viber adapter")

    try:
        await adapter.process_webhook(body, raw_body, signature)
    except Exception as e:
        logger.error(f"Error processing Viber webhook for {connection_id}: {e}")

    return {"status": "ok"}

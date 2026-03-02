"""
Custom Platform Webhook Routes

Handles incoming webhook events from user-provided custom platforms.
"""

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from cachibot.api.helpers import require_found
from cachibot.services.platform_manager import get_platform_manager
from cachibot.storage.repository import ConnectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/custom", tags=["webhooks"])

repo = ConnectionRepository()


class CustomWebhookPayload(BaseModel):
    """Inbound webhook payload from user's platform."""

    chat_id: str
    message: str
    user_id: str | None = None
    display_name: str | None = None
    metadata: dict[str, Any] | None = None


@router.post("/{connection_id}")
async def handle_custom_webhook(
    connection_id: str,
    payload: CustomWebhookPayload,
    request: Request,
) -> dict[str, str]:
    """Handle incoming messages from a custom platform.

    Validates the connection, optionally checks the API key, and routes the
    message through the adapter's on_message callback.

    Args:
        connection_id: The CachiBot connection ID.
        payload: The inbound message payload.
        request: The incoming FastAPI request.

    Returns:
        A simple acknowledgement dict.
    """
    # Validate connection exists and is a custom platform
    connection = require_found(await repo.get_connection(connection_id), "Connection")

    if connection.platform.value != "custom":
        raise HTTPException(status_code=400, detail="Connection is not a custom platform")

    # Optional API key auth
    expected_key = connection.config.get("api_key", "")
    if expected_key:
        # Accept via X-API-Key header or Authorization: Bearer header
        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            auth_header = request.headers.get("Authorization", "")
            if auth_header.startswith("Bearer "):
                api_key = auth_header[len("Bearer ") :]

        if api_key != expected_key:
            logger.warning(f"Custom webhook: API key mismatch for connection {connection_id}")
            raise HTTPException(status_code=403, detail="Invalid API key")

    # Get the adapter
    manager = get_platform_manager()
    adapter = manager.get_adapter(connection_id)

    if not adapter or not adapter.on_message:
        logger.warning(f"Custom webhook: no active adapter for connection {connection_id}")
        raise HTTPException(status_code=503, detail="Connection is not active")

    # Build metadata
    metadata: dict[str, Any] = {
        "platform": "custom",
        "chat_id": payload.chat_id,
        "user_id": payload.user_id or payload.chat_id,
        "display_name": payload.display_name or "",
    }
    if payload.metadata:
        metadata.update(payload.metadata)

    try:
        # Route through the adapter's on_message callback
        response = await adapter.on_message(
            connection_id,
            payload.chat_id,
            payload.message,
            metadata,
        )

        # Send the response back via the adapter
        if response.text or response.media:
            await adapter.send_response(payload.chat_id, response)

    except Exception as e:
        logger.error(f"Error processing custom webhook message: {e}")
        raise HTTPException(status_code=500, detail="Failed to process message")

    return {"status": "ok"}

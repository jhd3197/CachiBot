"""
WhatsApp Webhook Routes

Handles incoming webhook events from the WhatsApp Cloud API (Meta Business Platform).
Provides verification (GET) and message ingestion (POST) endpoints.
"""

import hashlib
import hmac
import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request

from cachibot.api.helpers import require_found
from cachibot.services.platform_manager import get_platform_manager
from cachibot.storage.repository import ConnectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/whatsapp", tags=["webhooks"])

repo = ConnectionRepository()


def _validate_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Validate the X-Hub-Signature-256 header from WhatsApp.

    Args:
        payload: The raw request body bytes.
        signature: The signature header value (e.g., "sha256=abc123...").
        secret: The app secret used for HMAC computation.

    Returns:
        True if the signature is valid, False otherwise.
    """
    if not signature.startswith("sha256="):
        return False

    expected = hmac.new(
        secret.encode("utf-8"),
        payload,
        hashlib.sha256,
    ).hexdigest()

    received = signature[len("sha256=") :]
    return hmac.compare_digest(expected, received)


@router.get("/{connection_id}")
async def verify_webhook(
    connection_id: str,
    hub_mode: str = Query(alias="hub.mode", default=""),
    hub_verify_token: str = Query(alias="hub.verify_token", default=""),
    hub_challenge: str = Query(alias="hub.challenge", default=""),
) -> int:
    """Webhook verification endpoint for WhatsApp Cloud API.

    Meta sends a GET request with hub.mode, hub.verify_token, and hub.challenge
    to verify ownership of the webhook URL.

    Args:
        connection_id: The CachiBot connection ID.
        hub_mode: Must be "subscribe".
        hub_verify_token: The token to verify against the connection config.
        hub_challenge: The challenge value to echo back.

    Returns:
        The hub.challenge value as an integer.
    """
    if hub_mode != "subscribe":
        logger.warning(f"WhatsApp webhook verification failed: invalid hub.mode '{hub_mode}'")
        raise HTTPException(status_code=403, detail="Invalid hub.mode")

    connection = require_found(await repo.get_connection(connection_id), "Connection")

    expected_token = connection.config.get("verify_token", "")
    if not expected_token or hub_verify_token != expected_token:
        logger.warning(
            f"WhatsApp webhook verification failed for connection {connection_id}: "
            "verify_token mismatch"
        )
        raise HTTPException(status_code=403, detail="Invalid verify token")

    logger.info(f"WhatsApp webhook verified for connection {connection_id}")
    return int(hub_challenge)


@router.post("/{connection_id}")
async def handle_webhook(connection_id: str, request: Request) -> dict[str, str]:
    """Handle incoming WhatsApp webhook events.

    Validates the request signature, parses the webhook payload, and routes
    incoming messages to the appropriate adapter via the platform manager.

    Args:
        connection_id: The CachiBot connection ID.
        request: The incoming FastAPI request.

    Returns:
        A simple acknowledgement dict.
    """
    # Read raw body for signature validation
    body = await request.body()

    # Get connection config for signature validation
    connection = require_found(await repo.get_connection(connection_id), "Connection")

    app_secret = connection.config.get("app_secret", "")

    # Validate signature
    signature = request.headers.get("X-Hub-Signature-256", "")
    if not signature or not _validate_signature(body, signature, app_secret):
        logger.warning(f"WhatsApp webhook signature validation failed for {connection_id}")
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse JSON payload
    try:
        payload: dict[str, Any] = await request.json()
    except Exception:
        logger.error(f"WhatsApp webhook: invalid JSON for {connection_id}")
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Process entries
    manager = get_platform_manager()
    adapter = manager.get_adapter(connection_id)

    for entry in payload.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            messages = value.get("messages", [])

            for msg in messages:
                try:
                    sender = msg.get("from", "")
                    msg_id = msg.get("id", "")
                    msg_type = msg.get("type", "")

                    # Extract text content based on message type
                    text = ""
                    if msg_type == "text":
                        text = msg.get("text", {}).get("body", "")
                    elif msg_type == "button":
                        text = msg.get("button", {}).get("text", "")
                    elif msg_type == "interactive":
                        interactive = msg.get("interactive", {})
                        if interactive.get("type") == "button_reply":
                            text = interactive.get("button_reply", {}).get("title", "")
                        elif interactive.get("type") == "list_reply":
                            text = interactive.get("list_reply", {}).get("title", "")

                    if not text:
                        continue

                    # Mark message as read (best-effort)
                    if adapter and msg_id:
                        from cachibot.services.adapters.whatsapp import WhatsAppAdapter

                        if isinstance(adapter, WhatsAppAdapter):
                            await adapter.mark_as_read(msg_id)

                    # Build metadata
                    metadata: dict[str, Any] = {
                        "platform": "whatsapp",
                        "chat_id": sender,
                        "user_id": sender,
                        "message_id": msg_id,
                        "message_type": msg_type,
                    }

                    # Extract contact name if available
                    contacts = value.get("contacts", [])
                    if contacts:
                        profile = contacts[0].get("profile", {})
                        metadata["display_name"] = profile.get("name", "")

                    # Route through the adapter's on_message callback
                    if adapter and adapter.on_message:
                        response = await adapter.on_message(
                            connection_id,
                            sender,
                            text,
                            metadata,
                        )

                        # Send the response back
                        if response.text or response.media:
                            await adapter.send_response(sender, response)
                    else:
                        logger.warning(
                            f"WhatsApp webhook: no active adapter for connection {connection_id}"
                        )

                except Exception as e:
                    logger.error(f"Error processing WhatsApp message: {e}")

    return {"status": "ok"}

"""
LINE Webhook Routes

Handles incoming webhook events from the LINE Messaging API.
"""

import logging

from fastapi import APIRouter, Header, HTTPException, Request

from cachibot.services.adapters.line import LineAdapter
from cachibot.services.platform_manager import get_platform_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/line", tags=["webhooks"])


@router.post("/{connection_id}")
async def line_webhook(
    connection_id: str,
    request: Request,
    x_line_signature: str = Header(..., alias="X-Line-Signature"),
) -> dict:
    """Handle incoming LINE webhook events.

    LINE sends message events to this endpoint. The request is validated
    using the X-Line-Signature header and forwarded to the adapter.

    Args:
        connection_id: The CachiBot connection ID.
        request: The incoming FastAPI request.
        x_line_signature: The LINE signature header for request validation.

    Returns:
        A simple OK response (LINE expects 200).
    """
    # Get raw body for signature validation
    raw_body = await request.body()

    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Get the adapter from platform manager
    manager = get_platform_manager()
    adapter = manager.get_adapter(connection_id)

    if adapter is None:
        logger.warning(f"LINE webhook received for unknown connection: {connection_id}")
        raise HTTPException(status_code=404, detail="Connection not found")

    if not isinstance(adapter, LineAdapter):
        logger.warning(
            f"LINE webhook received for non-LINE connection: {connection_id} "
            f"(adapter type: {type(adapter).__name__})"
        )
        raise HTTPException(status_code=400, detail="Connection is not a LINE adapter")

    try:
        await adapter.process_webhook(body, raw_body, x_line_signature)
    except ValueError as e:
        logger.warning(f"LINE webhook validation failed for {connection_id}: {e}")
        raise HTTPException(status_code=403, detail="Invalid signature")
    except Exception as e:
        logger.error(f"Error processing LINE webhook for {connection_id}: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

    return {"status": "ok"}

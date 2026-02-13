"""
Microsoft Teams Webhook Routes

FastAPI webhook endpoints as an alternative to the Teams adapter's built-in
aiohttp server. Forwards Bot Framework activities to the adapter's
process_activity method.
"""

import logging

from fastapi import APIRouter, HTTPException, Request

from cachibot.services.platform_manager import get_platform_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/webhooks/teams", tags=["webhooks"])


@router.post("/{connection_id}/messages")
async def handle_teams_message(connection_id: str, request: Request) -> dict:
    """Forward a Bot Framework activity to the Teams adapter.

    This endpoint receives incoming activities from the Bot Framework Service
    and delegates processing to the corresponding TeamsAdapter instance.

    Args:
        connection_id: The CachiBot connection ID for the Teams bot.
        request: The incoming HTTP request with the activity JSON body.

    Returns:
        A status dict on success.

    Raises:
        HTTPException: If the adapter is not found, not connected, or processing fails.
    """
    try:
        from cachibot.services.adapters.teams import TeamsAdapter
    except ImportError:
        raise HTTPException(
            status_code=501,
            detail=(
                "Bot Framework SDK is not installed. "
                "Run: pip install botbuilder-core botbuilder-schema"
            ),
        )

    manager = get_platform_manager()

    # Look up the adapter for this connection
    adapter = manager._adapters.get(connection_id)
    if adapter is None:
        raise HTTPException(
            status_code=404,
            detail=f"No active adapter found for connection {connection_id}",
        )

    if not isinstance(adapter, TeamsAdapter):
        raise HTTPException(
            status_code=400,
            detail=f"Connection {connection_id} is not a Teams adapter",
        )

    if not adapter.is_running:
        raise HTTPException(
            status_code=503,
            detail=f"Teams adapter for connection {connection_id} is not running",
        )

    # Extract the authorization header and request body
    auth_header = request.headers.get("Authorization", "")
    body = await request.json()

    try:
        await adapter.process_activity(body, auth_header)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Failed to process Teams webhook activity: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process Teams activity",
        )

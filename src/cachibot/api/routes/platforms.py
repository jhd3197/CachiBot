"""
Platforms API Route

Returns available platform adapter metadata from the AdapterRegistry.
No authentication required -- this is static class metadata, not user data.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cachibot.services.adapters.registry import AdapterRegistry

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("")
async def list_platforms() -> JSONResponse:
    """Return metadata for all registered platform adapters."""
    data = AdapterRegistry.available_platforms()
    return JSONResponse(
        content=data,
        headers={"Cache-Control": "public, max-age=3600"},
    )


@router.get("/custom/spec")
async def custom_platform_spec() -> dict:
    """Return the full API contract for the Custom platform adapter.

    Describes inbound webhook format, outbound endpoint specs, and example payloads
    so users can implement a compatible API.
    """
    return {
        "inbound": {
            "description": "POST messages from your platform to CachiBot",
            "method": "POST",
            "url_template": "/api/webhooks/custom/{connection_id}",
            "headers": {
                "Content-Type": "application/json",
                "X-API-Key": "(optional) Your configured API key",
            },
            "body": {
                "chat_id": {"type": "string", "required": True, "description": "Conversation ID"},
                "message": {"type": "string", "required": True, "description": "Message text"},
                "user_id": {
                    "type": "string",
                    "required": False,
                    "description": "Sender user ID",
                },
                "display_name": {
                    "type": "string",
                    "required": False,
                    "description": "Sender display name",
                },
                "metadata": {
                    "type": "object",
                    "required": False,
                    "description": "Additional metadata (passed through to the bot)",
                },
            },
            "example": {
                "chat_id": "user-123",
                "message": "Hello, bot!",
                "user_id": "user-123",
                "display_name": "Alice",
                "metadata": {"source": "my-app"},
            },
        },
        "outbound": [
            {
                "endpoint": "POST {base_url}/messages",
                "capability": "send_messages",
                "default": True,
                "body": {
                    "chat_id": "string",
                    "message": "string",
                    "metadata": {"connection_id": "string", "bot_id": "string"},
                },
            },
            {
                "endpoint": "POST {base_url}/typing",
                "capability": "typing_indicator",
                "default": False,
                "body": {"chat_id": "string"},
            },
            {
                "endpoint": "POST {base_url}/read",
                "capability": "read_receipts",
                "default": False,
                "body": {"chat_id": "string", "message_id": "string"},
            },
            {
                "endpoint": "POST {base_url}/status",
                "capability": "message_status",
                "default": False,
                "body": {"chat_id": "string", "message_id": "string", "status": "string"},
            },
        ],
    }

"""
Commands API Routes

Endpoint for discovering available /prefix:command entries for frontend autocomplete.
"""

from dataclasses import asdict

from fastapi import APIRouter, Depends, Query

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.services.command_registry import get_command_registry

router = APIRouter(prefix="/api/commands", tags=["commands"])


@router.get("")
async def list_commands(
    bot_id: str | None = Query(default=None, alias="bot_id"),
    _user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    """List all available /prefix:command entries.

    Returns commands from user-level skills, per-bot instructions, and CLI stubs.
    Used by the frontend for autocomplete in the chat input.
    """
    registry = get_command_registry()
    descriptors = await registry.get_all(bot_id=bot_id)
    return [asdict(d) for d in descriptors]

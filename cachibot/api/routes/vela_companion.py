"""Vela companion settings endpoints.

``GET /api/vela-companion/status`` tells the settings UI whether a local Vela
exists, whether the companion integration is on, and when Vela last talked to
the loopback server (the only honest "connected" signal — CachiBot never calls
Vela). ``PUT /api/vela-companion/settings`` is admin-only and applies
immediately. Neither exposes the bearer token nor the endpoint port.
"""

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cachibot.api.auth import get_admin_user, get_current_user
from cachibot.models.auth import User
from cachibot.services.vela_companion import get_vela_companion_service

router = APIRouter(tags=["vela-companion"])


class VelaCompanionSettings(BaseModel):
    enabled: bool


@router.get("/api/vela-companion/status")
async def vela_companion_status(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Presence/registration/last-seen for the settings section (any user)."""
    return get_vela_companion_service().status_snapshot()


@router.put("/api/vela-companion/settings")
async def vela_companion_update_settings(
    settings: VelaCompanionSettings, user: User = Depends(get_admin_user)
) -> dict[str, Any]:
    """Toggle the companion integration; applies immediately (admin only)."""
    await get_vela_companion_service().set_enabled(settings.enabled)
    return get_vela_companion_service().status_snapshot()

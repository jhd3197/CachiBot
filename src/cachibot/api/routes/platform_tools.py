"""
Platform Tools API Routes

Global tool visibility configuration — admins can disable capabilities and
skills platform-wide so they never appear in bot settings or at runtime.
"""

from fastapi import APIRouter, Depends

from cachibot.api.auth import get_admin_user, get_current_user
from cachibot.models.auth import User
from cachibot.models.platform_tools import PlatformToolConfig, PlatformToolConfigUpdate
from cachibot.storage.repository import PlatformToolConfigRepository

router = APIRouter(prefix="/api/platform/tools", tags=["platform-tools"])

repo = PlatformToolConfigRepository()


@router.get("", response_model=PlatformToolConfig)
async def get_platform_tool_config(
    user: User = Depends(get_current_user),
) -> PlatformToolConfig:
    """Get the current global tool visibility configuration."""
    return await repo.get_config()


@router.put("", response_model=PlatformToolConfig)
async def update_platform_tool_config(
    body: PlatformToolConfigUpdate,
    user: User = Depends(get_admin_user),
) -> PlatformToolConfig:
    """Update global tool visibility (admin only)."""
    return await repo.update_config(body, user_id=user.id)

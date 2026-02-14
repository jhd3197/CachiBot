"""
Platforms API Route

Returns available platform adapter metadata from the AdapterRegistry.
No authentication required — this is static class metadata, not user data.
"""

from typing import Any

from fastapi import APIRouter

from cachibot.services.adapters.registry import AdapterRegistry

router = APIRouter(prefix="/api/platforms", tags=["platforms"])


@router.get("")
async def list_platforms() -> dict[str, dict[str, Any]]:
    """Return metadata for all registered platform adapters."""
    return AdapterRegistry.available_platforms()

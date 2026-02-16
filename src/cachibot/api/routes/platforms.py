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

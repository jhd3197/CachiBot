"""Health check endpoint."""

import os
import platform
import sys

from fastapi import APIRouter
from pydantic import BaseModel

from cachibot import __version__

router = APIRouter()


def _detect_build() -> str:
    """Detect build type from version string."""
    if ".dev" in __version__:
        return "dev"
    if __version__ == "0.0.0-unknown":
        return "local"
    return "release"


class HealthResponse(BaseModel):
    """Health check response."""

    status: str = "ok"
    version: str = __version__
    build: str = _detect_build()
    python: str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    platform: str = platform.system().lower()
    desktop: bool = os.environ.get("CACHIBOT_DESKTOP", "").lower() == "true"


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check if the API is running."""
    return HealthResponse()

"""Telemetry API endpoints."""

import os
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.services.terms_checker import get_latest_terms_version

router = APIRouter()


# ---------- Response / request models ----------


class TelemetryStatusResponse(BaseModel):
    """Current telemetry status."""

    enabled: bool
    install_id: str
    last_sent: str
    terms_accepted: bool
    terms_version: str
    terms_accepted_at: str
    latest_terms_version: str


class TelemetrySettingsUpdate(BaseModel):
    """Update telemetry settings."""

    enabled: bool | None = None
    terms_accepted: bool | None = None
    terms_version: str | None = None


class ConsentRequest(BaseModel):
    """First-run consent request."""

    terms_accepted: bool
    terms_version: str
    telemetry_enabled: bool = False


class ResetIdResponse(BaseModel):
    """Response after resetting install ID."""

    install_id: str


# ---------- Endpoints ----------


@router.get("/telemetry/status", response_model=TelemetryStatusResponse)
async def telemetry_status(
    user: User = Depends(get_current_user),
) -> TelemetryStatusResponse:
    """Get current telemetry status."""
    from cachibot.config import Config

    config = Config.load()

    # Ensure install_id exists
    if not config.telemetry.install_id:
        config.telemetry.install_id = uuid.uuid4().hex
        config.save_telemetry_config()

    return TelemetryStatusResponse(
        enabled=config.telemetry.enabled
        and os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() not in ("1", "true", "yes"),
        install_id=config.telemetry.install_id,
        last_sent=config.telemetry.last_sent,
        terms_accepted=config.telemetry.terms_accepted,
        terms_version=config.telemetry.terms_version,
        terms_accepted_at=config.telemetry.terms_accepted_at,
        latest_terms_version=get_latest_terms_version(),
    )


@router.get("/telemetry/preview")
async def telemetry_preview(
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Preview the exact telemetry payload that would be sent."""
    from cachibot.telemetry.collector import collect_telemetry

    return collect_telemetry()


@router.put("/telemetry/settings", response_model=TelemetryStatusResponse)
async def update_telemetry_settings(
    update: TelemetrySettingsUpdate,
    user: User = Depends(get_current_user),
) -> TelemetryStatusResponse:
    """Update telemetry settings."""
    from cachibot.config import Config

    config = Config.load()

    if update.enabled is not None:
        config.telemetry.enabled = update.enabled
    if update.terms_accepted is not None:
        config.telemetry.terms_accepted = update.terms_accepted
        if update.terms_accepted:
            config.telemetry.terms_accepted_at = datetime.now(timezone.utc).isoformat()
    if update.terms_version is not None:
        config.telemetry.terms_version = update.terms_version

    # Ensure install_id
    if not config.telemetry.install_id:
        config.telemetry.install_id = uuid.uuid4().hex

    config.save_telemetry_config()

    return TelemetryStatusResponse(
        enabled=config.telemetry.enabled
        and os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() not in ("1", "true", "yes"),
        install_id=config.telemetry.install_id,
        last_sent=config.telemetry.last_sent,
        terms_accepted=config.telemetry.terms_accepted,
        terms_version=config.telemetry.terms_version,
        terms_accepted_at=config.telemetry.terms_accepted_at,
        latest_terms_version=get_latest_terms_version(),
    )


@router.post("/telemetry/reset-id", response_model=ResetIdResponse)
async def reset_install_id(
    user: User = Depends(get_current_user),
) -> ResetIdResponse:
    """Generate a new anonymous install UUID."""
    from cachibot.config import Config

    config = Config.load()
    config.telemetry.install_id = uuid.uuid4().hex
    config.save_telemetry_config()

    return ResetIdResponse(install_id=config.telemetry.install_id)


@router.post("/telemetry/consent", response_model=TelemetryStatusResponse)
async def accept_consent(
    req: ConsentRequest,
    user: User = Depends(get_current_user),
) -> TelemetryStatusResponse:
    """Accept terms and optionally opt in to telemetry (first-run flow)."""
    from cachibot.config import Config

    config = Config.load()

    config.telemetry.terms_accepted = req.terms_accepted
    config.telemetry.terms_version = req.terms_version
    config.telemetry.terms_accepted_at = datetime.now(timezone.utc).isoformat()
    config.telemetry.enabled = req.telemetry_enabled

    # Ensure install_id
    if not config.telemetry.install_id:
        config.telemetry.install_id = uuid.uuid4().hex

    config.save_telemetry_config()

    return TelemetryStatusResponse(
        enabled=config.telemetry.enabled
        and os.getenv("CACHIBOT_TELEMETRY_DISABLED", "").lower() not in ("1", "true", "yes"),
        install_id=config.telemetry.install_id,
        last_sent=config.telemetry.last_sent,
        terms_accepted=config.telemetry.terms_accepted,
        terms_version=config.telemetry.terms_version,
        terms_accepted_at=config.telemetry.terms_accepted_at,
        latest_terms_version=get_latest_terms_version(),
    )

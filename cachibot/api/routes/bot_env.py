"""
Bot Environment API Routes

CRUD endpoints for per-bot environment variables, platform environment
defaults, and skill configurations.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlalchemy import select as sa_select

from cachibot.api.auth import get_admin_user, require_bot_access, require_bot_access_level
from cachibot.api.helpers import require_found
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.services.encryption import get_encryption_service
from cachibot.storage import db
from cachibot.storage.models.env_var import (
    BotEnvironment,
    BotSkillConfig,
    EnvAuditLog,
    PlatformEnvironment,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots/{bot_id}/environment", tags=["bot-environment"])
platform_router = APIRouter(
    prefix="/api/platforms/{platform}/environment", tags=["platform-environment"]
)
skill_config_router = APIRouter(
    prefix="/api/bots/{bot_id}/skills/{skill_name}/config",
    tags=["skill-config"],
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mask_value(value: str) -> str:
    """Mask a secret value, showing only last 4 chars."""
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


async def _audit_log(
    action: str,
    key_name: str,
    source: str,
    *,
    bot_id: str | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
    details: dict[str, object] | None = None,
) -> None:
    """Write an entry to the env_audit_log table."""
    try:
        async with db.ensure_initialized()() as session:
            entry = EnvAuditLog(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=user_id,
                action=action,
                key_name=key_name,
                source=source,
                timestamp=datetime.now(timezone.utc),
                ip_address=ip_address,
                details=details or {},
            )
            session.add(entry)
            await session.commit()
    except Exception:
        logger.warning("Failed to write audit log entry", exc_info=True)


def _client_ip(request: Request) -> str | None:
    """Extract client IP from the request."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return None


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class EnvVarResponse(BaseModel):
    key: str
    masked_value: str
    source: str
    updated_at: str


class EnvVarListResponse(BaseModel):
    variables: list[EnvVarResponse]


class ResolvedVarResponse(BaseModel):
    masked_value: str | None = None
    value: str | float | int | None = None
    source: str


class ResolvedEnvResponse(BaseModel):
    resolved: dict[str, ResolvedVarResponse]
    skill_configs: dict[str, dict[str, ResolvedVarResponse]]


class EnvVarSetRequest(BaseModel):
    value: str


class SkillConfigSetRequest(BaseModel):
    config: dict[str, object]


# ---------------------------------------------------------------------------
# Bot Environment CRUD
# ---------------------------------------------------------------------------


@router.get("")
async def list_bot_env_vars(
    bot_id: str,
    request: Request,
    user: User = Depends(require_bot_access),
) -> EnvVarListResponse:
    """List per-bot environment variable overrides (masked values only)."""
    enc = get_encryption_service()
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
        )
        rows = result.scalars().all()

    variables = []
    for row in rows:
        try:
            plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt, bot_id)
            masked = _mask_value(plaintext)
        except Exception:
            masked = "****"
        variables.append(
            EnvVarResponse(
                key=row.key,
                masked_value=masked,
                source=row.source,
                updated_at=row.updated_at.isoformat() if row.updated_at else "",
            )
        )
    return EnvVarListResponse(variables=variables)


@router.put("/{key}", response_model=dict)
async def set_bot_env_var(
    bot_id: str,
    key: str,
    body: EnvVarSetRequest,
    request: Request,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> dict[str, object]:
    """Set or update a per-bot environment variable."""
    enc = get_encryption_service()
    ct, nonce, salt = enc.encrypt_value(body.value, bot_id)
    now = datetime.now(timezone.utc)

    async with db.ensure_initialized()() as session:
        # Check if key already exists
        result = await session.execute(
            sa_select(BotEnvironment).where(
                BotEnvironment.bot_id == bot_id,
                BotEnvironment.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value_encrypted = ct
            existing.nonce = nonce
            existing.salt = salt
            existing.updated_at = now
            existing.created_by = user.id
            action = "update"
        else:
            new_var = BotEnvironment(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                key=key,
                value_encrypted=ct,
                nonce=nonce,
                salt=salt,
                source="user",
                created_at=now,
                updated_at=now,
                created_by=user.id,
            )
            session.add(new_var)
            action = "create"

        await session.commit()

    await _audit_log(
        action=action,
        key_name=key,
        source="bot",
        bot_id=bot_id,
        user_id=user.id,
        ip_address=_client_ip(request),
        details={"masked_value": _mask_value(body.value)},
    )

    return {"ok": True, "action": action}


@router.delete("/{key}", status_code=204)
async def delete_bot_env_var(
    bot_id: str,
    key: str,
    request: Request,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> None:
    """Delete a per-bot environment variable override (falls back to inherited)."""
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_delete(BotEnvironment).where(
                BotEnvironment.bot_id == bot_id,
                BotEnvironment.key == key,
            )
        )
        await session.commit()
        deleted = result.rowcount > 0  # type: ignore[attr-defined]

    require_found(deleted, "Environment variable")

    await _audit_log(
        action="delete",
        key_name=key,
        source="bot",
        bot_id=bot_id,
        user_id=user.id,
        ip_address=_client_ip(request),
    )

    return None


@router.get("/resolved")
async def get_resolved_env(
    bot_id: str,
    request: Request,
    user: User = Depends(require_bot_access),
) -> ResolvedEnvResponse:
    """Get the fully resolved config for a bot showing all layers merged with source indicators."""
    import os

    enc = get_encryption_service()
    resolved: dict[str, ResolvedVarResponse] = {}

    # Layer 1: Global (from os.environ via the PROVIDERS dict)
    from cachibot.api.routes.providers import PROVIDERS

    for provider_name, info in PROVIDERS.items():
        env_key = info["env_key"]
        value = os.environ.get(env_key, "")
        if value:
            if info["type"] == "endpoint":
                resolved[env_key] = ResolvedVarResponse(value=value, source="global")
            else:
                resolved[env_key] = ResolvedVarResponse(
                    masked_value=_mask_value(value), source="global"
                )

    # Layer 3: Bot overrides (skip Layer 2 platform for now — v1)
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
        )
        bot_vars = result.scalars().all()

    for row in bot_vars:
        try:
            plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt, bot_id)
            resolved[row.key] = ResolvedVarResponse(
                masked_value=_mask_value(plaintext), source="bot"
            )
        except Exception:
            resolved[row.key] = ResolvedVarResponse(masked_value="****", source="bot")

    # Layer 4: Skill configs
    skill_configs: dict[str, dict[str, ResolvedVarResponse]] = {}
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(BotSkillConfig).where(BotSkillConfig.bot_id == bot_id)
        )
        skill_rows = result.scalars().all()

    for row in skill_rows:
        try:
            config = json.loads(row.config_json)  # type: ignore[attr-defined]
        except Exception:
            config = {}
        skill_configs[row.skill_name] = {  # type: ignore[attr-defined]
            k: ResolvedVarResponse(value=v, source="bot") for k, v in config.items()
        }

    return ResolvedEnvResponse(resolved=resolved, skill_configs=skill_configs)


# ---------------------------------------------------------------------------
# Bot Environment: Reset all
# ---------------------------------------------------------------------------


@router.delete("")
async def reset_bot_env(
    bot_id: str,
    request: Request,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> dict[str, object]:
    """Delete ALL per-bot environment overrides (reset to defaults)."""
    async with db.ensure_initialized()() as session:
        # Delete all env vars
        env_result = await session.execute(
            sa_delete(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
        )
        # Delete all skill configs
        skill_result = await session.execute(
            sa_delete(BotSkillConfig).where(BotSkillConfig.bot_id == bot_id)
        )
        await session.commit()
        total = env_result.rowcount + skill_result.rowcount  # type: ignore[attr-defined]

    await _audit_log(
        action="reset_all",
        key_name="*",
        source="bot",
        bot_id=bot_id,
        user_id=user.id,
        ip_address=_client_ip(request),
        details={"deleted_count": total},
    )

    return {"ok": True, "deleted": total}


# ---------------------------------------------------------------------------
# Platform Environment CRUD (Admin only)
# ---------------------------------------------------------------------------


@platform_router.get("")
async def list_platform_env_vars(
    platform: str,
    user: User = Depends(get_admin_user),
) -> EnvVarListResponse:
    """List platform environment variable defaults (admin only, masked)."""
    enc = get_encryption_service()
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(PlatformEnvironment).where(PlatformEnvironment.platform == platform)
        )
        rows = result.scalars().all()

    variables = []
    for row in rows:
        try:
            plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt)
            masked = _mask_value(plaintext)
        except Exception:
            masked = "****"
        variables.append(
            EnvVarResponse(
                key=row.key,
                masked_value=masked,
                source="platform",
                updated_at=row.updated_at.isoformat() if row.updated_at else "",
            )
        )
    return EnvVarListResponse(variables=variables)


@platform_router.put("/{key}", response_model=dict)
async def set_platform_env_var(
    platform: str,
    key: str,
    body: EnvVarSetRequest,
    request: Request,
    user: User = Depends(get_admin_user),
) -> dict[str, object]:
    """Set or update a platform environment variable default (admin only)."""
    enc = get_encryption_service()
    ct, nonce, salt = enc.encrypt_value(body.value)
    now = datetime.now(timezone.utc)

    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(PlatformEnvironment).where(
                PlatformEnvironment.platform == platform,
                PlatformEnvironment.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.value_encrypted = ct
            existing.nonce = nonce
            existing.salt = salt
            existing.updated_at = now
            existing.created_by = user.id
            action = "update"
        else:
            new_var = PlatformEnvironment(
                id=str(uuid.uuid4()),
                platform=platform,
                key=key,
                value_encrypted=ct,
                nonce=nonce,
                salt=salt,
                created_at=now,
                updated_at=now,
                created_by=user.id,
            )
            session.add(new_var)
            action = "create"

        await session.commit()

    await _audit_log(
        action=action,
        key_name=key,
        source="platform",
        user_id=user.id,
        ip_address=_client_ip(request),
        details={"platform": platform, "masked_value": _mask_value(body.value)},
    )

    return {"ok": True, "action": action}


@platform_router.delete("/{key}", status_code=204)
async def delete_platform_env_var(
    platform: str,
    key: str,
    request: Request,
    user: User = Depends(get_admin_user),
) -> None:
    """Delete a platform environment variable default (admin only)."""
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_delete(PlatformEnvironment).where(
                PlatformEnvironment.platform == platform,
                PlatformEnvironment.key == key,
            )
        )
        await session.commit()
        deleted = result.rowcount > 0  # type: ignore[attr-defined]

    require_found(deleted, "Platform env var")

    await _audit_log(
        action="delete",
        key_name=key,
        source="platform",
        user_id=user.id,
        ip_address=_client_ip(request),
        details={"platform": platform},
    )

    return None


# ---------------------------------------------------------------------------
# Skill Config CRUD
# ---------------------------------------------------------------------------


@skill_config_router.get("")
async def get_skill_config(
    bot_id: str,
    skill_name: str,
    user: User = Depends(require_bot_access),
) -> dict[str, object]:
    """Get skill configuration for a bot."""
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(BotSkillConfig).where(
                BotSkillConfig.bot_id == bot_id,
                BotSkillConfig.skill_name == skill_name,
            )
        )
        row = result.scalar_one_or_none()

    if row is None:
        return {"skill_name": skill_name, "config": {}}

    try:
        config = json.loads(row.config_json)
    except Exception:
        config = {}

    return {"skill_name": skill_name, "config": config}


@skill_config_router.put("")
async def set_skill_config(
    bot_id: str,
    skill_name: str,
    body: SkillConfigSetRequest,
    request: Request,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> dict[str, object]:
    """Set skill configuration for a bot."""
    config_json = json.dumps(body.config)
    now = datetime.now(timezone.utc)

    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_select(BotSkillConfig).where(
                BotSkillConfig.bot_id == bot_id,
                BotSkillConfig.skill_name == skill_name,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.config_json = config_json
            existing.updated_at = now
            action = "update"
        else:
            new_config = BotSkillConfig(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                skill_name=skill_name,
                config_json=config_json,
                created_at=now,
                updated_at=now,
            )
            session.add(new_config)
            action = "create"

        await session.commit()

    await _audit_log(
        action=action,
        key_name=f"skill:{skill_name}",
        source="bot",
        bot_id=bot_id,
        user_id=user.id,
        ip_address=_client_ip(request),
    )

    return {"ok": True, "action": action}


@skill_config_router.delete("")
async def delete_skill_config(
    bot_id: str,
    skill_name: str,
    request: Request,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> dict[str, object]:
    """Delete skill configuration for a bot (revert to defaults)."""
    async with db.ensure_initialized()() as session:
        result = await session.execute(
            sa_delete(BotSkillConfig).where(
                BotSkillConfig.bot_id == bot_id,
                BotSkillConfig.skill_name == skill_name,
            )
        )
        await session.commit()
        deleted = result.rowcount > 0  # type: ignore[attr-defined]

    require_found(deleted, "Skill config")

    await _audit_log(
        action="delete",
        key_name=f"skill:{skill_name}",
        source="bot",
        bot_id=bot_id,
        user_id=user.id,
        ip_address=_client_ip(request),
    )

    return {"ok": True}

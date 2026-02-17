"""
Bots API Routes

CRUD endpoints for syncing bot configuration from frontend.
"""

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cachibot.api.auth import get_current_user, require_bot_access
from cachibot.models.auth import BotOwnership, User, UserRole
from cachibot.models.bot import Bot, BotResponse
from cachibot.models.skill import BotSkillRequest, SkillResponse
from cachibot.storage.repository import BotRepository, SkillsRepository
from cachibot.storage.user_repository import OwnershipRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots", tags=["bots"])

# Repository instances
repo = BotRepository()
skills_repo = SkillsRepository()
ownership_repo = OwnershipRepository()


class BotSyncRequest(BaseModel):
    """Request body for syncing a bot from frontend."""

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    model: str
    models: dict | None = None
    systemPrompt: str
    capabilities: dict = Field(default_factory=dict)
    createdAt: str
    updatedAt: str


@router.get("")
async def list_bots(
    user: User = Depends(get_current_user),
) -> list[BotResponse]:
    """Get bots accessible to the current user."""
    if user.role == UserRole.ADMIN:
        bots = await repo.get_all_bots()
    else:
        bot_ids = await ownership_repo.get_user_bots(user.id)
        bots = [b for b in [await repo.get_bot(bid) for bid in bot_ids] if b is not None]
    return [BotResponse.from_bot(b) for b in bots]


@router.get("/{bot_id}")
async def get_bot(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotResponse:
    """Get a specific bot."""
    bot = await repo.get_bot(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")
    return BotResponse.from_bot(bot)


@router.put("/{bot_id}")
async def sync_bot(
    bot_id: str,
    body: BotSyncRequest,
    user: User = Depends(require_bot_access),
) -> BotResponse:
    """Sync a bot from frontend (create or update)."""
    if body.id != bot_id:
        raise HTTPException(status_code=400, detail="Bot ID mismatch")

    bot = Bot(
        id=body.id,
        name=body.name,
        description=body.description,
        icon=body.icon,
        color=body.color,
        model=body.model,
        models=body.models,
        systemPrompt=body.systemPrompt,
        capabilities=body.capabilities,
        createdAt=datetime.fromisoformat(body.createdAt.replace("Z", "+00:00")),
        updatedAt=datetime.fromisoformat(body.updatedAt.replace("Z", "+00:00")),
    )

    await repo.upsert_bot(bot)
    return BotResponse.from_bot(bot)


@router.delete("/{bot_id}", status_code=204)
async def delete_bot(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a bot."""
    deleted = await repo.delete_bot(bot_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Bot not found")


# =============================================================================
# BOT SKILLS ENDPOINTS
# =============================================================================


@router.get("/{bot_id}/skills")
async def get_bot_skills(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[SkillResponse]:
    """Get all activated skills for a bot."""
    skill_defs = await skills_repo.get_bot_skill_definitions(bot_id)
    return [SkillResponse.from_skill(s) for s in skill_defs]


@router.get("/{bot_id}/skills/ids")
async def get_bot_skill_ids(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[str]:
    """Get just the IDs of activated skills for a bot."""
    return await skills_repo.get_bot_skills(bot_id)


@router.post("/{bot_id}/skills")
async def activate_bot_skill(
    bot_id: str,
    body: BotSkillRequest,
    user: User = Depends(require_bot_access),
) -> dict:
    """Activate a skill for a bot."""
    # Verify skill exists
    skill = await skills_repo.get_skill(body.skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    await skills_repo.activate_skill(bot_id, body.skill_id)
    return {"status": "activated", "skill_id": body.skill_id}


@router.delete("/{bot_id}/skills/{skill_id}", status_code=204)
async def deactivate_bot_skill(
    bot_id: str,
    skill_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Deactivate a skill for a bot."""
    deactivated = await skills_repo.deactivate_skill(bot_id, skill_id)
    if not deactivated:
        raise HTTPException(status_code=404, detail="Skill not activated for this bot")


# =============================================================================
# PER-BOT MODEL DISCOVERY
# =============================================================================


class BotModelInfo(BaseModel):
    """A model available to a specific bot."""

    model: str = Field(description="Full model ID (provider/model-id)")
    provider: str = Field(description="Provider name")
    source: str = Field(description="Key source: 'custom' or 'platform' (inherited)")


class BotAvailableModelsResponse(BaseModel):
    """Response for per-bot model discovery."""

    models: list[BotModelInfo] = Field(default_factory=list)


@router.get("/{bot_id}/available-models")
async def get_bot_available_models(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotAvailableModelsResponse:
    """Get models available to a specific bot based on its configured API keys.

    Returns models the bot has access to, tagged with whether the key is
    the bot's own (``custom``) or inherited from the platform/global config
    (``platform``).
    """
    try:
        from cachibot.services.bot_environment import BotEnvironmentService
        from cachibot.services.encryption import get_encryption_service
        from cachibot.storage.db import ensure_initialized

        session_maker = ensure_initialized()
        async with session_maker() as session:
            encryption = get_encryption_service()
            env_service = BotEnvironmentService(session, encryption)
            resolved = await env_service.resolve(bot_id)
    except Exception:
        logger.warning("Failed to resolve bot environment for model discovery", exc_info=True)
        raise HTTPException(
            status_code=503,
            detail="Environment service unavailable. Using global model list.",
        )

    # Determine which providers have keys and whether they're custom or inherited
    from cachibot.api.routes.providers import PROVIDERS

    available: list[BotModelInfo] = []

    # Try live model discovery from Prompture
    try:
        from prompture import get_available_models

        all_models = get_available_models(include_capabilities=False)
    except Exception:
        all_models = []

    # Build a set of providers the bot has keys for
    bot_providers = set(resolved.provider_keys.keys())

    # Check which providers have bot-level (custom) vs global (platform) keys
    import os

    for entry in all_models:
        provider = entry.get("provider", "unknown")
        if provider not in bot_providers:
            continue

        raw_id = entry["model_id"]
        model_id = f"{provider}/{raw_id}" if not raw_id.startswith(f"{provider}/") else raw_id

        # Determine source: check if there's a bot-level override by comparing
        # against global os.environ
        provider_info = PROVIDERS.get(provider)
        global_key = os.environ.get(provider_info["env_key"]) if provider_info else None
        bot_key = resolved.provider_keys.get(provider)

        # If the bot key differs from the global key, it's a custom override
        source = "custom" if bot_key and bot_key != global_key else "platform"

        available.append(BotModelInfo(model=model_id, provider=provider, source=source))

    # If no live models discovered, provide entries for each configured provider
    if not available:
        for provider in bot_providers:
            provider_info = PROVIDERS.get(provider)
            global_key = os.environ.get(provider_info["env_key"]) if provider_info else None
            bot_key = resolved.provider_keys.get(provider)
            source = "custom" if bot_key and bot_key != global_key else "platform"
            available.append(
                BotModelInfo(model=f"{provider}/default", provider=provider, source=source)
            )

    available.sort(key=lambda m: m.model)
    return BotAvailableModelsResponse(models=available)


# =============================================================================
# BOT EXPORT/IMPORT ENDPOINTS
# =============================================================================


class BotExportFormat(BaseModel):
    """Export format for a bot configuration."""

    version: str = "1.0"
    exportedAt: str
    bot: dict


class BotImportRequest(BaseModel):
    """Request body for importing a bot."""

    version: str
    exportedAt: str
    bot: dict


class BotImportResponse(BaseModel):
    """Response after importing a bot."""

    id: str
    name: str
    imported: bool
    message: str


@router.get("/{bot_id}/export")
async def export_bot(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotExportFormat:
    """
    Export a bot configuration as JSON.

    Returns a portable format that can be imported to recreate the bot.
    """
    bot = await repo.get_bot(bot_id)
    if bot is None:
        raise HTTPException(status_code=404, detail="Bot not found")

    # Get skills for the bot
    skill_ids = await skills_repo.get_bot_skills(bot_id)

    return BotExportFormat(
        version="1.0",
        exportedAt=datetime.utcnow().isoformat() + "Z",
        bot={
            "name": bot.name,
            "description": bot.description,
            "icon": bot.icon,
            "color": bot.color,
            "model": bot.model,
            "models": bot.models,
            "systemPrompt": bot.system_prompt,
            "tools": list(bot.capabilities.keys()) if bot.capabilities else [],
            "capabilities": bot.capabilities,
            "skills": skill_ids,
        },
    )


@router.post("/import")
async def import_bot(
    body: BotImportRequest,
    user: User = Depends(get_current_user),
) -> BotImportResponse:
    """
    Import a bot from an exported configuration.

    Creates a new bot with a new ID based on the imported data.
    Assigns ownership to the importing user.
    """
    # Validate version
    if body.version not in ("1.0",):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported export version: {body.version}. Supported: 1.0",
        )

    bot_data = body.bot
    if not bot_data:
        raise HTTPException(status_code=400, detail="Invalid bot data")

    # Required fields
    required = ["name", "model", "systemPrompt"]
    for field in required:
        if field not in bot_data or not bot_data[field]:
            raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

    # Generate new ID
    import uuid

    new_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Create the bot
    bot = Bot(
        id=new_id,
        name=bot_data.get("name", "Imported Bot"),
        description=bot_data.get("description"),
        icon=bot_data.get("icon", "bot"),
        color=bot_data.get("color", "#3b82f6"),
        model=bot_data.get("model"),
        models=bot_data.get("models"),
        systemPrompt=bot_data.get("systemPrompt", ""),
        capabilities=bot_data.get("capabilities", {}),
        createdAt=now,
        updatedAt=now,
    )

    await repo.upsert_bot(bot)

    # Assign ownership to the importing user
    ownership = BotOwnership(
        id=str(uuid.uuid4()),
        bot_id=new_id,
        user_id=user.id,
        created_at=now,
    )
    await ownership_repo.assign_bot_owner(ownership)

    # Activate any skills
    skill_ids = bot_data.get("skills", [])
    for skill_id in skill_ids:
        try:
            skill = await skills_repo.get_skill(skill_id)
            if skill:
                await skills_repo.activate_skill(new_id, skill_id)
        except Exception:
            pass  # Skip invalid skills

    return BotImportResponse(
        id=new_id,
        name=bot.name,
        imported=True,
        message=f"Successfully imported bot '{bot.name}'",
    )

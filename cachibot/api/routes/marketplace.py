"""Marketplace API Routes for bot templates.

Supports both local templates and remote fetch from cachibot.com marketplace.
Remote templates are cached for 5 minutes to reduce API calls.
"""

import asyncio
import logging
import os
import platform
import time
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from cachibot import __version__

from cachibot.api.auth import get_current_user
from cachibot.config import Config
from cachibot.data.marketplace_templates import (
    get_all_templates,
    get_template_by_id,
    get_templates_by_category,
    search_templates,
)
from cachibot.data.room_marketplace_templates import (
    ROOM_CATEGORY_INFO,
    RoomTemplateCategory,
    get_all_room_templates,
    get_room_template_by_id,
    get_room_templates_by_category,
    search_room_templates,
)
from cachibot.models.auth import User
from cachibot.models.bot import Bot
from cachibot.storage.repository import BotRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

repo = BotRepository()

# Remote marketplace configuration
MARKETPLACE_URL = os.getenv("CACHIBOT_MARKETPLACE_URL", "")
CACHE_TTL_SECONDS = 300  # 5 minutes

# In-memory cache for remote templates
_remote_cache: dict[str, tuple[float, list[Any] | dict[str, Any]]] = {}


class TemplateResponse(BaseModel):
    """Response model for a template."""

    id: str
    name: str
    description: str
    icon: str
    color: str
    category: str
    tags: list[str]
    model: str
    system_prompt: str
    tools: list[str]
    rating: float
    downloads: int


class TemplateListResponse(BaseModel):
    """Response with list of templates."""

    templates: list[TemplateResponse]
    total: int
    source: str = "local"  # "local" or "remote"


class CategoryInfo(BaseModel):
    """Information about a template category."""

    id: str
    name: str
    description: str
    count: int


class InstallResponse(BaseModel):
    """Response after installing a template."""

    bot_id: str
    name: str
    installed: bool
    message: str


class RoomBotSpecResponse(BaseModel):
    template_id: str
    role: str
    position: str | None = None
    keywords: list[str] = []
    waterfall_condition: str | None = None


class RoomTemplateResponse(BaseModel):
    id: str
    name: str
    description: str
    icon: str
    color: str
    category: str
    tags: list[str]
    response_mode: str
    bots: list[RoomBotSpecResponse]
    settings: dict[str, Any]
    rating: float
    downloads: int
    bot_details: list[TemplateResponse] | None = None


class RoomTemplateListResponse(BaseModel):
    templates: list[RoomTemplateResponse]
    total: int
    source: str = "local"


class InstallRoomResponse(BaseModel):
    room_id: str
    room_title: str
    bot_ids: list[str]
    installed_bots: list[str]
    reused_bots: list[str]


# Category metadata (used when remote is unavailable)
CATEGORY_INFO: dict[str, CategoryInfo] = {
    "productivity": CategoryInfo(
        id="productivity",
        name="Productivity",
        description="Tools for getting things done efficiently",
        count=4,
    ),
    "coding": CategoryInfo(
        id="coding",
        name="Coding & Development",
        description="Programming assistants and code tools",
        count=4,
    ),
    "creative": CategoryInfo(
        id="creative",
        name="Creative & Writing",
        description="Writing, brainstorming, and creative work",
        count=3,
    ),
    "data": CategoryInfo(
        id="data",
        name="Data & Analysis",
        description="Data analysis, visualization, and SQL",
        count=3,
    ),
    "learning": CategoryInfo(
        id="learning",
        name="Learning & Education",
        description="Language learning, tutoring, and quizzes",
        count=3,
    ),
    "support": CategoryInfo(
        id="support",
        name="Support & Help",
        description="Tech support and troubleshooting",
        count=2,
    ),
    "research": CategoryInfo(
        id="research",
        name="Research",
        description="Research, analysis, and knowledge gathering",
        count=2,
    ),
    "marketing": CategoryInfo(
        id="marketing",
        name="Marketing & Growth",
        description="SEO, social media, campaigns, and ad copy",
        count=4,
    ),
    "health": CategoryInfo(
        id="health",
        name="Health & Wellness",
        description="Fitness, nutrition, and mindfulness",
        count=3,
    ),
    "finance": CategoryInfo(
        id="finance",
        name="Finance & Business",
        description="Budgeting, investing, and tax optimization",
        count=3,
    ),
}


def _get_cached(key: str) -> list[Any] | dict[str, Any] | None:
    """Get cached data if still valid."""
    if key in _remote_cache:
        timestamp, data = _remote_cache[key]
        if time.time() - timestamp < CACHE_TTL_SECONDS:
            return data
        del _remote_cache[key]
    return None


def _set_cache(key: str, data: list[Any] | dict[str, Any]) -> None:
    """Cache data with current timestamp."""
    _remote_cache[key] = (time.time(), data)


async def _track_remote_install(template_id: str, template_type: str, event: str = "install") -> None:
    """Fire-and-forget: notify remote marketplace of an install event."""
    if not MARKETPLACE_URL:
        return
    try:
        import httpx

        config = Config.load()
        app_id = config.telemetry.install_id or None

        url = f"{MARKETPLACE_URL.rstrip('/')}/marketplace/templates/install"
        payload = {
            "template_id": template_id,
            "template_type": template_type,
            "event": event,
            "app_id": app_id,
            "os": platform.system(),
            "app_version": __version__,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.debug(f"Remote install tracking failed: {e}")


async def _track_remote_view(template_id: str, template_type: str) -> None:
    """Fire-and-forget: notify remote marketplace of a view event."""
    if not MARKETPLACE_URL:
        return
    try:
        import httpx

        config = Config.load()
        app_id = config.telemetry.install_id or None

        url = f"{MARKETPLACE_URL.rstrip('/')}/marketplace/templates/view"
        payload = {
            "template_id": template_id,
            "template_type": template_type,
            "app_id": app_id,
        }
        async with httpx.AsyncClient(timeout=5.0) as client:
            await client.post(url, json=payload)
    except Exception as e:
        logger.debug(f"Remote view tracking failed: {e}")


async def _fetch_remote_templates(
    category: str | None = None,
    search: str | None = None,
) -> TemplateListResponse | None:
    """
    Fetch templates from remote marketplace API.

    Returns None if remote fetch fails or is not configured.
    """
    if not MARKETPLACE_URL:
        return None

    try:
        import httpx

        cache_key = f"templates:{category or ''}:{search or ''}"
        cached = _get_cached(cache_key)
        if cached and isinstance(cached, list):
            templates = [TemplateResponse(**t) for t in cached]
            return TemplateListResponse(
                templates=templates,
                total=len(templates),
                source="remote",
            )

        # Build URL with query params
        url = f"{MARKETPLACE_URL.rstrip('/')}/marketplace/templates"
        params = {}
        if category:
            params["category"] = category
        if search:
            params["search"] = search

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

        # Cache the raw template data
        _set_cache(cache_key, data.get("templates", []))

        templates = [TemplateResponse(**t) for t in data.get("templates", [])]
        return TemplateListResponse(
            templates=templates,
            total=len(templates),
            source="remote",
        )

    except Exception as e:
        logger.warning(f"Failed to fetch remote templates: {e}")
        return None


async def _fetch_remote_template(template_id: str) -> TemplateResponse | None:
    """Fetch a single template from remote marketplace."""
    if not MARKETPLACE_URL:
        return None

    try:
        import httpx

        cache_key = f"template:{template_id}"
        cached = _get_cached(cache_key)
        if cached:
            return TemplateResponse(**cached)  # type: ignore[arg-type]

        url = f"{MARKETPLACE_URL.rstrip('/')}/marketplace/templates/{template_id}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        _set_cache(cache_key, data)
        return TemplateResponse(**data)

    except Exception as e:
        logger.warning(f"Failed to fetch remote template {template_id}: {e}")
        return None


async def _fetch_remote_categories() -> list[CategoryInfo] | None:
    """Fetch categories from remote marketplace."""
    if not MARKETPLACE_URL:
        return None

    try:
        import httpx

        cache_key = "categories"
        cached = _get_cached(cache_key)
        if cached and isinstance(cached, list):
            return [CategoryInfo(**c) for c in cached]

        url = f"{MARKETPLACE_URL.rstrip('/')}/marketplace/categories"

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            data = response.json()

        _set_cache(cache_key, data)
        return [CategoryInfo(**c) for c in data]

    except Exception as e:
        logger.warning(f"Failed to fetch remote categories: {e}")
        return None


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search query"),
    user: User = Depends(get_current_user),
) -> TemplateListResponse:
    """
    List all available marketplace templates.

    If CACHIBOT_MARKETPLACE_URL is configured, attempts to fetch from remote.
    Falls back to local templates if remote is unavailable.
    """
    # Try remote first if configured
    remote_result = await _fetch_remote_templates(category, search)
    if remote_result:
        return remote_result

    # Fall back to local templates
    if search:
        templates = search_templates(search)
    elif category:
        templates = get_templates_by_category(category)  # type: ignore
    else:
        templates = get_all_templates()

    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in templates],
        total=len(templates),
        source="local",
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    user: User = Depends(get_current_user),
) -> TemplateResponse:
    """Get details of a specific template."""
    # Try remote first if configured
    remote_template = await _fetch_remote_template(template_id)
    if remote_template:
        return remote_template

    # Fall back to local
    template = get_template_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")
    return TemplateResponse(**template)


@router.post("/templates/{template_id}/install", response_model=InstallResponse)
async def install_template(
    template_id: str,
    user: User = Depends(get_current_user),
) -> InstallResponse:
    """
    Install a template to create a new bot.

    Creates a new bot with the template's configuration.
    Tries remote marketplace first, falls back to local templates.
    """
    # Try to get template from remote or local
    template_data: dict[str, Any] | None = None

    # Check remote first
    remote_template = await _fetch_remote_template(template_id)
    if remote_template:
        template_data = remote_template.model_dump()
    else:
        # Fall back to local
        local_template = get_template_by_id(template_id)
        if local_template:
            template_data = local_template  # type: ignore[assignment]

    if template_data is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Generate new bot ID
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    # Resolve model: use template's model if set, otherwise app default
    template_model = template_data.get("model", "")
    if not template_model:
        try:
            template_model = Config.load().agent.model
        except Exception:
            template_model = ""

    # Create the bot from template
    bot = Bot(
        id=bot_id,
        name=template_data["name"],
        description=template_data["description"],
        icon=template_data["icon"],
        color=template_data["color"],
        model=template_model,
        systemPrompt=template_data["system_prompt"],
        capabilities={tool: True for tool in template_data["tools"]},
        createdAt=now,
        updatedAt=now,
    )

    await repo.upsert_bot(bot)
    asyncio.create_task(_track_remote_install(template_id, "bot"))

    return InstallResponse(
        bot_id=bot_id,
        name=template_data["name"],
        installed=True,
        message=f"Successfully installed '{template_data['name']}' template",
    )


@router.get("/categories", response_model=list[CategoryInfo])
async def list_categories(
    user: User = Depends(get_current_user),
) -> list[CategoryInfo]:
    """List all template categories with counts."""
    # Try remote first if configured
    remote_categories = await _fetch_remote_categories()
    if remote_categories:
        return remote_categories

    # Fall back to local
    return list(CATEGORY_INFO.values())


class TrackViewRequest(BaseModel):
    """Request to track a template view event."""

    template_id: str
    template_type: str  # "bot" or "room"


@router.post("/track-view")
async def track_template_view(
    req: TrackViewRequest,
    user: User = Depends(get_current_user),
) -> dict[str, bool]:
    """Track a template view event by forwarding to remote marketplace."""
    asyncio.create_task(_track_remote_view(req.template_id, req.template_type))
    return {"tracked": True}


# =============================================================================
# ROOM TEMPLATES
# =============================================================================


@router.get("/room-templates", response_model=RoomTemplateListResponse)
async def list_room_templates(
    category: RoomTemplateCategory | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search query"),
    response_mode: str | None = Query(None, description="Filter by response mode"),
    user: User = Depends(get_current_user),
) -> RoomTemplateListResponse:
    """List all available room marketplace templates."""
    if search:
        templates = search_room_templates(search)
    elif category:
        templates = get_room_templates_by_category(category)
    else:
        templates = get_all_room_templates()

    if response_mode:
        templates = [t for t in templates if t["response_mode"] == response_mode]

    return RoomTemplateListResponse(
        templates=[RoomTemplateResponse.model_validate(t) for t in templates],
        total=len(templates),
        source="local",
    )


@router.get("/room-templates/{template_id}", response_model=RoomTemplateResponse)
async def get_room_template(
    template_id: str,
    user: User = Depends(get_current_user),
) -> RoomTemplateResponse:
    """Get details of a specific room template with resolved bot details."""
    template = get_room_template_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Room template not found")

    # Resolve bot details from bot marketplace templates
    bot_details = []
    for bot_spec in template["bots"]:
        bot_template = get_template_by_id(bot_spec["template_id"])
        if bot_template:
            bot_details.append(TemplateResponse(**bot_template))

    return RoomTemplateResponse.model_validate({**template, "bot_details": bot_details})


@router.get("/room-categories", response_model=list[CategoryInfo])
async def list_room_categories(
    user: User = Depends(get_current_user),
) -> list[CategoryInfo]:
    """List all room template categories with counts."""
    all_rooms = get_all_room_templates()
    result: list[CategoryInfo] = []
    for cat_id, cat_info in ROOM_CATEGORY_INFO.items():
        count = sum(1 for t in all_rooms if t["category"] == cat_id)
        if count > 0:
            result.append(
                CategoryInfo(
                    id=cat_info["id"],
                    name=cat_info["name"],
                    description=cat_info["description"],
                    count=count,
                )
            )
    return result


@router.post("/room-templates/{template_id}/install", response_model=InstallRoomResponse)
async def install_room_template(
    template_id: str,
    user: User = Depends(get_current_user),
) -> InstallRoomResponse:
    """
    Install a room template: creates all required bots and the room.

    For each bot in the template:
    - Checks if user already has a bot with the same name (reuses it)
    - If not, installs the bot template
    Then creates a room with all the bots and configured settings.
    """
    template = get_room_template_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Room template not found")

    installed_bots: list[str] = []
    reused_bots: list[str] = []
    bot_ids: list[str] = []
    bot_id_map: dict[str, str] = {}  # template_id -> actual bot ID

    # Fetch all existing bots once for name-matching
    all_existing_bots = await repo.get_all_bots()
    existing_bots_by_name: dict[str, Bot] = {b.name: b for b in all_existing_bots}

    # Step 1: Install or reuse bots
    for bot_spec in template["bots"]:
        bot_template = get_template_by_id(bot_spec["template_id"])
        if bot_template is None:
            continue

        # Check if user already has a bot with this name
        existing = existing_bots_by_name.get(bot_template["name"])
        if existing:
            bot_ids.append(existing.id)
            bot_id_map[bot_spec["template_id"]] = existing.id
            reused_bots.append(bot_template["name"])
        else:
            # Install the bot template
            bot_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)

            template_model = bot_template.get("model", "")
            if not template_model:
                try:
                    template_model = Config.load().agent.model
                except Exception:
                    template_model = ""

            bot = Bot(
                id=bot_id,
                name=bot_template["name"],
                description=bot_template["description"],
                icon=bot_template["icon"],
                color=bot_template["color"],
                model=template_model,
                systemPrompt=bot_template["system_prompt"],
                capabilities={tool: True for tool in bot_template["tools"]},
                createdAt=now,
                updatedAt=now,
            )
            await repo.upsert_bot(bot)
            bot_ids.append(bot_id)
            bot_id_map[bot_spec["template_id"]] = bot_id
            installed_bots.append(bot_template["name"])

    if len(bot_ids) < 2:
        raise HTTPException(status_code=400, detail="Could not install enough bots for the room")

    # Step 2: Build room settings from template
    from cachibot.models.room import (
        Room,
        RoomBot,
        RoomMember,
        RoomMemberRole,
        RoomSettings,
    )
    from cachibot.storage.room_repository import (
        RoomBotRepository,
        RoomMemberRepository,
        RoomRepository,
    )

    settings_data = dict(template.get("settings", {}))
    settings_data["response_mode"] = template["response_mode"]

    # Map mode-specific settings using actual bot IDs
    if template["response_mode"] == "debate":
        positions = {}
        judge_bot_id = None
        for bot_spec in template["bots"]:
            actual_id = bot_id_map.get(bot_spec["template_id"])
            if actual_id and bot_spec.get("position"):
                positions[actual_id] = bot_spec["position"]
                if bot_spec["position"] == "NEUTRAL":
                    judge_bot_id = actual_id
        settings_data["debate_positions"] = positions
        if judge_bot_id:
            settings_data["debate_judge_bot_id"] = judge_bot_id

    if template["response_mode"] == "router":
        keywords = {}
        for bot_spec in template["bots"]:
            actual_id = bot_id_map.get(bot_spec["template_id"])
            if actual_id and bot_spec.get("keywords"):
                keywords[actual_id] = bot_spec["keywords"]
        if keywords:
            settings_data["bot_keywords"] = keywords

    if template["response_mode"] == "waterfall":
        conditions = {}
        for bot_spec in template["bots"]:
            actual_id = bot_id_map.get(bot_spec["template_id"])
            if actual_id and bot_spec.get("waterfall_condition"):
                conditions[actual_id] = bot_spec["waterfall_condition"]
        if conditions:
            settings_data["waterfall_conditions"] = conditions

    # Step 3: Create the room
    room_repo = RoomRepository()
    member_repo = RoomMemberRepository()
    room_bot_repo = RoomBotRepository()

    now = datetime.now(timezone.utc)
    room = Room(
        id=str(uuid.uuid4()),
        title=template["name"],
        description=template["description"],
        creator_id=user.id,
        max_bots=max(len(bot_ids), 2),
        settings=RoomSettings(**settings_data),
        created_at=now,
        updated_at=now,
    )
    await room_repo.create_room(room)
    asyncio.create_task(_track_remote_install(template_id, "room"))

    # Add creator as member
    creator_member = RoomMember(
        room_id=room.id,
        user_id=user.id,
        username=user.username,
        role=RoomMemberRole.CREATOR,
        joined_at=now,
    )
    await member_repo.add_member(creator_member)

    # Add bots to the room
    for bid in bot_ids:
        bot_obj = await repo.get_bot(bid)
        rb = RoomBot(
            room_id=room.id,
            bot_id=bid,
            bot_name=bot_obj.name if bot_obj else "",
            added_at=now,
        )
        await room_bot_repo.add_bot(rb)

    # Step 4: Set bot roles
    for bot_spec in template["bots"]:
        actual_id = bot_id_map.get(bot_spec["template_id"])
        if actual_id and bot_spec.get("role") and bot_spec["role"] != "default":
            try:
                await room_bot_repo.update_bot_role(room.id, actual_id, bot_spec["role"])
            except Exception:
                pass  # Non-critical -- role is cosmetic

    return InstallRoomResponse(
        room_id=room.id,
        room_title=template["name"],
        bot_ids=bot_ids,
        installed_bots=installed_bots,
        reused_bots=reused_bots,
    )

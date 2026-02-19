"""Marketplace API Routes for bot templates.

Supports both local templates and remote fetch from cachibot.com marketplace.
Remote templates are cached for 5 minutes to reduce API calls.
"""

import logging
import os
import time
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.config import Config
from cachibot.data.marketplace_templates import (
    get_all_templates,
    get_template_by_id,
    get_templates_by_category,
    search_templates,
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
        count=1,
    ),
    "research": CategoryInfo(
        id="research",
        name="Research",
        description="Research, analysis, and knowledge gathering",
        count=1,
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
        url = f"{MARKETPLACE_URL.rstrip('/')}/api/v1/templates"
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

        url = f"{MARKETPLACE_URL.rstrip('/')}/api/v1/templates/{template_id}"

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

        url = f"{MARKETPLACE_URL.rstrip('/')}/api/v1/categories"

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
    now = datetime.utcnow()

    # Resolve model: use template's model if set, otherwise app default
    template_model = template_data.get("model", "")
    if not template_model:
        try:
            template_model = Config.load().agent.model
        except Exception:
            template_model = "moonshot/kimi-k2.5"

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

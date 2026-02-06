"""Marketplace API Routes for bot templates."""

from datetime import datetime
from typing import Literal
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.bot import Bot
from cachibot.storage.repository import BotRepository
from cachibot.data.marketplace_templates import (
    get_all_templates,
    get_templates_by_category,
    get_template_by_id,
    search_templates,
    TemplateCategory,
)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

repo = BotRepository()


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


# Category metadata
CATEGORY_INFO: dict[str, CategoryInfo] = {
    "productivity": CategoryInfo(
        id="productivity",
        name="Productivity",
        description="Tools for getting things done efficiently",
        count=3,
    ),
    "coding": CategoryInfo(
        id="coding",
        name="Coding & Development",
        description="Programming assistants and code tools",
        count=3,
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
}


@router.get("/templates", response_model=TemplateListResponse)
async def list_templates(
    category: str | None = Query(None, description="Filter by category"),
    search: str | None = Query(None, description="Search query"),
    user: User = Depends(get_current_user),
) -> TemplateListResponse:
    """
    List all available marketplace templates.

    Optionally filter by category or search query.
    """
    if search:
        templates = search_templates(search)
    elif category:
        templates = get_templates_by_category(category)  # type: ignore
    else:
        templates = get_all_templates()

    return TemplateListResponse(
        templates=[TemplateResponse(**t) for t in templates],
        total=len(templates),
    )


@router.get("/templates/{template_id}", response_model=TemplateResponse)
async def get_template(
    template_id: str,
    user: User = Depends(get_current_user),
) -> TemplateResponse:
    """Get details of a specific template."""
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
    """
    template = get_template_by_id(template_id)
    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    # Generate new bot ID
    bot_id = str(uuid.uuid4())
    now = datetime.utcnow()

    # Create the bot from template
    bot = Bot(
        id=bot_id,
        name=template["name"],
        description=template["description"],
        icon=template["icon"],
        color=template["color"],
        model=template["model"],
        systemPrompt=template["system_prompt"],
        capabilities={tool: True for tool in template["tools"]},
        createdAt=now,
        updatedAt=now,
    )

    await repo.upsert_bot(bot)

    return InstallResponse(
        bot_id=bot_id,
        name=template["name"],
        installed=True,
        message=f"Successfully installed '{template['name']}' template",
    )


@router.get("/categories", response_model=list[CategoryInfo])
async def list_categories(
    user: User = Depends(get_current_user),
) -> list[CategoryInfo]:
    """List all template categories with counts."""
    return list(CATEGORY_INFO.values())

"""
Skills API Routes

CRUD endpoints for managing skill definitions.
"""

import re
from pathlib import Path

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.skill import SkillInstallRequest, SkillResponse, SkillSource
from cachibot.services.skills import (
    USER_SKILLS_DIR,
    SkillInstallError,
    SkillParseError,
    get_skills_service,
)
from cachibot.storage.repository import PlatformToolConfigRepository, SkillsRepository

router = APIRouter(prefix="/api/skills", tags=["skills"])

# Repository instances
repo = SkillsRepository()
_platform_repo = PlatformToolConfigRepository()


class SkillCreateRequest(BaseModel):
    """Request body for creating a skill from markdown content."""

    content: str
    filename: str | None = None


@router.get("")
async def list_skills(
    user: User = Depends(get_current_user),
) -> list[SkillResponse]:
    """Get all available skills (globally disabled skills are excluded)."""
    # First sync from filesystem
    service = get_skills_service()
    await service.sync_skills_to_db()

    # Filter out globally disabled skills
    disabled_skill_ids = set(await _platform_repo.get_disabled_skills())
    skills = await repo.get_all_skills()
    return [SkillResponse.from_skill(s) for s in skills if s.id not in disabled_skill_ids]


@router.get("/{skill_id}")
async def get_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
) -> SkillResponse:
    """Get a specific skill by ID."""
    skill = await repo.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")
    return SkillResponse.from_skill(skill)


@router.post("")
async def create_skill(
    body: SkillCreateRequest,
    user: User = Depends(get_current_user),
) -> SkillResponse:
    """Create a new local skill from markdown content."""
    service = get_skills_service()

    # Generate filename if not provided
    filename = body.filename
    if not filename:
        # Try to extract name from frontmatter
        match = re.match(r"^---\s*\n(.*?)\n---", body.content, re.DOTALL)
        if match:
            try:
                frontmatter = yaml.safe_load(match.group(1))
                name = frontmatter.get("name", "skill")
                filename = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".md"
            except Exception:
                filename = "new-skill.md"
        else:
            filename = "new-skill.md"

    # Sanitize filename to prevent path traversal
    base_name = filename.rsplit(".", 1)[0]
    base_name = re.sub(r"[^a-z0-9_-]+", "-", base_name.lower()).strip("-")
    if not base_name:
        base_name = "new-skill"

    # Create in user's .claude/skills directory
    # Create skill directory with SKILL.md inside
    skill_dir = USER_SKILLS_DIR / base_name
    counter = 1
    while skill_dir.exists():
        base = filename.rsplit(".", 1)[0]
        skill_dir = USER_SKILLS_DIR / f"{base}-{counter}"
        counter += 1

    skill_dir.mkdir(parents=True, exist_ok=True)
    filepath = skill_dir / "SKILL.md"

    # Write the file
    filepath.write_text(body.content, encoding="utf-8")

    # Parse and validate
    try:
        skill = service.parse_skill_file(filepath, SkillSource.LOCAL)
    except SkillParseError as e:
        # Clean up invalid file
        filepath.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail=str(e))

    # Save to database
    await repo.upsert_skill(skill)

    return SkillResponse.from_skill(skill)


@router.delete("/{skill_id}", status_code=204)
async def delete_skill(
    skill_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete a skill by ID."""
    skill = await repo.get_skill(skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    # Delete the file if it exists
    if skill.filepath:
        Path(skill.filepath).unlink(missing_ok=True)

    # Delete from database
    await repo.delete_skill(skill_id)


@router.post("/install")
async def install_skill(
    body: SkillInstallRequest,
    user: User = Depends(get_current_user),
) -> SkillResponse:
    """Install a skill from a URL."""
    service = get_skills_service()

    try:
        # Check if it's a skills.sh format (owner/repo)
        if "/" in body.url and not body.url.startswith("http"):
            skill = await service.install_from_skillssh(body.url)
        else:
            skill = await service.install_from_url(body.url)
    except SkillInstallError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return SkillResponse.from_skill(skill)


@router.post("/refresh")
async def refresh_skills(
    user: User = Depends(get_current_user),
) -> list[SkillResponse]:
    """Rescan local directories and sync skills to database."""
    service = get_skills_service()
    skills = await service.sync_skills_to_db()
    return [SkillResponse.from_skill(s) for s in skills]

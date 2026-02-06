"""
Skill Models for CachiBot

Pydantic models for skill definitions and bot skill activations.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class SkillSource(str, Enum):
    """Source of the skill definition."""

    LOCAL = "local"
    INSTALLED = "installed"


class SkillDefinition(BaseModel):
    """
    A skill definition loaded from a markdown file.

    Skills are markdown files with YAML frontmatter that provide
    instructions to inject into the agent's system prompt.
    """

    id: str
    name: str
    description: str
    version: str = "1.0.0"
    author: str | None = None
    tags: list[str] = Field(default_factory=list)
    requires_tools: list[str] = Field(default_factory=list)
    instructions: str
    source: SkillSource = SkillSource.LOCAL
    filepath: str | None = None


class BotSkillActivation(BaseModel):
    """Tracks which skills are activated for a specific bot."""

    bot_id: str
    skill_id: str
    enabled: bool = True
    activated_at: datetime


class SkillResponse(BaseModel):
    """Response model for skill API endpoints."""

    id: str
    name: str
    description: str
    version: str
    author: str | None
    tags: list[str]
    requires_tools: list[str] = Field(alias="requiresTools")
    instructions: str
    source: str
    filepath: str | None = None

    class Config:
        populate_by_name = True

    @classmethod
    def from_skill(cls, skill: SkillDefinition) -> "SkillResponse":
        """Create response from SkillDefinition."""
        return cls(
            id=skill.id,
            name=skill.name,
            description=skill.description,
            version=skill.version,
            author=skill.author,
            tags=skill.tags,
            requiresTools=skill.requires_tools,
            instructions=skill.instructions,
            source=skill.source.value,
            filepath=skill.filepath,
        )


class SkillInstallRequest(BaseModel):
    """Request to install a skill from URL."""

    url: str


class BotSkillRequest(BaseModel):
    """Request to activate/deactivate a skill for a bot."""

    skill_id: str = Field(alias="skillId")

    class Config:
        populate_by_name = True

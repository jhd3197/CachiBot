"""
Pydantic schemas for platform-wide tool visibility configuration.
"""

from pydantic import BaseModel


class PlatformToolConfig(BaseModel):
    """Current global tool visibility state."""

    disabled_capabilities: list[str] = []
    disabled_skills: list[str] = []


class PlatformToolConfigUpdate(BaseModel):
    """Partial update — only provided fields are applied."""

    disabled_capabilities: list[str] | None = None
    disabled_skills: list[str] | None = None

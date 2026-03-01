"""Artifact models for rich content rendering."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    """Supported artifact types with built-in renderers."""

    CODE = "code"
    HTML = "html"
    MARKDOWN = "markdown"
    SVG = "svg"
    MERMAID = "mermaid"
    REACT = "react"
    IMAGE = "image"
    CUSTOM = "custom"


class Artifact(BaseModel):
    """A structured content block rendered in a side panel alongside chat.

    Artifacts are the universal primitive that enables Canvas mode,
    Artifacts mode, HTML previews, and any other interactive content.
    """

    id: str = Field(description="Unique artifact ID (uuid)")
    type: ArtifactType = Field(description="Artifact type determining the renderer")
    title: str = Field(description="Display title for the artifact panel header")
    content: str = Field(description="The artifact content (code, HTML, markdown, etc.)")
    language: str | None = Field(
        default=None,
        description="Programming language for code artifacts (python, typescript, etc.)",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Type-specific metadata (e.g., editable, theme)",
    )
    plugin: str | None = Field(
        default=None,
        description="Source plugin name (for custom renderers)",
    )
    version: int = Field(
        default=1,
        description="Increments when artifact is updated by the agent",
    )
    message_id: str | None = Field(
        default=None,
        description="Associated chat message ID",
    )


class ArtifactUpdate(BaseModel):
    """Partial update to an existing artifact."""

    id: str = Field(description="Artifact ID to update")
    content: str | None = Field(default=None, description="New content")
    title: str | None = Field(default=None, description="New title")
    metadata: dict[str, Any] | None = Field(default=None, description="Metadata merge")
    version: int | None = Field(default=None, description="New version number")

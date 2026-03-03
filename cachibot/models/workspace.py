"""Workspace configuration models for plugin workspace mode."""

from __future__ import annotations

from pydantic import BaseModel


class WorkspaceConfig(BaseModel):
    """Configuration for a plugin's workspace mode.

    When a plugin declares workspace support, this config controls
    how the entire chat experience is reconfigured: custom system prompt,
    default artifact type, toolbar items, and visual accent.
    """

    display_name: str
    icon: str = "puzzle"
    description: str = ""
    system_prompt: str = ""
    default_artifact_type: str | None = None
    toolbar: list[str] = []
    auto_open_panel: bool = True
    accent_color: str = ""

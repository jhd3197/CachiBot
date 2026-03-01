"""
Pydantic models for external plugin manifests.

Validates plugin.toml files dropped into ~/.cachibot/plugins/<name>/.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class PluginUI(BaseModel):
    """Visual presentation hints for the frontend."""

    icon: str = "puzzle"
    color: str = "#6b7280"
    group: str = "External"


class PluginScope(BaseModel):
    """Where the plugin is available."""

    contexts: list[str] = Field(default_factory=lambda: ["chat"])


class PluginRequirementsManifest(BaseModel):
    """Runtime requirements declared by the plugin."""

    python: str = ">=3.10"
    filesystem: bool = False
    network: bool = False
    imports: list[str] = Field(default_factory=list)


class PluginPermissions(BaseModel):
    """Security permissions the plugin requests."""

    allow_env_vars: list[str] = Field(default_factory=list)
    allow_paths: list[str] = Field(default_factory=list)


class WorkspaceManifest(BaseModel):
    """Workspace mode configuration declared in plugin.toml [plugin.workspace]."""

    display_name: str = ""
    icon: str = "puzzle"
    description: str = ""
    system_prompt: str = ""
    default_artifact_type: str | None = None
    toolbar: list[str] = Field(default_factory=list)
    auto_open_panel: bool = True
    accent_color: str = ""


class ViewConfig(BaseModel):
    """Configuration for view-type plugins."""

    route: str
    nav_label: str
    nav_icon: str = "puzzle"


class PluginConfigParam(BaseModel):
    """A user-configurable parameter for the plugin."""

    name: str
    display_name: str = ""
    type: str = "text"
    default: str | int | float | bool | None = None
    description: str = ""


class ExternalPluginManifest(BaseModel):
    """Full parsed representation of a plugin.toml manifest."""

    # Identity
    name: str
    display_name: str = ""
    description: str = ""
    version: str = "0.1.0"
    author: str = ""
    type: str = "tool"  # "tool" or "view"

    # Sub-sections
    ui: PluginUI = Field(default_factory=PluginUI)
    scope: PluginScope = Field(default_factory=PluginScope)
    requires: PluginRequirementsManifest = Field(default_factory=PluginRequirementsManifest)
    permissions: PluginPermissions = Field(default_factory=PluginPermissions)
    view: ViewConfig | None = None
    workspace: WorkspaceManifest | None = None
    config: list[PluginConfigParam] = Field(default_factory=list)

    @property
    def capability_key(self) -> str:
        """The capability key used in bot capabilities dict (e.g. ext_website_builder)."""
        return f"ext_{self.name}"

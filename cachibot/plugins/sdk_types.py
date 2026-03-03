"""
Plugin SDK type stubs for IDE autocompletion.

Provides Protocol classes and type aliases so plugin authors get
rich IDE support when developing CachiBot plugins.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from tukuy.skills import Skill

from cachibot.models.artifact import Artifact
from cachibot.models.external_plugin import ExternalPluginManifest


@runtime_checkable
class PluginProtocol(Protocol):
    """Protocol describing what a well-typed CachiBot plugin looks like.

    Use this for type checking without inheriting from CachibotPlugin.
    """

    @property
    def name(self) -> str: ...

    @property
    def skills(self) -> dict[str, Skill]: ...

    async def on_install(self) -> None: ...

    async def on_uninstall(self) -> None: ...

    async def on_enable(self, bot_id: str) -> None: ...

    async def on_disable(self, bot_id: str) -> None: ...


@runtime_checkable
class ExternalPluginProtocol(PluginProtocol, Protocol):
    """Extended protocol for external plugins with manifest support."""

    @property
    def manifest(self) -> ExternalPluginManifest: ...


class SkillResult(Protocol):
    """Protocol for tool skill return values."""

    def __getitem__(self, key: str) -> Any: ...


# Type alias for the on_artifact callback
ArtifactCallback = Callable[[Artifact], Any]

# Type alias for the on_tool_output callback
ToolOutputCallback = Callable[[str, str], Any]

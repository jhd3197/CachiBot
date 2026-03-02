"""
Base classes for CachiBot's plugin system.

Built on Tukuy's TransformerPlugin, adapted for CachiBot's
workspace-scoped, capability-gated tool architecture.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tukuy import PythonSandbox
from tukuy.plugins.base import TransformerPlugin

from cachibot.config import Config

if TYPE_CHECKING:
    from cachibot.models.artifact import Artifact
    from cachibot.models.workspace import WorkspaceConfig


@dataclass
class PluginContext:
    """Runtime context shared with all plugins.

    Carries everything a plugin's skills need to operate:
    workspace config, sandbox, bot identity, per-tool settings,
    and multi-model slot configuration.
    """

    config: Config
    sandbox: PythonSandbox
    bot_id: str | None = None
    chat_id: str | None = None
    tool_configs: dict[str, Any] = field(default_factory=dict)
    bot_models: dict[str, Any] | None = None
    on_tool_output: Callable[[str, str], Any] | None = None
    on_artifact: Callable[["Artifact"], Any] | None = None


class CachibotPlugin(TransformerPlugin):  # type: ignore[misc]
    """Base class for CachiBot plugins.

    Subclasses expose skills (tool functions) but no transformers,
    since CachiBot uses Prompture's ToolRegistry for execution.
    """

    def __init__(self, name: str, ctx: PluginContext) -> None:
        super().__init__(name)
        self.ctx = ctx

    @property
    def transformers(self) -> dict[str, Callable[..., Any]]:
        """CachiBot plugins don't provide transformers."""
        return {}

    @property
    def workspace_config(self) -> "WorkspaceConfig | None":
        """Override to declare workspace mode support for this plugin."""
        return None

    # -- Lifecycle hooks (override in subclasses as needed) --

    async def on_install(self) -> None:
        """Called when the plugin is first installed (e.g. extracted from archive)."""

    async def on_uninstall(self) -> None:
        """Called before the plugin directory is removed from disk."""

    async def on_enable(self, bot_id: str) -> None:
        """Called when the plugin is enabled on a specific bot."""

    async def on_disable(self, bot_id: str) -> None:
        """Called when the plugin is disabled on a specific bot."""

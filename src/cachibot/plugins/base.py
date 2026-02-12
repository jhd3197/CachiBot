"""
Base classes for CachiBot's plugin system.

Built on Tukuy's TransformerPlugin, adapted for CachiBot's
workspace-scoped, capability-gated tool architecture.
"""

from dataclasses import dataclass, field
from typing import Any

from tukuy import PythonSandbox
from tukuy.plugins.base import TransformerPlugin

from cachibot.config import Config


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
    tool_configs: dict[str, Any] = field(default_factory=dict)
    bot_models: dict | None = None


class CachibotPlugin(TransformerPlugin):
    """Base class for CachiBot plugins.

    Subclasses expose skills (tool functions) but no transformers,
    since CachiBot uses Prompture's ToolRegistry for execution.
    """

    def __init__(self, name: str, ctx: PluginContext) -> None:
        super().__init__(name)
        self.ctx = ctx

    @property
    def transformers(self) -> dict[str, callable]:
        """CachiBot plugins don't provide transformers."""
        return {}

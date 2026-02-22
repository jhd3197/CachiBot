"""
Plugin Manager Service

Bridges Tukuy plugins to Prompture's ToolRegistry, gated by bot capabilities.
Includes both CachiBot custom plugins and Tukuy's built-in plugins
(scoped via SecurityContext), and Tukuy instruction packs.
"""

from __future__ import annotations

import logging
from typing import Any

from prompture import ToolRegistry
from tukuy.plugins.base import TransformerPlugin
from tukuy.plugins.compression import CompressionPlugin
from tukuy.plugins.git import GitPlugin
from tukuy.plugins.http import HttpPlugin
from tukuy.plugins.instructions import (
    AnalysisInstructionPack,
    DeveloperInstructionPack,
    WritingInstructionPack,
)
from tukuy.plugins.shell import ShellPlugin
from tukuy.plugins.sql import SqlPlugin
from tukuy.plugins.web import WebPlugin

from cachibot.plugins import (
    AudioGenerationPlugin,
    CachibotPlugin,
    FileOpsPlugin,
    ImageGenerationPlugin,
    InstructionManagementPlugin,
    JobToolsPlugin,
    KnowledgePlugin,
    NotesPlugin,
    PlatformPlugin,
    PluginContext,
    PythonSandboxPlugin,
    TaskPlugin,
    WorkManagementPlugin,
)

logger = logging.getLogger(__name__)

# Type alias: plugins can be CachiBot custom or Tukuy built-in
PluginClass = type[CachibotPlugin] | type[TransformerPlugin]

# Mapping of capability names to plugin classes they gate
CAPABILITY_PLUGINS: dict[str, list[PluginClass]] = {
    "fileOperations": [FileOpsPlugin],
    "codeExecution": [PythonSandboxPlugin],
    "gitOperations": [GitPlugin],
    "shellAccess": [ShellPlugin],
    "webAccess": [WebPlugin, HttpPlugin],
    "dataOperations": [SqlPlugin, CompressionPlugin],
    "connections": [PlatformPlugin],
    "workManagement": [WorkManagementPlugin, JobToolsPlugin],
    "imageGeneration": [ImageGenerationPlugin],
    "audioGeneration": [AudioGenerationPlugin],
    "instructions": [
        AnalysisInstructionPack,
        WritingInstructionPack,
        DeveloperInstructionPack,
        InstructionManagementPlugin,
    ],
}

# Plugins that are always enabled regardless of capabilities
ALWAYS_ENABLED: list[PluginClass] = [TaskPlugin, NotesPlugin, KnowledgePlugin]


def plugins_to_registry(
    plugins: list[CachibotPlugin | TransformerPlugin],
    *,
    skill_config: dict[str, Any] | None = None,
) -> ToolRegistry:
    """Bridge Tukuy skills and instructions to a Prompture ToolRegistry.

    Registers all skills from each plugin. For plugins that also expose
    instructions (LLM-powered tools), those are registered too with the
    provided skill_config (which carries ``llm_backend`` for instructions).

    Args:
        plugins: Instantiated plugins (CachiBot custom or Tukuy built-in)
        skill_config: Optional config dict injected as SkillContext into
            instruction calls.  Should contain ``llm_backend`` key.

    Returns:
        Populated ToolRegistry
    """
    registry = ToolRegistry()
    for plugin in plugins:
        for _name, skill_obj in plugin.skills.items():
            registry.add_tukuy_skill(skill_obj, config=skill_config)
        # Also register instructions (LLM-powered tools)
        for _name, instr_obj in plugin.instructions.items():
            registry.add_tukuy_skill(instr_obj, config=skill_config)
    return registry


def build_registry(
    ctx: PluginContext,
    capabilities: dict[str, bool] | None = None,
    disabled_capabilities: set[str] | None = None,
    *,
    skill_config: dict[str, Any] | None = None,
) -> ToolRegistry:
    """Build a ToolRegistry from capabilities and plugin context.

    Args:
        ctx: Plugin runtime context (config, sandbox, bot_id, tool_configs)
        capabilities: Dict of capability name -> bool.
            None means legacy/CLI mode (all plugins enabled).
        disabled_capabilities: Set of capability keys globally disabled by
            the platform admin.  These are excluded even if the bot has
            them enabled.
        skill_config: Optional config dict injected as SkillContext into
            instruction/skill calls.  Should contain ``llm_backend`` key
            for instruction execution.

    Returns:
        ToolRegistry with tools from enabled plugins
    """
    plugins = _instantiate_plugins(ctx, capabilities, disabled_capabilities)
    return plugins_to_registry(plugins, skill_config=skill_config)


def get_enabled_plugins(
    ctx: PluginContext,
    capabilities: dict[str, bool] | None = None,
    disabled_capabilities: set[str] | None = None,
) -> list[CachibotPlugin | TransformerPlugin]:
    """Get the list of instantiated plugins for given capabilities.

    Useful for introspection (e.g. the /api/plugins endpoint).

    Args:
        ctx: Plugin runtime context
        capabilities: Dict of capability name -> bool, or None for all
        disabled_capabilities: Set of globally disabled capability keys

    Returns:
        List of instantiated plugin objects
    """
    return _instantiate_plugins(ctx, capabilities, disabled_capabilities)


def _instantiate_plugins(
    ctx: PluginContext,
    capabilities: dict[str, bool] | None,
    disabled_capabilities: set[str] | None = None,
) -> list[CachibotPlugin | TransformerPlugin]:
    """Instantiate the correct set of plugins based on capabilities."""
    globally_disabled = disabled_capabilities or set()
    plugin_classes: list[PluginClass] = list(ALWAYS_ENABLED)

    if capabilities is None:
        # Legacy/CLI mode: all plugins enabled (except globally disabled)
        for cap_name, classes in CAPABILITY_PLUGINS.items():
            if cap_name not in globally_disabled:
                plugin_classes.extend(classes)
    else:
        for cap_name, classes in CAPABILITY_PLUGINS.items():
            if cap_name in globally_disabled:
                continue
            if capabilities.get(cap_name, False):
                plugin_classes.extend(classes)

    # Deduplicate while preserving order
    seen: set[PluginClass] = set()
    unique: list[PluginClass] = []
    for cls in plugin_classes:
        if cls not in seen:
            seen.add(cls)
            unique.append(cls)

    result: list[CachibotPlugin | TransformerPlugin] = []
    for cls in unique:
        if issubclass(cls, CachibotPlugin):
            result.append(cls(ctx))  # type: ignore[arg-type, call-arg]
        else:
            # Tukuy built-in plugin: no context needed, SecurityContext handles scoping
            result.append(cls())  # type: ignore[call-arg]
    return result

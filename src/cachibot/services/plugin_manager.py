"""
Plugin Manager Service

Bridges Tukuy plugins to Prompture's ToolRegistry, gated by bot capabilities.
Includes both CachiBot custom plugins and Tukuy's built-in plugins
(scoped via SecurityContext).
"""

from __future__ import annotations

from prompture import ToolRegistry
from tukuy.plugins.base import TransformerPlugin
from tukuy.plugins.compression import CompressionPlugin
from tukuy.plugins.git import GitPlugin
from tukuy.plugins.http import HttpPlugin
from tukuy.plugins.shell import ShellPlugin
from tukuy.plugins.sql import SqlPlugin
from tukuy.plugins.web import WebPlugin

from cachibot.plugins import (
    AudioGenerationPlugin,
    CachibotPlugin,
    FileOpsPlugin,
    ImageGenerationPlugin,
    KnowledgePlugin,
    NotesPlugin,
    PlatformPlugin,
    PluginContext,
    PythonSandboxPlugin,
    TaskPlugin,
    WorkManagementPlugin,
)

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
    "workManagement": [WorkManagementPlugin],
    "imageGeneration": [ImageGenerationPlugin],
    "audioGeneration": [AudioGenerationPlugin],
}

# Plugins that are always enabled regardless of capabilities
ALWAYS_ENABLED: list[PluginClass] = [TaskPlugin, NotesPlugin, KnowledgePlugin]


def plugins_to_registry(
    plugins: list[CachibotPlugin | TransformerPlugin],
) -> ToolRegistry:
    """Bridge Tukuy skills to a Prompture ToolRegistry.

    Each skill's underlying function is registered directly,
    since Prompture infers name/description from the callable.

    Args:
        plugins: Instantiated plugins (CachiBot custom or Tukuy built-in)

    Returns:
        Populated ToolRegistry
    """
    registry = ToolRegistry()
    for plugin in plugins:
        for _name, skill_obj in plugin.skills.items():
            registry.add_tukuy_skill(skill_obj)
    return registry


def build_registry(
    ctx: PluginContext,
    capabilities: dict | None = None,
) -> ToolRegistry:
    """Build a ToolRegistry from capabilities and plugin context.

    Args:
        ctx: Plugin runtime context (config, sandbox, bot_id, tool_configs)
        capabilities: Dict of capability name -> bool.
            None means legacy/CLI mode (all plugins enabled).

    Returns:
        ToolRegistry with tools from enabled plugins
    """
    plugins = _instantiate_plugins(ctx, capabilities)
    return plugins_to_registry(plugins)


def get_enabled_plugins(
    ctx: PluginContext,
    capabilities: dict | None = None,
) -> list[CachibotPlugin | TransformerPlugin]:
    """Get the list of instantiated plugins for given capabilities.

    Useful for introspection (e.g. the /api/plugins endpoint).

    Args:
        ctx: Plugin runtime context
        capabilities: Dict of capability name -> bool, or None for all

    Returns:
        List of instantiated plugin objects
    """
    return _instantiate_plugins(ctx, capabilities)


def _instantiate_plugins(
    ctx: PluginContext,
    capabilities: dict | None,
) -> list[CachibotPlugin | TransformerPlugin]:
    """Instantiate the correct set of plugins based on capabilities."""
    plugin_classes: list[PluginClass] = list(ALWAYS_ENABLED)

    if capabilities is None:
        # Legacy/CLI mode: all plugins enabled
        for classes in CAPABILITY_PLUGINS.values():
            plugin_classes.extend(classes)
    else:
        for cap_name, classes in CAPABILITY_PLUGINS.items():
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
            result.append(cls(ctx))
        else:
            # Tukuy built-in plugin: no context needed, SecurityContext handles scoping
            result.append(cls())
    return result

"""
Plugin Manager Service

Bridges Tukuy plugins to Prompture's ToolRegistry, gated by bot capabilities.
"""

from __future__ import annotations

from prompture import ToolRegistry

from cachibot.plugins import (
    CachibotPlugin,
    FileOpsPlugin,
    PlatformPlugin,
    PluginContext,
    PythonSandboxPlugin,
    TaskPlugin,
    WorkManagementPlugin,
)

# Mapping of capability names to plugin classes they gate
CAPABILITY_PLUGINS: dict[str, list[type[CachibotPlugin]]] = {
    "fileOperations": [FileOpsPlugin],
    "codeExecution": [PythonSandboxPlugin],
    "connections": [PlatformPlugin],
    "workManagement": [WorkManagementPlugin],
}

# Plugins that are always enabled regardless of capabilities
ALWAYS_ENABLED: list[type[CachibotPlugin]] = [TaskPlugin]


def plugins_to_registry(plugins: list[CachibotPlugin]) -> ToolRegistry:
    """Bridge Tukuy skills to a Prompture ToolRegistry.

    Each skill's underlying function is registered directly,
    since Prompture infers name/description from the callable.

    Args:
        plugins: Instantiated CachiBot plugins

    Returns:
        Populated ToolRegistry
    """
    registry = ToolRegistry()
    for plugin in plugins:
        for _name, skill_obj in plugin.skills.items():
            registry.register(skill_obj.fn)
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
) -> list[CachibotPlugin]:
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
) -> list[CachibotPlugin]:
    """Instantiate the correct set of plugins based on capabilities."""
    plugin_classes: list[type[CachibotPlugin]] = list(ALWAYS_ENABLED)

    if capabilities is None:
        # Legacy/CLI mode: all plugins enabled
        for classes in CAPABILITY_PLUGINS.values():
            plugin_classes.extend(classes)
    else:
        for cap_name, classes in CAPABILITY_PLUGINS.items():
            if capabilities.get(cap_name, False):
                plugin_classes.extend(classes)

    # Deduplicate while preserving order
    seen: set[type[CachibotPlugin]] = set()
    unique: list[type[CachibotPlugin]] = []
    for cls in plugin_classes:
        if cls not in seen:
            seen.add(cls)
            unique.append(cls)

    return [cls(ctx) for cls in unique]

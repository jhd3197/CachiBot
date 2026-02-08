"""
Plugin introspection endpoints.

Allows the frontend to discover available plugins and their skills.
"""

from fastapi import APIRouter

from cachibot.plugins import CACHIBOT_PLUGINS
from cachibot.services.plugin_manager import ALWAYS_ENABLED, CAPABILITY_PLUGINS

router = APIRouter()


@router.get("/api/plugins")
async def list_plugins():
    """List all available plugins with their skills and capability mapping."""
    # Build reverse map: plugin class -> capability name
    plugin_to_cap: dict[str, str | None] = {}
    for cap_name, classes in CAPABILITY_PLUGINS.items():
        for cls in classes:
            plugin_to_cap[cls.__name__] = cap_name
    for cls in ALWAYS_ENABLED:
        plugin_to_cap[cls.__name__] = None  # always enabled

    result = []
    for name, cls in CACHIBOT_PLUGINS.items():
        # Instantiate with a minimal context to introspect skills
        # We only need the skill metadata, not actual execution
        cap = plugin_to_cap.get(cls.__name__)
        result.append(
            {
                "name": name,
                "class": cls.__name__,
                "capability": cap,
                "alwaysEnabled": cap is None,
                "skills": _get_plugin_skill_names(cls),
            }
        )

    return {"plugins": result}


@router.get("/api/plugins/{name}/skills")
async def get_plugin_skills(name: str):
    """Get skill metadata for a specific plugin."""
    cls = CACHIBOT_PLUGINS.get(name)
    if not cls:
        return {"error": f"Plugin '{name}' not found"}

    # Create a dummy context for introspection
    from prompture import PythonSandbox

    from cachibot.config import Config
    from cachibot.plugins.base import PluginContext

    config = Config()
    sandbox = PythonSandbox(
        allowed_imports=[],
        timeout_seconds=1,
        allowed_read_paths=[],
        allowed_write_paths=[],
    )
    ctx = PluginContext(config=config, sandbox=sandbox)

    try:
        plugin = cls(ctx)
        skills = []
        for skill_name, skill_obj in plugin.skills.items():
            desc = skill_obj.descriptor
            skills.append(
                {
                    "name": skill_name,
                    "description": desc.description,
                    "category": desc.category,
                    "tags": desc.tags,
                    "version": desc.version,
                    "isAsync": desc.is_async,
                    "idempotent": desc.idempotent,
                    "sideEffects": desc.side_effects,
                    "requiresNetwork": desc.requires_network,
                    "requiresFilesystem": desc.requires_filesystem,
                }
            )
        return {"plugin": name, "skills": skills}
    except Exception as e:
        return {"error": f"Failed to inspect plugin '{name}': {e}"}


def _get_plugin_skill_names(cls: type) -> list[str]:
    """Get skill names from a plugin class without full instantiation.

    Falls back to class-level introspection if possible.
    """
    # We need to instantiate to get skills; use a minimal context
    try:
        from prompture import PythonSandbox

        from cachibot.config import Config
        from cachibot.plugins.base import PluginContext

        config = Config()
        sandbox = PythonSandbox(
            allowed_imports=[],
            timeout_seconds=1,
            allowed_read_paths=[],
            allowed_write_paths=[],
        )
        ctx = PluginContext(config=config, sandbox=sandbox)
        plugin = cls(ctx)
        return list(plugin.skills.keys())
    except Exception:
        return []

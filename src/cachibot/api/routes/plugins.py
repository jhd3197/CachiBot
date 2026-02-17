"""
Plugin introspection endpoints.

Allows the frontend to discover available plugins and their skills.
Respects the global PlatformToolConfig — plugins whose capability is
globally disabled are omitted from the response.
"""

from fastapi import APIRouter

from cachibot.plugins import CACHIBOT_PLUGINS
from cachibot.plugins.base import CachibotPlugin
from cachibot.services.plugin_manager import ALWAYS_ENABLED, CAPABILITY_PLUGINS
from cachibot.storage.repository import PlatformToolConfigRepository

router = APIRouter()

_platform_repo = PlatformToolConfigRepository()


@router.get("/api/plugins")
async def list_plugins():
    """List all available plugins with their skills and capability mapping."""
    disabled_caps = set(await _platform_repo.get_disabled_capabilities())

    # Build reverse map: plugin class -> capability name
    plugin_to_cap: dict[str, str | None] = {}
    for cap_name, classes in CAPABILITY_PLUGINS.items():
        for cls in classes:
            plugin_to_cap[cls.__name__] = cap_name
    for cls in ALWAYS_ENABLED:
        plugin_to_cap[cls.__name__] = None  # always enabled

    result = []
    for name, cls in CACHIBOT_PLUGINS.items():
        cap = plugin_to_cap.get(cls.__name__)

        # Skip plugins whose capability is globally disabled
        if cap and cap in disabled_caps:
            continue

        plugin_data: dict = {
            "name": name,
            "class": cls.__name__,
            "capability": cap,
            "alwaysEnabled": cap is None,
            "skills": _get_plugin_skills_metadata(cls),
        }

        # Include manifest metadata if available
        try:
            instance = _instantiate_for_introspection(cls)
            manifest = instance.manifest
            plugin_data["displayName"] = manifest.display_name
            plugin_data["icon"] = manifest.icon
            plugin_data["color"] = manifest.color
            plugin_data["group"] = manifest.group
        except Exception:
            plugin_data["displayName"] = name
            plugin_data["icon"] = None
            plugin_data["color"] = None
            plugin_data["group"] = None

        result.append(plugin_data)

    return {"plugins": result}


@router.get("/api/plugins/{name}/skills")
async def get_plugin_skills(name: str):
    """Get skill metadata for a specific plugin."""
    cls = CACHIBOT_PLUGINS.get(name)
    if not cls:
        return {"error": f"Plugin '{name}' not found"}

    try:
        plugin = _instantiate_for_introspection(cls)
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
                    "displayName": desc.resolved_display_name,
                    "icon": desc.icon,
                    "riskLevel": desc.resolved_risk_level.value,
                    "group": desc.group,
                    "configParams": [p.to_dict() for p in desc.config_params]
                    if desc.config_params
                    else [],
                    "hidden": desc.hidden,
                    "deprecated": desc.deprecated,
                }
            )
        return {"plugin": name, "skills": skills}
    except Exception as e:
        return {"error": f"Failed to inspect plugin '{name}': {e}"}


def _instantiate_for_introspection(cls: type):
    """Instantiate a plugin for metadata introspection.

    CachiBot custom plugins need a PluginContext; Tukuy built-in plugins don't.
    """
    if issubclass(cls, CachibotPlugin):
        from tukuy import PythonSandbox

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
        return cls(ctx)
    else:
        # Tukuy built-in plugin: no context needed
        return cls()


def _get_plugin_skills_metadata(cls: type) -> list[dict]:
    """Get full skill metadata from a plugin class."""
    try:
        plugin = _instantiate_for_introspection(cls)
        skills = []
        for skill_name, skill_obj in plugin.skills.items():
            desc = skill_obj.descriptor
            skill_data: dict = {
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
                # New metadata from Tukuy
                "displayName": desc.resolved_display_name,
                "icon": desc.icon,
                "riskLevel": desc.resolved_risk_level.value,
                "group": desc.group,
                "configParams": [p.to_dict() for p in desc.config_params]
                if desc.config_params
                else [],
                "hidden": desc.hidden,
                "deprecated": desc.deprecated,
            }
            skills.append(skill_data)
        return skills
    except Exception:
        return []

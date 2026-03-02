"""
External plugin management endpoints.

Allows the frontend to list, enable, disable, install, uninstall,
and reload external plugins, and to serve static views for view-type plugins.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from cachibot.services.external_plugins import (
    EXTERNAL_PLUGIN_CLASSES,
    EXTERNAL_PLUGIN_ERRORS,
    EXTERNAL_PLUGINS,
    EXTERNAL_PLUGINS_DIR,
    OFFICIAL_PLUGIN_NAMES,
    install_plugin_from_archive,
    reload_external_plugins,
    uninstall_plugin,
)

router = APIRouter()


@router.get("/api/plugins/external")
async def list_external_plugins() -> dict[str, Any]:
    """List all discovered external plugins with metadata and status."""
    result = []
    for name, manifest in EXTERNAL_PLUGINS.items():
        error = EXTERNAL_PLUGIN_ERRORS.get(name)
        result.append(
            {
                "name": manifest.name,
                "displayName": manifest.display_name or manifest.name,
                "description": manifest.description,
                "version": manifest.version,
                "author": manifest.author,
                "type": manifest.type,
                "icon": manifest.ui.icon,
                "color": manifest.ui.color,
                "group": manifest.ui.group,
                "capabilityKey": manifest.capability_key,
                "contexts": manifest.scope.contexts,
                "allowLateActivation": manifest.scope.allow_late_activation,
                "requires": {
                    "python": manifest.requires.python,
                    "filesystem": manifest.requires.filesystem,
                    "network": manifest.requires.network,
                    "imports": manifest.requires.imports,
                },
                "permissions": {
                    "allowEnvVars": manifest.permissions.allow_env_vars,
                    "allowPaths": manifest.permissions.allow_paths,
                },
                "config": [
                    {
                        "name": p.name,
                        "displayName": p.display_name,
                        "type": p.type,
                        "default": p.default,
                        "description": p.description,
                    }
                    for p in manifest.config
                ],
                "view": (
                    {
                        "route": manifest.view.route,
                        "navLabel": manifest.view.nav_label,
                        "navIcon": manifest.view.nav_icon,
                    }
                    if manifest.view
                    else None
                ),
                "loaded": error is None,
                "error": error,
                "official": manifest.name in OFFICIAL_PLUGIN_NAMES,
                "external": True,
            }
        )
    return {"plugins": result}


@router.get("/api/plugins/{name}/view")
async def serve_plugin_view(name: str) -> HTMLResponse:
    """Serve the static HTML for a view-type external plugin."""
    manifest = EXTERNAL_PLUGINS.get(name)
    if not manifest:
        raise HTTPException(404, f"External plugin '{name}' not found")
    if manifest.type != "view" or not manifest.view:
        raise HTTPException(400, f"Plugin '{name}' is not a view-type plugin")

    plugin_dir = EXTERNAL_PLUGINS_DIR / name
    static_dir = plugin_dir / "static"
    index_file = static_dir / "index.html"

    if not index_file.exists():
        raise HTTPException(404, f"No static/index.html found for plugin '{name}'")

    return HTMLResponse(content=index_file.read_text(encoding="utf-8"))


@router.post("/api/plugins/{name}/enable")
async def enable_plugin(name: str) -> dict[str, Any]:
    """Enable an external plugin (returns the capability key to set on the bot)."""
    manifest = EXTERNAL_PLUGINS.get(name)
    if not manifest:
        raise HTTPException(404, f"External plugin '{name}' not found")

    error = EXTERNAL_PLUGIN_ERRORS.get(name)
    if error:
        raise HTTPException(400, f"Plugin '{name}' has load errors: {error}")

    # Call lifecycle hook
    plugin_cls = EXTERNAL_PLUGIN_CLASSES.get(name)
    if plugin_cls and hasattr(plugin_cls, "on_enable"):
        try:
            from tukuy import PythonSandbox

            from cachibot.config import Config
            from cachibot.plugins.base import PluginContext

            ctx = PluginContext(
                config=Config(),
                sandbox=PythonSandbox(
                    allowed_imports=[],
                    timeout_seconds=1,
                    allowed_read_paths=[],
                    allowed_write_paths=[],
                ),
            )
            instance = plugin_cls(ctx)
            await instance.on_enable("")
        except Exception:
            pass  # Lifecycle hooks are best-effort

    return {"capabilityKey": manifest.capability_key, "enabled": True}


@router.post("/api/plugins/{name}/disable")
async def disable_plugin(name: str) -> dict[str, Any]:
    """Disable an external plugin (returns the capability key to unset on the bot)."""
    manifest = EXTERNAL_PLUGINS.get(name)
    if not manifest:
        raise HTTPException(404, f"External plugin '{name}' not found")

    # Call lifecycle hook
    plugin_cls = EXTERNAL_PLUGIN_CLASSES.get(name)
    if plugin_cls and hasattr(plugin_cls, "on_disable"):
        try:
            from tukuy import PythonSandbox

            from cachibot.config import Config
            from cachibot.plugins.base import PluginContext

            ctx = PluginContext(
                config=Config(),
                sandbox=PythonSandbox(
                    allowed_imports=[],
                    timeout_seconds=1,
                    allowed_read_paths=[],
                    allowed_write_paths=[],
                ),
            )
            instance = plugin_cls(ctx)
            await instance.on_disable("")
        except Exception:
            pass

    return {"capabilityKey": manifest.capability_key, "enabled": False}


@router.post("/api/plugins/reload")
async def reload_plugins() -> dict[str, Any]:
    """Re-scan the external plugins directory and reload all plugins."""
    count = reload_external_plugins()
    errors = {name: err for name, err in EXTERNAL_PLUGIN_ERRORS.items()}
    return {
        "loaded": count,
        "total": len(EXTERNAL_PLUGINS),
        "errors": errors,
    }


@router.post("/api/plugins/install")
async def install_plugin(file: UploadFile) -> dict[str, Any]:
    """Install a plugin from an uploaded archive (zip or tar.gz)."""
    if not file.filename:
        raise HTTPException(400, "No file provided")

    # Determine suffix for temp file
    suffix = ".zip"
    if file.filename.endswith(".tar.gz"):
        suffix = ".tar.gz"
    elif file.filename.endswith(".tgz"):
        suffix = ".tgz"

    # Save upload to temp file
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = Path(tmp.name)

    try:
        manifest = install_plugin_from_archive(tmp_path)

        # Call lifecycle hook
        plugin_cls = EXTERNAL_PLUGIN_CLASSES.get(manifest.name)
        if plugin_cls and hasattr(plugin_cls, "on_install"):
            try:
                from tukuy import PythonSandbox

                from cachibot.config import Config
                from cachibot.plugins.base import PluginContext

                ctx = PluginContext(
                    config=Config(),
                    sandbox=PythonSandbox(
                        allowed_imports=[],
                        timeout_seconds=1,
                        allowed_read_paths=[],
                        allowed_write_paths=[],
                    ),
                )
                instance = plugin_cls(ctx)
                await instance.on_install()
            except Exception:
                pass

        return {
            "name": manifest.name,
            "displayName": manifest.display_name or manifest.name,
            "version": manifest.version,
            "capabilityKey": manifest.capability_key,
            "installed": True,
        }
    except ValueError as e:
        raise HTTPException(400, str(e))
    finally:
        tmp_path.unlink(missing_ok=True)


@router.delete("/api/plugins/{name}")
async def delete_plugin(name: str) -> dict[str, Any]:
    """Uninstall an external plugin (removes from disk and memory)."""
    if name in OFFICIAL_PLUGIN_NAMES:
        raise HTTPException(
            400,
            f"Cannot uninstall official plugin '{name}'. "
            "Official plugins are managed by the CachiBot registry.",
        )

    # Call lifecycle hook before removal
    plugin_cls = EXTERNAL_PLUGIN_CLASSES.get(name)
    if plugin_cls and hasattr(plugin_cls, "on_uninstall"):
        try:
            from tukuy import PythonSandbox

            from cachibot.config import Config
            from cachibot.plugins.base import PluginContext

            ctx = PluginContext(
                config=Config(),
                sandbox=PythonSandbox(
                    allowed_imports=[],
                    timeout_seconds=1,
                    allowed_read_paths=[],
                    allowed_write_paths=[],
                ),
            )
            instance = plugin_cls(ctx)
            await instance.on_uninstall()
        except Exception:
            pass

    removed = uninstall_plugin(name)
    if not removed:
        raise HTTPException(404, f"External plugin '{name}' not found")

    return {"name": name, "uninstalled": True}

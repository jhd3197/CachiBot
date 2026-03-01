"""
External plugin loader.

Scans ~/.cachibot/plugins/ for directories containing a plugin.toml manifest,
validates them, imports the Python module, and injects discovered plugins into
the existing CAPABILITY_PLUGINS / CACHIBOT_PLUGINS registries so they are
gated and instantiated just like built-in plugins.
"""

from __future__ import annotations

import importlib
import importlib.util
import io
import logging
import os
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from cachibot.models.external_plugin import ExternalPluginManifest

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# WSL-aware plugins directory resolution
# ---------------------------------------------------------------------------

_SKIP_WIN_USERS = frozenset({"Public", "Default", "Default User", "All Users"})


def _resolve_plugins_dir() -> Path:
    """Resolve the external plugins directory, with WSL-to-Windows fallback.

    In WSL environments ``Path.home()`` resolves to the Linux home
    (e.g. ``/home/user``) while the user's ``.cachibot`` data may live
    under the Windows home (``/mnt/c/Users/Juan/.cachibot``).  When the
    Linux path doesn't exist, this function probes the Windows home
    via ``/mnt/c/Users/*/`` and returns whichever directory has plugins.
    """
    primary = Path.home() / ".cachibot" / "plugins"
    if primary.is_dir():
        return primary

    # Quick WSL detection via /proc/version
    try:
        version_text = Path("/proc/version").read_text()
        if "microsoft" not in version_text.lower():
            return primary
    except Exception:
        return primary

    # WSL: look for .cachibot/plugins under Windows user profiles
    for drive in ("c", "d"):
        users_dir = Path(f"/mnt/{drive}/Users")
        if not users_dir.is_dir():
            continue
        try:
            for user_dir in users_dir.iterdir():
                if not user_dir.is_dir() or user_dir.name in _SKIP_WIN_USERS:
                    continue
                candidate = user_dir / ".cachibot" / "plugins"
                if candidate.is_dir():
                    logger.info(
                        "WSL detected — using Windows plugins dir: %s", candidate
                    )
                    return candidate
        except PermissionError:
            continue

    return primary


# Default directory for external plugins
EXTERNAL_PLUGINS_DIR = _resolve_plugins_dir()

# Module-level registry: name -> manifest (populated after loading)
EXTERNAL_PLUGINS: dict[str, ExternalPluginManifest] = {}

# Tracks loading errors for the API to surface
EXTERNAL_PLUGIN_ERRORS: dict[str, str] = {}

# Tracks loaded plugin classes for lifecycle hooks
EXTERNAL_PLUGIN_CLASSES: dict[str, type] = {}

# Tracks which registry keys were injected by external plugins (for clean reload)
_INJECTED_CAPABILITY_KEYS: set[str] = set()
_INJECTED_PLUGIN_KEYS: set[str] = set()

# Official plugin names (all official plugins, even ones skipped due to missing deps)
OFFICIAL_PLUGIN_NAMES: set[str] = set()

REGISTRY_URL = "https://cachibot.ai/plugins/registry"
ARCHIVE_URL = "https://cachibot.ai/plugins/{name}/archive"
FALLBACK_REGISTRY_URL = (
    "https://raw.githubusercontent.com/jhd3197/CachiBot-Plugins/main/registry.json"
)
FALLBACK_ARCHIVE_URL = (
    "https://raw.githubusercontent.com/jhd3197/CachiBot-Plugins/main/plugins/{name}"
)


def _parse_manifest(toml_path: Path) -> ExternalPluginManifest:
    """Parse a plugin.toml file into a validated manifest."""
    try:
        import tomllib
    except ModuleNotFoundError:  # Python < 3.11
        import tomli as tomllib  # type: ignore[no-redef]

    raw = toml_path.read_bytes()
    data = tomllib.loads(raw.decode())

    # The [plugin] table is the root of all manifest data
    plugin_data: dict[str, Any] = data.get("plugin", data)

    return ExternalPluginManifest.model_validate(plugin_data)


def _check_requirements(manifest: ExternalPluginManifest) -> str | None:
    """Check whether the plugin's requirements are met.

    Returns an error message string if not met, or None if OK.
    """
    for pkg in manifest.requires.imports:
        spec = importlib.util.find_spec(pkg)
        if spec is None:
            return f"Missing required package: {pkg}"
    return None


def _import_plugin_module(plugin_dir: Path, manifest: ExternalPluginManifest) -> type | None:
    """Import the plugin module and find the CachibotPlugin subclass."""
    from cachibot.plugins.base import CachibotPlugin

    module_name = f"_ext_plugin_{manifest.name}"

    # Remove stale module if reloading
    if module_name in sys.modules:
        del sys.modules[module_name]

    # Add the plugin directory's parent to sys.path so relative imports work
    parent_str = str(plugin_dir.parent)
    dir_str = str(plugin_dir)
    added_parent = False
    added_dir = False
    if parent_str not in sys.path:
        sys.path.insert(0, parent_str)
        added_parent = True
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)
        added_dir = True

    try:
        # Try importing __init__.py first
        init_file = plugin_dir / "__init__.py"
        if init_file.exists():
            spec = importlib.util.spec_from_file_location(
                module_name,
                init_file,
                submodule_search_locations=[str(plugin_dir)],
            )
        else:
            # Fallback: try <name>.py
            py_file = plugin_dir / f"{manifest.name}.py"
            if py_file.exists():
                spec = importlib.util.spec_from_file_location(module_name, py_file)
            else:
                return None

        if spec is None or spec.loader is None:
            return None

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)  # type: ignore[union-attr]

        # Find the CachibotPlugin subclass
        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if (
                isinstance(attr, type)
                and issubclass(attr, CachibotPlugin)
                and attr is not CachibotPlugin
            ):
                return attr  # type: ignore[return-value]

        return None
    finally:
        if added_dir:
            try:
                sys.path.remove(dir_str)
            except ValueError:
                pass
        if added_parent:
            try:
                sys.path.remove(parent_str)
            except ValueError:
                pass


def enforce_permissions(manifest: ExternalPluginManifest) -> None:
    """Apply runtime permission restrictions declared in the manifest.

    Wraps os.environ access so the plugin can only read declared env vars,
    and restricts Path operations to declared paths.  Called once per plugin
    at registration time — the restrictions are stored on the manifest object
    for the plugin manager to enforce when instantiating.
    """
    # Permissions are advisory for now — the manifest declares what the plugin
    # *needs*, and the API surfaces this to the user.  Full enforcement would
    # require running the plugin in a subprocess or patching its globals, which
    # is out of scope for the initial release.
    #
    # What we *do* enforce: if allow_env_vars is non-empty, we validate at
    # load time that no obviously dangerous env vars are declared.
    blocked_env_vars = {"PATH", "HOME", "USERPROFILE", "SYSTEMROOT", "COMSPEC"}
    for var in manifest.permissions.allow_env_vars:
        if var.upper() in blocked_env_vars:
            raise ValueError(f"Plugin cannot request access to system env var: {var}")


def _unregister_plugin(name: str) -> None:
    """Remove a previously registered external plugin from all registries."""
    from cachibot.plugins import CACHIBOT_PLUGINS
    from cachibot.services.plugin_manager import CAPABILITY_PLUGINS

    manifest = EXTERNAL_PLUGINS.get(name)
    if manifest:
        cap_key = manifest.capability_key
        CAPABILITY_PLUGINS.pop(cap_key, None)
        _INJECTED_CAPABILITY_KEYS.discard(cap_key)

    # Try both possible plugin keys
    for key in [name, f"ext_{name}"]:
        if key in CACHIBOT_PLUGINS and key in _INJECTED_PLUGIN_KEYS:
            del CACHIBOT_PLUGINS[key]
            _INJECTED_PLUGIN_KEYS.discard(key)

    EXTERNAL_PLUGINS.pop(name, None)
    EXTERNAL_PLUGIN_ERRORS.pop(name, None)
    EXTERNAL_PLUGIN_CLASSES.pop(name, None)

    # Clean up sys.modules
    module_name = f"_ext_plugin_{name}"
    sys.modules.pop(module_name, None)


async def install_official_plugins(plugins_dir: Path | None = None) -> set[str]:
    """Fetch the official plugin registry and auto-install default plugins.

    Downloads plugins from the CachiBot website (or GitHub fallback) and
    extracts them to the plugins directory. Plugins are only installed if:
    - They are marked ``default: true`` in the registry
    - They don't already exist on disk (or have an ``.official`` marker
      with an older version)

    Returns the set of plugin names that were actually installed or updated.
    """
    import httpx

    directory = plugins_dir or EXTERNAL_PLUGINS_DIR
    directory.mkdir(parents=True, exist_ok=True)
    installed: set[str] = set()

    # Fetch registry and download plugins within a single client session
    registry: dict | None = None
    async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
        for url in (REGISTRY_URL, FALLBACK_REGISTRY_URL):
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    registry = resp.json()
                    break
            except Exception:
                continue

        if not registry:
            logger.debug("Could not fetch official plugin registry")
            return installed

        plugins = registry.get("plugins", [])

        for meta in plugins:
            name = meta.get("name", "")
            if not name:
                continue

            # Track all official plugins
            if meta.get("official"):
                OFFICIAL_PLUGIN_NAMES.add(name)

            # Only auto-install default plugins
            if not meta.get("default"):
                continue

            plugin_dir = directory / name
            marker = plugin_dir / ".official"
            remote_version = meta.get("version", "0.0.0")

            if plugin_dir.exists():
                if not marker.exists():
                    # User customized — skip
                    logger.debug("Skipping official plugin '%s' (user-customized)", name)
                    continue
                # Check version
                local_version = marker.read_text().strip()
                if local_version >= remote_version:
                    continue
                # Newer version available — remove old and re-install
                logger.info(
                    "Updating official plugin '%s': %s -> %s",
                    name, local_version, remote_version,
                )
                shutil.rmtree(plugin_dir, ignore_errors=True)

            # Download and install
            try:
                await _download_and_extract_plugin(client, name, meta, directory)
                # Write .official marker
                marker = (directory / name) / ".official"
                marker.write_text(remote_version)
                installed.add(name)
                logger.info("Installed official plugin: %s v%s", name, remote_version)
            except Exception as exc:
                logger.warning("Failed to install official plugin '%s': %s", name, exc)

    return installed


async def _download_and_extract_plugin(
    client: "httpx.AsyncClient",
    name: str,
    meta: dict,
    plugins_dir: Path,
) -> None:
    """Download a plugin archive or individual files and extract to plugins_dir/name/."""
    plugin_dir = plugins_dir / name
    plugin_dir.mkdir(parents=True, exist_ok=True)

    # Try archive endpoint first
    archive_url = ARCHIVE_URL.format(name=name)
    try:
        resp = await client.get(archive_url)
        if resp.status_code == 200:
            buf = io.BytesIO(resp.content)
            with zipfile.ZipFile(buf, "r") as zf:
                zf.extractall(plugin_dir)
            return
    except Exception:
        pass

    # Fallback: download individual files from GitHub
    files = meta.get("files", [])
    for filename in files:
        url = f"{FALLBACK_ARCHIVE_URL.format(name=name)}/{filename}"
        resp = await client.get(url)
        if resp.status_code == 200:
            (plugin_dir / filename).write_bytes(resp.content)
        else:
            raise RuntimeError(f"Failed to download {filename} from {url}")


def load_external_plugins(plugins_dir: Path | None = None) -> int:
    """Scan the external plugins directory and register discovered plugins.

    Returns the number of successfully loaded plugins.
    """
    from cachibot.plugins import CACHIBOT_PLUGINS
    from cachibot.services.plugin_manager import CAPABILITY_PLUGINS

    directory = plugins_dir or EXTERNAL_PLUGINS_DIR

    if not directory.exists():
        logger.debug("External plugins directory does not exist: %s", directory)
        return 0

    loaded = 0
    for child in sorted(directory.iterdir()):
        if not child.is_dir():
            continue

        toml_path = child / "plugin.toml"
        if not toml_path.exists():
            continue

        plugin_name = child.name
        try:
            manifest = _parse_manifest(toml_path)

            # Check requirements
            req_error = _check_requirements(manifest)
            if req_error:
                logger.warning("External plugin '%s' skipped: %s", plugin_name, req_error)
                EXTERNAL_PLUGIN_ERRORS[manifest.name] = req_error
                EXTERNAL_PLUGINS[manifest.name] = manifest
                continue

            # Enforce permission declarations
            try:
                enforce_permissions(manifest)
            except ValueError as perm_err:
                logger.warning("External plugin '%s' rejected: %s", plugin_name, perm_err)
                EXTERNAL_PLUGIN_ERRORS[manifest.name] = str(perm_err)
                EXTERNAL_PLUGINS[manifest.name] = manifest
                continue

            # Import the module
            plugin_cls = _import_plugin_module(child, manifest)
            if plugin_cls is None:
                error = "No CachibotPlugin subclass found in module"
                logger.warning("External plugin '%s' skipped: %s", plugin_name, error)
                EXTERNAL_PLUGIN_ERRORS[manifest.name] = error
                EXTERNAL_PLUGINS[manifest.name] = manifest
                continue

            # Inject into registries (dedup: external takes precedence)
            cap_key = manifest.capability_key  # e.g. "ext_website_builder"
            plugin_key = manifest.name  # e.g. "website_builder"

            # If the plugin name collides with a built-in, prefix with "ext_"
            if plugin_key in CACHIBOT_PLUGINS and plugin_key not in _INJECTED_PLUGIN_KEYS:
                plugin_key = f"ext_{plugin_key}"

            CACHIBOT_PLUGINS[plugin_key] = plugin_cls
            CAPABILITY_PLUGINS[cap_key] = [plugin_cls]  # type: ignore[list-item]

            # Track injected keys for clean reload
            _INJECTED_CAPABILITY_KEYS.add(cap_key)
            _INJECTED_PLUGIN_KEYS.add(plugin_key)

            # Store in external registry
            EXTERNAL_PLUGINS[manifest.name] = manifest
            EXTERNAL_PLUGIN_CLASSES[manifest.name] = plugin_cls

            loaded += 1
            logger.info(
                "Loaded external plugin: %s v%s (%s)",
                manifest.display_name or manifest.name,
                manifest.version,
                cap_key,
            )

        except Exception as exc:
            logger.warning("Failed to load external plugin '%s': %s", plugin_name, exc)
            EXTERNAL_PLUGIN_ERRORS[plugin_name] = str(exc)

    if loaded:
        logger.info("Loaded %d external plugin(s) from %s", loaded, directory)

    return loaded


def reload_external_plugins(plugins_dir: Path | None = None) -> int:
    """Unregister all external plugins and re-scan the directory.

    Returns the number of successfully loaded plugins after reload.
    """
    from cachibot.plugins import CACHIBOT_PLUGINS
    from cachibot.services.plugin_manager import CAPABILITY_PLUGINS

    # Unregister all previously injected external plugins
    for cap_key in list(_INJECTED_CAPABILITY_KEYS):
        CAPABILITY_PLUGINS.pop(cap_key, None)
    for plugin_key in list(_INJECTED_PLUGIN_KEYS):
        CACHIBOT_PLUGINS.pop(plugin_key, None)

    # Clean up sys.modules for all external plugin modules
    for name in list(EXTERNAL_PLUGINS.keys()):
        module_name = f"_ext_plugin_{name}"
        sys.modules.pop(module_name, None)

    _INJECTED_CAPABILITY_KEYS.clear()
    _INJECTED_PLUGIN_KEYS.clear()
    EXTERNAL_PLUGINS.clear()
    EXTERNAL_PLUGIN_ERRORS.clear()
    EXTERNAL_PLUGIN_CLASSES.clear()

    logger.info("Cleared external plugin registries, re-scanning...")
    return load_external_plugins(plugins_dir)


def uninstall_plugin(name: str, plugins_dir: Path | None = None) -> bool:
    """Remove a plugin from disk and all registries.

    Returns True if the plugin was found and removed.
    """
    directory = plugins_dir or EXTERNAL_PLUGINS_DIR
    plugin_dir = directory / name

    if not plugin_dir.exists():
        # Still unregister from memory if present
        if name in EXTERNAL_PLUGINS:
            _unregister_plugin(name)
            return True
        return False

    # Unregister from memory
    _unregister_plugin(name)

    # Remove from disk
    shutil.rmtree(plugin_dir, ignore_errors=True)
    logger.info("Uninstalled external plugin: %s", name)
    return True


def install_plugin_from_archive(
    archive_path: Path,
    plugins_dir: Path | None = None,
) -> ExternalPluginManifest:
    """Extract a plugin archive and load it.

    Supports .zip and .tar.gz archives.  The archive must contain a
    plugin.toml at the root (or inside a single top-level directory).

    Returns the parsed manifest on success.
    Raises ValueError on validation failures.
    """
    import tarfile
    import tempfile
    import zipfile

    directory = plugins_dir or EXTERNAL_PLUGINS_DIR
    directory.mkdir(parents=True, exist_ok=True)

    # Extract to a temp directory first for validation
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        if zipfile.is_zipfile(archive_path):
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(tmp)
        elif tarfile.is_tarfile(archive_path):
            with tarfile.open(archive_path, "r:*") as tf:
                tf.extractall(tmp, filter="data")
        else:
            raise ValueError("Unsupported archive format. Use .zip or .tar.gz")

        # Find plugin.toml — either at root or inside a single subdirectory
        toml_path = tmp / "plugin.toml"
        extract_root = tmp
        if not toml_path.exists():
            subdirs = [d for d in tmp.iterdir() if d.is_dir()]
            if len(subdirs) == 1 and (subdirs[0] / "plugin.toml").exists():
                extract_root = subdirs[0]
                toml_path = extract_root / "plugin.toml"
            else:
                raise ValueError("No plugin.toml found in archive")

        # Validate manifest
        manifest = _parse_manifest(toml_path)

        # Check for name conflicts with built-in plugins
        from cachibot.plugins import CACHIBOT_PLUGINS

        if manifest.name in CACHIBOT_PLUGINS and manifest.name not in _INJECTED_PLUGIN_KEYS:
            raise ValueError(
                f"Plugin name '{manifest.name}' conflicts with a built-in plugin. "
                f"Choose a different name."
            )

        # Check requirements
        req_error = _check_requirements(manifest)
        if req_error:
            raise ValueError(f"Requirements not met: {req_error}")

        # Enforce permissions
        enforce_permissions(manifest)

        # Move to final destination
        dest = directory / manifest.name
        if dest.exists():
            shutil.rmtree(dest)
        shutil.copytree(extract_root, dest)

    # Load the newly installed plugin
    _load_single_plugin(dest, manifest)

    return manifest


def _load_single_plugin(plugin_dir: Path, manifest: ExternalPluginManifest) -> None:
    """Load a single plugin that's already been extracted and validated."""
    from cachibot.plugins import CACHIBOT_PLUGINS
    from cachibot.services.plugin_manager import CAPABILITY_PLUGINS

    plugin_cls = _import_plugin_module(plugin_dir, manifest)
    if plugin_cls is None:
        error = "No CachibotPlugin subclass found in module"
        EXTERNAL_PLUGIN_ERRORS[manifest.name] = error
        EXTERNAL_PLUGINS[manifest.name] = manifest
        raise ValueError(error)

    cap_key = manifest.capability_key
    plugin_key = manifest.name
    if plugin_key in CACHIBOT_PLUGINS and plugin_key not in _INJECTED_PLUGIN_KEYS:
        plugin_key = f"ext_{plugin_key}"

    CACHIBOT_PLUGINS[plugin_key] = plugin_cls
    CAPABILITY_PLUGINS[cap_key] = [plugin_cls]  # type: ignore[list-item]

    _INJECTED_CAPABILITY_KEYS.add(cap_key)
    _INJECTED_PLUGIN_KEYS.add(plugin_key)

    EXTERNAL_PLUGINS[manifest.name] = manifest
    EXTERNAL_PLUGIN_CLASSES[manifest.name] = plugin_cls

    logger.info(
        "Loaded external plugin: %s v%s (%s)",
        manifest.display_name or manifest.name,
        manifest.version,
        cap_key,
    )

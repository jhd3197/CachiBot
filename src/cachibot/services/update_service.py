"""Update service for checking and applying CachiBot updates."""

import asyncio
import json
import logging
import os
import sys
import time
import urllib.request
from dataclasses import dataclass
from typing import Any

from packaging.version import Version

from cachibot import __version__
from cachibot.models.update import UpdateCheckResponse, UpdatePerformResponse

logger = logging.getLogger(__name__)

# In-memory cache
CACHE_TTL = 3600  # 1 hour


@dataclass
class _UpdateCache:
    result: UpdateCheckResponse | None = None
    timestamp: float = 0.0


_cache = _UpdateCache()


def _is_docker() -> bool:
    """Detect if running inside a Docker container."""
    if os.path.exists("/.dockerenv"):
        return True
    for var in ("DOCKER_CONTAINER", "DOCKER", "container"):
        if os.environ.get(var):
            return True
    return False


def _fetch_pypi_json() -> dict[str, Any]:
    """Fetch package info from PyPI (blocking)."""
    url = "https://pypi.org/pypi/cachibot/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 — hardcoded HTTPS URL
        result: dict[str, Any] = json.loads(resp.read().decode())
        return result


def _fetch_github_release_notes(version: str) -> tuple[str | None, str | None]:
    """Fetch release notes from GitHub (blocking). Returns (body, published_at)."""
    url = f"https://api.github.com/repos/jhd3197/cachibot/releases/tags/v{version}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310 — hardcoded HTTPS URL
            data = json.loads(resp.read().decode())
            return data.get("body"), data.get("published_at")
    except Exception:
        return None, None


def _check_updates_sync() -> UpdateCheckResponse:
    """Synchronous update check (runs in thread)."""
    current = Version(__version__)
    is_docker = _is_docker()

    try:
        pypi_data = _fetch_pypi_json()
    except Exception as exc:
        logger.warning("Failed to fetch PyPI data: %s", exc)
        return UpdateCheckResponse(
            current_version=__version__,
            is_docker=is_docker,
        )

    # Find latest stable and latest pre-release
    all_versions: list[Version] = []
    for v_str in pypi_data.get("releases", {}):
        try:
            all_versions.append(Version(v_str))
        except Exception:
            continue

    stable_versions = [v for v in all_versions if not v.is_prerelease and not v.is_devrelease]
    pre_versions = [v for v in all_versions if v.is_prerelease or v.is_devrelease]

    latest_stable = max(stable_versions) if stable_versions else None
    latest_pre = max(pre_versions) if pre_versions else None

    # Determine target version for release notes
    target = latest_stable
    update_available = latest_stable is not None and latest_stable > current
    prerelease_available = latest_pre is not None and latest_pre > current
    if latest_pre and (not latest_stable or latest_pre > latest_stable):
        prerelease_available = True

    # Fetch release notes for the latest stable
    release_notes = None
    published_at = None
    release_url = None
    if target:
        release_notes, published_at = _fetch_github_release_notes(str(target))
        release_url = f"https://github.com/jhd3197/cachibot/releases/tag/v{target}"

    return UpdateCheckResponse(
        current_version=__version__,
        latest_stable=str(latest_stable) if latest_stable else None,
        latest_prerelease=str(latest_pre) if latest_pre else None,
        update_available=update_available,
        prerelease_available=prerelease_available,
        release_notes=release_notes,
        release_url=release_url,
        published_at=published_at,
        is_docker=is_docker,
    )


async def check_for_updates(force: bool = False) -> UpdateCheckResponse:
    """Check PyPI for available updates. Cached for 1 hour unless force=True."""
    now = time.time()
    if not force and _cache.result and (now - _cache.timestamp) < CACHE_TTL:
        return _cache.result

    result = await asyncio.to_thread(_check_updates_sync)
    _cache.result = result
    _cache.timestamp = time.time()
    return result


async def perform_update(
    target_version: str | None = None,
    include_prerelease: bool = False,
) -> UpdatePerformResponse:
    """Install a specific version of cachibot via pip."""
    if _is_docker():
        return UpdatePerformResponse(
            success=False,
            old_version=__version__,
            new_version=__version__,
            message="Cannot auto-update inside Docker. Rebuild the container instead.",
        )

    # Determine target
    if not target_version:
        info = await check_for_updates(force=True)
        if include_prerelease and info.latest_prerelease:
            target_version = info.latest_prerelease
        elif info.latest_stable:
            target_version = info.latest_stable
        else:
            return UpdatePerformResponse(
                success=False,
                old_version=__version__,
                new_version=__version__,
                message="No update available.",
            )

    install_spec = f"cachibot=={target_version}"
    cmd = [sys.executable, "-m", "pip", "install", install_spec]

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        stdout, _ = await proc.communicate()
        pip_output = stdout.decode(errors="replace") if stdout else ""

        if proc.returncode == 0:
            # Invalidate cache
            _cache.result = None
            _cache.timestamp = 0.0

            return UpdatePerformResponse(
                success=True,
                old_version=__version__,
                new_version=target_version,
                message=f"Successfully installed CachiBot {target_version}.",
                restart_required=True,
                pip_output=pip_output,
            )
        else:
            return UpdatePerformResponse(
                success=False,
                old_version=__version__,
                new_version=__version__,
                message=f"pip install failed (exit code {proc.returncode}).",
                pip_output=pip_output,
            )
    except Exception as exc:
        return UpdatePerformResponse(
            success=False,
            old_version=__version__,
            new_version=__version__,
            message=f"Update failed: {exc}",
        )


async def restart_server(host: str, port: int) -> None:
    """Spawn a new cachibot server process and schedule shutdown of the current one."""
    cmd = [sys.executable, "-m", "cachibot", "server", "--host", host, "--port", str(port)]

    kwargs: dict[str, Any] = {}
    if sys.platform == "win32":
        kwargs["creationflags"] = 0x00000200 | 0x00000008  # NEW_PROCESS_GROUP | DETACHED
    else:
        kwargs["start_new_session"] = True

    await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        **kwargs,
    )

    # Schedule graceful shutdown after a short delay so the HTTP response can be sent
    async def _delayed_exit() -> None:
        await asyncio.sleep(2)
        os._exit(0)

    asyncio.create_task(_delayed_exit())

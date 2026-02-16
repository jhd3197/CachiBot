"""Update service for checking and applying CachiBot updates.

Handles version checking, safe installation with Windows corruption prevention,
post-install verification, retry logic, and rollback on failure.
"""

import asyncio
import importlib
import json
import logging
import os
import shutil
import site
import sys
import tempfile
import textwrap
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from packaging.version import Version

from cachibot import __version__
from cachibot.models.update import UpdateCheckResponse, UpdatePerformResponse

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CACHE_TTL = 3600  # 1 hour
_PKG_NAME = "cachibot"
_MAX_RETRIES = 3
_RETRY_BACKOFF = 2.0  # seconds, doubles each attempt
_LAST_GOOD_FILE = Path.home() / ".cachibot" / "last_good_version"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


@dataclass
class _UpdateCache:
    result: UpdateCheckResponse | None = None
    timestamp: float = 0.0


_cache = _UpdateCache()

# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------


def _is_docker() -> bool:
    """Detect if running inside a Docker container."""
    if os.path.exists("/.dockerenv"):
        return True
    for var in ("DOCKER_CONTAINER", "DOCKER", "container"):
        if os.environ.get(var):
            return True
    return False


def _is_venv() -> bool:
    """Detect if running inside a virtual environment."""
    return hasattr(sys, "real_prefix") or (
        hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix
    )


def _python_info() -> dict[str, Any]:
    """Gather Python environment diagnostics."""
    return {
        "version": sys.version,
        "executable": sys.executable,
        "platform": sys.platform,
        "prefix": sys.prefix,
        "base_prefix": getattr(sys, "base_prefix", sys.prefix),
        "is_venv": _is_venv(),
    }


# ---------------------------------------------------------------------------
# Site-packages helpers
# ---------------------------------------------------------------------------


def _get_site_packages_dirs() -> list[Path]:
    """Return all site-packages directories for the current interpreter."""
    dirs: list[Path] = []
    for d in site.getsitepackages():
        p = Path(d)
        if p.is_dir():
            dirs.append(p)
    # Also include the user site-packages
    user = site.getusersitepackages()
    if isinstance(user, str):
        p = Path(user)
        if p.is_dir():
            dirs.append(p)
    return dirs


@dataclass
class CorruptionReport:
    """Result of scanning site-packages for corrupted files."""

    corrupted_dirs: list[str] = field(default_factory=list)
    corrupted_dists: list[str] = field(default_factory=list)
    is_corrupted: bool = False
    details: str = ""


def detect_corruption() -> CorruptionReport:
    """Scan site-packages for corrupted (tilde-prefixed) cachibot directories.

    On Windows, interrupted pip installs leave directories like ``~achibot``
    or ``~achibot-0.2.23.dist-info`` that prevent the package from loading.
    """
    report = CorruptionReport()
    for sp_dir in _get_site_packages_dirs():
        for item in sp_dir.iterdir():
            name = item.name
            # Detect ~-prefixed remnants of cachibot
            if name.startswith("~") and "achibot" in name.lower():
                if item.is_dir():
                    report.corrupted_dirs.append(str(item))
                else:
                    report.corrupted_dists.append(str(item))

    if report.corrupted_dirs or report.corrupted_dists:
        report.is_corrupted = True
        all_items = report.corrupted_dirs + report.corrupted_dists
        report.details = (
            f"Found {len(all_items)} corrupted package artifact(s) in site-packages: "
            + ", ".join(Path(p).name for p in all_items)
            + ". This is caused by an interrupted pip install on Windows. "
            "Run 'cachibot repair' to fix."
        )

    return report


def cleanup_corrupted_packages() -> list[str]:
    """Remove tilde-prefixed corrupted cachibot directories from site-packages.

    Returns list of paths that were removed.
    """
    removed: list[str] = []
    for sp_dir in _get_site_packages_dirs():
        for item in sp_dir.iterdir():
            name = item.name
            if name.startswith("~") and "achibot" in name.lower():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                    removed.append(str(item))
                    logger.info("Removed corrupted artifact: %s", item)
                except OSError as exc:
                    logger.warning("Could not remove %s: %s", item, exc)
    return removed


# ---------------------------------------------------------------------------
# Installation verification
# ---------------------------------------------------------------------------


def verify_installation(expected_version: str | None = None) -> tuple[bool, str]:
    """Verify that cachibot is importable and (optionally) at the expected version.

    Returns ``(ok, detail_message)``.
    """
    # Force Python to rescan packages
    importlib.invalidate_caches()

    try:
        # Use a fresh metadata lookup — don't trust the cached __version__
        from importlib.metadata import distribution

        dist = distribution(_PKG_NAME)
        installed_version = dist.version
    except Exception as exc:
        return False, f"Cannot load {_PKG_NAME} metadata: {exc}"

    if expected_version and installed_version != expected_version:
        return False, (f"Version mismatch: expected {expected_version}, got {installed_version}")

    # Smoke-test critical submodules
    critical_modules = [
        "cachibot.agent",
        "cachibot.api.server",
        "cachibot.cli",
    ]
    for mod_name in critical_modules:
        try:
            importlib.import_module(mod_name)
        except Exception as exc:
            return False, f"Failed to import {mod_name}: {exc}"

    return True, f"CachiBot {installed_version} verified OK"


# ---------------------------------------------------------------------------
# Last-known-good version tracking  (P3 rollback)
# ---------------------------------------------------------------------------


def _save_good_version(version: str) -> None:
    """Persist the current working version for rollback purposes."""
    try:
        _LAST_GOOD_FILE.parent.mkdir(parents=True, exist_ok=True)
        _LAST_GOOD_FILE.write_text(version)
    except OSError:
        pass


def _load_good_version() -> str | None:
    """Read the last-known-good version, or None."""
    try:
        return _LAST_GOOD_FILE.read_text().strip() or None
    except OSError:
        return None


# ---------------------------------------------------------------------------
# PyPI helpers  (unchanged)
# ---------------------------------------------------------------------------


def _fetch_pypi_json() -> dict[str, Any]:
    """Fetch package info from PyPI (blocking)."""
    url = "https://pypi.org/pypi/cachibot/json"
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
        result: dict[str, Any] = json.loads(resp.read().decode())
        return result


def _fetch_github_release_notes(version: str) -> tuple[str | None, str | None]:
    """Fetch release notes from GitHub (blocking). Returns (body, published_at)."""
    url = f"https://api.github.com/repos/jhd3197/cachibot/releases/tags/v{version}"
    req = urllib.request.Request(url, headers={"Accept": "application/vnd.github.v3+json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec B310
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


# ---------------------------------------------------------------------------
# pip install with retry + Windows safety  (P0 + P2)
# ---------------------------------------------------------------------------


async def _pip_install(
    install_spec: str,
    *,
    force: bool = False,
) -> tuple[int, str]:
    """Run pip install and return (returncode, combined_output).

    On Windows, automatically adds ``--force-reinstall --no-cache-dir`` to
    work around NTFS file-locking issues that cause ``~``-prefixed corruption.
    """
    cmd = [sys.executable, "-m", "pip", "install", install_spec]

    if sys.platform == "win32" or force:
        cmd.extend(["--force-reinstall", "--no-cache-dir"])

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    stdout, _ = await proc.communicate()
    output = stdout.decode(errors="replace") if stdout else ""
    return proc.returncode or 0, output


async def _pip_install_with_retry(
    install_spec: str,
    *,
    max_retries: int = _MAX_RETRIES,
    force: bool = False,
) -> tuple[int, str]:
    """Run pip install with exponential-backoff retry on failure.

    Returns (returncode, combined_output) from the last attempt.
    """
    last_rc = 1
    last_output = ""
    backoff = _RETRY_BACKOFF

    for attempt in range(1, max_retries + 1):
        logger.info("pip install attempt %d/%d: %s", attempt, max_retries, install_spec)
        last_rc, last_output = await _pip_install(install_spec, force=force)

        if last_rc == 0:
            return last_rc, last_output

        if attempt < max_retries:
            logger.warning("pip install failed (exit %d), retrying in %.1fs...", last_rc, backoff)
            # Clean up any corruption left by the failed attempt before retrying
            await asyncio.to_thread(cleanup_corrupted_packages)
            await asyncio.sleep(backoff)
            backoff *= 2

    return last_rc, last_output


# ---------------------------------------------------------------------------
# Core update operation  (P0 rewrite)
# ---------------------------------------------------------------------------


async def perform_update(
    target_version: str | None = None,
    include_prerelease: bool = False,
) -> UpdatePerformResponse:
    """Install a specific version of cachibot via pip.

    The update flow is:
      1. Block if Docker.
      2. Resolve target version from PyPI if not specified.
      3. Save current version as last-known-good (for rollback).
      4. Clean corrupted artifacts from previous failed installs.
      5. Run ``pip install`` with retry + Windows-safe flags.
      6. Verify the new installation is importable.
      7. On verification failure, attempt rollback to previous version.
    """
    if _is_docker():
        return UpdatePerformResponse(
            success=False,
            old_version=__version__,
            new_version=__version__,
            message="Cannot auto-update inside Docker. Rebuild the container instead.",
        )

    # --- 1. Resolve target ---------------------------------------------------
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

    # --- 2. Save current version for rollback ---------------------------------
    _save_good_version(__version__)

    # --- 3. Pre-install cleanup -----------------------------------------------
    removed = await asyncio.to_thread(cleanup_corrupted_packages)
    if removed:
        logger.info("Pre-install cleanup removed %d corrupted artifact(s)", len(removed))

    # --- 4. Install with retry ------------------------------------------------
    install_spec = f"{_PKG_NAME}=={target_version}"
    rc, pip_output = await _pip_install_with_retry(install_spec)

    if rc != 0:
        return UpdatePerformResponse(
            success=False,
            old_version=__version__,
            new_version=__version__,
            message=f"pip install failed after {_MAX_RETRIES} attempt(s) (exit code {rc}).",
            pip_output=pip_output,
        )

    # --- 5. Post-install cleanup (catch any new ~-prefixed dirs) --------------
    await asyncio.to_thread(cleanup_corrupted_packages)

    # --- 6. Verify installation -----------------------------------------------
    ok, detail = await asyncio.to_thread(verify_installation, target_version)
    if not ok:
        logger.error("Post-install verification failed: %s", detail)

        # --- 7. Rollback on failure -------------------------------------------
        rollback_version = _load_good_version()
        rollback_msg = ""
        if rollback_version and rollback_version != target_version:
            logger.info("Attempting rollback to %s", rollback_version)
            rb_spec = f"{_PKG_NAME}=={rollback_version}"
            rb_rc, rb_out = await _pip_install(rb_spec, force=True)
            if rb_rc == 0:
                rollback_msg = f" Rolled back to {rollback_version}."
            else:
                rollback_msg = (
                    f" Rollback to {rollback_version} also failed. "
                    "Run 'cachibot repair' to fix the installation."
                )

        return UpdatePerformResponse(
            success=False,
            old_version=__version__,
            new_version=__version__,
            message=f"Verification failed after install: {detail}.{rollback_msg}",
            pip_output=pip_output,
        )

    # --- Success! -------------------------------------------------------------
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


# ---------------------------------------------------------------------------
# Server restart  (P0 — external updater on Windows)
# ---------------------------------------------------------------------------

# Template for the external updater script used on Windows.
# This script runs as a detached process:
#   1. Waits for the old server (by PID) to exit.
#   2. Cleans corrupted artifacts.
#   3. Starts the new server.
_WIN_UPDATER_TEMPLATE = textwrap.dedent("""\
    \"\"\"CachiBot external updater — launched by the server before it exits.\"\"\"
    import os, sys, time, shutil, subprocess
    from pathlib import Path

    OLD_PID = {old_pid}
    SERVER_CMD = {server_cmd!r}
    SITE_PACKAGES = {site_packages!r}

    def pid_alive(pid):
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    # Wait up to 30s for old process to die
    for _ in range(60):
        if not pid_alive(OLD_PID):
            break
        time.sleep(0.5)

    # Clean corrupted ~-prefixed dirs
    sp = Path(SITE_PACKAGES)
    if sp.is_dir():
        for item in sp.iterdir():
            if item.name.startswith("~") and "achibot" in item.name.lower():
                try:
                    if item.is_dir():
                        shutil.rmtree(item)
                    else:
                        item.unlink()
                except OSError:
                    pass

    # Start the new server (detached)
    flags = 0x00000200 | 0x00000008  # CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS
    subprocess.Popen(
        SERVER_CMD,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )
""")


async def restart_server(host: str, port: int) -> None:
    """Spawn a new cachibot server process and schedule shutdown of the current one.

    On Windows an external updater script is used so the old process fully
    releases file locks before the new server starts.
    """
    server_cmd = [
        sys.executable,
        "-m",
        "cachibot",
        "server",
        "--host",
        host,
        "--port",
        str(port),
    ]

    if sys.platform == "win32":
        # Write an external updater script that waits for us to die, cleans up,
        # then spawns the new server.
        sp_dirs = _get_site_packages_dirs()
        sp_path = str(sp_dirs[0]) if sp_dirs else ""

        script = _WIN_UPDATER_TEMPLATE.format(
            old_pid=os.getpid(),
            server_cmd=server_cmd,
            site_packages=sp_path,
        )
        tmp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", prefix="cachibot_updater_", delete=False
        )
        tmp.write(script)
        tmp.close()

        await asyncio.create_subprocess_exec(
            sys.executable,
            tmp.name,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            creationflags=0x00000200 | 0x00000008,  # DETACHED
        )
    else:
        # Unix: just spawn the new server in a new session
        await asyncio.create_subprocess_exec(
            *server_cmd,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            start_new_session=True,
        )

    # Schedule graceful shutdown after a short delay so the HTTP response can be sent
    async def _delayed_exit() -> None:
        await asyncio.sleep(2)
        os._exit(0)

    asyncio.create_task(_delayed_exit())


# ---------------------------------------------------------------------------
# Repair (called from CLI)
# ---------------------------------------------------------------------------


async def repair_installation() -> tuple[bool, str]:
    """Detect corruption, clean up, and force-reinstall the current version.

    Returns ``(success, detail_message)``.
    """
    lines: list[str] = []

    # Step 1 — detect
    report = detect_corruption()
    if report.is_corrupted:
        lines.append(f"Corruption detected: {report.details}")
    else:
        lines.append("No corruption detected.")

    # Step 2 — cleanup
    removed = cleanup_corrupted_packages()
    if removed:
        lines.append(f"Removed {len(removed)} corrupted artifact(s).")

    # Step 3 — force reinstall current version
    install_spec = f"{_PKG_NAME}=={__version__}"
    rc, pip_output = await _pip_install(install_spec, force=True)
    if rc != 0:
        lines.append(f"pip install failed (exit {rc}). Output:\n{pip_output}")
        return False, "\n".join(lines)

    # Step 4 — post-install cleanup
    cleanup_corrupted_packages()

    # Step 5 — verify
    ok, detail = verify_installation(__version__)
    lines.append(detail)

    if ok:
        _save_good_version(__version__)

    return ok, "\n".join(lines)

"""Docker probe: is a usable Docker daemon available on this machine?

Finds the ``docker`` CLI (PATH first, then the usual Docker Desktop
locations), then asks the daemon for its version with a short timeout. The
CLI is invoked with no overrides, so a user's ``DOCKER_HOST`` /
``DOCKER_CONTEXT`` environment (Linux socket, Windows named pipe
``npipe:////./pipe/docker_engine``, Docker Desktop's macOS socket) is
respected exactly as any other docker command would respect it.

The result is cached briefly; callers that need a fresh answer (the global
status endpoint, the startup reconcile) pass ``force=True``.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import time
from collections.abc import Callable
from pathlib import Path

from cachibot.models.computer import DockerProbeResult
from cachibot.services.computer.runner import (
    CommandResult,
    DockerCommandTimeoutError,
    DockerRunner,
)

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 10.0
CACHE_SECONDS = 15.0

_WINDOWS_CLI = Path(r"C:\Program Files\Docker\Docker\resources\bin\docker.exe")
_MACOS_CANDIDATES = (
    Path("/Applications/Docker.app/Contents/Resources/bin/docker"),
    Path("/usr/local/bin/docker"),
    Path("/opt/homebrew/bin/docker"),
)
_LINUX_CANDIDATES = (
    Path("/usr/bin/docker"),
    Path("/usr/local/bin/docker"),
    Path("/bin/docker"),
)


def default_cli_candidates() -> list[Path]:
    """Platform-specific fallback locations checked when PATH has no docker."""
    system = platform.system()
    if system == "Windows":
        program_files = os.environ.get("ProgramFiles", r"C:\Program Files")
        return [Path(program_files) / "Docker" / "Docker" / "resources" / "bin" / "docker.exe"]
    if system == "Darwin":
        return list(_MACOS_CANDIDATES)
    return list(_LINUX_CANDIDATES)


def find_docker_cli(
    candidates: list[Path] | None = None,
    which: Callable[[str], str | None] = shutil.which,
    isfile: Callable[[Path], bool] = os.path.isfile,
) -> str | None:
    """Locate the docker CLI: PATH first, then known install locations.

    ``which``/``isfile`` are injectable so tests can exercise Windows and
    macOS discovery from any host. On Windows a file check suffices (every
    file is "executable" there).
    """
    found = which("docker")
    if found:
        return found
    for candidate in candidates if candidates is not None else default_cli_candidates():
        try:
            if isfile(candidate):
                return str(candidate)
        except OSError:
            continue
    return None


def _classify_failure(result: CommandResult) -> str:
    """Turn a failed ``docker version`` into a plain-language reason."""
    blob = f"{result.stderr}\n{result.stdout}".lower()
    if "permission denied" in blob or "access is denied" in blob:
        return (
            "permission denied — add your user to the docker group (or check Docker Desktop access)"
        )
    if (
        "cannot connect" in blob
        or "is the docker daemon running" in blob
        or "error during connect" in blob
        or "pipe docker_engine" in blob
        or "the docker client must be run with elevated privileges" in blob
    ):
        return "the Docker daemon is not running (start Docker Desktop or the docker service)"
    first_line = next((ln.strip() for ln in blob.splitlines() if ln.strip()), "")
    detail = f": {first_line}" if first_line else ""
    return f"docker version failed (exit {result.returncode}){detail}"


class DockerProbe:
    """Probe and briefly cache the local Docker installation."""

    def __init__(
        self,
        runner: DockerRunner,
        *,
        cli_resolver: Callable[[], str | None] = find_docker_cli,
        clock: Callable[[], float] = time.monotonic,
        cache_seconds: float = CACHE_SECONDS,
        timeout: float = PROBE_TIMEOUT_SECONDS,
    ) -> None:
        self._runner = runner
        self._cli_resolver = cli_resolver
        self._clock = clock
        self._cache_seconds = cache_seconds
        self._timeout = timeout
        self._cached_at: float | None = None
        self._cached: DockerProbeResult | None = None

    def invalidate(self) -> None:
        """Drop the cached result (e.g. after a failed build's daemon blip)."""
        self._cached_at = None
        self._cached = None

    async def probe(self, force: bool = False) -> DockerProbeResult:
        """Return the probe result, re-running it when stale or forced."""
        now = self._clock()
        if (
            not force
            and self._cached is not None
            and self._cached_at is not None
            and now - self._cached_at < self._cache_seconds
        ):
            return self._cached

        result = await self._run_probe()
        self._cached = result
        self._cached_at = now
        return result

    async def _run_probe(self) -> DockerProbeResult:
        cli = self._cli_resolver()
        if not cli:
            return DockerProbeResult(
                available=False,
                reason="the docker CLI was not found — install Docker or Docker Desktop",
            )
        try:
            completed = await self._runner.run(
                [cli, "version", "--format", "{{json .}}"],
                timeout=self._timeout,
            )
        except DockerCommandTimeoutError:
            return DockerProbeResult(
                available=False, reason="the Docker daemon did not answer in time"
            )
        except Exception as exc:  # noqa: BLE001 - any CLI failure means "not usable"
            logger.debug("docker version probe raised: %s", exc)
            return DockerProbeResult(available=False, reason=f"docker version failed: {exc}")

        if completed.returncode != 0:
            return DockerProbeResult(available=False, reason=_classify_failure(completed))

        try:
            data = json.loads(completed.stdout.strip().splitlines()[-1])
        except (ValueError, IndexError):
            return DockerProbeResult(
                available=False, reason="could not parse docker version output"
            )

        server = data.get("Server")
        client = data.get("Client") or {}
        if not isinstance(server, dict) or not server.get("Version"):
            return DockerProbeResult(
                available=False,
                reason="the Docker daemon is not reachable",
                docker_version=client.get("Version"),
            )
        return DockerProbeResult(
            available=True,
            reason=None,
            docker_version=server.get("Version") or client.get("Version"),
            server_os=server.get("Os"),
            arch=server.get("Arch"),
        )

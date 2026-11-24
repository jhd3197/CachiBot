"""ComputerService: one Vela container per bot, managed through the Docker CLI.

Lifecycle: ``wake`` probes Docker, builds the pinned image on first use,
creates (or starts) the bot's container and waits for Vela's health and
controller endpoints; ``sleep`` stops the container but keeps the volumes;
``stop`` stops it and marks the computer off. An idle loop sleeps computers
that have had no activity for ``idle_minutes``; C2+ callers report activity
through :meth:`touch`.

All Docker access flows through the injected :class:`DockerRunner`, and all
Vela access through an injected client factory, so tests run with fakes and
no Docker, network or containers. State changes and (throttled) build
progress are broadcast as ``computer_update`` WS events scoped to users who
can see the bot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cachibot.config import ComputerConfig, Config
from cachibot.models.computer import (
    BuildProgress,
    ComputerRecord,
    ComputerState,
    DockerProbeResult,
)
from cachibot.services.computer.build import (
    COMPUTER_IMAGE_TAG,
    VELA_VERSION,
    BuildManager,
    ImageBuildError,
)
from cachibot.services.computer.probe import DockerProbe, find_docker_cli
from cachibot.services.computer.runner import DockerRunner, SubprocessDockerRunner
from cachibot.services.computer.tokens import TokenManager
from cachibot.services.computer.vela_client import VelaClient, VelaComputerClient
from cachibot.storage.computer_repository import ComputerRepository

logger = logging.getLogger(__name__)

VELA_CONTAINER_PORT = 7700  # VELA_PORT inside the image
CONTAINER_NAME_PREFIX = "cachibot-computer-"
DATA_VOLUME_SUFFIX = "-data"
WORKSPACE_VOLUME_SUFFIX = "-workspace"
LABEL_MANAGED = "cachibot.managed"
LABEL_BOT_ID = "cachibot.bot_id"
TOKEN_MOUNT_TARGET = "/run/secrets/vela-controller-token"

HEALTH_TIMEOUT_SECONDS = 60.0
HEALTH_POLL_SECONDS = 1.0
MIN_VELA_PROTOCOL = 2
IDLE_LOOP_POLL_SECONDS = 30.0
BUILD_BROADCAST_THROTTLE_SECONDS = 0.5
DOCKER_CALL_TIMEOUT = 60.0

#: A ``computer_update`` broadcast: (payload, bot_id).
BroadcastFn = Callable[[dict[str, Any], str], Awaitable[None]]
#: Builds a Vela client for a host port + controller token.
VelaFactory = Callable[[int, str], VelaComputerClient]


def container_name_for(bot_id: str) -> str:
    """Container name for a bot: ``cachibot-computer-<short id>``."""
    return f"{CONTAINER_NAME_PREFIX}{bot_id[:8]}"


def data_volume_for(bot_id: str) -> str:
    """Named volume for Vela's own state (/data)."""
    return f"{CONTAINER_NAME_PREFIX}{bot_id}{DATA_VOLUME_SUFFIX}"


def workspace_volume_for(bot_id: str) -> str:
    """Named volume for the bot's workspace (/workspace)."""
    return f"{CONTAINER_NAME_PREFIX}{bot_id}{WORKSPACE_VOLUME_SUFFIX}"


def _one_line(text: str, limit: int = 300) -> str:
    return " ".join(text.split())[:limit]


def _parse_labels(raw: str | None) -> dict[str, str]:
    """Parse ``docker ps``'s comma-separated ``k=v`` label string."""
    labels: dict[str, str] = {}
    for part in (raw or "").split(","):
        key, sep, value = part.partition("=")
        if sep and key:
            labels[key] = value
    return labels


class ComputerService:
    """Owns the per-bot computer lifecycle and the idle/reconcile loops."""

    def __init__(
        self,
        *,
        runner: DockerRunner | None = None,
        config: ComputerConfig | None = None,
        token_dir: Path | None = None,
        repo: ComputerRepository | None = None,
        clock: Callable[[], datetime] | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        vela_factory: VelaFactory | None = None,
        broadcast: BroadcastFn | None = None,
        cli_resolver: Callable[[], str | None] = find_docker_cli,
        health_timeout: float = HEALTH_TIMEOUT_SECONDS,
        health_poll: float = HEALTH_POLL_SECONDS,
        idle_poll: float = IDLE_LOOP_POLL_SECONDS,
    ) -> None:
        self._runner = runner or SubprocessDockerRunner()
        self._config = config if config is not None else Config.load().computer
        self._repo = repo or ComputerRepository()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._monotonic = monotonic
        self._tokens = TokenManager(token_dir)
        self._vela_factory = vela_factory or (
            lambda port, token: VelaClient(f"http://127.0.0.1:{port}", token)
        )
        self._broadcast_fn = broadcast
        self._cli_resolver = cli_resolver
        self._health_timeout = health_timeout
        self._health_poll = health_poll
        self._idle_poll = idle_poll
        self._probe = DockerProbe(self._runner, cli_resolver=cli_resolver)
        self._builds = BuildManager(
            self._runner,
            cli_resolver=cli_resolver,
            on_progress=self._on_build_progress,
        )
        self._last_build_progress = BuildProgress(status="idle")
        self._building_bots: set[str] = set()
        self._last_build_broadcast_at = 0.0
        self._wake_tasks: dict[str, asyncio.Task[None]] = {}
        self._idle_task: asyncio.Task[None] | None = None
        self._started = False

    # ------------------------------------------------------------------
    # Lifecycle (owned by the app lifespan)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Reconcile with reality and start the idle loop. Idempotent."""
        if self._started or not self._config.enabled:
            return
        self._started = True
        try:
            await self.reconcile_on_startup()
        except Exception:
            logger.warning("Computer startup reconcile failed", exc_info=True)
        self._idle_task = asyncio.create_task(self._idle_loop())

    async def stop(self) -> None:
        """Cancel the idle loop and any in-flight wakes. Nothing is stopped
        on the Docker side — containers outlive the app by design."""
        self._started = False
        idle_task, self._idle_task = self._idle_task, None
        if idle_task is not None:
            idle_task.cancel()
            await asyncio.gather(idle_task, return_exceptions=True)
        for task in list(self._wake_tasks.values()):
            task.cancel()
        if self._wake_tasks:
            await asyncio.gather(*self._wake_tasks.values(), return_exceptions=True)
        self._wake_tasks.clear()
        self._building_bots.clear()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def get_status(self, bot_id: str) -> dict[str, Any]:
        """Status payload for one bot's computer (what GET /computer returns)."""
        record = await self._get_or_create_record(bot_id)
        return self._status_payload(record, await self._effective_probe())

    async def get_docker_status(self) -> dict[str, Any]:
        """The Docker probe summary (what GET /api/computer/status returns)."""
        probe = await self._effective_probe()
        return probe.model_dump()

    async def wake(self, bot_id: str) -> dict[str, Any]:
        """Start the computer in the background; return the current status."""
        await self.touch(bot_id, reason="wake")
        record = await self._get_or_create_record(bot_id)
        probe = await self._effective_probe()
        if not probe.available:
            record.last_error = probe.reason
            await self._repo.upsert(record)
            await self._broadcast(record, probe)
            return self._status_payload(record, probe)

        in_flight = self._wake_tasks.get(bot_id)
        if in_flight is not None and not in_flight.done():
            return self._status_payload(record, probe)
        if record.state in (ComputerState.AWAKE, ComputerState.STARTING):
            return self._status_payload(record, probe)

        self._wake_tasks[bot_id] = asyncio.create_task(self._wake_async(bot_id))
        return self._status_payload(record, probe)

    async def sleep(self, bot_id: str) -> dict[str, Any]:
        """Stop the container, keep the volumes: the computer falls asleep."""
        record = await self._get_or_create_record(bot_id)
        probe = await self._effective_probe()
        if probe.available:
            name = record.container_name or container_name_for(bot_id)
            running = await self._inspect_running(name)
            if running is not None:
                if running:
                    await self._runner.run(
                        [self._require_cli(), "stop", name], timeout=DOCKER_CALL_TIMEOUT
                    )
                await self._set_state(record, ComputerState.ASLEEP, last_error=None)
            elif record.state != ComputerState.ASLEEP:
                await self._set_state(record, ComputerState.OFF, last_error=None)
        return self._status_payload(record, await self._effective_probe())

    async def stop_computer(self, bot_id: str) -> dict[str, Any]:
        """Stop the container and mark the computer off (volumes kept)."""
        record = await self._get_or_create_record(bot_id)
        probe = await self._effective_probe()
        if probe.available:
            name = record.container_name or container_name_for(bot_id)
            running = await self._inspect_running(name)
            if running:
                await self._runner.run(
                    [self._require_cli(), "stop", name], timeout=DOCKER_CALL_TIMEOUT
                )
            await self._set_state(record, ComputerState.OFF, last_error=None)
        return self._status_payload(record, await self._effective_probe())

    async def touch(self, bot_id: str, reason: str = "") -> None:
        """Record activity so the idle loop keeps the computer awake.

        The C2+ hooks (tool steps, drivers, watchers) call this; "watching
        keeps it awake" is wired in C2.
        """
        record = await self._get_or_create_record(bot_id)
        record.last_active_at = self._clock()
        await self._repo.upsert(record)

    async def reconcile_on_startup(self) -> None:
        """Make rows match containers after a restart. Never auto-starts.

        Rows stuck in building/starting (a restart interrupted a wake) go
        back to off; containers still running become awake with their port
        re-read; containers that are gone leave the row off (or asleep).
        """
        for record in await self._repo.list_all():
            if record.state in (ComputerState.BUILDING, ComputerState.STARTING):
                record.state = ComputerState.OFF
                await self._repo.upsert(record)

        if not self._config.enabled:
            return
        probe = await self._probe.probe(force=True)
        if not probe.available:
            logger.info(
                "Docker unavailable at startup; computer rows stay as persisted: %s", probe.reason
            )
            return

        cli = self._require_cli()
        result = await self._runner.run(
            [cli, "ps", "-a", "--filter", f"label={LABEL_MANAGED}=1", "--format", "{{json .}}"],
            timeout=DOCKER_CALL_TIMEOUT,
        )
        seen: set[str] = set()
        for line in result.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                info = json.loads(line)
            except ValueError:
                continue
            labels = _parse_labels(info.get("Labels"))
            bot_id = labels.get(LABEL_BOT_ID)
            if not bot_id:
                continue
            seen.add(bot_id)
            record = await self._get_or_create_record(bot_id)
            name = info.get("Names") or container_name_for(bot_id)
            record.container_name = name
            if info.get("State") == "running":
                record.host_port = (await self._read_host_port(name)) or record.host_port
                record.state = ComputerState.AWAKE
            else:
                record.state = (
                    ComputerState.ASLEEP
                    if record.state == ComputerState.ASLEEP
                    else ComputerState.OFF
                )
            await self._repo.upsert(record)

        # Awake rows whose container is missing go off (rows already asleep
        # or off stay as they are).
        for record in await self._repo.list_with_state(ComputerState.AWAKE):
            if record.bot_id in seen:
                continue
            record.state = ComputerState.OFF
            await self._repo.upsert(record)

    async def _idle_loop(self) -> None:
        while True:
            await asyncio.sleep(self._idle_poll)
            try:
                await self._idle_tick()
            except Exception:
                logger.debug("idle tick failed", exc_info=True)

    async def _idle_tick(self) -> None:
        """Sleep every awake computer that has been idle too long."""
        if not self._config.enabled:
            return
        idle_for = timedelta(minutes=self._config.idle_minutes)
        for record in await self._repo.list_with_state(ComputerState.AWAKE):
            last_active = record.last_active_at or record.updated_at
            if self._clock() - last_active >= idle_for:
                logger.info("Computer for bot %s idle for %s; sleeping", record.bot_id, idle_for)
                await self.sleep(record.bot_id)

    # ------------------------------------------------------------------
    # Wake internals
    # ------------------------------------------------------------------

    async def _wake_async(self, bot_id: str) -> None:
        try:
            await self._do_wake(bot_id)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Wake for bot %s failed", bot_id)
            record = await self._get_or_create_record(bot_id)
            if record.state != ComputerState.AWAKE:
                await self._set_state(record, ComputerState.OFF, last_error=_one_line(str(exc)))
        finally:
            self._wake_tasks.pop(bot_id, None)
            self._building_bots.discard(bot_id)

    async def _do_wake(self, bot_id: str) -> None:
        record = await self._get_or_create_record(bot_id)
        probe = await self._effective_probe()
        if not probe.available:
            await self._set_state(record, record.state, last_error=probe.reason)
            return

        # 1. Image (built once, shared single-flight build).
        if not await self._builds.image_exists():
            await self._set_state(record, ComputerState.BUILDING, last_error=None)
            self._building_bots.add(bot_id)
            try:
                await self._builds.ensure_image()
            except ImageBuildError as exc:
                # A later wake retries from scratch.
                await self._set_state(record, ComputerState.OFF, last_error=_one_line(str(exc)))
                return
            finally:
                self._building_bots.discard(bot_id)

        # 2. Container (start the existing one, or create it).
        cli = self._require_cli()
        token = self._tokens.ensure_token(bot_id)
        name = record.container_name or container_name_for(bot_id)
        running = await self._inspect_running(name)
        if running is True:
            pass  # already up (e.g. woken outside CachiBot) — just re-verify
        elif running is False:
            await self._runner.run([cli, "start", name], timeout=DOCKER_CALL_TIMEOUT)
        else:
            run = self._run_argv(cli, bot_id, name, token)
            await self._runner.run(run, timeout=DOCKER_CALL_TIMEOUT)
        port = await self._read_host_port(name)
        if port is None:
            raise RuntimeError(f"could not read the published port of {name}")
        await self._set_state(
            record,
            ComputerState.STARTING,
            container_name=name,
            host_port=port,
            last_error=None,
        )

        # 3. Wait for health, then verify the controller speaks protocol >= 2.
        client = self._vela_factory(port, token)
        try:
            if not await self._wait_healthy(client):
                await self._stop_container(name)
                await self._set_state(
                    record,
                    ComputerState.OFF,
                    last_error="the computer did not become healthy in time",
                )
                return
            try:
                info = await client.controller_info()
            except Exception as exc:
                raise RuntimeError(f"controller check failed: {_one_line(str(exc))}") from exc
            protocol = info.get("protocol", 0)
            is_controller = info.get("mode") == "controller"
            if not is_controller or not isinstance(protocol, int) or protocol < MIN_VELA_PROTOCOL:
                await self._stop_container(name)
                await self._set_state(
                    record,
                    ComputerState.OFF,
                    last_error="the container is not a Vela controller (protocol >= 2 required)",
                )
                return
        finally:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:
                    pass

        await self._set_state(record, ComputerState.AWAKE, last_error=None)
        await self.touch(bot_id, reason="wake")

    def _run_argv(self, cli: str, bot_id: str, name: str, token: str) -> list[str]:
        """Exact ``docker run`` invocation for a bot's computer.

        The port is published on 127.0.0.1 with an ephemeral host port
        (``127.0.0.1::7700``) and read back with ``docker port`` — no race
        with other processes grabbing a "free" port. The controller token
        appears only as a read-only mount path, never as an argument value
        or environment variable.
        """
        return [
            cli,
            "run",
            "-d",
            "--name",
            name,
            "--label",
            f"{LABEL_BOT_ID}={bot_id}",
            "--label",
            f"{LABEL_MANAGED}=1",
            "-v",
            f"{data_volume_for(bot_id)}:/data",
            "-v",
            f"{workspace_volume_for(bot_id)}:/workspace",
            "-v",
            f"{self._tokens.token_path(bot_id)}:{TOKEN_MOUNT_TARGET}:ro",
            "-p",
            f"127.0.0.1::{VELA_CONTAINER_PORT}",
            *self._resource_cap_args(),
            COMPUTER_IMAGE_TAG,
        ]

    def _resource_cap_args(self) -> list[str]:
        """Resource caps for the container. C5 fills this in (--memory,
        --cpus, --pids-limit) from config; C1 leaves the container uncapped."""
        return []

    async def _wait_healthy(self, client: VelaComputerClient) -> bool:
        deadline = self._monotonic() + self._health_timeout
        while True:
            try:
                if await client.health():
                    return True
            except Exception:
                pass
            if self._monotonic() >= deadline:
                return False
            await asyncio.sleep(self._health_poll)

    async def _stop_container(self, name: str) -> None:
        try:
            await self._runner.run([self._require_cli(), "stop", name], timeout=DOCKER_CALL_TIMEOUT)
        except Exception:
            logger.debug("could not stop container %s", name, exc_info=True)

    # ------------------------------------------------------------------
    # Docker helpers
    # ------------------------------------------------------------------

    def _require_cli(self) -> str:
        cli = self._cli_resolver()
        if not cli:
            raise RuntimeError("docker CLI not found")
        return cli

    async def _inspect_running(self, name: str) -> bool | None:
        """True/False for a running/stopped container; None when it doesn't exist."""
        result = await self._runner.run(
            [self._require_cli(), "inspect", "-f", "{{.State.Running}}", name],
            timeout=DOCKER_CALL_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip() == "true"

    async def _read_host_port(self, name: str) -> int | None:
        """The host side of the 127.0.0.1::7700 publish, via ``docker port``."""
        result = await self._runner.run(
            [self._require_cli(), "port", name, f"{VELA_CONTAINER_PORT}/tcp"],
            timeout=DOCKER_CALL_TIMEOUT,
        )
        if result.returncode != 0:
            return None
        first = next((ln.strip() for ln in result.stdout.splitlines() if ln.strip()), "")
        _, _, port_text = first.rpartition(":")
        try:
            return int(port_text)
        except ValueError:
            return None

    async def _effective_probe(self) -> DockerProbeResult:
        if not self._config.enabled:
            return DockerProbeResult(available=False, reason="the computer feature is disabled")
        return await self._probe.probe()

    # ------------------------------------------------------------------
    # Persistence helpers
    # ------------------------------------------------------------------

    async def _get_or_create_record(self, bot_id: str) -> ComputerRecord:
        record = await self._repo.get_for_bot(bot_id)
        if record is None:
            record = ComputerRecord(
                bot_id=bot_id,
                state=ComputerState.OFF,
                container_name=container_name_for(bot_id),
                image_tag=COMPUTER_IMAGE_TAG,
                vela_version=VELA_VERSION,
            )
            await self._repo.upsert(record)
        return record

    async def _set_state(
        self,
        record: ComputerRecord,
        state: ComputerState,
        *,
        last_error: str | None = None,
        container_name: str | None = None,
        host_port: int | None = None,
    ) -> None:
        record.state = state
        record.updated_at = self._clock()
        record.last_error = last_error
        if container_name is not None:
            record.container_name = container_name
        if host_port is not None:
            record.host_port = host_port
        await self._repo.upsert(record)
        await self._broadcast(record)

    # ------------------------------------------------------------------
    # Status payload + WS broadcast
    # ------------------------------------------------------------------

    def _status_payload(self, record: ComputerRecord, probe: DockerProbeResult) -> dict[str, Any]:
        state = ComputerState.UNAVAILABLE if not probe.available else record.state
        build = None
        if record.state == ComputerState.BUILDING:
            build = self._last_build_progress.model_dump()
        return {
            "available": probe.available,
            "reason": probe.reason,
            "state": state.value,
            "build": build,
            "velaVersion": record.vela_version,
            "lastActiveAt": record.last_active_at.isoformat() if record.last_active_at else None,
            "lastError": record.last_error,
        }

    async def _broadcast(
        self, record: ComputerRecord, probe: DockerProbeResult | None = None
    ) -> None:
        """Send a ``computer_update`` to every socket that can see the bot."""
        if probe is None:
            probe = await self._effective_probe()
        payload = self._status_payload(record, probe)
        payload["botId"] = record.bot_id
        try:
            if self._broadcast_fn is not None:
                await self._broadcast_fn(payload, record.bot_id)
                return
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            await get_ws_manager().broadcast_to_bot(
                WSMessage.computer_update(payload), record.bot_id
            )
        except Exception:
            logger.debug("could not broadcast computer update", exc_info=True)

    def _on_build_progress(self, progress: BuildProgress) -> None:
        """BuildManager callback: broadcast throttled progress to building bots."""
        self._last_build_progress = progress
        now = self._monotonic()
        if (
            progress.status == "building"
            and now - self._last_build_broadcast_at < BUILD_BROADCAST_THROTTLE_SECONDS
        ):
            return
        self._last_build_broadcast_at = now
        try:
            asyncio.get_running_loop().create_task(self._broadcast_build_progress())
        except RuntimeError:
            pass

    async def _broadcast_build_progress(self) -> None:
        try:
            for record in await self._repo.list_with_state(ComputerState.BUILDING):
                await self._broadcast(record)
        except Exception:
            logger.debug("could not broadcast build progress", exc_info=True)


_computer_service: ComputerService | None = None


def get_computer_service() -> ComputerService:
    """Process-wide ComputerService singleton (constructed lazily)."""
    global _computer_service
    if _computer_service is None:
        _computer_service = ComputerService()
    return _computer_service

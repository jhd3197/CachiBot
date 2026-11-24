"""ComputerService: one Vela container per bot, managed through the Docker CLI.

Lifecycle: ``wake`` probes Docker, builds the pinned image on first use,
creates (or starts) the bot's container and waits for Vela's health and
controller endpoints; ``sleep`` stops the container but keeps the volumes;
``stop`` stops it and marks the computer off. An idle loop sleeps computers
that have had no activity for ``idle_minutes``; callers report activity
through :meth:`touch`.

C2 adds the live surface on top of the lifecycle:

- **Watchers keep it awake.** Watch heartbeats and preview/frame fetches
  call :meth:`touch` and count as live watchers (TTL ~30 s); while anyone
  watches, the idle loop never sleeps the computer. Heartbeats are forwarded
  to Vela (protocol >= 5) so its own watcher count is right.
- **Preview.** The opt-in full-desktop frame when the container's Vela
  advertises ``features.desktopFrame``; otherwise the focused/top window's
  frame. ETag/If-None-Match → 304 on both paths; a preview request never
  wakes the computer.
- **Take-over.** A person acquires Vela's control lease through CachiBot;
  the driver (who, since when) is mirrored here with the same TTL Vela
  enforces, so a disconnected driver expires cleanly. :meth:`driver_for` is
  what the bot's own driving (C3) checks before acting.
- **Needs-you.** A per-bot events poller (bounded cursor pages) maps Vela's
  ``task.attention``/``approval.waiting`` to the ``needs_you`` state with a
  reason, and clears it when resolved, resumed, taken over or handed back.

All Docker access flows through the injected :class:`DockerRunner`, and all
Vela access through an injected client factory, so tests run with fakes and
no Docker, network or containers. State changes and (throttled) live updates
are broadcast as ``computer_update`` WS events scoped to users who can see
the bot.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cachibot.config import ComputerConfig, Config
from cachibot.models.computer import (
    BuildProgress,
    ComputerInputRequest,
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
from cachibot.services.computer.vela_client import (
    VelaClient,
    VelaClientError,
    VelaComputerClient,
)
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
#: Viewer heartbeats, the activity line and watcher counts arrived with Vela
#: protocol 5; below that the service degrades (no heartbeat forwarding, no
#: activity line) rather than calling routes that answer 404.
MIN_VELA_PROTOCOL_WATCHERS = 5
IDLE_LOOP_POLL_SECONDS = 30.0
BUILD_BROADCAST_THROTTLE_SECONDS = 0.5
LIVE_BROADCAST_THROTTLE_SECONDS = 1.0
DOCKER_CALL_TIMEOUT = 60.0

#: How long one watch heartbeat (or preview fetch) counts as watching. The
#: frontend heartbeats well inside this; a closed tab stops counting on its own.
WATCHER_TTL_SECONDS = 30.0
#: Vela's watcher heartbeats last 20 s; forward at most this often per viewer.
VELA_HEARTBEAT_FORWARD_SECONDS = 10.0
#: Mirrors Vela's LEASE_SECONDS: a take-over nobody types into expires.
DRIVER_LEASE_SECONDS = 180.0
#: The opt-in that lets the controller (and only the controller) read one
#: full-desktop frame. A plain feature flag, not a secret.
DESKTOP_FRAME_ENV = "VELA_CONTROLLER_DESKTOP_FRAME"
EVENTS_POLL_SECONDS = 2.0
EVENTS_PAGE_LIMIT = 200
DEFAULT_DESKTOP_NAME = "Bot computer"
#: View kinds whose frames are pictures (terminals/editors answer text frames).
PICTURE_VIEW_KINDS = ("app", "web")

#: A ``computer_update`` broadcast: (payload, bot_id).
BroadcastFn = Callable[[dict[str, Any], str], Awaitable[None]]
#: Builds a Vela client for a host port + controller token.
VelaFactory = Callable[[int, str], VelaComputerClient]


class ComputerRequestError(Exception):
    """A live-computer request that cannot be served, with an HTTP status.

    The routes translate this into the response; ``detail`` is a plain
    sentence for the user (never a token, never an internal address).
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class DriverInfo:
    """A person holding the take-over, mirrored from Vela's control lease."""

    user_id: str
    name: str
    lease_id: str
    desktop_id: str
    since: datetime
    expires_at: float  # monotonic; refreshed by each input, like Vela's lease


@dataclass
class NeedsYouInfo:
    """Why the computer needs a person, mapped from Vela's events."""

    kind: str  # "attention" (needs-person pause) or "approval"
    reason: str
    desktop_id: str
    run_id: str | None = None
    request_id: str | None = None


@dataclass
class PreviewResult:
    """One preview/frame answer: image bytes, or 304 for a current ETag."""

    status: int  # 200 or 304
    body: bytes | None
    etag: str | None
    revision: str | None
    media_type: str = "image/png"


def _unquote_etag(etag: str | None) -> str | None:
    if not etag:
        return None
    return etag.strip().strip('"')


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


def _window_payload(view: dict[str, Any]) -> dict[str, Any]:
    """One open window as the UI lists it: app + title (+ url when there is one)."""
    kind = str(view.get("kind") or "web")
    url = view.get("url")
    app = view.get("appId")
    if not app and url:
        app = urlparse(str(url)).hostname or str(url)
    if not app:
        app = kind
    return {
        "id": str(view.get("id") or ""),
        "kind": kind,
        "title": str(view.get("title") or ""),
        "app": str(app),
        "url": str(url) if url else None,
    }


def _focused_view(views: dict[str, Any]) -> dict[str, Any] | None:
    """The desktop's selected view, else the first open one."""
    items: list[dict[str, Any]] = list(views.get("views") or [])
    if not items:
        return None
    selected = (views.get("layout") or {}).get("selectedView")
    for view in items:
        if view.get("id") == selected:
            return view
    return items[0]


def _top_picture_view(views: dict[str, Any]) -> dict[str, Any] | None:
    """The window a preview falls back to: the focused one with a picture
    frame (app/web), else the first such window."""
    items: list[dict[str, Any]] = [
        view for view in views.get("views") or [] if view.get("kind") in PICTURE_VIEW_KINDS
    ]
    if not items:
        return None
    selected = (views.get("layout") or {}).get("selectedView")
    for view in items:
        if view.get("id") == selected:
            return view
    return items[0]


def _event_timestamp(event: dict[str, Any], clock: Callable[[], datetime]) -> float:
    """Vela's event time as unix seconds (its activity line uses the same)."""
    raw = event.get("createdAt")
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        try:
            return datetime.fromisoformat(raw).timestamp()
        except ValueError:
            pass
    return clock().timestamp()


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
        events_poll: float = EVENTS_POLL_SECONDS,
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
        self._events_poll = events_poll
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
        self._events_task: asyncio.Task[None] | None = None
        self._started = False
        # Live (C2) state, per bot. None of it survives a restart by design:
        # Vela's leases and watcher heartbeats expire on their own, and the
        # events poller re-derives needs-you and the activity line from the
        # event stream when it reconnects.
        self._clients: dict[str, VelaComputerClient] = {}
        self._features: dict[str, dict[str, Any]] = {}
        self._desktop_ids: dict[str, str] = {}
        self._event_cursors: dict[str, int] = {}
        self._activity: dict[str, dict[str, Any] | None] = {}
        self._needs_you: dict[str, NeedsYouInfo] = {}
        self._drivers: dict[str, DriverInfo] = {}
        self._watchers: dict[str, dict[str, float]] = {}
        self._hb_forwarded_at: dict[tuple[str, str], float] = {}
        self._preview: dict[str, dict[str, Any]] = {}
        self._windows_count: dict[str, int] = {}
        self._last_live_broadcast: dict[str, float] = {}
        self._live_dirty: set[str] = set()

    # ------------------------------------------------------------------
    # Lifecycle (owned by the app lifespan)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Reconcile with reality and start the loops. Idempotent."""
        if self._started or not self._config.enabled:
            return
        self._started = True
        try:
            await self.reconcile_on_startup()
        except Exception:
            logger.warning("Computer startup reconcile failed", exc_info=True)
        self._idle_task = asyncio.create_task(self._idle_loop())
        self._events_task = asyncio.create_task(self._events_loop())

    async def stop(self) -> None:
        """Cancel the loops and any in-flight wakes, and close the Vela
        clients. Nothing is stopped on the Docker side — containers outlive
        the app by design."""
        self._started = False
        idle_task, self._idle_task = self._idle_task, None
        if idle_task is not None:
            idle_task.cancel()
            await asyncio.gather(idle_task, return_exceptions=True)
        events_task, self._events_task = self._events_task, None
        if events_task is not None:
            events_task.cancel()
            await asyncio.gather(events_task, return_exceptions=True)
        for task in list(self._wake_tasks.values()):
            task.cancel()
        if self._wake_tasks:
            await asyncio.gather(*self._wake_tasks.values(), return_exceptions=True)
        self._wake_tasks.clear()
        self._building_bots.clear()
        for bot_id in list(self._clients):
            await self._drop_client(bot_id)

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
                await self._clear_live_state(bot_id)
                await self._set_state(record, ComputerState.ASLEEP, last_error=None)
            elif record.state != ComputerState.ASLEEP:
                await self._clear_live_state(bot_id)
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
            await self._clear_live_state(bot_id)
            await self._set_state(record, ComputerState.OFF, last_error=None)
        return self._status_payload(record, await self._effective_probe())

    async def _clear_live_state(self, bot_id: str) -> None:
        """Drop the live state a stopped container can no longer back.

        The Vela client, the driver (its lease dies with the container), the
        needs-you flag, the activity line, the preview revision, the features
        cache and the windows count. Watchers stay: they are CachiBot-side
        and their heartbeats simply stop being answered while the computer is
        down. The event cursor stays too — Vela's event history survives a
        stop in /data, and if it does not, the poller notices the reset.
        """
        self._drivers.pop(bot_id, None)
        self._needs_you.pop(bot_id, None)
        self._activity.pop(bot_id, None)
        self._preview.pop(bot_id, None)
        self._windows_count.pop(bot_id, None)
        self._features.pop(bot_id, None)
        await self._drop_client(bot_id)

    async def _drop_client(self, bot_id: str) -> None:
        """Close and forget one bot's Vela client."""
        client = self._clients.pop(bot_id, None)
        if client is not None:
            aclose = getattr(client, "aclose", None)
            if aclose is not None:
                try:
                    await aclose()
                except Exception:
                    pass

    async def touch(self, bot_id: str, reason: str = "") -> None:
        """Record activity so the idle loop keeps the computer awake.

        Called by wake, by the bot's tool steps (C3), by watch heartbeats and
        preview/frame fetches ("watching keeps it awake"), by take-over input
        and by driver activity — anything that means somebody is using the
        computer.
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
        """Sleep every awake computer that has been idle too long.

        A needs-you computer is idle like any other when nobody watches or
        drives it — the run it was paused for survives the sleep.
        """
        if not self._config.enabled:
            return
        idle_for = timedelta(minutes=self._config.idle_minutes)
        candidates = await self._repo.list_with_state(ComputerState.AWAKE)
        candidates += await self._repo.list_with_state(ComputerState.NEEDS_YOU)
        for record in candidates:
            last_active = record.last_active_at or record.updated_at
            if self._clock() - last_active >= idle_for:
                logger.info("Computer for bot %s idle for %s; sleeping", record.bot_id, idle_for)
                await self.sleep(record.bot_id)

    # ------------------------------------------------------------------
    # Live surface (C2): watchers, preview, take-over, input, needs-you
    # ------------------------------------------------------------------

    async def note_watching(self, bot_id: str, user_id: str) -> dict[str, Any]:
        """Count one live watcher and keep the computer awake.

        Called by the watch heartbeat route and by every preview/frame fetch.
        The watcher expires on its own after ``WATCHER_TTL_SECONDS`` without a
        heartbeat; the heartbeat is forwarded to Vela (throttled, protocol >=
        5) so Vela's own watcher count is right. Never wakes the computer.
        """
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        key = f"u-{user_id}"
        self._watchers.setdefault(bot_id, {})[key] = self._monotonic() + WATCHER_TTL_SECONDS
        await self.touch(bot_id, reason="watching")
        await self._forward_heartbeat(bot_id, key, record)
        await self._broadcast_live(bot_id)
        return {
            "watching": True,
            "watchers": self.watchers_count(bot_id),
            "expiresInSeconds": int(WATCHER_TTL_SECONDS),
        }

    def watchers_count(self, bot_id: str) -> int:
        """Live watchers for a bot (expired heartbeats drop out on read)."""
        now = self._monotonic()
        live = {
            key: expiry for key, expiry in self._watchers.get(bot_id, {}).items() if expiry > now
        }
        if bot_id in self._watchers:
            self._watchers[bot_id] = live
        return len(live)

    def driver_for(self, bot_id: str) -> dict[str, Any] | None:
        """Who is driving the computer, or None.

        This is the check the bot's own driving (C3) makes before every step:
        while a person holds the take-over, the bot waits.
        """
        info = self._driver_info(bot_id)
        if info is None:
            return None
        return {
            "userId": info.user_id,
            "name": info.name,
            "since": info.since.isoformat(),
        }

    async def get_preview(
        self, bot_id: str, user_id: str, etag: str | None = None
    ) -> PreviewResult:
        """The preview image: the full-desktop frame when the container's Vela
        offers it, otherwise the focused/top window's frame. Never wakes."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        await self.note_watching(bot_id, user_id)
        client = await self._client_for(bot_id, record)
        desktop_id = await self._ensure_desktop(bot_id, client)
        info = await self._features_for(bot_id, record)
        features = (info or {}).get("features") or {}
        if features.get("desktopFrame"):
            result = await self._desktop_preview(client, desktop_id, etag)
        else:
            result = await self._window_preview(bot_id, client, desktop_id, etag)
        if result.status == 200 and result.revision:
            self._note_preview_revision(bot_id, result.etag, result.revision)
        return result

    async def get_views(self, bot_id: str, user_id: str) -> dict[str, Any]:
        """The open windows (app + title) and the activity line, live from Vela."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        await self.note_watching(bot_id, user_id)
        client = await self._client_for(bot_id, record)
        desktop_id = await self._ensure_desktop(bot_id, client)
        try:
            views = await self._load_views(bot_id, client, desktop_id)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "list the windows") from exc
        activity = self._activity.get(bot_id)
        try:
            status = await client.viewer_status(desktop_id)
            if status.get("activity") is not None:
                activity = status["activity"]
        except VelaClientError:
            pass  # the poller's line (or None) is the honest fallback
        return {
            "windows": [_window_payload(view) for view in views.get("views") or []],
            "activity": activity,
        }

    async def get_view_frame(
        self, bot_id: str, user_id: str, view_id: str, etag: str | None = None
    ) -> PreviewResult:
        """One window's frame, proxied. 304 when the caller's ETag is current."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        await self.note_watching(bot_id, user_id)
        client = await self._client_for(bot_id, record)
        desktop_id = await self._ensure_desktop(bot_id, client)
        try:
            meta = await client.view_frame(desktop_id, view_id)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "read that window") from exc
        digest = meta.get("digest")
        if not digest:
            raise ComputerRequestError(404, "that window has no picture to show")
        if etag and _unquote_etag(etag) == digest:
            return PreviewResult(status=304, body=None, etag=etag, revision=digest)
        try:
            body = await client.view_frame_bytes(desktop_id, view_id, digest)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "read that window") from exc
        return PreviewResult(status=200, body=body, etag=f'"{digest}"', revision=digest)

    async def takeover(self, bot_id: str, user_id: str, user_name: str) -> dict[str, Any]:
        """Hand the desktop to a person: Vela pauses the run, bumps the
        control epoch and issues the lease, in that order. While the lease is
        held the bot's own driving waits (:meth:`driver_for`)."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        existing = self._driver_info(bot_id)
        if existing is not None:
            if existing.user_id == user_id:
                return await self.get_status(bot_id)  # already driving
            raise ComputerRequestError(409, f"{existing.name} is driving this computer")
        client = await self._client_for(bot_id, record)
        desktop_id = await self._ensure_desktop(bot_id, client)
        try:
            lease = await client.takeover(desktop_id)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "take over") from exc
        self._drivers[bot_id] = DriverInfo(
            user_id=user_id,
            name=user_name,
            lease_id=str(lease.get("leaseId") or ""),
            desktop_id=desktop_id,
            since=self._clock(),
            expires_at=self._monotonic() + DRIVER_LEASE_SECONDS,
        )
        await self._clear_needs_you(bot_id)  # a person took over: they have it
        await self.touch(bot_id, reason="takeover")
        await self._broadcast(await self._get_or_create_record(bot_id))
        return await self.get_status(bot_id)

    async def handback(self, bot_id: str, user_id: str) -> dict[str, Any]:
        """Release the control lease. As in Vela, this never resumes the run
        by itself — the run carries on when somebody says so (C3)."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        driver = self._driver_info(bot_id)
        if driver is None:
            raise ComputerRequestError(409, "nobody is driving this computer")
        client = await self._client_for(bot_id, record)
        try:
            await client.release(driver.desktop_id, driver.lease_id)
        except VelaClientError as exc:
            # A lease that is already gone (expired, container restarted) is
            # released as far as anyone can tell — fall through and clear.
            if exc.status_code not in (404, 409):
                raise self._map_vela_error(exc, "hand back") from exc
        self._drivers.pop(bot_id, None)
        await self._clear_needs_you(bot_id)
        await self._broadcast(await self._get_or_create_record(bot_id))
        return await self.get_status(bot_id)

    async def send_input(
        self, bot_id: str, user_id: str, data: ComputerInputRequest
    ) -> dict[str, Any]:
        """Proxy one piece of person input, only while the caller holds the
        take-over. Bounds were validated by the request model; Vela enforces
        its own (viewport, frame age) on top."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        driver = self._driver_info(bot_id)
        if driver is None or driver.user_id != user_id:
            raise ComputerRequestError(409, "you are not driving this computer — take over first")
        client = await self._client_for(bot_id, record)
        view_id = data.viewId
        if view_id is None:
            try:
                views = await self._load_views(bot_id, client, driver.desktop_id)
            except VelaClientError as exc:
                raise self._map_vela_error(exc, "list the windows") from exc
            focused = _focused_view(views)
            if focused is None:
                raise ComputerRequestError(409, "no window is open on the computer")
            view_id = str(focused.get("id"))
        try:
            result = await client.send_input(
                driver.desktop_id, driver.lease_id, data.to_vela_payload(view_id)
            )
        except VelaClientError as exc:
            if exc.status_code in (404, 409):
                # The lease or the window is gone — the take-over is over.
                self._drivers.pop(bot_id, None)
                raise ComputerRequestError(
                    409, "your take-over is no longer active — take over again"
                ) from exc
            raise self._map_vela_error(exc, "send input") from exc
        driver.expires_at = self._monotonic() + DRIVER_LEASE_SECONDS
        await self.touch(bot_id, reason="input")
        return {"ok": bool(result.get("ok", True))}

    async def respond_needs_you(
        self, bot_id: str, user_id: str, user_name: str, action: str
    ) -> dict[str, Any]:
        """Answer a needs-you. ``takeover`` hands the desktop to the person.
        ``skip`` is the documented closest refusal: Vela has no "skip this
        step", so an approval is denied, and a needs-person pause stops the
        run (the two answers Vela's API documents for "no")."""
        record = await self._get_or_create_record(bot_id)
        self._require_awake(record)
        needs = self._needs_you.get(bot_id)
        if needs is None:
            raise ComputerRequestError(409, "the computer does not need you right now")
        if action == "takeover":
            return await self.takeover(bot_id, user_id, user_name)
        client = await self._client_for(bot_id, record)
        try:
            if needs.kind == "approval" and needs.request_id:
                await client.resolve_approval(needs.desktop_id, needs.request_id, "deny")
            elif needs.run_id:
                await client.control_task(needs.desktop_id, needs.run_id, "stop")
            else:
                raise ComputerRequestError(409, "that needs-you can no longer be answered")
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "answer the needs-you") from exc
        await self._clear_needs_you(bot_id)
        await self._broadcast(await self._get_or_create_record(bot_id))
        return await self.get_status(bot_id)

    # ------------------------------------------------------------------
    # Live surface internals
    # ------------------------------------------------------------------

    def _require_awake(self, record: ComputerRecord) -> None:
        if record.state in (ComputerState.AWAKE, ComputerState.NEEDS_YOU):
            return
        reasons = {
            ComputerState.ASLEEP: "the computer is asleep — wake it first",
            ComputerState.OFF: "the computer is off — wake it first",
            ComputerState.BUILDING: "the computer is still being built",
            ComputerState.STARTING: "the computer is still starting",
            ComputerState.UNAVAILABLE: "the computer is not available on this server",
        }
        raise ComputerRequestError(409, reasons.get(record.state, "the computer is not awake"))

    def _driver_info(self, bot_id: str) -> DriverInfo | None:
        """The live driver, expiring a stale lease on read (like Vela does)."""
        info = self._drivers.get(bot_id)
        if info is None:
            return None
        if info.expires_at <= self._monotonic():
            self._drivers.pop(bot_id, None)
            return None
        return info

    def _map_vela_error(self, exc: VelaClientError, what: str) -> ComputerRequestError:
        """Translate a Vela failure into a plain answer for the caller."""
        detail = exc.detail
        if exc.status_code is None:
            return ComputerRequestError(503, f"the computer is not answering ({what})")
        if exc.status_code == 404:
            return ComputerRequestError(404, detail or f"not found on the computer ({what})")
        if exc.status_code == 409:
            return ComputerRequestError(409, detail or f"the computer refused ({what})")
        if exc.status_code == 422:
            return ComputerRequestError(422, detail or f"the computer refused ({what})")
        return ComputerRequestError(
            503, detail or f"the computer answered {exc.status_code} ({what})"
        )

    async def _client_for(
        self, bot_id: str, record: ComputerRecord | None = None
    ) -> VelaComputerClient:
        """The bot's cached Vela client, created from its published port."""
        client = self._clients.get(bot_id)
        if client is not None:
            return client
        if record is None:
            record = await self._get_or_create_record(bot_id)
        if record.host_port is None:
            raise ComputerRequestError(409, "the computer is not awake")
        token = self._tokens.ensure_token(bot_id)
        client = self._vela_factory(record.host_port, token)
        self._clients[bot_id] = client
        return client

    async def _features_for(
        self, bot_id: str, record: ComputerRecord | None = None
    ) -> dict[str, Any] | None:
        """The cached /api/controller document (protocol + features)."""
        info = self._features.get(bot_id)
        if info is not None:
            return info
        try:
            client = await self._client_for(bot_id, record)
            info = await client.controller_info()
        except Exception:
            logger.debug("could not read controller features for bot %s", bot_id, exc_info=True)
            return None
        self._features[bot_id] = info
        return info

    async def _ensure_desktop(self, bot_id: str, client: VelaComputerClient) -> str:
        """The bot's desktop on its Vela: the first one, created once if the
        container is fresh (as the controller-mode docs describe)."""
        cached = self._desktop_ids.get(bot_id)
        if cached:
            return cached
        try:
            data = await client.list_desktops()
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "list desktops") from exc
        desktops = data.get("desktops") or []
        desktop_id = data.get("defaultId") or (desktops[0].get("id") if desktops else None)
        if not desktop_id:
            try:
                created = await client.create_desktop(DEFAULT_DESKTOP_NAME)
            except VelaClientError as exc:
                raise self._map_vela_error(exc, "create the desktop") from exc
            desktop_id = created.get("id")
        if not desktop_id:
            raise ComputerRequestError(503, "the computer did not report a desktop")
        self._desktop_ids[bot_id] = str(desktop_id)
        return self._desktop_ids[bot_id]

    async def _load_views(
        self, bot_id: str, client: VelaComputerClient, desktop_id: str
    ) -> dict[str, Any]:
        """The views list; also refreshes the windows count for the payload."""
        views = await client.views(desktop_id)
        self._windows_count[bot_id] = len(views.get("views") or [])
        return views

    async def _desktop_preview(
        self, client: VelaComputerClient, desktop_id: str, etag: str | None
    ) -> PreviewResult:
        """The opt-in full-desktop frame; ETag/If-None-Match pass through."""
        try:
            frame = await client.desktop_frame(desktop_id, etag=etag)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "the desktop preview") from exc
        if frame.status == 304:
            current = frame.etag or etag
            return PreviewResult(
                status=304, body=None, etag=current, revision=_unquote_etag(current)
            )
        revision = _unquote_etag(frame.etag) or frame.revision
        return PreviewResult(status=200, body=frame.body, etag=frame.etag, revision=revision)

    async def _window_preview(
        self, bot_id: str, client: VelaComputerClient, desktop_id: str, etag: str | None
    ) -> PreviewResult:
        """Fallback preview: the focused/top picture window's frame.

        Used when the container's Vela has no full-desktop frame (protocol <
        5 or the opt-in off). The frame's content digest is the ETag.
        """
        try:
            views = await self._load_views(bot_id, client, desktop_id)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "list the windows") from exc
        top = _top_picture_view(views)
        if top is None:
            raise ComputerRequestError(404, "no window on the computer has a picture to preview")
        view_id = str(top.get("id"))
        try:
            meta = await client.view_frame(desktop_id, view_id)
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "the window preview") from exc
        digest = meta.get("digest")
        if not digest:
            raise ComputerRequestError(404, "that window has no picture to preview")
        if etag and _unquote_etag(etag) == digest:
            return PreviewResult(status=304, body=None, etag=etag, revision=str(digest))
        try:
            body = await client.view_frame_bytes(desktop_id, view_id, str(digest))
        except VelaClientError as exc:
            raise self._map_vela_error(exc, "the window preview") from exc
        return PreviewResult(status=200, body=body, etag=f'"{digest}"', revision=str(digest))

    def _note_preview_revision(self, bot_id: str, etag: str | None, revision: str | None) -> None:
        """Record the latest preview revision; broadcast on change.

        Revision changes are what make clients refetch the preview, so they
        are never throttled away — the fetch path that produced them is
        already rate-limited by Vela's compose interval.
        """
        if not self._set_preview_revision(bot_id, etag, revision):
            return
        try:
            asyncio.get_running_loop().create_task(self._broadcast_live(bot_id, force=True))
        except RuntimeError:
            pass

    async def _forward_heartbeat(
        self, bot_id: str, viewer_key: str, record: ComputerRecord
    ) -> None:
        """Forward one viewer heartbeat to Vela, throttled per viewer.

        Only on protocol >= 5 (the route is a protocol-5 addition); failures
        never break watching — CachiBot's own count is the one that keeps the
        computer awake.
        """
        now = self._monotonic()
        last = self._hb_forwarded_at.get((bot_id, viewer_key))
        if last is not None and now - last < VELA_HEARTBEAT_FORWARD_SECONDS:
            return
        info = await self._features_for(bot_id, record)
        protocol = int((info or {}).get("protocol") or 0)
        if protocol < MIN_VELA_PROTOCOL_WATCHERS:
            return
        try:
            client = await self._client_for(bot_id, record)
            desktop_id = await self._ensure_desktop(bot_id, client)
            await client.viewer_heartbeat(desktop_id, viewer_key, kind="person")
            self._hb_forwarded_at[(bot_id, viewer_key)] = now
        except Exception:
            logger.debug("could not forward the viewer heartbeat", exc_info=True)

    async def _set_needs_you(self, bot_id: str, info: NeedsYouInfo) -> None:
        """Mark the computer as needing a person, with the reason."""
        self._needs_you[bot_id] = info
        record = await self._get_or_create_record(bot_id)
        if record.state == ComputerState.AWAKE:
            record.state = ComputerState.NEEDS_YOU
            record.updated_at = self._clock()
            await self._repo.upsert(record)
        await self._broadcast(record)

    async def _clear_needs_you(self, bot_id: str) -> bool:
        """Clear the needs-you flag; True when anything actually changed."""
        had_flag = self._needs_you.pop(bot_id, None) is not None
        record = await self._repo.get_for_bot(bot_id)
        changed_state = False
        if record is not None and record.state == ComputerState.NEEDS_YOU:
            record.state = ComputerState.AWAKE
            record.updated_at = self._clock()
            await self._repo.upsert(record)
            changed_state = True
        return had_flag or changed_state

    # ------------------------------------------------------------------
    # Events poller: activity, needs-you, lease expiry, preview revision
    # ------------------------------------------------------------------

    async def _events_loop(self) -> None:
        while True:
            await asyncio.sleep(self._events_poll)
            try:
                await self._live_tick()
            except Exception:
                logger.debug("computer live tick failed", exc_info=True)

    async def _live_tick(self) -> None:
        """One pass over the live state: expiries, then each awake computer."""
        if not self._config.enabled:
            return
        await self._sweep_drivers()
        candidates = await self._repo.list_with_state(ComputerState.AWAKE)
        candidates += await self._repo.list_with_state(ComputerState.NEEDS_YOU)
        for record in candidates:
            await self._poll_bot(record)

    async def _sweep_drivers(self) -> None:
        """Expire take-overs whose lease TTL lapsed (Vela expires them too)."""
        now = self._monotonic()
        for bot_id, info in list(self._drivers.items()):
            if info.expires_at > now:
                continue
            self._drivers.pop(bot_id, None)
            logger.info("Take-over for bot %s expired (no input within the lease TTL)", bot_id)
            record = await self._repo.get_for_bot(bot_id)
            if record is not None:
                await self._broadcast(record)

    async def _poll_bot(self, record: ComputerRecord) -> None:
        """Poll one awake computer: events, windows, and — while watched —
        the preview revision. One broadcast per tick at most."""
        if record.host_port is None:
            return
        bot_id = record.bot_id
        changed = False
        try:
            client = await self._client_for(bot_id, record)
            desktop_id = await self._ensure_desktop(bot_id, client)
            changed |= await self._poll_events(bot_id, client, desktop_id)
            views = await self._load_views(bot_id, client, desktop_id)
            if self.watchers_count(bot_id) > 0:
                changed |= await self._poll_preview_revision(bot_id, client, desktop_id, views)
        except Exception:
            logger.debug("could not poll the computer for bot %s", bot_id, exc_info=True)
            return
        if changed or bot_id in self._live_dirty:
            self._live_dirty.discard(bot_id)
            fresh = await self._repo.get_for_bot(bot_id)
            if fresh is not None:
                await self._broadcast(fresh)

    async def _poll_events(self, bot_id: str, client: VelaComputerClient, desktop_id: str) -> bool:
        """One bounded events page; maps activity, needs-you and lease expiry."""
        cursor = self._event_cursors.get(bot_id)
        try:
            page = await client.events(desktop_id, after=cursor or 0, limit=EVENTS_PAGE_LIMIT)
        except VelaClientError as exc:
            if exc.status_code == 404:
                return False  # no events surface on this Vela; nothing to map
            raise
        latest = int(page.get("latest") or 0)
        if cursor is not None and latest < cursor:
            # The container restarted with a fresh history: start over.
            cursor = 0
            self._activity.pop(bot_id, None)
            await self._clear_needs_you(bot_id)
            page = await client.events(desktop_id, after=0, limit=EVENTS_PAGE_LIMIT)
        changed = False
        for event in page.get("events") or []:
            changed |= await self._apply_event(bot_id, desktop_id, event)
        self._event_cursors[bot_id] = int(page.get("cursor") or cursor or 0)
        return changed

    async def _apply_event(self, bot_id: str, desktop_id: str, event: dict[str, Any]) -> bool:
        """Map one Vela event onto the live state. True when something changed."""
        kind = event.get("kind")
        payload = event.get("payload") or {}
        if kind == "desktop.activity":
            text = payload.get("text")
            if text:
                self._activity[bot_id] = {
                    "text": str(text),
                    "at": _event_timestamp(event, self._clock),
                    "viewId": payload.get("viewId"),
                }
            else:
                self._activity[bot_id] = None
            return True
        if kind == "task.attention":
            reason = payload.get("detail") or payload.get("reason") or "the computer needs you"
            await self._set_needs_you(
                bot_id,
                NeedsYouInfo(
                    kind="attention",
                    reason=_one_line(str(reason)),
                    desktop_id=desktop_id,
                    run_id=payload.get("runId") or event.get("runId"),
                ),
            )
            return True
        if kind == "approval.waiting":
            summary = payload.get("summary")
            headline = summary.get("headline") if isinstance(summary, dict) else None
            await self._set_needs_you(
                bot_id,
                NeedsYouInfo(
                    kind="approval",
                    reason=_one_line(str(headline or "a change needs your approval")),
                    desktop_id=desktop_id,
                    run_id=payload.get("runId") or event.get("runId"),
                    request_id=payload.get("requestId"),
                ),
            )
            return True
        if kind == "approval.resolved":
            needs = self._needs_you.get(bot_id)
            if (
                needs is not None
                and needs.kind == "approval"
                and (not needs.request_id or needs.request_id == payload.get("requestId"))
            ):
                return await self._clear_needs_you(bot_id)
            return False
        if kind in ("task.resumed", "task.succeeded", "task.failed", "task.cancelled"):
            return await self._clear_needs_you(bot_id)
        if kind == "control.taken":
            # A person took over — they are handling whatever was needed.
            return await self._clear_needs_you(bot_id)
        if kind == "control.released":
            changed = self._drivers.pop(bot_id, None) is not None
            return await self._clear_needs_you(bot_id) or changed
        if kind == "control.expired":
            return self._drivers.pop(bot_id, None) is not None
        return False

    async def _poll_preview_revision(
        self,
        bot_id: str,
        client: VelaComputerClient,
        desktop_id: str,
        views: dict[str, Any],
    ) -> bool:
        """Refresh the preview revision while somebody is watching, so clients
        refetch the preview only when it changed. Cheap by construction: the
        desktop frame answers 304 to the last ETag, and a window frame shares
        the capture every other watcher uses."""
        info = await self._features_for(bot_id)
        features = (info or {}).get("features") or {}
        current = self._preview.get(bot_id) or {}
        if features.get("desktopFrame"):
            try:
                frame = await client.desktop_frame(desktop_id, etag=current.get("etag"))
            except VelaClientError:
                return False
            if frame.status != 200:
                return False
            revision = _unquote_etag(frame.etag) or frame.revision
            return self._set_preview_revision(bot_id, frame.etag, revision)
        top = _top_picture_view(views)
        if top is None:
            return False
        try:
            meta = await client.view_frame(desktop_id, str(top.get("id")))
        except VelaClientError:
            return False
        digest = meta.get("digest")
        if not digest:
            return False
        return self._set_preview_revision(bot_id, f'"{digest}"', str(digest))

    def _set_preview_revision(self, bot_id: str, etag: str | None, revision: str | None) -> bool:
        if not revision:
            return False
        current = self._preview.get(bot_id)
        if current and current.get("revision") == revision:
            return False
        self._preview[bot_id] = {"etag": etag, "revision": revision}
        return True

    async def _broadcast_live(self, bot_id: str, *, force: bool = False) -> None:
        """Throttled broadcast for the chatty live fields (activity, watchers,
        preview revision) — at most one per throttle window per bot. A dropped
        update marks the bot dirty so the next live tick flushes it; ``force``
        (preview revisions) always sends."""
        now = self._monotonic()
        last = self._last_live_broadcast.get(bot_id)
        if not force and last is not None and now - last < LIVE_BROADCAST_THROTTLE_SECONDS:
            self._live_dirty.add(bot_id)
            return
        self._live_dirty.discard(bot_id)
        self._last_live_broadcast[bot_id] = now
        record = await self._repo.get_for_bot(bot_id)
        if record is not None:
            await self._broadcast(record)

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
            # Cache the discovery document: the C2 surface (desktop frame,
            # watcher heartbeats, activity) is feature-detected from it.
            self._features[bot_id] = info
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
        or environment variable. ``VELA_CONTROLLER_DESKTOP_FRAME=1`` is the
        documented opt-in for the controller-only full-desktop frame — a
        plain feature flag, not a secret.
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
            "-e",
            f"{DESKTOP_FRAME_ENV}=1",
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
        needs = self._needs_you.get(record.bot_id)
        preview = self._preview.get(record.bot_id) or {}
        return {
            "available": probe.available,
            "reason": probe.reason,
            "state": state.value,
            "build": build,
            "velaVersion": record.vela_version,
            "lastActiveAt": record.last_active_at.isoformat() if record.last_active_at else None,
            "lastError": record.last_error,
            "activity": self._activity.get(record.bot_id),
            "windowsCount": self._windows_count.get(record.bot_id, 0),
            "watchers": self.watchers_count(record.bot_id),
            "driver": self.driver_for(record.bot_id),
            "needsYou": needs.reason if needs else None,
            "previewRevision": preview.get("revision"),
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

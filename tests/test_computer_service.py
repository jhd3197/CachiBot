"""Tests for ComputerService: wake/sleep/stop transitions, idle sleep,
startup reconcile, WS payloads and the Docker run/build argv contracts.

Everything runs on SQLite in a tmp dir with a scripted FakeDockerRunner and
FakeVelaClient — no Docker, no network, no containers, no real sleeps.
"""

import asyncio
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.config import ComputerConfig
from cachibot.models.computer import BuildProgress, ComputerRecord, ComputerState
from cachibot.services.computer.build import COMPUTER_IMAGE_TAG
from cachibot.services.computer.runner import CommandResult
from cachibot.services.computer.service import (
    TOKEN_MOUNT_TARGET,
    ComputerService,
    container_name_for,
    data_volume_for,
    workspace_volume_for,
)
from cachibot.storage.computer_repository import ComputerRepository
from cachibot.storage.db import Base
from tests.computer_fakes import (
    FakeClock,
    FakeDockerRunner,
    FakeVelaClient,
    docker_version_json,
    ps_line,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite database in a tmp dir, patched into the shared session maker
    (same pattern as the side-task tests, including WAL: wake and build
    progress broadcasts touch the DB concurrently)."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_conn, _record) -> None:  # pragma: no cover - plumbing
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

    import cachibot.storage.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_mod.engine
    original_session_maker = db_mod.async_session_maker
    db_mod.engine = engine
    db_mod.async_session_maker = session_maker

    yield session_maker

    await engine.dispose()
    db_mod.engine = original_engine
    db_mod.async_session_maker = original_session_maker


@pytest.fixture
async def computer_env(tmp_path, sqlite_db):
    """ComputerService wired to fakes, with per-test broadcast recording."""
    runner = FakeDockerRunner()
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    clock = FakeClock()
    vela_clients: list[FakeVelaClient] = []

    def vela_factory(port: int, token: str) -> FakeVelaClient:
        client = FakeVelaClient()
        vela_clients.append(client)
        return client

    svc = ComputerService(
        runner=runner,
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=tmp_path / "tokens",
        clock=clock.now,
        monotonic=clock.monotonic,
        vela_factory=vela_factory,
        broadcast=broadcast,
        cli_resolver=lambda: runner.cli,
        health_timeout=5.0,
        health_poll=0.001,
        idle_poll=3600.0,
    )
    # Baseline Docker answers: CLI works, daemon is up, image not built yet.
    runner.when("version", result=CommandResult([], 0, docker_version_json(), ""))

    # The image "appears" once a build succeeds (single source of truth for
    # skip-if-image-exists across the whole suite).
    image_built = {"built": False}

    def inspect_image() -> CommandResult:
        if image_built["built"]:
            return CommandResult([], 0, "[]", "")
        return CommandResult([], 1, "", "No such image")

    runner.when("image", "inspect", COMPUTER_IMAGE_TAG, result=inspect_image)

    original_build = svc._builds._build

    async def tracking_build() -> None:
        await original_build()
        image_built["built"] = True

    svc._builds._build = tracking_build  # type: ignore[method-assign]

    env = SimpleNamespace(
        svc=svc,
        runner=runner,
        broadcasts=broadcasts,
        clock=clock,
        vela_clients=vela_clients,
        token_dir=tmp_path / "tokens",
    )
    yield env
    await svc.stop()


async def wait_for(predicate, timeout: float = 5.0) -> None:
    import time as time_mod

    deadline = time_mod.monotonic() + timeout
    while time_mod.monotonic() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        await asyncio.sleep(0.01)
    raise AssertionError("timed out waiting for condition")


async def record_state(bot_id: str) -> ComputerState:
    record = await ComputerRepository().get_for_bot(bot_id)
    assert record is not None
    return record.state


async def state_is(bot_id: str, state: ComputerState) -> bool:
    return (await record_state(bot_id)) == state


async def error_contains(bot_id: str, text: str) -> bool:
    record = await ComputerRepository().get_for_bot(bot_id)
    return record is not None and text in (record.last_error or "")


def script_container_lifecycle(runner: FakeDockerRunner, bot_id: str, port: int = 49153) -> None:
    """Container answers for one bot: missing until ``docker run`` creates it,
    running until ``docker stop`` stops it. Volumes are never removed."""
    name = container_name_for(bot_id)
    box = {"exists": False, "running": False}

    def inspect() -> CommandResult:
        if not box["exists"]:
            return CommandResult([], 1, "", f"Error: No such container: {name}")
        return CommandResult([], 0, "true" if box["running"] else "false", "")

    def create() -> CommandResult:
        box["exists"] = True
        box["running"] = True
        return CommandResult([], 0, "", "")

    def start() -> CommandResult:
        box["running"] = True
        return CommandResult([], 0, "", "")

    def stop() -> CommandResult:
        box["running"] = False
        return CommandResult([], 0, "", "")

    runner.when("inspect", "-f", "{{.State.Running}}", name, result=inspect)
    runner.when("run", result=create)
    runner.when("start", name, result=start)
    runner.when("stop", name, result=stop)
    runner.when("port", name, "7700/tcp", result=CommandResult([], 0, f"127.0.0.1:{port}\n", ""))


def make_bot_id() -> str:
    return str(uuid.uuid4())


# ---------------------------------------------------------------------------
# Wake
# ---------------------------------------------------------------------------


class TestWake:
    async def test_wake_happy_path_and_run_argv(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        runner: FakeDockerRunner = env.runner
        runner.when("build", result=["#1 [1/2] FROM scratch", "#2 [2/2] DONE"])
        script_container_lifecycle(runner, bot_id)

        status = await env.svc.wake(bot_id)
        assert status["available"] is True
        assert status["state"] in ("off", "building", "starting")

        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))

        # docker run argv: 127.0.0.1 only, named volumes, labels, read-only
        # token mount, the desktop-frame opt-in flag, no other env vars, no
        # token value anywhere.
        runs = runner.calls_for("run")
        assert len(runs) == 1
        argv = runs[0]
        name = container_name_for(bot_id)
        token_path = env.token_dir / bot_id / "controller-token"
        expected = [
            runner.cli,
            "run",
            "-d",
            "--name",
            name,
            "--label",
            f"cachibot.bot_id={bot_id}",
            "--label",
            "cachibot.managed=1",
            "-v",
            f"{data_volume_for(bot_id)}:/data",
            "-v",
            f"{workspace_volume_for(bot_id)}:/workspace",
            "-v",
            f"{token_path}:{TOKEN_MOUNT_TARGET}:ro",
            "-p",
            "127.0.0.1::7700",
            "-e",
            "VELA_CONTROLLER_DESKTOP_FRAME=1",
            COMPUTER_IMAGE_TAG,
        ]
        assert argv == expected
        # The only env var is the desktop-frame opt-in (a plain flag, not a
        # secret); the token never appears in argv.
        env_vars = [argv[i + 1] for i, part in enumerate(argv) if part == "-e"]
        assert env_vars == ["VELA_CONTROLLER_DESKTOP_FRAME=1"]
        assert "--env" not in argv

        token = token_path.read_text(encoding="utf-8").strip()
        assert len(token) >= 32
        for call in runner.calls:
            assert token not in " ".join(str(part) for part in call), (
                "token must never leak into argv"
            )

        record = await ComputerRepository().get_for_bot(bot_id)
        assert record is not None
        assert record.state == ComputerState.AWAKE
        assert record.host_port == 49153
        assert record.vela_version == "0.2.0"
        assert record.image_tag == COMPUTER_IMAGE_TAG

    async def test_wake_builds_image_first(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        runner: FakeDockerRunner = env.runner
        runner.when("build", result=["#1 [1/1] FROM scratch", "#1 DONE 0.1s"])
        script_container_lifecycle(runner, bot_id)

        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))

        assert len(runner.calls_for("build")) == 1
        build_argv = runner.calls_for("build")[0]
        assert build_argv[1:3] == ["build", "--target"]
        assert "computer" in build_argv
        assert "VELA_VERSION=0.2.0" in build_argv
        assert "https://github.com/jhd3197/Vela.git#v0.2.0" in build_argv
        # Second wake with the image present must not rebuild.
        await env.svc.sleep(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.ASLEEP))
        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))
        assert len(runner.calls_for("build")) == 1

    async def test_wake_broadcasts_state_changes(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        env.runner.when("build", result=["#1 [1/1] DONE"])
        script_container_lifecycle(env.runner, bot_id)

        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))

        states = [
            payload["state"] for _, payload in env.broadcasts if payload.get("botId") == bot_id
        ]
        assert ComputerState.BUILDING.value in states
        assert ComputerState.STARTING.value in states
        assert states[-1] == ComputerState.AWAKE.value
        # Payload contract: no token, no port; carries the pinned version.
        for _, payload in env.broadcasts:
            assert "hostPort" not in payload
            assert "token" not in payload
            assert payload["velaVersion"] == "0.2.0"

    async def test_concurrent_wakes_share_one_build_and_one_run(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        runner: FakeDockerRunner = env.runner
        gate = asyncio.Event()

        async def gated_build():
            await gate.wait()
            return ["#1 [1/1] DONE"]

        runner.when("build", result=gated_build)
        script_container_lifecycle(runner, bot_id)

        await env.svc.wake(bot_id)
        first = env.svc._wake_tasks.get(bot_id)
        assert first is not None
        await env.svc.wake(bot_id)  # joins the in-flight wake
        gate.set()
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))

        assert len(runner.calls_for("build")) == 1
        assert len(runner.calls_for("run")) == 1

    async def test_build_failure_then_wake_retries(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        runner: FakeDockerRunner = env.runner
        attempts = {"count": 0}

        def flaky_build():
            attempts["count"] += 1
            if attempts["count"] == 1:
                return CommandResult([], 1, "#1 [1/1] RUN explode\nboom: kaboom", "")
            return ["#1 [1/1] DONE"]

        runner.when("build", result=flaky_build)
        script_container_lifecycle(runner, bot_id)

        await env.svc.wake(bot_id)
        await wait_for(lambda: error_contains(bot_id, "kaboom"))

        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))
        assert attempts["count"] == 2

    async def test_protocol_below_two_fails_wake(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        env.runner.when("build", result=["#1 [1/1] DONE"])
        script_container_lifecycle(env.runner, bot_id)
        env.vela_clients.clear()
        env.svc._vela_factory = lambda port, token: _client_with(
            env, FakeVelaClient(info={"mode": "controller", "version": "0.1.0", "protocol": 1})
        )

        await env.svc.wake(bot_id)
        await wait_for(lambda: error_contains(bot_id, "protocol"))
        # The failed container was stopped, not left running.
        assert len(env.runner.calls_for("stop")) == 1

    async def test_health_timeout_fails_wake(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        env.runner.when("build", result=["#1 [1/1] DONE"])
        script_container_lifecycle(env.runner, bot_id)
        env.svc._health_timeout = 0.05
        env.svc._health_poll = 0.005
        # The health deadline uses the monotonic clock; use the real one here
        # (the fake one only advances when the test advances it).
        import time as time_mod

        env.svc._monotonic = time_mod.monotonic
        env.svc._vela_factory = lambda port, token: FakeVelaClient(health=False)

        await env.svc.wake(bot_id)
        await wait_for(lambda: error_contains(bot_id, "healthy"))
        assert len(env.runner.calls_for("stop")) == 1

    async def test_wake_without_docker_reports_unavailable(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        env.runner.when(
            "version",
            result=CommandResult(
                [], 1, "", "Cannot connect to the Docker daemon. Is the docker daemon running?"
            ),
        )
        status = await env.svc.wake(bot_id)
        assert status["available"] is False
        assert "daemon" in (status["reason"] or "").lower()
        assert status["state"] == "unavailable"
        assert env.runner.calls_for("run") == []
        assert env.runner.calls_for("build") == []

    async def test_disabled_config_never_touches_docker(self, computer_env) -> None:
        env = computer_env
        env.svc._config = ComputerConfig(enabled=False, idle_minutes=10)
        bot_id = make_bot_id()
        status = await env.svc.get_status(bot_id)
        assert status["available"] is False
        assert "disabled" in (status["reason"] or "")
        assert env.runner.calls == []


def _client_with(env, client: FakeVelaClient) -> FakeVelaClient:
    env.vela_clients.append(client)
    return client


# ---------------------------------------------------------------------------
# Sleep / stop / touch / idle
# ---------------------------------------------------------------------------


class TestSleepStopIdle:
    async def _awake(self, env, bot_id: str) -> None:
        env.runner.when("build", result=["#1 [1/1] DONE"])
        script_container_lifecycle(env.runner, bot_id)
        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))

    async def test_sleep_stops_container_and_keeps_volumes(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        await self._awake(env, bot_id)

        status = await env.svc.sleep(bot_id)
        assert status["state"] == ComputerState.ASLEEP.value
        stops = env.runner.calls_for("stop")
        assert len(stops) == 1
        # Sleep stops the container; volumes are never removed.
        assert env.runner.calls_for("volume", "rm") == []
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record.state == ComputerState.ASLEEP

    async def test_wake_from_sleep_starts_existing_container(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        await self._awake(env, bot_id)
        await env.svc.sleep(bot_id)
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.ASLEEP

        # Container exists but is stopped -> docker start, not docker run.
        await env.svc.wake(bot_id)
        await wait_for(lambda: state_is(bot_id, ComputerState.AWAKE))
        assert len(env.runner.calls_for("start")) == 1
        assert len(env.runner.calls_for("run")) == 1  # only the original creation

    async def test_stop_marks_off(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        await self._awake(env, bot_id)
        status = await env.svc.stop_computer(bot_id)
        assert status["state"] == ComputerState.OFF.value
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.OFF
        assert len(env.runner.calls_for("stop")) == 1

    async def test_idle_tick_sleeps_computer_after_idle_minutes(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        await self._awake(env, bot_id)

        # Still active: no sleep.
        env.clock.advance(minutes=9)
        await env.svc._idle_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.AWAKE

        env.clock.advance(minutes=2)
        await env.svc._idle_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.ASLEEP
        assert len(env.runner.calls_for("stop")) == 1

    async def test_touch_resets_the_idle_clock(self, computer_env) -> None:
        env = computer_env
        bot_id = make_bot_id()
        await self._awake(env, bot_id)
        env.clock.advance(minutes=9)
        await env.svc.touch(bot_id, reason="tool step")
        env.clock.advance(minutes=9)
        await env.svc._idle_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.AWAKE


# ---------------------------------------------------------------------------
# Startup reconcile
# ---------------------------------------------------------------------------


class TestReconcile:
    async def test_reconcile_resets_stuck_rows_and_matches_containers(self, computer_env) -> None:
        env = computer_env
        repo = ComputerRepository()
        stuck_building = make_bot_id()
        stuck_starting = make_bot_id()
        running_bot = make_bot_id()
        asleep_bot = make_bot_id()

        base = dict(
            image_tag=COMPUTER_IMAGE_TAG,
            vela_version="0.2.0",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        await repo.upsert(
            ComputerRecord(bot_id=stuck_building, state=ComputerState.BUILDING, **base)
        )
        await repo.upsert(
            ComputerRecord(bot_id=stuck_starting, state=ComputerState.STARTING, **base)
        )
        await repo.upsert(ComputerRecord(bot_id=asleep_bot, state=ComputerState.ASLEEP, **base))
        running_name = container_name_for(running_bot)
        await repo.upsert(
            ComputerRecord(
                bot_id=running_bot,
                state=ComputerState.AWAKE,
                container_name=running_name,
                **base,
            )
        )
        env.runner.when(
            "ps",
            result=CommandResult(
                [],
                0,
                ps_line(bot_id=running_bot, names=running_name, state="running") + "\n",
                "",
            ),
        )
        env.runner.when(
            "port", running_name, "7700/tcp", result=CommandResult([], 0, "127.0.0.1:47777\n", "")
        )

        await env.svc.reconcile_on_startup()

        assert (await repo.get_for_bot(stuck_building)).state == ComputerState.OFF
        assert (await repo.get_for_bot(stuck_starting)).state == ComputerState.OFF
        running = await repo.get_for_bot(running_bot)
        assert running.state == ComputerState.AWAKE
        assert running.host_port == 47777
        # Missing container on an asleep row stays asleep.
        assert (await repo.get_for_bot(asleep_bot)).state == ComputerState.ASLEEP

    async def test_reconcile_marks_awake_without_container_off(self, computer_env) -> None:
        env = computer_env
        repo = ComputerRepository()
        bot_id = make_bot_id()
        await repo.upsert(
            ComputerRecord(
                bot_id=bot_id,
                state=ComputerState.AWAKE,
                image_tag=COMPUTER_IMAGE_TAG,
                vela_version="0.2.0",
            )
        )
        env.runner.when("ps", result=CommandResult([], 0, "", ""))
        await env.svc.reconcile_on_startup()
        assert (await repo.get_for_bot(bot_id)).state == ComputerState.OFF


# ---------------------------------------------------------------------------
# Build progress broadcast (throttled)
# ---------------------------------------------------------------------------


class TestBuildProgressBroadcast:
    async def test_progress_events_broadcast_throttled(self, computer_env) -> None:
        env = computer_env
        repo = ComputerRepository()
        bot_id = make_bot_id()
        await repo.upsert(
            ComputerRecord(
                bot_id=bot_id,
                state=ComputerState.BUILDING,
                image_tag=COMPUTER_IMAGE_TAG,
                vela_version="0.2.0",
            )
        )
        env.svc._last_build_broadcast_at = -1.0

        def emit(line: str) -> None:
            env.svc._on_build_progress(BuildProgress(status="building", step=1, total=2, line=line))

        def building_count() -> int:
            return len([p for _, p in env.broadcasts if p.get("state") == "building"])

        emit("first")
        await wait_for(lambda: building_count() == 1)
        building_payloads = [p for _, p in env.broadcasts if p.get("state") == "building"]
        assert building_payloads[0]["build"]["line"] == "first"

        # Within the throttle window: skipped.
        emit("second")
        await asyncio.sleep(0.05)
        assert building_count() == 1

        # Past the window: broadcast again.
        env.clock.advance(seconds=1.0)
        emit("third")
        await wait_for(lambda: building_count() == 2)
        building_payloads = [p for _, p in env.broadcasts if p.get("state") == "building"]
        assert building_payloads[-1]["build"]["line"] == "third"
        assert building_payloads[-1]["botId"] == bot_id

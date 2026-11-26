"""Tests for the C2 live surface of ComputerService: feature detection and
preview fallback, ETag/304, watchers keeping the computer awake, take-over /
hand back with lease TTL, input proxying, the needs-you mapping from Vela
events, and the WS payload contract.

Everything runs on SQLite in a tmp dir with a scripted FakeDockerRunner and
FakeVelaClient — no Docker, no network, no containers, no real sleeps.
"""

import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.config import ComputerConfig
from cachibot.models.computer import ComputerInputRequest, ComputerState
from cachibot.services.computer.build import COMPUTER_IMAGE_TAG
from cachibot.services.computer.runner import CommandResult
from cachibot.services.computer.service import (
    ComputerRequestError,
    ComputerService,
)
from cachibot.services.computer.vela_client import VelaClientError
from cachibot.storage.computer_repository import ComputerRepository
from cachibot.storage.db import Base
from tests.computer_fakes import (
    FakeClock,
    FakeDockerRunner,
    FakeVelaClient,
    docker_version_json,
    events_page,
    make_event,
)
from tests.test_computer_service import script_container_lifecycle, wait_for, wait_for_wake

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite database in a tmp dir, patched into the shared session maker."""
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
async def live_env(tmp_path, sqlite_db):
    """ComputerService wired to fakes, with one shared FakeVelaClient."""
    runner = FakeDockerRunner()
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    clock = FakeClock()
    vela = FakeVelaClient()
    svc = ComputerService(
        runner=runner,
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=tmp_path / "tokens",
        clock=clock.now,
        monotonic=clock.monotonic,
        vela_factory=lambda port, token: vela,
        broadcast=broadcast,
        cli_resolver=lambda: runner.cli,
        health_timeout=5.0,
        health_poll=0.001,
        idle_poll=3600.0,
        events_poll=3600.0,
    )
    runner.when("version", result=CommandResult([], 0, docker_version_json(), ""))
    image_built = {"built": False}
    runner.when(
        "image",
        "inspect",
        COMPUTER_IMAGE_TAG,
        result=lambda: CommandResult(
            [], 0 if image_built["built"] else 1, "[]" if image_built["built"] else "", ""
        ),
    )
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
        vela=vela,
        token_dir=tmp_path / "tokens",
    )
    yield env
    await svc.stop()


def make_bot_id() -> str:
    return str(uuid.uuid4())


async def wake_bot(env, bot_id: str) -> None:
    """Script the container lifecycle and wake the bot's computer."""
    env.runner.when("build", result=["#1 [1/1] DONE"])
    script_container_lifecycle(env.runner, bot_id)
    await env.svc.wake(bot_id)
    await wait_for(lambda: _state_is(bot_id, ComputerState.AWAKE))
    await wait_for_wake(env, bot_id)


async def _state_is(bot_id: str, state: ComputerState) -> bool:
    record = await ComputerRepository().get_for_bot(bot_id)
    return record is not None and record.state == state


def last_payload(env, bot_id: str) -> dict[str, Any]:
    payloads = [p for b, p in env.broadcasts if b == bot_id]
    assert payloads, "expected at least one broadcast for the bot"
    return payloads[-1]


PROTOCOL_5_INFO = {
    "mode": "controller",
    "version": "0.3.0",
    "protocol": 5,
    "features": {
        "controller": True,
        "driver": True,
        "workspace": True,
        "editor": True,
        "terminal": True,
        "desktopFrame": True,
    },
}


# ---------------------------------------------------------------------------
# Preview: feature detection, fallback, ETag/304, refusals
# ---------------------------------------------------------------------------


class TestPreview:
    async def test_desktop_frame_used_when_advertised(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.info = PROTOCOL_5_INFO
        await wake_bot(env, bot_id)

        result = await env.svc.get_preview(bot_id, "user-1")
        assert result.status == 200
        assert result.body == b"desktop-png-1"
        assert result.etag == '"desktop-digest-1"'
        assert result.revision == "desktop-digest-1"
        assert env.vela.desktop_frame_calls == [None]
        # The fallback was not consulted.
        assert env.vela.frame_bytes_calls == []

    async def test_desktop_frame_304_passthrough(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.info = PROTOCOL_5_INFO
        await wake_bot(env, bot_id)

        first = await env.svc.get_preview(bot_id, "user-1")
        second = await env.svc.get_preview(bot_id, "user-1", etag=first.etag)
        assert second.status == 304
        assert second.body is None
        assert second.revision == "desktop-digest-1"
        # The client's ETag went through to Vela.
        assert env.vela.desktop_frame_calls[-1] == '"desktop-digest-1"'

    async def test_fallback_to_focused_window_frame(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        # The default fake info does not advertise desktopFrame (the opt-in
        # is off): the preview falls back to the focused window's frame.
        await wake_bot(env, bot_id)

        result = await env.svc.get_preview(bot_id, "user-1")
        assert result.status == 200
        assert result.body == b"png-1"
        assert result.etag == '"digest-1"'
        assert result.revision == "digest-1"
        assert env.vela.frame_bytes_calls == [("desk-1", "view-1", "digest-1")]

    async def test_fallback_304_when_digest_matches(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)

        first = await env.svc.get_preview(bot_id, "user-1")
        bytes_calls = len(env.vela.frame_bytes_calls)
        second = await env.svc.get_preview(bot_id, "user-1", etag=first.etag)
        assert second.status == 304
        assert len(env.vela.frame_bytes_calls) == bytes_calls  # no refetch

    async def test_fallback_picks_the_selected_window(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.views_payload = {
            "views": [
                {"id": "view-1", "kind": "web", "title": "One", "url": "https://a.com/"},
                {"id": "view-2", "kind": "web", "title": "Two", "url": "https://b.com/"},
                {"id": "term-1", "kind": "terminal", "title": "dev"},
            ],
            "layout": {"selectedView": "view-2"},
        }
        env.vela.frame_meta = {"viewId": "view-2", "digest": "digest-2"}
        env.vela.frame_bytes_map = {("view-2", "digest-2"): b"png-2"}
        await wake_bot(env, bot_id)

        result = await env.svc.get_preview(bot_id, "user-1")
        assert result.body == b"png-2"
        assert env.vela.frame_bytes_calls == [("desk-1", "view-2", "digest-2")]

    async def test_no_windows_is_a_plain_404(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.views_payload = {"views": [], "layout": {}}
        await wake_bot(env, bot_id)

        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.get_preview(bot_id, "user-1")
        assert excinfo.value.status_code == 404
        assert "no window" in excinfo.value.detail

    async def test_not_awake_refuses_without_waking(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.get_preview(bot_id, "user-1")
        assert excinfo.value.status_code == 409
        assert "off" in excinfo.value.detail
        # A preview request never wakes the computer.
        assert env.runner.calls_for("run") == []
        assert env.runner.calls_for("start") == []
        assert env.vela.desktop_frame_calls == []

    async def test_view_frame_proxy_and_304(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)

        result = await env.svc.get_view_frame(bot_id, "user-1", "view-1")
        assert result.status == 200
        assert result.body == b"png-1"
        again = await env.svc.get_view_frame(bot_id, "user-1", "view-1", etag=result.etag)
        assert again.status == 304

    async def test_views_payload_windows_and_activity(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.viewer_status_payload = {
            "desktopId": "desk-1",
            "kind": "personal",
            "control": None,
            "task": None,
            "watchers": {"count": 1, "kinds": {"person": 1}},
            "activity": {
                "text": "Clicking 'Re-run failed jobs'",
                "at": 1732473600.0,
                "viewId": None,
            },
        }
        await wake_bot(env, bot_id)

        payload = await env.svc.get_views(bot_id, "user-1")
        assert payload["windows"] == [
            {
                "id": "view-1",
                "kind": "web",
                "title": "Example",
                "app": "example.com",
                "url": "https://example.com/",
            }
        ]
        assert payload["activity"]["text"] == "Clicking 'Re-run failed jobs'"


# ---------------------------------------------------------------------------
# Watchers: counting, heartbeats, idle sleep
# ---------------------------------------------------------------------------


class TestWatchers:
    async def test_watch_counts_touches_and_forwards(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)

        result = await env.svc.note_watching(bot_id, "user-1")
        assert result["watching"] is True
        assert result["watchers"] == 1
        assert result["expiresInSeconds"] == 30
        assert env.svc.watchers_count(bot_id) == 1
        # Forwarded to Vela as a person, throttled per viewer.
        assert env.vela.heartbeats == [
            {"desktopId": "desk-1", "viewerId": "u-user-1", "kind": "person", "viewId": None}
        ]
        await env.svc.note_watching(bot_id, "user-1")
        assert len(env.vela.heartbeats) == 1  # inside the forward window
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record.last_active_at == env.clock.now()

    async def test_watch_expires(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.note_watching(bot_id, "user-1")
        assert env.svc.watchers_count(bot_id) == 1
        env.clock.advance(seconds=31)
        assert env.svc.watchers_count(bot_id) == 0

    async def test_watch_refused_when_asleep(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.note_watching(bot_id, "user-1")
        assert excinfo.value.status_code == 409

    async def test_watcher_heartbeats_prevent_idle_sleep(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)

        await env.svc.note_watching(bot_id, "user-1")
        env.clock.advance(minutes=9)
        await env.svc._idle_tick()
        assert await _state_is(bot_id, ComputerState.AWAKE)

        await env.svc.note_watching(bot_id, "user-1")  # still watching
        env.clock.advance(minutes=9)
        await env.svc._idle_tick()
        assert await _state_is(bot_id, ComputerState.AWAKE)

        # The tab closed: no more heartbeats, the computer idles to sleep.
        env.clock.advance(minutes=11)
        await env.svc._idle_tick()
        assert await _state_is(bot_id, ComputerState.ASLEEP)


# ---------------------------------------------------------------------------
# Take-over, input, hand back
# ---------------------------------------------------------------------------


class TestTakeover:
    async def test_takeover_sets_driver_and_broadcasts(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)

        status = await env.svc.takeover(bot_id, "user-1", "ada")
        driver = status["driver"]
        assert driver["userId"] == "user-1"
        assert driver["name"] == "ada"
        assert driver["since"]
        assert env.vela.takeover_calls == [{"desktopId": "desk-1", "viewId": None}]
        assert last_payload(env, bot_id)["driver"]["name"] == "ada"
        # The check C3 makes before the bot drives.
        assert env.svc.driver_for(bot_id)["userId"] == "user-1"

    async def test_takeover_conflict_and_idempotent_retake(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")

        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.takeover(bot_id, "user-2", "grace")
        assert excinfo.value.status_code == 409
        assert "ada" in excinfo.value.detail

        # The same user taking over again is a no-op, not a second lease.
        status = await env.svc.takeover(bot_id, "user-1", "ada")
        assert status["driver"]["userId"] == "user-1"
        assert len(env.vela.takeover_calls) == 1

    async def test_takeover_refused_when_asleep(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.takeover(bot_id, "user-1", "ada")
        assert excinfo.value.status_code == 409

    async def test_handback_releases_the_lease(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")

        status = await env.svc.handback(bot_id, "user-1")
        assert status["driver"] is None
        assert env.vela.release_calls == [("desk-1", "lease-1")]
        assert env.svc.driver_for(bot_id) is None
        assert last_payload(env, bot_id)["driver"] is None

    async def test_handback_without_driver_is_a_409(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.handback(bot_id, "user-1")
        assert excinfo.value.status_code == 409

    async def test_driver_expires_with_the_lease_ttl(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")

        env.clock.advance(seconds=179)
        await env.svc._sweep_drivers()
        assert env.svc.driver_for(bot_id) is not None

        env.clock.advance(seconds=2)
        await env.svc._sweep_drivers()
        assert env.svc.driver_for(bot_id) is None
        assert last_payload(env, bot_id)["driver"] is None

    async def test_input_requires_the_callers_takeover(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        data = ComputerInputRequest(kind="click", point={"x": 10.0, "y": 20.0})

        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.send_input(bot_id, "user-1", data)
        assert excinfo.value.status_code == 409
        assert "take over" in excinfo.value.detail

        await env.svc.takeover(bot_id, "user-1", "ada")
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.send_input(bot_id, "user-2", data)
        assert excinfo.value.status_code == 409
        assert env.vela.input_calls == []

    async def test_input_passes_through_with_focused_view_default(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")

        click = ComputerInputRequest(kind="click", point={"x": 10.0, "y": 20.0}, button="right")
        result = await env.svc.send_input(bot_id, "user-1", click)
        assert result == {"ok": True}
        call = env.vela.input_calls[-1]
        assert call["leaseId"] == "lease-1"
        assert call["payload"] == {
            "kind": "click",
            "viewId": "view-1",  # defaulted to the focused window
            "point": {"x": 10.0, "y": 20.0},
            "button": "right",
        }

        typed = ComputerInputRequest(kind="type", text="hello", viewId="view-9")
        await env.svc.send_input(bot_id, "user-1", typed)
        assert env.vela.input_calls[-1]["payload"] == {
            "kind": "text",
            "viewId": "view-9",
            "text": "hello",
        }

        scroll = ComputerInputRequest(kind="scroll", dy=240.0)
        await env.svc.send_input(bot_id, "user-1", scroll)
        assert env.vela.input_calls[-1]["payload"]["kind"] == "scroll"
        assert env.vela.input_calls[-1]["payload"]["dy"] == 240.0

    async def test_input_refreshes_the_driver_lease(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")

        env.clock.advance(seconds=170)
        key = ComputerInputRequest(kind="key", key="enter")
        await env.svc.send_input(bot_id, "user-1", key)
        env.clock.advance(seconds=170)  # 340s after the take-over, 170 after input
        await env.svc._sweep_drivers()
        assert env.svc.driver_for(bot_id) is not None

    async def test_input_after_lease_lost_clears_the_driver(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")
        env.vela.input_error = VelaClientError("send input: HTTP 409", status_code=409)

        key = ComputerInputRequest(kind="key", key="enter")
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.send_input(bot_id, "user-1", key)
        assert excinfo.value.status_code == 409
        assert env.svc.driver_for(bot_id) is None


class TestInputValidation:
    def test_click_needs_a_point_in_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="click")
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="click", point={"x": -1.0, "y": 5.0})
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="click", point={"x": 5.0, "y": 10001.0})
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="click", point={"x": float("nan"), "y": 5.0})
        ok = ComputerInputRequest(kind="click", point={"x": 0.0, "y": 800.0})
        assert ok.button is None

    def test_scroll_bounds(self) -> None:
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="scroll", dy=4001.0)
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="scroll", dx=0.0, dy=0.0)
        ok = ComputerInputRequest(kind="scroll", dx=-4000.0, dy=4000.0)
        assert ok.dy == 4000.0

    def test_type_and_key_need_content(self) -> None:
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="type")
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="type", text="x" * 4001)
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="key")
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="key", key="k" * 33)
        with pytest.raises(ValidationError):
            ComputerInputRequest(kind="move")  # not a C2 input kind


# ---------------------------------------------------------------------------
# Needs-you mapping from Vela events
# ---------------------------------------------------------------------------


class TestNeedsYou:
    async def test_attention_event_sets_needs_you(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.vela.events_handler = events_page(
            [
                make_event(
                    1,
                    "task.attention",
                    {"runId": "run-1", "reason": "sign_in", "detail": "Sign in to GitHub"},
                    run_id="run-1",
                )
            ]
        )

        await env.svc._live_tick()
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record.state == ComputerState.NEEDS_YOU
        payload = last_payload(env, bot_id)
        assert payload["state"] == "needs_you"
        assert payload["needsYou"] == "Sign in to GitHub"

    async def test_approval_waiting_and_resolved(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        events = [
            make_event(
                1,
                "approval.waiting",
                {
                    "runId": "run-1",
                    "requestId": "req-1",
                    "summary": {"headline": "Post the comment?"},
                    "expiresAt": 999999999.0,
                },
                run_id="run-1",
            )
        ]
        env.vela.events_handler = events_page(events)
        await env.svc._live_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.NEEDS_YOU
        assert last_payload(env, bot_id)["needsYou"] == "Post the comment?"

        events.append(
            make_event(
                2,
                "approval.resolved",
                {"runId": "run-1", "requestId": "req-1", "state": "denied"},
                run_id="run-1",
            )
        )
        await env.svc._live_tick()
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record.state == ComputerState.AWAKE
        assert last_payload(env, bot_id)["needsYou"] is None

    async def test_takeover_clears_needs_you(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.vela.events_handler = events_page(
            [make_event(1, "task.attention", {"runId": "run-1", "detail": "Sign in"})]
        )
        await env.svc._live_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.NEEDS_YOU

        await env.svc.takeover(bot_id, "user-1", "ada")
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record.state == ComputerState.AWAKE
        payload = last_payload(env, bot_id)
        assert payload["needsYou"] is None
        assert payload["state"] == "awake"  # the broadcast carries the fresh state
        assert payload["driver"]["userId"] == "user-1"

    async def test_handback_clears_needs_you(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")
        env.vela.events_handler = events_page(
            [make_event(1, "task.attention", {"runId": "run-1", "detail": "Sign in"})]
        )
        await env.svc._live_tick()
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.NEEDS_YOU

        await env.svc.handback(bot_id, "user-1")
        assert (await ComputerRepository().get_for_bot(bot_id)).state == ComputerState.AWAKE

    async def test_respond_takeover(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.vela.events_handler = events_page(
            [make_event(1, "task.attention", {"runId": "run-1", "detail": "Sign in"})]
        )
        await env.svc._live_tick()

        status = await env.svc.respond_needs_you(bot_id, "user-1", "ada", "takeover")
        assert status["driver"]["userId"] == "user-1"
        assert status["needsYou"] is None
        assert status["state"] == "awake"

    async def test_respond_skip_denies_an_approval(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.vela.events_handler = events_page(
            [
                make_event(
                    1,
                    "approval.waiting",
                    {"runId": "run-1", "requestId": "req-1", "summary": {"headline": "Post?"}},
                    run_id="run-1",
                )
            ]
        )
        await env.svc._live_tick()

        status = await env.svc.respond_needs_you(bot_id, "user-1", "ada", "skip")
        # Vela's documented refusal for an approval is "deny".
        assert env.vela.resolve_approval_calls == [("desk-1", "req-1", "deny")]
        assert status["needsYou"] is None
        assert status["state"] == "awake"

    async def test_respond_skip_stops_a_needs_person_run(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.vela.events_handler = events_page(
            [make_event(1, "task.attention", {"runId": "run-1", "detail": "Sign in"})]
        )
        await env.svc._live_tick()

        status = await env.svc.respond_needs_you(bot_id, "user-1", "ada", "skip")
        # Vela has no "skip this step": the documented closest refusal for a
        # needs-person pause is stopping the run.
        assert env.vela.control_task_calls == [("desk-1", "run-1", "stop")]
        assert status["needsYou"] is None

    async def test_respond_without_needs_you_is_a_409(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.respond_needs_you(bot_id, "user-1", "ada", "skip")
        assert excinfo.value.status_code == 409

    async def test_activity_line_from_events(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        events = [
            make_event(1, "desktop.activity", {"text": "Running npm run dev", "viewId": None})
        ]
        env.vela.events_handler = events_page(events)
        await env.svc._live_tick()
        payload = last_payload(env, bot_id)
        assert payload["activity"]["text"] == "Running npm run dev"

        events.append(make_event(2, "desktop.activity", {"text": None, "viewId": None}))
        await env.svc._live_tick()
        assert last_payload(env, bot_id)["activity"] is None

    async def test_lease_expired_event_clears_the_driver(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")
        env.vela.events_handler = events_page(
            [make_event(1, "control.expired", {"leaseId": "lease-1"})]
        )
        await env.svc._live_tick()
        assert env.svc.driver_for(bot_id) is None
        assert last_payload(env, bot_id)["driver"] is None

    async def test_event_history_reset_is_detected(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        seen_after: list[int] = []

        def handler(after: int, limit: int) -> dict[str, Any]:
            seen_after.append(after)
            if after == 0:
                return {
                    "events": [
                        make_event(1, "desktop.activity", {"text": "Working", "viewId": None})
                    ],
                    "cursor": 1,
                    "latest": 1,
                    "gap": False,
                }
            # The container restarted: its history is shorter than our cursor.
            return {"events": [], "cursor": after, "latest": 1, "gap": False}

        env.vela.events_handler = handler
        await env.svc._live_tick()
        env.svc._event_cursors[bot_id] = 42  # pretend we were far ahead
        await env.svc._live_tick()
        # The reset was noticed and the stream re-read from 0.
        assert seen_after == [0, 42, 0]


# ---------------------------------------------------------------------------
# WS payload contract + preview revision propagation
# ---------------------------------------------------------------------------


class TestPayloadContract:
    async def test_computer_update_carries_the_live_fields(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.info = PROTOCOL_5_INFO
        await wake_bot(env, bot_id)
        await env.svc.note_watching(bot_id, "user-1")
        await env.svc.takeover(bot_id, "user-1", "ada")
        env.vela.events_handler = events_page(
            [make_event(1, "desktop.activity", {"text": "Clicking 'Run'", "viewId": None})]
        )
        await env.svc._live_tick()
        await env.svc.get_preview(bot_id, "user-1")

        payload = await env.svc.get_status(bot_id)
        assert payload["activity"]["text"] == "Clicking 'Run'"
        assert payload["windowsCount"] == 1
        assert payload["watchers"] == 1
        assert payload["driver"]["name"] == "ada"
        assert payload["needsYou"] is None
        assert payload["previewRevision"] == "desktop-digest-1"
        # The contract stands: never a token, never a port.
        for _, p in env.broadcasts:
            assert "token" not in p
            assert "hostPort" not in p

    async def test_preview_revision_broadcasts_on_change_while_watched(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        env.vela.info = PROTOCOL_5_INFO
        await wake_bot(env, bot_id)
        await env.svc.note_watching(bot_id, "user-1")

        await env.svc._live_tick()
        assert last_payload(env, bot_id)["previewRevision"] == "desktop-digest-1"

        env.vela.desktop_frame_etag = '"desktop-digest-2"'
        env.vela.desktop_frame_body = b"desktop-png-2"
        await env.svc._live_tick()
        assert last_payload(env, bot_id)["previewRevision"] == "desktop-digest-2"

        # Nobody watching: the revision is not polled (the computer may idle).
        env.clock.advance(seconds=31)
        env.vela.desktop_frame_etag = '"desktop-digest-3"'
        await env.svc._live_tick()
        assert last_payload(env, bot_id)["previewRevision"] == "desktop-digest-2"

    async def test_preview_fetch_updates_the_revision(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.get_preview(bot_id, "user-1")
        await wait_for(
            lambda: _payload_revision_is(env, bot_id, "digest-1"),
            timeout=2.0,
        )

    async def test_live_broadcasts_are_throttled(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        env.clock.advance(seconds=2)
        before = len(env.broadcasts)
        await env.svc.note_watching(bot_id, "user-1")
        await env.svc.note_watching(bot_id, "user-2")
        await env.svc.note_watching(bot_id, "user-3")
        assert len(env.broadcasts) == before + 1  # one per throttle window
        env.clock.advance(seconds=2)
        await env.svc.note_watching(bot_id, "user-4")
        assert len(env.broadcasts) == before + 2


async def _payload_revision_is(env, bot_id: str, revision: str) -> bool:
    payloads = [p for b, p in env.broadcasts if b == bot_id]
    return bool(payloads) and payloads[-1].get("previewRevision") == revision


# ---------------------------------------------------------------------------
# Sleep clears the live state
# ---------------------------------------------------------------------------


class TestSleepClearsLiveState:
    async def test_sleep_clears_driver_needs_you_and_activity(self, live_env) -> None:
        env = live_env
        bot_id = make_bot_id()
        await wake_bot(env, bot_id)
        await env.svc.takeover(bot_id, "user-1", "ada")
        env.vela.events_handler = events_page(
            [make_event(1, "desktop.activity", {"text": "Working", "viewId": None})]
        )
        await env.svc._live_tick()
        await env.svc.get_preview(bot_id, "user-1")

        status = await env.svc.sleep(bot_id)
        assert status["state"] == "asleep"
        assert status["driver"] is None
        assert status["activity"] is None
        assert status["previewRevision"] is None
        assert status["windowsCount"] == 0
        assert env.svc.driver_for(bot_id) is None

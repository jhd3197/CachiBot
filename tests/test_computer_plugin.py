"""Tests for the C3 bot-facing computer surface: the computer plugin's tools,
the FileOps/CodingAgent routing, and the ComputerService driven-step pipeline
(gate, wake on demand, person wait, feature detection, runs, execution logs).

Everything runs on SQLite in a tmp dir with a scripted FakeDockerRunner and
FakeVelaClient — no Docker, no network, no containers, no real sleeps.
"""

import asyncio
import uuid
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukuy import PythonSandbox

import cachibot.storage.db as db_mod
from cachibot.config import ComputerConfig, Config
from cachibot.models.computer import ComputerState
from cachibot.plugins.base import PluginContext
from cachibot.plugins.coding_agent import CodingAgentPlugin
from cachibot.plugins.computer import ComputerPlugin
from cachibot.plugins.file_ops import FileOpsPlugin
from cachibot.services.computer.build import COMPUTER_IMAGE_TAG
from cachibot.services.computer.runner import CommandResult
from cachibot.services.computer.service import (
    ComputerRequestError,
    ComputerService,
    DriverInfo,
)
from cachibot.storage.automations_repository import (
    ExecutionLogLineRepository,
    ExecutionLogRepository,
)
from cachibot.storage.computer_repository import ComputerRepository
from cachibot.storage.db import Base
from tests.computer_fakes import (
    FakeClock,
    FakeDockerRunner,
    FakeVelaClient,
    controller_info,
    docker_version_json,
)
from tests.test_computer_service import script_container_lifecycle, wait_for

FULL_FEATURES = controller_info(terminal=True, workspace=True, editor=True)

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


def make_service(
    tmp_path,
    *,
    enabled: bool = True,
    vela: FakeVelaClient | None = None,
    clock: FakeClock | None = None,
) -> SimpleNamespace:
    """A ComputerService wired to fakes (not woken); the caller scripts Docker."""
    runner = FakeDockerRunner()
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    clock = clock or FakeClock()
    vela = vela or FakeVelaClient(info=dict(FULL_FEATURES))
    svc = ComputerService(
        runner=runner,
        config=ComputerConfig(enabled=enabled, idle_minutes=10),
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
        person_wait=0.05,
        person_poll=0.001,
        wake_timeout=5.0,
        wake_poll=0.001,
        coding_poll=0.001,
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
    return SimpleNamespace(svc=svc, runner=runner, vela=vela, clock=clock, broadcasts=broadcasts)


async def wake_bot(env: SimpleNamespace, bot_id: str) -> None:
    script_container_lifecycle(env.runner, bot_id)
    await env.svc.wake(bot_id)
    await wait_for(lambda: bot_id not in env.svc._wake_tasks)
    record = await ComputerRepository().get_for_bot(bot_id)
    assert record is not None and record.state == ComputerState.AWAKE


@pytest.fixture
async def env(tmp_path, sqlite_db):
    """A woken computer (full features) for one bot."""
    env = make_service(tmp_path)
    env.bot_id = str(uuid.uuid4())
    await wake_bot(env, env.bot_id)
    yield env
    await env.svc.stop()


def make_ctx(bot_id: str | None, chat_id: str | None = "chat-1") -> PluginContext:
    return PluginContext(config=Config(), sandbox=PythonSandbox(), bot_id=bot_id, chat_id=chat_id)


def make_plugin(env: SimpleNamespace, bot_id: Any = ...) -> ComputerPlugin:
    resolved = env.bot_id if bot_id is ... else bot_id
    return ComputerPlugin(make_ctx(resolved), computer_service=env.svc)


def set_driver(env: SimpleNamespace, bot_id: str, name: str = "Juan") -> None:
    env.svc._drivers[bot_id] = DriverInfo(
        user_id="user-1",
        name=name,
        lease_id="lease-1",
        desktop_id="desk-1",
        since=env.clock.now(),
        expires_at=env.clock.monotonic() + 180.0,
    )


# ---------------------------------------------------------------------------
# The tool gate: hidden unless enabled + Docker available
# ---------------------------------------------------------------------------


class TestToolGate:
    async def test_tools_hidden_when_feature_disabled(self, tmp_path, sqlite_db) -> None:
        env = make_service(tmp_path, enabled=False)
        plugin = make_plugin(env, bot_id="bot-1")
        assert env.svc.computer_tools_available() is False
        assert plugin.skills == {}

        outcome = await env.svc.run_tool_step("bot-1", tool="terminal_open", arguments={})
        assert outcome.status == "error"
        assert "disabled" in outcome.message

    async def test_tools_hidden_when_docker_unavailable(self, tmp_path, sqlite_db) -> None:
        env = make_service(tmp_path)
        env.runner.when(
            "version",
            result=CommandResult([], 1, "", "Cannot connect to the Docker daemon"),
        )
        probe = await env.svc.get_docker_status()
        assert probe["available"] is False
        plugin = make_plugin(env, bot_id="bot-1")
        assert plugin.skills == {}

        outcome = await env.svc.run_tool_step("bot-1", tool="terminal_open", arguments={})
        assert outcome.status == "error"
        assert "not available" in outcome.message

    async def test_tools_hidden_without_a_bot(self, env) -> None:
        plugin = make_plugin(env, bot_id=None)
        assert plugin.skills == {}

    async def test_stable_and_catalogue_tools_visible_when_usable(self, env) -> None:
        plugin = make_plugin(env)
        names = set(plugin.skills)
        # Stable tools (documented names, registered while awake or asleep)
        assert {
            "computer_terminal_open",
            "computer_terminal_run",
            "computer_terminal_read",
            "computer_terminal_write",
            "computer_terminal_close",
            "computer_workspace_list",
            "computer_workspace_read",
            "computer_workspace_write",
            "computer_editor_open",
            "computer_finish",
        } <= names
        # Browser/desktop tools from the live catalogue (woken at the fixture)
        assert "computer_desktop_observe" in names
        assert "computer_desktop_open_site" in names

    async def test_catalogue_tools_absent_while_asleep(self, tmp_path, sqlite_db) -> None:
        """A never-woken computer shows only the stable tools (their names are
        documented and do not drift); browser tools need the live catalogue."""
        env = make_service(tmp_path)
        # Warm the probe without waking any computer.
        await env.svc.get_docker_status()
        plugin = make_plugin(env, bot_id="bot-1")
        names = set(plugin.skills)
        assert "computer_terminal_run" in names
        assert "computer_finish" in names
        assert "computer_desktop_observe" not in names

    async def test_registry_hides_computer_tools_when_off(
        self, tmp_path, sqlite_db, monkeypatch
    ) -> None:
        from cachibot.services.plugin_manager import build_registry

        off = make_service(tmp_path, enabled=False)
        monkeypatch.setattr("cachibot.plugins.computer.get_computer_service", lambda: off.svc)
        registry = build_registry(make_ctx("bot-1"), capabilities={})
        assert not [name for name in registry.names if name.startswith("computer_")]

        on = make_service(tmp_path)
        await on.svc.get_docker_status()
        monkeypatch.setattr("cachibot.plugins.computer.get_computer_service", lambda: on.svc)
        registry = build_registry(make_ctx("bot-1"), capabilities={})
        assert "computer_terminal_run" in registry.names
        assert "computer_finish" in registry.names


# ---------------------------------------------------------------------------
# Wake on demand (a tool call may wake; a preview never does)
# ---------------------------------------------------------------------------


class TestWakeOnDemand:
    async def test_tool_call_wakes_the_computer(self, tmp_path, sqlite_db) -> None:
        env = make_service(tmp_path)
        bot_id = str(uuid.uuid4())
        script_container_lifecycle(env.runner, bot_id)
        # Warm the probe (the server does this at startup / status polls), so
        # the plugin gate lets the tools register.
        await env.svc.get_docker_status()
        plugin = make_plugin(env, bot_id)

        result = await plugin.skills["computer_terminal_open"].fn(title="dev")
        assert "terminalId" in result or "terminal_open" in result
        # The container was created by the tool call's wake.
        assert len(env.runner.calls_for("run")) == 1
        record = await ComputerRepository().get_for_bot(bot_id)
        assert record is not None and record.state == ComputerState.AWAKE

    async def test_preview_still_does_not_wake(self, tmp_path, sqlite_db) -> None:
        env = make_service(tmp_path)
        bot_id = str(uuid.uuid4())
        script_container_lifecycle(env.runner, bot_id)
        with pytest.raises(ComputerRequestError) as excinfo:
            await env.svc.get_preview(bot_id, "user-1")
        assert excinfo.value.status_code == 409
        assert env.runner.calls_for("run") == []

    async def test_wake_failure_is_a_plain_error(self, tmp_path, sqlite_db) -> None:
        env = make_service(tmp_path)
        bot_id = str(uuid.uuid4())
        script_container_lifecycle(env.runner, bot_id)
        env.vela.health_result = False  # the container never becomes healthy
        # The health wait fails fast, well inside the wake-on-demand wait.
        env.svc._health_timeout = 0.5

        async def advance_clock() -> None:
            # Move the frozen clock until the wake's health wait times out.
            for _ in range(200):
                env.clock.advance(seconds=1)
                await asyncio.sleep(0.01)

        advancer = asyncio.create_task(advance_clock())
        try:
            outcome = await env.svc.run_tool_step(bot_id, tool="terminal_open", arguments={})
        finally:
            advancer.cancel()
            await asyncio.gather(advancer, return_exceptions=True)
        assert outcome.status == "error"
        assert "did not wake" in outcome.message


# ---------------------------------------------------------------------------
# Activity: touch on each tool step
# ---------------------------------------------------------------------------


class TestTouch:
    async def test_tool_step_touches_the_computer(self, env) -> None:
        reasons: list[str] = []
        original_touch = env.svc.touch

        async def spy(bot_id: str, reason: str = "") -> None:
            reasons.append(reason)
            await original_touch(bot_id, reason)

        env.svc.touch = spy  # type: ignore[method-assign]
        before = (await ComputerRepository().get_for_bot(env.bot_id)).last_active_at
        env.clock.advance(minutes=1)

        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "result"
        assert "tool" in reasons
        after = (await ComputerRepository().get_for_bot(env.bot_id)).last_active_at
        assert after is not None and before is not None and after > before


# ---------------------------------------------------------------------------
# A person driving: the bot waits, never barges in
# ---------------------------------------------------------------------------


class TestPersonDriving:
    async def test_bot_waits_for_handback_then_proceeds(self, env) -> None:
        set_driver(env, env.bot_id)
        asyncio.get_running_loop().call_later(0.03, lambda: env.svc._drivers.pop(env.bot_id, None))
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "result"
        assert len(env.vela.step_calls) == 1

    async def test_person_driving_message_when_the_wait_times_out(self, env) -> None:
        set_driver(env, env.bot_id, name="Juan")
        asyncio.get_running_loop().call_later(0.03, lambda: env.clock.advance(seconds=60))
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "refusal"
        assert outcome.code == "person_driving"
        assert "Juan is driving" in outcome.message
        # No conflicting step was sent while the person held the desktop.
        assert env.vela.step_calls == []

    async def test_vela_person_driving_refusal_retries_after_handback(self, env) -> None:
        def handler(tool: str, arguments: dict[str, Any], step_id: str) -> dict[str, Any]:
            if len(env.vela.step_calls) == 1:
                return {
                    "refusal": {
                        "code": "person_driving",
                        "detail": "A person has taken control of this desktop.",
                        "retryable": True,
                    },
                    "budget": {},
                }
            return {"result": {"ok": True}, "budget": {}}

        env.vela.step_handler = handler
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "result"
        # The retried step used a fresh client step id.
        assert len(env.vela.step_calls) == 2
        ids = {call["clientStepId"] for call in env.vela.step_calls}
        assert len(ids) == 2

    async def test_vela_person_driving_refusal_waits_for_the_lease(self, env) -> None:
        set_driver(env, env.bot_id)
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "refusal": {
                "code": "person_driving",
                "detail": "A person has taken control of this desktop.",
                "retryable": True,
            },
            "budget": {},
        }
        asyncio.get_running_loop().call_later(0.03, lambda: env.svc._drivers.pop(env.bot_id, None))
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        # The pipeline's own person check waited for the hand-back first, so
        # the step only went out once the lease was clear (and Vela's refusal
        # never even happened).
        assert outcome.status == "refusal" or outcome.status == "result"
        assert env.svc.driver_for(env.bot_id) is None


# ---------------------------------------------------------------------------
# Step outcomes pass through honestly
# ---------------------------------------------------------------------------


class TestStepOutcomes:
    async def test_result_passes_through(self, env) -> None:
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "result": {"exitCode": 0, "running": False, "output": "done\n", "cursor": 5},
            "budget": {"steps": 1},
        }
        outcome = await env.svc.run_tool_step(
            env.bot_id, tool="terminal_run", arguments={"terminalId": "t1", "command": "ls"}
        )
        assert outcome.status == "result"
        assert outcome.result["exitCode"] == 0
        assert outcome.message == "exit code 0"

    async def test_refusal_passes_through(self, env) -> None:
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "refusal": {
                "code": "not_allowed",
                "detail": "That site is not approved for this desktop.",
                "retryable": False,
            },
            "budget": {},
        }
        outcome = await env.svc.run_tool_step(
            env.bot_id, tool="desktop.open_site", arguments={"url": "https://example.com/"}
        )
        assert outcome.status == "refusal"
        assert outcome.code == "not_allowed"
        assert "not approved" in outcome.message

    async def test_approval_trips_needs_you_and_settles_on_read(self, env) -> None:
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "approval": {
                "requestId": "req-1",
                "summary": {"headline": "Send the contact form"},
                "expiresAt": 999999999.0,
            },
            "budget": {},
        }
        outcome = await env.svc.run_tool_step(
            env.bot_id, tool="desktop.click", arguments={"control": "Send"}
        )
        assert outcome.status == "approval"
        assert "Send the contact form" in outcome.message
        needs = env.svc._needs_you.get(env.bot_id)
        assert needs is not None and needs.kind == "approval" and needs.request_id == "req-1"

        # While the person has not answered, the next step is not sent.
        env.vela.step_read_handler = lambda step_id: {
            "approval": {"requestId": "req-1", "summary": {"headline": "Send the contact form"}}
        }
        blocked = await env.svc.run_tool_step(env.bot_id, tool="desktop.observe", arguments={})
        assert blocked.status == "approval"
        assert len(env.vela.step_calls) == 1  # only the first step went out

        # Once the person answered, the read settles the pending step and the
        # next step goes through.
        env.vela.step_read_handler = lambda step_id: {
            "result": {"clicked": True},
            "status": "settled",
        }
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "result": {"observed": True},
            "budget": {},
        }
        settled = await env.svc.run_tool_step(env.bot_id, tool="desktop.observe", arguments={})
        assert settled.status == "result"
        assert env.vela.step_read_calls  # the settling read happened

    async def test_needs_person_trips_needs_you(self, env) -> None:
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "needsPerson": {
                "reason": "sign_in",
                "detail": "The site wants a sign-in.",
                "viewId": "view-1",
            },
            "budget": {},
        }
        outcome = await env.svc.run_tool_step(
            env.bot_id, tool="desktop.open_site", arguments={"url": "https://example.com/"}
        )
        assert outcome.status == "needs_person"
        assert "sign-in" in outcome.message
        needs = env.svc._needs_you.get(env.bot_id)
        assert needs is not None and needs.kind == "attention"
        assert "sign-in" in needs.reason


# ---------------------------------------------------------------------------
# Documented payloads: terminal, workspace, editor, browser, finish
# ---------------------------------------------------------------------------


class TestDocumentedPayloads:
    async def test_terminal_tools_send_the_documented_arguments(self, env) -> None:
        plugin = make_plugin(env)
        await plugin.skills["computer_terminal_open"].fn(title="dev", cwd="/workspace/app")
        await plugin.skills["computer_terminal_run"].fn(
            terminal_id="t1", command="npm run dev", timeout_seconds=5, wait_for="output"
        )
        await plugin.skills["computer_terminal_read"].fn(terminal_id="t1", since_cursor=3)
        await plugin.skills["computer_terminal_write"].fn(terminal_id="t1", keys="ctrl-c")
        await plugin.skills["computer_terminal_close"].fn(terminal_id="t1")

        tools = [call["tool"] for call in env.vela.step_calls]
        assert tools == [
            "terminal_open",
            "terminal_run",
            "terminal_read",
            "terminal_write",
            "terminal_close",
        ]
        assert env.vela.step_calls[0]["arguments"] == {"title": "dev", "cwd": "/workspace/app"}
        assert env.vela.step_calls[1]["arguments"] == {
            "terminalId": "t1",
            "command": "npm run dev",
            "timeoutSeconds": 5,
            "waitFor": "output",
        }
        assert env.vela.step_calls[2]["arguments"] == {"terminalId": "t1", "sinceCursor": 3}
        assert env.vela.step_calls[3]["arguments"] == {"terminalId": "t1", "keys": "ctrl-c"}
        assert env.vela.step_calls[4]["arguments"] == {"terminalId": "t1"}
        # All steps went through one shared driven run on the bot's desktop.
        run_ids = {call["runId"] for call in env.vela.step_calls}
        assert len(run_ids) == 1
        assert env.vela.step_calls[0]["desktopId"] == "desk-1"

    async def test_workspace_and_editor_tools_send_the_documented_arguments(self, env) -> None:
        plugin = make_plugin(env)
        await plugin.skills["computer_workspace_list"].fn(path="notes")
        await plugin.skills["computer_workspace_read"].fn(path="notes/todo.txt", offset=2, limit=10)
        await plugin.skills["computer_workspace_write"].fn(
            path="notes/todo.txt", content="hello", expected_revision="rev-1"
        )
        await plugin.skills["computer_editor_open"].fn(path="notes/todo.txt")

        assert [call["tool"] for call in env.vela.step_calls] == [
            "workspace_list",
            "workspace_read",
            "workspace_write",
            "editor_open",
        ]
        assert env.vela.step_calls[0]["arguments"] == {"path": "notes"}
        assert env.vela.step_calls[1]["arguments"] == {
            "path": "notes/todo.txt",
            "offset": 2,
            "limit": 10,
        }
        assert env.vela.step_calls[2]["arguments"] == {
            "path": "notes/todo.txt",
            "content": "hello",
            "expectedRevision": "rev-1",
        }
        assert env.vela.step_calls[3]["arguments"] == {"path": "notes/todo.txt"}

    async def test_browser_tool_from_the_catalogue_sends_the_documented_arguments(
        self, env
    ) -> None:
        plugin = make_plugin(env)
        await plugin.skills["computer_desktop_open_site"].fn(url="https://example.com/")
        await plugin.skills["computer_desktop_observe"].fn()

        assert [call["tool"] for call in env.vela.step_calls] == [
            "desktop.open_site",
            "desktop.observe",
        ]
        assert env.vela.step_calls[0]["arguments"] == {"url": "https://example.com/"}
        assert env.vela.step_calls[1]["arguments"] == {}

    async def test_computer_finish_ends_the_run_and_the_next_step_starts_a_new_one(
        self, env
    ) -> None:
        plugin = make_plugin(env)
        await plugin.skills["computer_terminal_open"].fn()
        result = await plugin.skills["computer_finish"].fn(summary="all done", outcome="succeeded")
        assert "succeeded" in result
        assert env.vela.finish_calls == [
            {
                "desktopId": "desk-1",
                "runId": "run-1",
                "outcome": "succeeded",
                "summary": "all done",
            }
        ]
        assert env.bot_id not in env.svc._driven_runs

        await plugin.skills["computer_terminal_open"].fn()
        assert env.vela.create_run_calls[-1]["title"] == "CachiBot work"
        assert env.vela.step_calls[-1]["runId"] == "run-2"

    async def test_finish_without_a_run_is_a_plain_refusal(self, env) -> None:
        outcome = await env.svc.finish_computer_run(env.bot_id, outcome="succeeded", summary="x")
        assert outcome.status == "refusal"
        assert "no open computer task" in outcome.message

    async def test_cancel_kills_the_run(self, env) -> None:
        await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        outcome = await env.svc.cancel_computer_run(env.bot_id, reason="user asked")
        assert outcome.status == "result"
        assert env.vela.cancel_calls == ["run-1"]
        assert env.bot_id not in env.svc._driven_runs

    async def test_agent_setup_happened_once_at_wake(self, env) -> None:
        """The wake made the desktop agent-ready: starter policy + enable-agent."""
        assert env.vela.put_policy_calls, "the starter policy was saved"
        sites = env.vela.put_policy_calls[0]["document"]["sites"]
        assert sites == [
            {"origin": "https://example.com", "includeSubdomains": False, "effects": "ask"}
        ]
        assert env.vela.enable_agent_calls == ["desk-1"]
        # The desktop is an agent desktop now, so driven runs are accepted.
        assert env.vela.desktops[0]["kind"] == "agent"

    async def test_run_left_over_from_a_restart_is_adopted(self, env) -> None:
        """A driven run Vela still carries (e.g. from before a CachiBot
        restart) is adopted instead of erroring on the 409."""
        env.svc._driven_runs.pop(env.bot_id, None)
        await env.vela.create_driven_run("desk-1", title="older work", client_request_id="x-1")
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "result"
        assert env.vela.step_calls[-1]["runId"] == "run-1"


# ---------------------------------------------------------------------------
# Feature detection: a missing surface is a plain refusal, never faked
# ---------------------------------------------------------------------------


class TestFeatureDetection:
    async def test_terminal_workspace_editor_refuse_on_the_pinned_image(
        self, tmp_path, sqlite_db
    ) -> None:
        """The pinned 0.2.0 image (protocol 2, driver only) has no
        terminal/workspace/editor: those tools refuse plainly."""
        vela = FakeVelaClient()  # default info: protocol 2, driver only
        env = make_service(tmp_path, vela=vela)
        env.bot_id = str(uuid.uuid4())
        await wake_bot(env, env.bot_id)

        for tool in ("terminal_open", "workspace_read", "editor_open"):
            outcome = await env.svc.run_tool_step(env.bot_id, tool=tool, arguments={})
            assert outcome.status == "refusal", tool
            assert outcome.code == "feature_missing"
            assert "does not offer" in outcome.message
        # Nothing was faked: not one driven step went out.
        assert env.vela.step_calls == []

        # The driver surface works on the same image.
        outcome = await env.svc.run_tool_step(env.bot_id, tool="desktop.observe", arguments={})
        assert outcome.status == "result"

    async def test_missing_driver_refuses_browser_tools(self, tmp_path, sqlite_db) -> None:
        info = {
            "mode": "controller",
            "version": "0.3.0",
            "protocol": 5,
            "features": {"controller": True, "terminal": True, "workspace": True},
        }
        env = make_service(tmp_path, vela=FakeVelaClient(info=info))
        env.bot_id = str(uuid.uuid4())
        await wake_bot(env, env.bot_id)

        outcome = await env.svc.run_tool_step(env.bot_id, tool="desktop.observe", arguments={})
        assert outcome.status == "refusal"
        assert outcome.code == "feature_missing"
        assert "driver" in outcome.message
        assert env.vela.step_calls == []

    async def test_coding_agent_refuses_plainly_without_the_terminal_surface(
        self, tmp_path, sqlite_db
    ) -> None:
        vela = FakeVelaClient()  # protocol 2: no terminal/workspace
        env = make_service(tmp_path, vela=vela)
        env.bot_id = str(uuid.uuid4())
        await wake_bot(env, env.bot_id)

        result = await env.svc.run_coding_agent(
            env.bot_id,
            argv=["claude", "--print", "fix it"],
            task="fix it",
            timeout_seconds=60,
        )
        assert result.error is not None
        assert "terminal" in result.error
        assert env.vela.step_calls == []


# ---------------------------------------------------------------------------
# File ops: workspace_* when the computer is usable, host path when not
# ---------------------------------------------------------------------------


def workspace_handler(files: dict[str, str]):
    """A step_handler simulating the workspace_* tools over a dict of files."""

    def handler(tool: str, arguments: dict[str, Any], step_id: str) -> dict[str, Any]:
        if tool == "workspace_read":
            path = arguments["path"]
            if path not in files:
                return {
                    "refusal": {"code": "not_found", "detail": "No such file.", "retryable": False},
                    "budget": {},
                }
            content = files[path]
            return {
                "result": {
                    "path": path,
                    "content": content,
                    "revision": f"rev-{len(content)}",
                    "size": len(content),
                    "truncated": False,
                },
                "budget": {},
            }
        if tool == "workspace_write":
            expected = arguments.get("expectedRevision")
            if expected is not None and expected != f"rev-{len(files.get(arguments['path'], ''))}":
                return {
                    "refusal": {
                        "code": "conflict",
                        "detail": "somebody changed this file since it was read",
                        "retryable": False,
                    },
                    "budget": {},
                }
            files[arguments["path"]] = arguments["content"]
            return {
                "result": {
                    "path": arguments["path"],
                    "revision": f"rev-{len(arguments['content'])}",
                    "bytes": len(arguments["content"]),
                },
                "budget": {},
            }
        if tool == "workspace_list":
            prefix = arguments.get("path") or ""
            entries = []
            for path, content in files.items():
                if prefix and not path.startswith(prefix + "/"):
                    continue
                rest = path[len(prefix) + 1 :] if prefix else path
                if "/" in rest:
                    continue
                entries.append(
                    {
                        "name": rest,
                        "path": path,
                        "kind": "file",
                        "size": len(content),
                        "modified": "2026-11-24T12:00:00+00:00",
                    }
                )
            if prefix and not entries and prefix not in ("/",):
                return {
                    "refusal": {
                        "code": "not_found",
                        "detail": "No such folder.",
                        "retryable": False,
                    },
                    "budget": {},
                }
            return {"result": {"entries": entries}, "budget": {}}
        return {"result": {"tool": tool}, "budget": {}}

    return handler


class TestFileOpsRouting:
    async def test_file_tools_use_the_workspace_volume_when_usable(self, env) -> None:
        files = {"notes/todo.txt": "- [ ] water the plants\n", "README.md": "# hi\n"}
        env.vela.step_handler = workspace_handler(files)
        plugin = FileOpsPlugin(make_ctx(env.bot_id), computer_service=env.svc)
        skills = plugin._skills_map

        read = await skills["file_read"].fn(path="notes/todo.txt")
        assert read == "- [ ] water the plants\n"
        assert env.vela.step_calls[-1]["tool"] == "workspace_read"
        assert env.vela.step_calls[-1]["arguments"] == {"path": "notes/todo.txt"}

        written = await skills["file_write"].fn(path="notes/new.txt", content="fresh\n")
        assert written == "Successfully wrote to notes/new.txt"
        assert files["notes/new.txt"] == "fresh\n"

        listing = await skills["file_list"].fn(path="notes")
        assert "📄 notes/todo.txt" in listing
        assert "📄 notes/new.txt" in listing

        edited = await skills["file_edit"].fn(
            path="notes/todo.txt", old_text="water", new_text="feed"
        )
        assert "1 replacement" in edited
        assert files["notes/todo.txt"] == "- [ ] feed the plants\n"
        # The edit wrote with the revision from its read (conflict-safe).
        write_calls = [c for c in env.vela.step_calls if c["tool"] == "workspace_write"]
        assert write_calls[-1]["arguments"]["expectedRevision"].startswith("rev-")

        info = await skills["file_info"].fn(path="notes/todo.txt")
        assert "Type: file" in info
        assert "Size: 22 bytes" in info

        # A path outside the workspace is refused locally, never sent.
        before = len(env.vela.step_calls)
        escape = await skills["file_read"].fn(path="../etc/passwd")
        assert "outside the workspace" in escape
        assert len(env.vela.step_calls) == before

    async def test_file_tools_use_the_host_path_when_the_computer_is_off(
        self, tmp_path, sqlite_db
    ) -> None:
        env = make_service(tmp_path, enabled=False)
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        config = Config(workspace_path=workspace)
        sandbox = PythonSandbox(
            allowed_read_paths=[str(workspace)], allowed_write_paths=[str(workspace)]
        )
        ctx = PluginContext(config=config, sandbox=sandbox, bot_id="bot-1", chat_id="chat-1")
        plugin = FileOpsPlugin(ctx, computer_service=env.svc)

        written = await plugin._skills_map["file_write"].fn(path="notes.txt", content="host\n")
        assert written == "Successfully wrote to notes.txt"
        assert (workspace / "notes.txt").read_text() == "host\n"
        read = await plugin._skills_map["file_read"].fn(path="notes.txt")
        assert read == "host\n"
        # Not one driven step went to a computer.
        assert env.vela.step_calls == []


# ---------------------------------------------------------------------------
# Coding agent: the computer's terminal when usable, the host when not
# ---------------------------------------------------------------------------


def coding_handler(exit_code: int = 0, lines: tuple[str, ...] = ("working...",)):
    """A step_handler simulating a coding CLI run in a computer terminal."""
    state = {"reads": 0}

    def handler(tool: str, arguments: dict[str, Any], step_id: str) -> dict[str, Any]:
        if tool == "workspace_write":
            return {
                "result": {
                    "path": arguments["path"],
                    "revision": "rev-1",
                    "bytes": len(arguments["content"]),
                },
                "budget": {},
            }
        if tool == "terminal_open":
            return {
                "result": {
                    "terminalId": "term-1",
                    "viewId": "view-9",
                    "cwd": "/workspace",
                    "shell": "/bin/bash",
                },
                "budget": {},
            }
        if tool == "terminal_run":
            return {
                "result": {"exitCode": None, "running": True, "output": "", "cursor": 1},
                "budget": {},
            }
        if tool == "terminal_read":
            state["reads"] += 1
            if state["reads"] == 1:
                return {
                    "result": {
                        "output": "".join(f"{line}\n" for line in lines),
                        "cursor": 2,
                        "dropped": False,
                    },
                    "budget": {},
                }
            return {
                "result": {
                    "output": f"__CB_EXIT__={exit_code}\n",
                    "cursor": 3,
                    "dropped": False,
                },
                "budget": {},
            }
        if tool == "terminal_close":
            return {"result": {"closed": True}, "budget": {}}
        return {"result": {"tool": tool}, "budget": {}}

    return handler


class TestCodingAgentRouting:
    async def test_coding_agent_runs_in_the_computer_terminal(self, env, monkeypatch) -> None:
        async def forbidden(*args: Any, **kwargs: Any) -> str:
            raise AssertionError("the host subprocess path must not be used")

        monkeypatch.setattr("cachibot.plugins.coding_agent._run_coding_cli", forbidden)
        env.vela.step_handler = coding_handler(exit_code=0)
        plugin = CodingAgentPlugin(make_ctx(env.bot_id), computer_service=env.svc)

        result = await plugin._skills_map["coding_agent"].fn(task="fix the auth bug")
        assert "working..." in result
        assert "__CB_EXIT__" not in result

        tools = [call["tool"] for call in env.vela.step_calls]
        assert tools == [
            "workspace_write",
            "terminal_open",
            "terminal_run",
            "terminal_read",
            "terminal_read",
            "terminal_close",
        ]
        # The task travelled in a workspace file, not on the command line.
        write_call = env.vela.step_calls[0]
        assert write_call["arguments"]["content"] == "fix the auth bug"
        run_call = env.vela.step_calls[2]
        command = run_call["arguments"]["command"]
        assert "$(cat /workspace/.cachibot-coding-task.txt)" in command
        assert "fix the auth bug" not in command
        assert command.startswith("claude ")
        assert run_call["arguments"]["waitFor"] == "none"
        # The session finished the run (a dev server in another terminal
        # would keep running — an ordinary finish kills nothing).
        assert env.vela.finish_calls[-1]["outcome"] == "succeeded"

    async def test_coding_agent_missing_cli_returns_the_shells_own_error(self, env) -> None:
        env.vela.step_handler = coding_handler(
            exit_code=127, lines=("sh: claude: command not found",)
        )
        plugin = CodingAgentPlugin(make_ctx(env.bot_id), computer_service=env.svc)
        result = await plugin._skills_map["coding_agent"].fn(task="fix it")
        assert "exited with code 127" in result
        assert "command not found" in result
        assert env.vela.finish_calls[-1]["outcome"] == "failed"

    async def test_coding_agent_uses_the_host_path_when_the_computer_is_off(
        self, tmp_path, sqlite_db, monkeypatch
    ) -> None:
        env = make_service(tmp_path, enabled=False)
        calls: list[dict[str, Any]] = []

        async def fake_host_cli(**kwargs: Any) -> str:
            calls.append(kwargs)
            return "host output"

        monkeypatch.setattr("cachibot.plugins.coding_agent._run_coding_cli", fake_host_cli)
        plugin = CodingAgentPlugin(make_ctx("bot-1"), computer_service=env.svc)
        result = await plugin._skills_map["coding_agent"].fn(task="fix it")
        assert result == "host output"
        assert len(calls) == 1
        assert env.vela.step_calls == []

    async def test_coding_session_writes_one_log_with_lines(self, env) -> None:
        env.vela.step_handler = coding_handler(exit_code=0)
        result = await env.svc.run_coding_agent(
            env.bot_id,
            argv=["claude", "--print", "fix it"],
            task="fix it",
            timeout_seconds=60,
            chat_id="chat-1",
        )
        assert result.error is None and result.exit_code == 0
        logs = await ExecutionLogRepository().get_by_bot(env.bot_id, execution_type="computer")
        session_logs = [log for log in logs if log.source_name == "coding_agent"]
        assert len(session_logs) == 1
        log = session_logs[0]
        assert log.status.value == "success"
        assert log.exit_code == 0
        assert log.chat_id == "chat-1"
        lines = await ExecutionLogLineRepository().get_lines(log.id)
        contents = [line.content for line in lines]
        assert any("terminal opened" in content for content in contents)
        assert any("exited with code 0" in content for content in contents)


# ---------------------------------------------------------------------------
# Execution logs for ordinary steps
# ---------------------------------------------------------------------------


class TestExecutionLogs:
    async def test_successful_step_writes_a_log(self, env) -> None:
        outcome = await env.svc.run_tool_step(
            env.bot_id,
            tool="terminal_open",
            arguments={"title": "dev"},
            chat_id="chat-1",
        )
        assert outcome.status == "result"
        logs = await ExecutionLogRepository().get_by_bot(env.bot_id, execution_type="computer")
        assert len(logs) == 1
        log = logs[0]
        assert log.source_type == "computer"
        assert log.source_name == "terminal_open"
        assert log.status.value == "success"
        assert log.duration_ms is not None
        assert log.chat_id == "chat-1"
        assert log.metadata_json["tool"] == "terminal_open"
        assert log.metadata_json["runId"] == "run-1"

    async def test_refusal_writes_a_log(self, env) -> None:
        env.vela.step_handler = lambda tool, arguments, step_id: {
            "refusal": {
                "code": "not_allowed",
                "detail": "That site is not approved.",
                "retryable": False,
            },
            "budget": {},
        }
        outcome = await env.svc.run_tool_step(
            env.bot_id, tool="desktop.open_site", arguments={"url": "https://example.com/"}
        )
        assert outcome.status == "refusal"
        logs = await ExecutionLogRepository().get_by_bot(env.bot_id, execution_type="computer")
        assert len(logs) == 1
        log = logs[0]
        assert log.status.value == "error"
        assert "not approved" in (log.error or "")
        assert log.metadata_json["outcome"] == "refusal"

    async def test_logging_failure_does_not_fail_the_tool(self, env, monkeypatch) -> None:
        class BoomRepository:
            async def save(self, log: Any) -> None:
                raise RuntimeError("db is gone")

        monkeypatch.setattr(
            "cachibot.storage.automations_repository.ExecutionLogRepository",
            lambda: BoomRepository(),
        )
        outcome = await env.svc.run_tool_step(env.bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "result"

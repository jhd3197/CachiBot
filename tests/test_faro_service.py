"""Tests for the Faro bridge client/service: detection, token handling,
calls, approvals polling and the no-approve guarantee.

SQLite in a tmp dir; the bridge is a fake aiohttp server bound to
127.0.0.1 inside the test — no other network, no real Faro, no Docker.
"""

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.models.bot import Bot
from cachibot.services.faro.client import FaroClient, FaroClientError
from cachibot.services.faro.service import (
    FaroRequestError,
    FaroService,
    _is_local_url,
    default_faro_data_dir,
)
from cachibot.storage.db import Base
from cachibot.storage.repository import BotRepository
from tests.faro_fakes import DENIED_TEXT, FakeFaroBridge

TOKEN = "faro-test-token-1"


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite in a tmp dir patched into the shared session maker."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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


async def make_bot() -> str:
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await BotRepository().upsert_bot(
        Bot(
            id=bot_id,
            name="Faro Bot",
            model="test/model",
            systemPrompt="You are a test bot.",
            createdAt=now,
            updatedAt=now,
        )
    )
    return bot_id


@pytest.fixture
async def bridge():
    server = FakeFaroBridge(token=TOKEN)
    await server.start()
    yield server
    await server.stop()


def write_discovery(tmp_path, payload: dict[str, Any] | None) -> None:
    path = tmp_path / "agent-endpoint.json"
    if payload is None:
        path.unlink(missing_ok=True)
    else:
        path.write_text(json.dumps(payload), encoding="utf-8")


@pytest.fixture
def faro_env(tmp_path, sqlite_db, bridge):
    """A service pointed at the fake bridge's discovery file."""
    write_discovery(tmp_path, bridge.discovery(pid=os.getpid()))
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    svc = FaroService(
        data_dir=tmp_path,
        broadcast=broadcast,
        status_ttl=0.2,
        tools_ttl=0.2,
        approvals_poll=0.05,
    )
    return SimpleNamespace(svc=svc, broadcasts=broadcasts, bridge=bridge, tmp_path=tmp_path)


async def wait_for(predicate, timeout: float = 5.0) -> None:
    deadline = asyncio.get_event_loop().time() + timeout
    while True:
        if predicate():
            return
        if asyncio.get_event_loop().time() >= deadline:
            raise AssertionError("condition not met in time")
        await asyncio.sleep(0.01)


# ---------------------------------------------------------------------------
# Detection
# ---------------------------------------------------------------------------


class TestDetection:
    async def test_missing_file_is_unavailable_with_guidance(self, tmp_path, sqlite_db) -> None:
        svc = FaroService(data_dir=tmp_path)
        status = await svc.get_status()
        assert status.available is False
        assert "Agent Bridge" in (status.reason or "")

    async def test_healthy_bridge_is_available(self, faro_env) -> None:
        status = await faro_env.svc.get_status()
        assert status.available is True
        assert status.version == "1.2.3"
        assert status.supportsApprovals is True
        assert status.reason is None

    async def test_status_is_ttl_cached(self, faro_env) -> None:
        svc = faro_env.svc
        await svc.get_status(force=True)
        before = list(faro_env.bridge.get_paths)
        await svc.get_status()  # cached: no new HTTP
        assert faro_env.bridge.get_paths == before
        await svc.get_status(force=True)  # forced: re-detects
        assert len(faro_env.bridge.get_paths) > len(before)

    async def test_stale_pid_is_unavailable(self, faro_env, monkeypatch) -> None:
        monkeypatch.setattr("cachibot.services.faro.service._pid_alive", lambda pid: False)
        status = await faro_env.svc.get_status(force=True)
        assert status.available is False
        assert "not running" in (status.reason or "")

    async def test_no_pid_is_checkable(self, faro_env) -> None:
        write_discovery(faro_env.tmp_path, faro_env.bridge.discovery(pid=None))
        status = await faro_env.svc.get_status(force=True)
        assert status.available is True

    async def test_non_localhost_url_is_rejected(self, faro_env) -> None:
        payload = faro_env.bridge.discovery()
        payload["url"] = "http://192.168.1.50:9911"
        write_discovery(faro_env.tmp_path, payload)
        status = await faro_env.svc.get_status(force=True)
        assert status.available is False

    async def test_wrong_name_is_unavailable(self, faro_env) -> None:
        faro_env.bridge.name = "some-other-bridge"
        status = await faro_env.svc.get_status(force=True)
        assert status.available is False
        assert "not Faro's Agent Bridge" in (status.reason or "")

    async def test_old_build_without_approvals_route(self, faro_env) -> None:
        faro_env.bridge.supports_approvals = False
        status = await faro_env.svc.get_status(force=True)
        assert status.available is True
        assert status.supportsApprovals is False

    async def test_dead_bridge_is_unavailable(self, faro_env) -> None:
        await faro_env.bridge.stop()
        status = await faro_env.svc.get_status(force=True)
        assert status.available is False
        assert "did not answer" in (status.reason or "")

    async def test_faro_data_dir_env_is_honored(self, tmp_path, sqlite_db, bridge, monkeypatch):
        monkeypatch.setenv("FARO_DATA_DIR", str(tmp_path / "faro-data"))
        (tmp_path / "faro-data").mkdir()
        write_discovery(tmp_path / "faro-data", bridge.discovery(pid=None))
        svc = FaroService()
        status = await svc.get_status()
        assert status.available is True

    async def test_default_data_dir_respects_xdg(self, tmp_path, monkeypatch) -> None:
        monkeypatch.delenv("FARO_DATA_DIR", raising=False)
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))
        assert default_faro_data_dir() == tmp_path / "xdg" / "com.juandenis.faro"

    def test_local_url_check(self) -> None:
        assert _is_local_url("http://127.0.0.1:8080")
        assert _is_local_url("http://localhost:8080/")
        assert not _is_local_url("http://example.com:8080")
        assert not _is_local_url("file:///etc/passwd")
        assert not _is_local_url("http://127.0.0.1.evil.example.com")


# ---------------------------------------------------------------------------
# The token: re-read on failure, never stored, never leaked
# ---------------------------------------------------------------------------


class TestTokenHandling:
    async def test_401_re_reads_the_file_and_retries_once(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        mcp_posts = faro_env.bridge.post_paths.count("/mcp")
        # Faro relaunched mid-use: the next request is rejected, the
        # re-read+retry must recover (the file already holds the new token).
        bridge.reject_next_mcp = True
        text = await svc.call_tool(bot_id, "faro_read", {"session": "s", "path": "/a"})
        assert text == "ok:faro_read"
        # initialize+call, then the retried initialize+call.
        assert faro_env.bridge.post_paths.count("/mcp") == mcp_posts + 4

    async def test_persistent_401_is_an_honest_error(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.token = "faro-test-token-2"  # the file still says token-1
        text = await svc.call_tool(bot_id, "faro_read", {})
        assert text.startswith("Error:")
        assert TOKEN not in text
        assert TOKEN not in str(faro_env.broadcasts)

    async def test_token_never_appears_in_logs_broadcasts_or_results(
        self, faro_env, caplog
    ) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        command_secret = "hunter2-production-password"
        with caplog.at_level(logging.DEBUG):
            await svc.connect(bot_id)
            bridge.blocked_tools = {"faro_exec"}
            bridge.release.clear()
            bridge.pending_approvals = [
                {
                    "requestId": "req-1",
                    "sessionId": "sess-1",
                    "sessionName": "prod",
                    "kind": "exec",
                    "command": f"deploy --password {command_secret}",
                }
            ]
            task = asyncio.create_task(
                svc.call_tool(bot_id, "faro_exec", {"command": command_secret})
            )
            await wait_for(lambda: any(b[1]["pendingApprovals"] for b in faro_env.broadcasts))
            bridge.release.set()
            result_text = await task
            await svc.deny_approval(bot_id, "req-1")
            await svc.get_bot_status(bot_id)

        haystacks: list[str] = [rec.getMessage() for rec in caplog.records]
        haystacks += [str(b) for pair in faro_env.broadcasts for b in pair]
        # The bridge token never appears in logs, broadcasts or results...
        for haystack in haystacks:
            assert TOKEN not in haystack
        assert result_text == "ok:faro_exec"
        # ...while the approval summary (user data, scoped to bot viewers)
        # really is delivered — nothing faked, nothing suppressed.
        assert any(command_secret in haystack for haystack in haystacks)


# ---------------------------------------------------------------------------
# Calls: results, refusals, errors
# ---------------------------------------------------------------------------


class TestCalls:
    async def test_call_returns_the_tools_text(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await svc.connect(bot_id)
        assert await svc.call_tool(bot_id, "faro_read", {"path": "/a"}) == "ok:faro_read"
        methods = [c["method"] for c in faro_env.bridge.mcp_calls]
        assert "initialize" in methods
        assert "notifications/initialized" not in methods  # notifications carry no id
        assert methods.count("tools/call") == 1

    async def test_call_requires_connection(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()  # never connected
        text = await svc.call_tool(bot_id, "faro_read", {})
        assert text.startswith("Error:")
        assert "not connected" in text

    async def test_denied_call_says_the_user_denied(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.deny_tools = {"faro_exec"}
        text = await svc.call_tool(bot_id, "faro_exec", {"command": "rm -rf /"})
        assert "denied or did not respond" in text
        assert "Faro" in text
        assert "rm -rf" not in text  # arguments are never repeated

    async def test_is_error_with_denial_marker_is_honest(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.error_tools = {"faro_exec"}
        # The fake's error text is not the denial marker: a plain refusal.
        text = await svc.call_tool(bot_id, "faro_exec", {})
        assert text.startswith("Faro refused:")
        assert "the remote failed" in text

    async def test_is_error_denial_marker_text(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        # Script an isError answer carrying Faro's own denial sentence.
        bridge.mcp_override = lambda _request: _async_denied()
        text = await svc.call_tool(bot_id, "faro_exec", {})
        assert "denied or did not respond" in text

    async def test_huge_results_are_capped(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.huge_tools = {"faro_read"}
        text = await svc.call_tool(bot_id, "faro_read", {})
        assert text.endswith("... (truncated)")
        assert len(text) < 7000

    async def test_bridge_away_before_call_is_honest(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        await bridge.stop()
        await svc.get_status(force=True)  # the truth: the bridge is gone
        text = await svc.call_tool(bot_id, "faro_exec", {})
        assert "Error:" in text
        assert "not available" in text
        assert svc.faro_tools_available(bot_id) is False

    async def test_call_ending_clears_the_approvals_line(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.blocked_tools = {"faro_exec"}
        bridge.release.clear()
        bridge.pending_approvals = [
            {"requestId": "req-2", "sessionName": "prod", "kind": "exec", "command": "ls"}
        ]
        task = asyncio.create_task(svc.call_tool(bot_id, "faro_exec", {}))
        await wait_for(lambda: any(b[1]["pendingApprovals"] for b in faro_env.broadcasts))
        bridge.release.set()
        await task
        final = faro_env.broadcasts[-1][1]
        assert final["pendingApprovals"] == []
        assert final["callInFlight"] is False

    def test_connection_error_text_is_honest(self) -> None:
        from cachibot.services.faro.service import _honest_call_error

        text = _honest_call_error(
            FaroClientError("connection_error", "could not reach the Faro bridge (X)")
        )
        assert "went away" in text


def web_json_denied():  # noqa: ANN202 - tiny test helper
    from aiohttp import web

    return web.json_response(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "result": {
                "content": [{"type": "text", "text": DENIED_TEXT}],
                "isError": True,
            },
        }
    )


async def _async_denied():  # noqa: ANN202 - coroutine for mcp_override
    return web_json_denied()


# ---------------------------------------------------------------------------
# Approvals: poll while in flight, clear when done, deny only
# ---------------------------------------------------------------------------


class TestApprovals:
    async def test_pending_approval_surfaces_then_clears(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.blocked_tools = {"faro_exec"}
        bridge.release.clear()

        task = asyncio.create_task(svc.call_tool(bot_id, "faro_exec", {"command": "ls"}))
        await wait_for(lambda: any(b[1]["callInFlight"] for b in faro_env.broadcasts))
        # Faro starts waiting for the human.
        bridge.pending_approvals = [
            {
                "requestId": "req-9",
                "sessionId": "sess-2",
                "sessionName": "staging",
                "kind": "exec",
                "command": "ls /var/www",
            }
        ]
        await wait_for(lambda: any(b[1]["pendingApprovals"] for b in faro_env.broadcasts))
        payload = [b for b in faro_env.broadcasts if b[1]["pendingApprovals"]][-1][1]
        approval = payload["pendingApprovals"][0]
        assert approval["requestId"] == "req-9"
        assert approval["sessionName"] == "staging"
        assert approval["kind"] == "exec"
        assert approval["summary"] == "ls /var/www"
        assert payload["botId"] == bot_id

        bridge.release.set()
        assert await task == "ok:faro_exec"
        final = faro_env.broadcasts[-1][1]
        assert final["pendingApprovals"] == []
        assert final["callInFlight"] is False

    async def test_no_poll_when_approvals_unsupported(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bridge.supports_approvals = False
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.blocked_tools = {"faro_exec"}
        bridge.release.clear()
        task = asyncio.create_task(svc.call_tool(bot_id, "faro_exec", {}))
        await wait_for(lambda: bot_id in svc._in_flight)
        before = list(bridge.get_paths)
        await asyncio.sleep(0.2)
        assert "/approvals" not in [p for p in bridge.get_paths if p not in before]
        bridge.release.set()
        await task

    async def test_deny_approval_reaches_faro(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.pending_approvals = [
            {"requestId": "req-1", "sessionName": "prod", "kind": "exec", "command": "ls"}
        ]
        await svc.deny_approval(bot_id, "req-1")
        assert bridge.deny_calls == ["req-1"]
        assert bridge.pending_approvals == []

    async def test_deny_unknown_approval_is_404(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await svc.connect(bot_id)
        with pytest.raises(FaroRequestError) as excinfo:
            await svc.deny_approval(bot_id, "req-missing")
        assert excinfo.value.status_code == 404

    async def test_deny_on_build_without_approvals_is_404(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bridge.supports_approvals = False
        bot_id = await make_bot()
        await svc.connect(bot_id)
        with pytest.raises(FaroRequestError) as excinfo:
            await svc.deny_approval(bot_id, "req-1")
        assert excinfo.value.status_code == 404

    async def test_deny_requires_connection(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        with pytest.raises(FaroRequestError) as excinfo:
            await svc.deny_approval(bot_id, "req-1")
        assert excinfo.value.status_code == 409


# ---------------------------------------------------------------------------
# The no-approve guarantee
# ---------------------------------------------------------------------------


class TestNoApprovePath:
    async def test_only_denial_is_ever_posted(self, faro_env) -> None:
        svc, bridge = faro_env.svc, faro_env.bridge
        bot_id = await make_bot()
        await svc.connect(bot_id)
        bridge.blocked_tools = {"faro_exec"}
        bridge.release.clear()
        bridge.pending_approvals = [
            {"requestId": "req-1", "sessionName": "prod", "kind": "exec", "command": "ls"}
        ]
        task = asyncio.create_task(svc.call_tool(bot_id, "faro_exec", {}))
        await wait_for(lambda: any(b[1]["pendingApprovals"] for b in faro_env.broadcasts))
        await svc.deny_approval(bot_id, "req-1")
        bridge.release.set()
        await task

        posted = [path for path in bridge.post_paths if "approvals" in path]
        assert posted == ["/approvals/deny"]
        assert bridge.deny_calls == ["req-1"]

    def test_no_approve_route_exists_in_source(self) -> None:
        """The tree must not contain any path that approves in Faro."""
        import pathlib

        root = pathlib.Path(__file__).resolve().parent.parent / "cachibot"
        offenders: list[str] = []
        for path in root.rglob("*.py"):
            text = path.read_text(encoding="utf-8")
            if "approvals/approve" in text or "approve_approval" in text:
                offenders.append(str(path))
        assert offenders == []


# ---------------------------------------------------------------------------
# Per-bot connection state
# ---------------------------------------------------------------------------


class TestConnection:
    async def test_connect_persists_the_flag(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        payload = await svc.connect(bot_id)
        assert payload["connected"] is True
        assert payload["available"] is True
        assert payload["version"] == "1.2.3"
        # The plugin's synchronous gate now sees the bot.
        assert svc.faro_tools_available(bot_id) is True

    async def test_connect_requires_a_running_bridge(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await faro_env.bridge.stop()
        with pytest.raises(FaroRequestError) as excinfo:
            await svc.connect(bot_id)
        assert excinfo.value.status_code == 409
        assert svc.faro_tools_available(bot_id) is False

    async def test_disconnect_clears_everything(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await svc.connect(bot_id)
        payload = await svc.disconnect(bot_id)
        assert payload["connected"] is False
        assert svc.faro_tools_available(bot_id) is False
        # The flag survives a service restart (it is persisted).
        assert await svc.refresh_bot(bot_id) is False
        await svc._repo.set_connected(bot_id, True)
        assert await svc.refresh_bot(bot_id) is True

    async def test_start_warms_connected_bots(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await svc.connect(bot_id)
        fresh = FaroService(
            data_dir=faro_env.tmp_path,
            status_ttl=5.0,
            approvals_poll=0.05,
        )
        await fresh.start()
        assert fresh.sync_connected(bot_id) is True
        assert fresh.faro_tools_available(bot_id) is True
        assert fresh.cached_tools(bot_id) is not None  # catalogue warmed
        await fresh.stop()

    async def test_tools_cache_is_per_bot(self, faro_env) -> None:
        svc = faro_env.svc
        bot_a = await make_bot()
        bot_b = await make_bot()
        await svc.connect(bot_a)
        tools = await svc.list_tools(bot_a)
        assert any(t["name"] == "faro_exec" for t in tools)
        # bot_b never connected: no catalogue, no tools.
        assert svc.cached_tools(bot_b) is None
        with pytest.raises(FaroRequestError):
            await svc.list_tools(bot_b)

    async def test_unexpected_client_error_propagates(self, faro_env) -> None:
        svc = faro_env.svc
        bot_id = await make_bot()
        await svc.connect(bot_id)

        async def boom(client):  # noqa: ANN001 - test double
            raise FaroClientError("rpc_error", "the bridge reported an error")

        with pytest.raises(FaroClientError):
            await svc._run(boom)


class TestClientDirect:
    """The client itself, against the fake bridge, for the error branches."""

    async def test_health_maps_a_401_to_an_error(self, bridge) -> None:
        client = FaroClient(bridge.url, TOKEN)
        data = await client.health()
        assert data["name"] == "faro-agent-bridge"
        bad = FaroClient(bridge.url, "wrong")
        with pytest.raises(FaroClientError) as excinfo:
            await bad.health()
        assert excinfo.value.code == "rpc_error"
        await client.aclose()
        await bad.aclose()

    async def test_initialize_notification_gets_202(self, bridge) -> None:
        client = FaroClient(bridge.url, TOKEN)
        await client.initialize()
        await client.aclose()

    async def test_rpc_error_object_raises(self, bridge) -> None:
        client = FaroClient(bridge.url, TOKEN)
        with pytest.raises(FaroClientError) as excinfo:
            await client._post_rpc("nope", timeout=5.0)
        assert "unknown method" in excinfo.value.detail
        await client.aclose()

    async def test_unauthorized_call_raises(self, bridge) -> None:
        client = FaroClient(bridge.url, "wrong-token")
        with pytest.raises(FaroClientError) as excinfo:
            await client.call_tool("faro_read", {})
        assert excinfo.value.code == "unauthorized"
        await client.aclose()

    async def test_non_json_body_raises(self) -> None:
        from cachibot.services.faro.client import _decode_json

        with pytest.raises(FaroClientError):
            _decode_json(b"<html>")

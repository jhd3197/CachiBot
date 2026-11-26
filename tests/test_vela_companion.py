"""Tests for the Vela companion integration.

Hermetic: tmp dirs stand in for the Vela home (VELA_DATA_DIR) and the user
home, the loopback server binds an ephemeral port on 127.0.0.1 only, and all
data sources (ws manager, computer service, repositories) are faked. Nothing
touches the real ~/.vela, a real Vela, Docker, or PostgreSQL.
"""

import asyncio
import json
import os
import re
from pathlib import Path

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

import cachibot.services.vela_companion as vc
from cachibot.api.websocket import ConnectionManager
from cachibot.services.vela_companion import VelaCompanionService

CONTRACTS_SCHEMA = Path("/home/box/work/vela-study/vela-contracts/companion-v1.schema.json")

DECLARED_WIDGET_IDS = {"needs-you", "runs"}
DECLARED_ACTION_IDS = {"approve", "deny"}
_SUMMARY_ALLOWED_KEYS = {
    "value",
    "unit",
    "delta",
    "caption",
    "progress",
    "rows",
    "actions",
    "series",
    "domain",
    "attention",
    "badge",
    "expiresAt",
}


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeNeedsYouEntry:
    """Stands in for cachibot.services.computer.service.NeedsYouItem."""

    def __init__(
        self,
        bot_id: str,
        kind: str = "attention",
        reason: str = "the computer needs a person",
        run_id: str | None = "run-1",
        request_id: str | None = None,
    ) -> None:
        self.bot_id = bot_id
        self.kind = kind
        self.reason = reason
        self.run_id = run_id
        self.request_id = request_id


class FakeComputerService:
    def __init__(self, needs_you: list | None = None) -> None:
        self._needs_you = needs_you or []
        self.respond_calls: list[tuple[str, str, str, str]] = []
        self.fail_respond: Exception | None = None

    def list_needs_you(self) -> list:
        return list(self._needs_you)

    async def respond_needs_you(
        self, bot_id: str, user_id: str, user_name: str, action: str
    ) -> dict:
        self.respond_calls.append((bot_id, user_id, user_name, action))
        if self.fail_respond is not None:
            raise self.fail_respond
        return {"ok": True}


def make_ws_manager(approvals: list[dict] | None = None) -> ConnectionManager:
    """A real ConnectionManager pre-seeded with pending approvals."""
    manager = ConnectionManager()
    for info in approvals or []:
        approval_id = info["id"]
        manager.pending_approvals[approval_id] = asyncio.Event()
        manager.approval_results[approval_id] = False
        manager.approval_info[approval_id] = {
            "id": approval_id,
            "tool": info.get("tool", "bash"),
            "action": info.get("action", "run a command"),
            "botId": info.get("botId"),
            "createdAt": "2026-11-26T00:00:00+00:00",
        }
    return manager


def fake_bot_name(name: str):
    async def resolve(bot_id: str) -> str:
        return name

    return resolve


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def vela_env(tmp_path, monkeypatch):
    """A fake Vela home in tmp; HOME points into tmp so nothing leaks."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VELA_DATA_DIR", raising=False)
    monkeypatch.delenv("CACHIBOT_VELA_COMPANION", raising=False)
    vela = tmp_path / "vela"
    vela.mkdir()
    monkeypatch.setenv("VELA_DATA_DIR", str(vela))
    return vela


@pytest.fixture
def no_vela_env(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.delenv("VELA_DATA_DIR", raising=False)
    monkeypatch.delenv("CACHIBOT_VELA_COMPANION", raising=False)
    return home


@pytest.fixture
async def companion(vela_env, monkeypatch):
    """Started service with all data sources faked empty; always torn down."""
    monkeypatch.setattr(vc, "_ws_manager", lambda: make_ws_manager())
    monkeypatch.setattr(vc, "_computer_service", lambda: FakeComputerService())
    monkeypatch.setattr(vc, "_bot_name", _async_none)
    monkeypatch.setattr(vc, "_side_tasks_needs_you", _async_empty_list)
    monkeypatch.setattr(vc, "_side_task_counts", _async_counts)
    monkeypatch.setattr(vc, "_running_executions_count", _async_zero)
    monkeypatch.setattr(vc, "_awake_computers_count", _async_zero)

    service = VelaCompanionService(monitor_interval=3600)
    await service.start()
    yield service
    await service.stop()


async def _async_none(bot_id: str) -> None:
    return None


async def _async_empty_list() -> list:
    return []


async def _async_counts() -> tuple[int, int]:
    return (0, 0)


async def _async_zero() -> int:
    return 0


async def wait_until(predicate, timeout: float = 3.0) -> None:
    """Bounded poll; raises AssertionError on timeout."""
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.01)
    raise AssertionError("condition was not met in time")


def registration_file(vela_home: Path) -> Path:
    return vela_home / "companions" / "cachibot.json"


def read_registration(vela_home: Path) -> dict:
    return json.loads(registration_file(vela_home).read_text(encoding="utf-8"))


async def registered_client(service: VelaCompanionService, vela_home: Path) -> httpx.AsyncClient:
    """An httpx client pointed at the companion loopback server with the token."""
    await wait_until(service.is_registered)
    registration = read_registration(vela_home)
    base_url = registration["endpoint"]
    return httpx.AsyncClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {registration['token']}"},
        trust_env=False,
        timeout=5.0,
    )


def check_summary_contract(widgets: dict) -> None:
    """The key rules of Vela's validate_summary, re-implemented inline."""
    assert set(widgets) <= DECLARED_WIDGET_IDS
    for summary in widgets.values():
        assert isinstance(summary, dict)
        assert len(json.dumps(summary).encode("utf-8")) <= 4096
        assert set(summary) <= _SUMMARY_ALLOWED_KEYS
        for row in summary.get("rows", []):
            assert set(row) <= {"label", "detail"}
            assert isinstance(row.get("label"), str)
        for action in summary.get("actions", []):
            assert set(action) <= {"action", "label"}
            assert action["action"] in DECLARED_ACTION_IDS
        if "attention" in summary:
            assert isinstance(summary["attention"], bool)


# ---------------------------------------------------------------------------
# Presence detection + registration file
# ---------------------------------------------------------------------------


async def test_no_vela_dir_creates_nothing(no_vela_env):
    service = VelaCompanionService(monitor_interval=3600)
    await service.start()
    try:
        await asyncio.sleep(0.05)
        assert not service.is_detected()
        assert not service.is_registered()
        assert service._server is None
        assert not (no_vela_env / ".vela").exists(), "must never create the Vela home"
        assert not (no_vela_env / "companions").exists()
    finally:
        await service.stop()
    assert not list(no_vela_env.rglob("*.json")), "no files may leak into the fake home"


async def test_registration_file_schema_and_inline_checks(companion, vela_env):
    await wait_until(companion.is_registered)
    registration = read_registration(vela_env)

    # Inline checks of the required fields and regexes (always run, also in CI
    # where the contracts checkout is missing).
    assert registration["companion"] == 1
    assert registration["id"] == "cachibot"
    assert re.fullmatch(r"^[a-z0-9]+(-[a-z0-9]+)*$", registration["id"])
    assert 1 <= len(registration["name"]) <= 40
    assert len(registration.get("description", "")) <= 200
    assert re.fullmatch(r"^[0-9]+\.[0-9]+\.[0-9]+([-+][0-9A-Za-z.-]+)?$", registration["version"])
    assert re.fullmatch(r"^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$", registration["color"])
    assert re.fullmatch(
        r"^http://(127\.0\.0\.1|localhost|\[::1\]):[1-9][0-9]{0,4}$", registration["endpoint"]
    )
    assert re.fullmatch(r"^[A-Za-z0-9_-]{32,128}$", registration["token"])
    assert registration["pid"] == os.getpid()
    assert "executable" not in registration, "Vela must not try to launch CachiBot"
    assert len(registration["widgets"]) <= 4
    assert len(registration["actions"]) <= 8
    for widget in registration["widgets"]:
        assert re.fullmatch(r"^[a-z][a-z0-9-]{0,31}$", widget["id"])
        assert widget["layout"] in {"stat", "progress", "list", "actions", "chart", "keyvalue"}
        assert widget["size"] in {"s", "m", "l"}
    for action in registration["actions"]:
        assert re.fullmatch(r"^[a-z][a-z0-9-]{0,31}$", action["id"])
        assert action["id"] in DECLARED_ACTION_IDS

    # The full schema, when the contracts checkout is present (the inline
    # checks above are the CI fallback and always run).
    if CONTRACTS_SCHEMA.exists():
        from jsonschema import Draft202012Validator

        schema = json.loads(CONTRACTS_SCHEMA.read_text(encoding="utf-8"))
        Draft202012Validator(schema).validate(registration)

    # Atomic write: no tmp siblings left behind, and the icon is our PNG.
    companions_dir = vela_env / "companions"
    assert not list(companions_dir.glob("*.tmp"))
    icon = companions_dir / "cachibot.png"
    assert icon.is_file()
    assert icon.stat().st_size <= 256 * 1024
    assert icon.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


async def test_stop_removes_registration_but_keeps_foreign_files(companion, vela_env):
    await wait_until(companion.is_registered)
    registration_path = registration_file(vela_env)

    # A foreign file (another CachiBot server's registration) must survive.
    foreign = json.loads(registration_path.read_text(encoding="utf-8"))
    foreign["token"] = "x" * 64
    registration_path.write_text(json.dumps(foreign), encoding="utf-8")

    await companion.stop()
    assert registration_path.is_file(), "a file with another token must not be deleted"

    # Our own file is removed.
    await companion.start()
    await wait_until(companion.is_registered)
    assert registration_path.is_file()
    await companion.stop()
    assert not registration_path.exists()


async def test_invalid_version_does_not_register(vela_env, monkeypatch):
    # A version that cannot satisfy the schema regex (missing patch component).
    monkeypatch.setattr(vc, "__version__", "1.0")
    service = VelaCompanionService(monitor_interval=3600)
    await service.start()
    try:
        await asyncio.sleep(0.05)
        assert not service.is_registered()
        assert service._server is None
        assert not registration_file(vela_env).exists()
    finally:
        await service.stop()


async def test_env_var_disables(vela_env, monkeypatch):
    monkeypatch.setenv("CACHIBOT_VELA_COMPANION", "0")
    service = VelaCompanionService(monitor_interval=3600)
    await service.start()
    try:
        await asyncio.sleep(0.05)
        assert not service.is_enabled()
        assert not service.is_registered()
        assert service._server is None
    finally:
        await service.stop()


# ---------------------------------------------------------------------------
# Loopback HTTP surface
# ---------------------------------------------------------------------------


async def test_http_requires_bearer_token_and_answers_status(companion, vela_env):
    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/status")
        assert response.status_code == 200
        assert response.json() == {"id": "cachibot"}
        assert companion.status_snapshot()["lastSeenAt"] is not None

    # No token at all.
    registration = read_registration(vela_env)
    async with httpx.AsyncClient(base_url=registration["endpoint"], trust_env=False) as client:
        response = await client.get("/vela/v1/status")
        assert response.status_code == 401
        assert response.json() == {"error": "Not allowed."}

    # A wrong token is also refused.
    async with httpx.AsyncClient(
        base_url=registration["endpoint"],
        headers={"Authorization": "Bearer " + "y" * 64},
        trust_env=False,
    ) as client:
        response = await client.get("/vela/v1/widgets")
        assert response.status_code == 401


async def test_unknown_action_and_unknown_route(companion, vela_env):
    async with await registered_client(companion, vela_env) as client:
        response = await client.post("/vela/v1/actions/pause")
        assert response.status_code == 404
        assert "error" in response.json()
        response = await client.get("/vela/v1/nope")
        assert response.status_code == 404


async def test_widgets_answer_passes_summary_rules(companion, vela_env):
    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        assert response.status_code == 200
        body = response.json()
        check_summary_contract(body["widgets"])

        needs_you = body["widgets"]["needs-you"]
        assert needs_you["attention"] is False
        assert needs_you["caption"] == "Nothing needs you"
        assert needs_you["rows"] == []

        runs = body["widgets"]["runs"]
        rows = {row["label"]: row["detail"] for row in runs["rows"]}
        assert rows == {
            "Side tasks running": "0",
            "Side tasks waiting": "0",
            "Runs": "0",
            "Awake computers": "0",
        }
        assert runs["caption"] == "Nothing is running right now"


# ---------------------------------------------------------------------------
# Needs-you widget content
# ---------------------------------------------------------------------------


async def test_needs_you_one_tool_approval_offers_both_buttons(companion, vela_env, monkeypatch):
    monkeypatch.setattr(
        vc, "_ws_manager", lambda: make_ws_manager([{"id": "a1", "botId": "bot-1"}])
    )
    monkeypatch.setattr(vc, "_bot_name", fake_bot_name("Finance Bot"))

    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        summary = response.json()["widgets"]["needs-you"]
        assert summary["attention"] is True
        assert summary["badge"] == "1"
        assert summary["actions"] == [
            {"action": "approve", "label": "Approve"},
            {"action": "deny", "label": "Deny"},
        ]
        assert summary["rows"][0]["label"] == "Finance Bot"
        assert "bash" in summary["rows"][0]["detail"]


async def test_needs_you_computer_item_offers_deny_only(companion, vela_env, monkeypatch):
    entry = FakeNeedsYouEntry("bot-9", kind="attention", reason="approve the file change")
    monkeypatch.setattr(vc, "_computer_service", lambda: FakeComputerService([entry]))
    monkeypatch.setattr(vc, "_bot_name", fake_bot_name("Desktop Bot"))

    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        summary = response.json()["widgets"]["needs-you"]
        assert summary["actions"] == [{"action": "deny", "label": "Deny"}]
        assert summary["rows"][0]["label"] == "Desktop Bot"
        assert summary["rows"][0]["detail"] == "approve the file change"


async def test_needs_you_two_items_offer_no_buttons(companion, vela_env, monkeypatch):
    approvals = [{"id": "a1", "botId": "bot-1"}, {"id": "a2", "botId": "bot-2"}]
    monkeypatch.setattr(vc, "_ws_manager", lambda: make_ws_manager(approvals))

    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        summary = response.json()["widgets"]["needs-you"]
        assert summary["attention"] is True
        assert summary["badge"] == "2"
        assert "actions" not in summary
        assert len(summary["rows"]) == 2


async def test_needs_you_side_task_is_display_only(companion, vela_env, monkeypatch):
    """A needs-you side task shows and counts, but is never itself actionable."""

    class FakeSideTask:
        title = "Fix the parser"
        needs_you_reason = "merge_conflict"

    async def fake_side_tasks() -> list:
        return [FakeSideTask()]

    approvals = [{"id": "a1", "botId": "bot-1"}]
    monkeypatch.setattr(vc, "_ws_manager", lambda: make_ws_manager(approvals))
    monkeypatch.setattr(vc, "_side_tasks_needs_you", fake_side_tasks)

    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        summary = response.json()["widgets"]["needs-you"]
        # The side task counts for the badge; the one approval is still the
        # single actionable item, so its buttons are offered.
        assert summary["badge"] == "2"
        assert summary["actions"] == [
            {"action": "approve", "label": "Approve"},
            {"action": "deny", "label": "Deny"},
        ]
        labels = [row["label"] for row in summary["rows"]]
        assert "Fix the parser" in labels

    # Side task alone: shown, nothing actionable, no buttons.
    monkeypatch.setattr(vc, "_ws_manager", lambda: make_ws_manager())
    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        summary = response.json()["widgets"]["needs-you"]
        assert "actions" not in summary
        assert summary["rows"][0]["label"] == "Fix the parser"


# ---------------------------------------------------------------------------
# Actions: pinning + resolution paths
# ---------------------------------------------------------------------------


async def test_approve_resolves_through_ws_manager(companion, vela_env, monkeypatch):
    manager = make_ws_manager([{"id": "a1", "botId": "bot-1"}])
    monkeypatch.setattr(vc, "_ws_manager", lambda: manager)

    async with await registered_client(companion, vela_env) as client:
        await client.get("/vela/v1/widgets")  # advertises a1
        response = await client.post("/vela/v1/actions/approve", json={})
        assert response.status_code == 200
        assert "message" in response.json()

    assert manager.approval_results["a1"] is True
    assert manager.pending_approvals["a1"].is_set()


async def test_deny_resolves_through_ws_manager(companion, vela_env, monkeypatch):
    manager = make_ws_manager([{"id": "a1", "botId": "bot-1"}])
    monkeypatch.setattr(vc, "_ws_manager", lambda: manager)

    async with await registered_client(companion, vela_env) as client:
        await client.get("/vela/v1/widgets")
        response = await client.post("/vela/v1/actions/deny", json={})
        assert response.status_code == 200

    assert manager.approval_results["a1"] is False
    assert manager.pending_approvals["a1"].is_set()


async def test_action_pins_the_advertised_item(companion, vela_env, monkeypatch):
    """a1 was advertised; a1 resolves and b1 appears -> approve must 409 and
    must NOT resolve b1."""
    manager = make_ws_manager([{"id": "a1"}])
    monkeypatch.setattr(vc, "_ws_manager", lambda: manager)

    async with await registered_client(companion, vela_env) as client:
        await client.get("/vela/v1/widgets")
        assert companion._advertised == "approval:a1"

        # a1 goes away (the agent side popped it); b1 appears in its place.
        manager.pending_approvals.pop("a1")
        manager.approval_results.pop("a1")
        manager.approval_info.pop("a1")
        manager.pending_approvals["b1"] = asyncio.Event()
        manager.approval_results["b1"] = False
        manager.approval_info["b1"] = {
            "id": "b1",
            "tool": "bash",
            "action": "run something else",
            "botId": None,
            "createdAt": "2026-11-26T00:00:00+00:00",
        }

        response = await client.post("/vela/v1/actions/approve", json={})
        assert response.status_code == 409
        assert "changed" in response.json()["error"]

    assert manager.approval_results["b1"] is False
    assert not manager.pending_approvals["b1"].is_set()


async def test_action_with_no_advertised_item_conflicts(companion, vela_env, monkeypatch):
    manager = make_ws_manager([{"id": "a1"}])
    monkeypatch.setattr(vc, "_ws_manager", lambda: manager)

    async with await registered_client(companion, vela_env) as client:
        # No widget fetch happened, so nothing was advertised.
        response = await client.post("/vela/v1/actions/approve", json={})
        assert response.status_code == 409


async def test_computer_deny_uses_existing_skip_semantics(companion, vela_env, monkeypatch):
    entry = FakeNeedsYouEntry("bot-9", request_id="req-1", run_id="run-1")
    fake = FakeComputerService([entry])
    monkeypatch.setattr(vc, "_computer_service", lambda: fake)

    async with await registered_client(companion, vela_env) as client:
        await client.get("/vela/v1/widgets")
        assert companion._advertised == "computer:bot-9:req-1"
        response = await client.post("/vela/v1/actions/deny", json={})
        assert response.status_code == 200
        assert "message" in response.json()

    assert fake.respond_calls == [("bot-9", "vela", "Vela companion", "skip")]


async def test_computer_approve_is_refused(companion, vela_env, monkeypatch):
    entry = FakeNeedsYouEntry("bot-9", request_id="req-1")
    fake = FakeComputerService([entry])
    monkeypatch.setattr(vc, "_computer_service", lambda: fake)

    async with await registered_client(companion, vela_env) as client:
        await client.get("/vela/v1/widgets")
        response = await client.post("/vela/v1/actions/approve", json={})
        assert response.status_code == 409
        assert response.json()["error"] == vc._COMPUTER_APPROVE_MESSAGE

    assert fake.respond_calls == []


# ---------------------------------------------------------------------------
# Toggle / teardown
# ---------------------------------------------------------------------------


async def test_toggle_off_removes_files_and_closes_server(companion, vela_env):
    await wait_until(companion.is_registered)
    registration = read_registration(vela_env)

    await companion.set_enabled(False)
    await wait_until(lambda: not companion.is_registered())
    assert not registration_file(vela_env).exists()
    assert not (vela_env / "companions" / "cachibot.png").exists()

    async with httpx.AsyncClient(base_url=registration["endpoint"], trust_env=False) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("/vela/v1/status")

    # Toggling back on registers again, with a fresh token.
    await companion.set_enabled(True)
    await wait_until(companion.is_registered)
    fresh = read_registration(vela_env)
    assert fresh["token"] != registration["token"]


async def test_runs_widget_reports_real_counts(companion, vela_env, monkeypatch):
    async def counts() -> tuple[int, int]:
        return (2, 1)

    monkeypatch.setattr(vc, "_side_task_counts", counts)
    monkeypatch.setattr(vc, "_running_executions_count", _async_three)
    monkeypatch.setattr(vc, "_awake_computers_count", _async_one)

    async with await registered_client(companion, vela_env) as client:
        response = await client.get("/vela/v1/widgets")
        runs = response.json()["widgets"]["runs"]
        rows = {row["label"]: row["detail"] for row in runs["rows"]}
        assert rows == {
            "Side tasks running": "2",
            "Side tasks waiting": "1",
            "Runs": "3",
            "Awake computers": "1",
        }
        assert runs["caption"] == "5 running"


async def _async_three() -> int:
    return 3


async def _async_one() -> int:
    return 1


# ---------------------------------------------------------------------------
# WebSocket regression: the approval flow still resolves through the shared method
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite in a tmp dir patched into the shared session maker (WAL on)."""
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    import cachibot.storage.db as db_mod

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
    from cachibot.storage.db import Base

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


async def test_ws_approval_flow_uses_resolve_approval(sqlite_db, auth_service, tmp_path):
    from starlette.testclient import TestClient

    from cachibot.api import websocket as ws_module
    from tests.conftest import create_test_user

    user, _ = await create_test_user(auth_service)
    token = auth_service.create_access_token(user.id, user.role.value)

    from fastapi import FastAPI

    app = FastAPI()
    app.state.workspace = tmp_path
    app.include_router(ws_module.router)

    manager = ws_module.manager
    manager.pending_approvals["ap1"] = asyncio.Event()
    manager.approval_results["ap1"] = False
    manager.approval_info["ap1"] = {
        "id": "ap1",
        "tool": "bash",
        "action": "run a command",
        "botId": None,
        "createdAt": "2026-11-26T00:00:00+00:00",
    }
    try:
        client = TestClient(app)
        with client.websocket_connect(f"/ws?token={token}") as ws:
            ws.send_json({"type": "approval", "payload": {"id": "ap1", "approved": True}})
            for _ in range(200):
                if manager.approval_results.get("ap1") is True:
                    break
                await asyncio.sleep(0.01)
            assert manager.approval_results.get("ap1") is True
            assert manager.pending_approvals["ap1"].is_set()

            # An unknown approval id is ignored, not an error.
            ws.send_json({"type": "approval", "payload": {"id": "nope", "approved": True}})
            ws.send_json({"type": "approval", "payload": {"id": "ap1", "approved": False}})
            for _ in range(200):
                if manager.approval_results.get("ap1") is False:
                    break
                await asyncio.sleep(0.01)
            assert manager.approval_results.get("ap1") is False
    finally:
        manager.pending_approvals.pop("ap1", None)
        manager.approval_results.pop("ap1", None)
        manager.approval_info.pop("ap1", None)


# ---------------------------------------------------------------------------
# HTTP API routes (settings view)
# ---------------------------------------------------------------------------


class _StubCompanionService:
    def __init__(self) -> None:
        self.enabled = True
        self.set_calls: list[bool] = []

    def is_detected(self) -> bool:
        return True

    def is_enabled(self) -> bool:
        return self.enabled

    def is_registered(self) -> bool:
        return True

    def status_snapshot(self) -> dict:
        return {
            "detected": self.is_detected(),
            "enabled": self.enabled,
            "registered": self.is_registered(),
            "lastSeenAt": "2026-11-26T00:00:00+00:00",
        }

    async def set_enabled(self, enabled: bool) -> None:
        self.set_calls.append(enabled)
        self.enabled = enabled


@pytest.fixture
async def vela_api_client(auth_service, monkeypatch):
    from fastapi import FastAPI

    from cachibot.api.routes import vela_companion

    stub = _StubCompanionService()
    monkeypatch.setattr(vela_companion, "get_vela_companion_service", lambda: stub)

    app = FastAPI()
    app.include_router(vela_companion.router)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        client.stub = stub  # type: ignore[attr-defined]
        yield client


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_status_route_any_user(sqlite_db, auth_service, vela_api_client):
    from tests.conftest import create_test_user

    user, _ = await create_test_user(auth_service)
    token = auth_service.create_access_token(user.id, user.role.value)

    response = await vela_api_client.get("/api/vela-companion/status", headers=auth(token))
    assert response.status_code == 200
    body = response.json()
    assert body == {
        "detected": True,
        "enabled": True,
        "registered": True,
        "lastSeenAt": "2026-11-26T00:00:00+00:00",
    }
    # The token and the loopback port are never exposed.
    assert "token" not in body
    assert "port" not in body
    assert "endpoint" not in body


async def test_status_route_requires_auth(vela_api_client):
    response = await vela_api_client.get("/api/vela-companion/status")
    assert response.status_code == 401


async def test_settings_route_admin_only(sqlite_db, auth_service, vela_api_client):
    from cachibot.models.auth import UserRole
    from tests.conftest import create_test_user

    user, _ = await create_test_user(auth_service, role=UserRole.USER)
    token = auth_service.create_access_token(user.id, user.role.value)
    response = await vela_api_client.put(
        "/api/vela-companion/settings", headers=auth(token), json={"enabled": False}
    )
    assert response.status_code == 403

    admin, _ = await create_test_user(
        auth_service, email="admin2@test.com", username="admin2", role=UserRole.ADMIN
    )
    admin_token = auth_service.create_access_token(admin.id, admin.role.value)
    response = await vela_api_client.put(
        "/api/vela-companion/settings", headers=auth(admin_token), json={"enabled": False}
    )
    assert response.status_code == 200
    assert response.json()["enabled"] is False
    assert vela_api_client.stub.set_calls == [False]  # type: ignore[attr-defined]

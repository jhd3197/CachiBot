"""API tests for the computer routes: bot-access rules and response shapes.

SQLite in a tmp dir, scripted FakeDockerRunner/FakeVelaClient — no Docker,
no network, no containers. The route singleton is pointed at the faked
service; broadcasts are recorded to assert the WS payload contract.
"""

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.config import ComputerConfig
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.group import BotAccessLevel
from cachibot.services.computer.runner import CommandResult
from cachibot.services.computer.service import ComputerService, container_name_for
from cachibot.storage.computer_repository import ComputerRepository
from cachibot.storage.db import Base
from cachibot.storage.group_repository import BotAccessRepository, GroupRepository
from cachibot.storage.repository import BotRepository
from cachibot.storage.user_repository import OwnershipRepository
from tests.computer_fakes import FakeClock, FakeDockerRunner, FakeVelaClient, docker_version_json
from tests.conftest import create_test_user  # noqa: F401  (re-exported helper)


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite in a tmp dir patched into the shared session maker (WAL on)."""
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
    """Faked ComputerService plus broadcast recording (same wiring as the
    service tests). One shared FakeVelaClient so tests can script Vela."""
    runner = FakeDockerRunner()
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    vela = FakeVelaClient()
    svc = ComputerService(
        runner=runner,
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=tmp_path / "tokens",
        clock=(clock := FakeClock()).now,
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
        "cachibot-vela-computer:0.3.0",
        result=lambda: CommandResult(
            [], 0 if image_built["built"] else 1, "[]" if image_built["built"] else "", ""
        ),
    )
    original_build = svc._builds._build

    async def tracking_build() -> None:
        await original_build()
        image_built["built"] = True

    svc._builds._build = tracking_build  # type: ignore[method-assign]

    env = SimpleNamespace(svc=svc, runner=runner, broadcasts=broadcasts, vela=vela, clock=clock)
    yield env
    await svc.stop()


@pytest.fixture
async def computer_client(sqlite_db, auth_service, computer_env, monkeypatch):
    """HTTP client wired to an app with only the computer routes."""
    from fastapi import FastAPI

    from cachibot.api.routes import computer

    monkeypatch.setattr("cachibot.services.computer.service._computer_service", computer_env.svc)

    app = FastAPI()
    app.include_router(computer.router, tags=["computer"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def make_bot(owner_user_id: str | None = None) -> str:
    """Create a bot (optionally owned by a user). Returns bot id."""
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await BotRepository().upsert_bot(
        Bot(
            id=bot_id,
            name="Test Bot",
            model="test/model",
            systemPrompt="You are a test bot.",
            createdAt=now,
            updatedAt=now,
        )
    )
    if owner_user_id:
        await OwnershipRepository().assign_bot_owner(
            BotOwnership(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=owner_user_id,
                created_at=now,
            )
        )
    return bot_id


async def share_bot(bot_id: str, user_id: str, level: BotAccessLevel, owner_id: str) -> None:
    """Share a bot with a user's group at the given access level."""
    group = await GroupRepository().create_group(
        f"{level.value}s-{uuid.uuid4().hex[:6]}", created_by=owner_id
    )
    await GroupRepository().add_member(group.id, user_id)
    await BotAccessRepository().share_bot(bot_id, group.id, level, granted_by=owner_id)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def wait_for(predicate, timeout: float = 5.0) -> None:
    import asyncio
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


async def port_is(bot_id: str, port: int) -> bool:
    record = await ComputerRepository().get_for_bot(bot_id)
    return record is not None and record.host_port == port


# ---------------------------------------------------------------------------
# Access rules
# ---------------------------------------------------------------------------


class TestAccess:
    async def test_requires_auth(self, computer_client) -> None:
        bot_id = await make_bot()
        resp = await computer_client.get(f"/api/bots/{bot_id}/computer")
        assert resp.status_code == 401
        resp = await computer_client.get("/api/computer/status")
        assert resp.status_code == 401

    async def test_no_access_gets_403(self, computer_client, auth_service) -> None:
        stranger, _ = await create_test_user(auth_service, email="s@test.com", username="stranger")
        token = auth_service.create_access_token(stranger.id, UserRole.USER.value)
        bot_id = await make_bot()  # owned by nobody
        resp = await computer_client.get(f"/api/bots/{bot_id}/computer", headers=auth(token))
        assert resp.status_code == 403

    async def test_viewer_can_read_but_not_wake(self, computer_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="o@test.com", username="owner1")
        viewer, _ = await create_test_user(auth_service, email="v@test.com", username="viewer1")
        viewer_token = auth_service.create_access_token(viewer.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        await share_bot(bot_id, viewer.id, BotAccessLevel.VIEWER, owner.id)

        resp = await computer_client.get(f"/api/bots/{bot_id}/computer", headers=auth(viewer_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["state"] == "off"
        assert body["available"] is True

        for action in ("wake", "sleep", "stop"):
            resp = await computer_client.post(
                f"/api/bots/{bot_id}/computer/{action}", headers=auth(viewer_token)
            )
            assert resp.status_code == 403, action

    async def test_operator_can_wake(self, computer_client, auth_service, computer_env) -> None:
        owner, _ = await create_test_user(auth_service, email="o2@test.com", username="owner2")
        operator, _ = await create_test_user(auth_service, email="op@test.com", username="op1")
        token = auth_service.create_access_token(operator.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        await share_bot(bot_id, operator.id, BotAccessLevel.OPERATOR, owner.id)

        name = container_name_for(bot_id)
        computer_env.runner.when(
            "inspect",
            "-f",
            "{{.State.Running}}",
            name,
            result=lambda: CommandResult([], 1, "", "missing"),
        )
        computer_env.runner.when("run", result=CommandResult([], 0, "", ""))
        computer_env.runner.when(
            "port", name, "7700/tcp", result=CommandResult([], 0, "127.0.0.1:49153\n", "")
        )

        resp = await computer_client.post(f"/api/bots/{bot_id}/computer/wake", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        # Never exposes the controller token or the host port.
        assert "hostPort" not in body
        assert "containerName" not in body
        assert "token" not in body
        assert body["velaVersion"] == "0.3.0"

        # Wake runs in the background; wait for the container port to land.
        await wait_for(lambda: port_is(bot_id, 49153))


class TestDockerStatus:
    async def test_status_reports_probe(self, computer_client, auth_service) -> None:
        user, _ = await create_test_user(auth_service, email="d@test.com", username="dockerstat")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        resp = await computer_client.get("/api/computer/status", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["docker_version"] == "27.3.1"
        assert body["server_os"] == "linux"
        assert body["arch"] == "x86_64"


# ---------------------------------------------------------------------------
# C2: live routes — preview, views, watch, take-over, input, needs-you
# ---------------------------------------------------------------------------


async def wake_bot(env, bot_id: str) -> None:
    """Wake a bot's computer directly through the service (scripted Docker)."""
    from tests.test_computer_service import script_container_lifecycle

    env.runner.when("build", result=["#1 [1/1] DONE"])
    script_container_lifecycle(env.runner, bot_id)
    await env.svc.wake(bot_id)
    await wait_for(lambda: port_is(bot_id, 49153))


async def make_shared_bot(auth_service, *, level: BotAccessLevel) -> tuple[str, str, str]:
    """(bot_id, owner_id, member_token) with the member at the given level."""
    owner, _ = await create_test_user(
        auth_service,
        email=f"o-{uuid.uuid4().hex[:6]}@test.com",
        username=f"o{uuid.uuid4().hex[:6]}",
    )
    member, _ = await create_test_user(
        auth_service,
        email=f"m-{uuid.uuid4().hex[:6]}@test.com",
        username=f"m{uuid.uuid4().hex[:6]}",
    )
    token = auth_service.create_access_token(member.id, UserRole.USER.value)
    bot_id = await make_bot(owner.id)
    await share_bot(bot_id, member.id, level, owner.id)
    return bot_id, owner.id, token


class TestLiveAccess:
    async def test_viewer_can_watch_and_preview_but_not_control(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        await wake_bot(computer_env, bot_id)

        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/preview", headers=auth(token)
        )
        assert resp.status_code == 200
        resp = await computer_client.get(f"/api/bots/{bot_id}/computer/views", headers=auth(token))
        assert resp.status_code == 200
        resp = await computer_client.post(f"/api/bots/{bot_id}/computer/watch", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["watchers"] == 1

        for action in ("takeover", "handback"):
            resp = await computer_client.post(
                f"/api/bots/{bot_id}/computer/{action}", headers=auth(token)
            )
            assert resp.status_code == 403, action
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/input",
            headers=auth(token),
            json={"kind": "key", "key": "enter"},
        )
        assert resp.status_code == 403
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/needs-you/respond",
            headers=auth(token),
            json={"action": "skip"},
        )
        assert resp.status_code == 403

    async def test_operator_can_drive(self, computer_client, auth_service, computer_env) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        await wake_bot(computer_env, bot_id)

        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/takeover", headers=auth(token)
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["driver"]["userId"]
        assert body["driver"]["name"]
        assert body["driver"]["since"]

        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/input",
            headers=auth(token),
            json={"kind": "click", "point": {"x": 5, "y": 6}, "button": "right"},
        )
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}
        payload = computer_env.vela.input_calls[-1]["payload"]
        assert payload["kind"] == "click"
        assert payload["button"] == "right"
        assert payload["viewId"] == "view-1"  # the focused window

        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/handback", headers=auth(token)
        )
        assert resp.status_code == 200
        assert resp.json()["driver"] is None
        assert computer_env.vela.release_calls == [("desk-1", "lease-1")]

    async def test_input_requires_takeover(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        await wake_bot(computer_env, bot_id)
        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/input",
            headers=auth(token),
            json={"kind": "key", "key": "enter"},
        )
        assert resp.status_code == 409
        assert "take over" in resp.json()["detail"]

    async def test_input_bounds_are_validated(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        await wake_bot(computer_env, bot_id)
        await computer_client.post(f"/api/bots/{bot_id}/computer/takeover", headers=auth(token))

        bad_payloads = [
            {"kind": "click"},  # no point
            {"kind": "click", "point": {"x": -1, "y": 5}},
            {"kind": "click", "point": {"x": 5, "y": 20000}},
            {"kind": "scroll", "dy": 4001},
            {"kind": "scroll", "dx": 0, "dy": 0},
            {"kind": "type"},
            {"kind": "key", "key": "k" * 40},
            {"kind": "teleport"},
        ]
        for payload in bad_payloads:
            resp = await computer_client.post(
                f"/api/bots/{bot_id}/computer/input", headers=auth(token), json=payload
            )
            assert resp.status_code == 422, payload
        assert computer_env.vela.input_calls == []


class TestPreviewRoutes:
    async def test_preview_bytes_etag_and_304(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        await wake_bot(computer_env, bot_id)

        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/preview", headers=auth(token)
        )
        assert resp.status_code == 200
        assert resp.content == b"png-1"  # no desktopFrame advertised: the window fallback
        assert resp.headers["content-type"] == "image/png"
        assert resp.headers["cache-control"] == "no-store"
        etag = resp.headers["etag"]
        assert etag == '"digest-1"'

        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/preview",
            headers={**auth(token), "If-None-Match": etag},
        )
        assert resp.status_code == 304
        assert resp.content == b""

    async def test_preview_uses_the_desktop_frame_when_advertised(
        self, computer_client, auth_service, computer_env
    ) -> None:
        from tests.test_computer_live import PROTOCOL_5_INFO

        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        computer_env.vela.info = PROTOCOL_5_INFO
        await wake_bot(computer_env, bot_id)

        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/preview", headers=auth(token)
        )
        assert resp.status_code == 200
        assert resp.content == b"desktop-png-1"
        assert resp.headers["etag"] == '"desktop-digest-1"'

    async def test_preview_not_awake_is_409_and_never_wakes(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/preview", headers=auth(token)
        )
        assert resp.status_code == 409
        assert "off" in resp.json()["detail"]
        assert computer_env.runner.calls_for("run") == []
        assert computer_env.runner.calls_for("start") == []

    async def test_views_lists_windows_and_activity(
        self, computer_client, auth_service, computer_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        computer_env.vela.viewer_status_payload = {
            "desktopId": "desk-1",
            "kind": "personal",
            "control": None,
            "task": None,
            "watchers": {"count": 1, "kinds": {"person": 1}},
            "activity": {"text": "Running npm run dev", "at": 1732473600.0, "viewId": None},
        }
        await wake_bot(computer_env, bot_id)

        resp = await computer_client.get(f"/api/bots/{bot_id}/computer/views", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["windows"] == [
            {
                "id": "view-1",
                "kind": "web",
                "title": "Example",
                "app": "example.com",
                "url": "https://example.com/",
            }
        ]
        assert body["activity"]["text"] == "Running npm run dev"

        resp = await computer_client.get(
            f"/api/bots/{bot_id}/computer/views/view-1/frame", headers=auth(token)
        )
        assert resp.status_code == 200
        assert resp.content == b"png-1"

    async def test_needs_you_respond_route(
        self, computer_client, auth_service, computer_env
    ) -> None:
        from tests.computer_fakes import events_page, make_event

        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        await wake_bot(computer_env, bot_id)
        computer_env.vela.events_handler = events_page(
            [
                make_event(
                    1,
                    "approval.waiting",
                    {"runId": "run-1", "requestId": "req-1", "summary": {"headline": "Post?"}},
                    run_id="run-1",
                )
            ]
        )
        await computer_env.svc._live_tick()

        resp = await computer_client.get(f"/api/bots/{bot_id}/computer", headers=auth(token))
        assert resp.json()["state"] == "needs_you"
        assert resp.json()["needsYou"] == "Post?"

        resp = await computer_client.post(
            f"/api/bots/{bot_id}/computer/needs-you/respond",
            headers=auth(token),
            json={"action": "skip"},
        )
        assert resp.status_code == 200
        assert resp.json()["state"] == "awake"
        assert computer_env.vela.resolve_approval_calls == [("desk-1", "req-1", "deny")]

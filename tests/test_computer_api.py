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
    service tests)."""
    runner = FakeDockerRunner()
    broadcasts: list[tuple[str, dict[str, Any]]] = []

    async def broadcast(payload: dict[str, Any], bot_id: str) -> None:
        broadcasts.append((bot_id, payload))

    svc = ComputerService(
        runner=runner,
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=tmp_path / "tokens",
        clock=(clock := FakeClock()).now,
        monotonic=clock.monotonic,
        vela_factory=lambda port, token: FakeVelaClient(),
        broadcast=broadcast,
        cli_resolver=lambda: runner.cli,
        health_timeout=5.0,
        health_poll=0.001,
        idle_poll=3600.0,
    )
    runner.when("version", result=CommandResult([], 0, docker_version_json(), ""))
    image_built = {"built": False}
    runner.when(
        "image",
        "inspect",
        "cachibot-vela-computer:0.2.0",
        result=lambda: CommandResult(
            [], 0 if image_built["built"] else 1, "[]" if image_built["built"] else "", ""
        ),
    )
    original_build = svc._builds._build

    async def tracking_build() -> None:
        await original_build()
        image_built["built"] = True

    svc._builds._build = tracking_build  # type: ignore[method-assign]

    env = SimpleNamespace(svc=svc, runner=runner, broadcasts=broadcasts)
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
        assert body["velaVersion"] == "0.2.0"

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

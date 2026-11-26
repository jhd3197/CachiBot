"""API tests for the Faro routes: access rules, response shapes and the
deny flow.

SQLite in a tmp dir; the bridge is the fake aiohttp server on 127.0.0.1;
the route singleton is pointed at a service built on that fake.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.faro import FaroApproval
from cachibot.models.group import BotAccessLevel
from cachibot.services.faro.service import FaroService
from cachibot.storage.db import Base
from cachibot.storage.group_repository import BotAccessRepository, GroupRepository
from cachibot.storage.repository import BotRepository
from cachibot.storage.user_repository import OwnershipRepository
from tests.conftest import create_test_user  # noqa: F401  (re-exported helper)
from tests.faro_fakes import FakeFaroBridge

TOKEN = "faro-test-token-1"


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
async def bridge():
    server = FakeFaroBridge(token=TOKEN)
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def faro_env(tmp_path, sqlite_db, bridge):
    (tmp_path / "agent-endpoint.json").write_text(
        json.dumps(bridge.discovery(pid=os.getpid())), encoding="utf-8"
    )
    svc = FaroService(data_dir=tmp_path, status_ttl=5.0, approvals_poll=0.05)
    return SimpleNamespace(svc=svc, bridge=bridge)


@pytest.fixture
async def faro_client(sqlite_db, auth_service, faro_env, monkeypatch):
    """HTTP client wired to an app with only the faro routes."""
    from fastapi import FastAPI

    from cachibot.api.routes import faro

    monkeypatch.setattr("cachibot.services.faro.service._faro_service", faro_env.svc)

    app = FastAPI()
    app.include_router(faro.router, tags=["faro"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def make_bot(owner_user_id: str | None = None) -> str:
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
    group = await GroupRepository().create_group(
        f"{level.value}s-{uuid.uuid4().hex[:6]}", created_by=owner_id
    )
    await GroupRepository().add_member(group.id, user_id)
    await BotAccessRepository().share_bot(bot_id, group.id, level, granted_by=owner_id)


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


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


# ---------------------------------------------------------------------------
# Access rules
# ---------------------------------------------------------------------------


class TestAccess:
    async def test_requires_auth(self, faro_client) -> None:
        bot_id = await make_bot()
        resp = await faro_client.get("/api/integrations/faro/status")
        assert resp.status_code == 401
        resp = await faro_client.get(f"/api/bots/{bot_id}/faro")
        assert resp.status_code == 401
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect")
        assert resp.status_code == 401
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/disconnect")
        assert resp.status_code == 401
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/approvals/r1/deny")
        assert resp.status_code == 401

    async def test_stranger_gets_403(self, faro_client, auth_service) -> None:
        stranger, _ = await create_test_user(auth_service, email="s@test.com", username="stranger")
        token = auth_service.create_access_token(stranger.id, UserRole.USER.value)
        bot_id = await make_bot()
        resp = await faro_client.get(f"/api/bots/{bot_id}/faro", headers=auth(token))
        assert resp.status_code == 403
        resp = await faro_client.post(
            f"/api/bots/{bot_id}/faro/approvals/r1/deny", headers=auth(token)
        )
        assert resp.status_code == 403

    async def test_viewer_can_read_but_not_connect_or_deny(self, faro_client, auth_service) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.VIEWER)
        resp = await faro_client.get(f"/api/bots/{bot_id}/faro", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is False
        assert body["available"] is True

        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(token))
        assert resp.status_code == 403
        resp = await faro_client.post(
            f"/api/bots/{bot_id}/faro/approvals/r1/deny", headers=auth(token)
        )
        assert resp.status_code == 403

    async def test_editor_can_connect_disconnect(self, faro_client, auth_service, faro_env) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.EDITOR)
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["version"] == "1.2.3"
        assert body["supportsApprovals"] is True
        assert "token" not in body
        assert "url" not in body
        assert "pid" not in body
        assert TOKEN not in resp.text

        # Disconnect is allowed for anyone with bot access.
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/disconnect", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["connected"] is False
        assert faro_env.svc.faro_tools_available(bot_id) is False

    async def test_operator_can_deny(self, faro_client, auth_service, faro_env) -> None:
        bot_id, owner_id, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        owner_token = auth_service.create_access_token(owner_id, UserRole.USER.value)
        await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(owner_token))
        faro_env.bridge.pending_approvals = [
            {"requestId": "req-1", "sessionName": "prod", "kind": "exec", "command": "ls"}
        ]
        resp = await faro_client.post(
            f"/api/bots/{bot_id}/faro/approvals/req-1/deny", headers=auth(token)
        )
        assert resp.status_code == 200
        assert resp.json() == {"denied": True}
        assert faro_env.bridge.deny_calls == ["req-1"]

    async def test_deny_unknown_approval_is_404(self, faro_client, auth_service) -> None:
        bot_id, owner_id, token = await make_shared_bot(auth_service, level=BotAccessLevel.OPERATOR)
        owner_token = auth_service.create_access_token(owner_id, UserRole.USER.value)
        await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(owner_token))
        resp = await faro_client.post(
            f"/api/bots/{bot_id}/faro/approvals/req-missing/deny", headers=auth(token)
        )
        assert resp.status_code == 404

    async def test_connect_requires_a_running_bridge(
        self, faro_client, auth_service, faro_env
    ) -> None:
        bot_id, _, token = await make_shared_bot(auth_service, level=BotAccessLevel.EDITOR)
        await faro_env.bridge.stop()
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(token))
        assert resp.status_code == 409
        assert "Faro" in resp.json()["detail"]

    async def test_owner_can_connect(self, faro_client, auth_service) -> None:
        owner, _ = await create_test_user(auth_service, email="ow@test.com", username="ownerow")
        token = auth_service.create_access_token(owner.id, UserRole.USER.value)
        bot_id = await make_bot(owner.id)
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(token))
        assert resp.status_code == 200
        assert resp.json()["connected"] is True

    async def test_admin_can_connect_any_bot(self, faro_client, auth_service) -> None:
        admin, _ = await create_test_user(
            auth_service,
            email="ad@test.com",
            username="adminad",
            role=UserRole.ADMIN,
        )
        token = auth_service.create_access_token(admin.id, UserRole.ADMIN.value)
        bot_id = await make_bot()  # owned by nobody
        resp = await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(token))
        assert resp.status_code == 200


class TestStatusRoute:
    async def test_global_status(self, faro_client, auth_service) -> None:
        user, _ = await create_test_user(auth_service, email="g@test.com", username="globalstat")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        resp = await faro_client.get("/api/integrations/faro/status", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is True
        assert body["version"] == "1.2.3"
        assert body["supportsApprovals"] is True
        assert "token" not in body
        assert TOKEN not in resp.text

    async def test_global_status_unavailable(self, faro_client, auth_service, faro_env) -> None:
        user, _ = await create_test_user(auth_service, email="u2@test.com", username="unavail")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        await faro_env.bridge.stop()
        resp = await faro_client.get("/api/integrations/faro/status", headers=auth(token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["available"] is False
        assert body["reason"]

    async def test_bot_status_carries_pending_approvals(
        self, faro_client, auth_service, faro_env
    ) -> None:
        bot_id, _, editor_token = await make_shared_bot(auth_service, level=BotAccessLevel.EDITOR)
        viewer, _ = await create_test_user(auth_service, email="v2@test.com", username="viewer2")
        viewer_token = auth_service.create_access_token(viewer.id, UserRole.USER.value)
        owner_id = await _owner_id(bot_id)
        await share_bot(bot_id, viewer.id, BotAccessLevel.VIEWER, owner_id)
        await faro_client.post(f"/api/bots/{bot_id}/faro/connect", headers=auth(editor_token))
        # The service holds one pending approval (as it does while a call is
        # in flight); the status route serializes it for bot viewers.
        faro_env.svc._set_pending(
            bot_id,
            [
                FaroApproval(
                    requestId="req-7",
                    sessionId="s1",
                    sessionName="prod",
                    kind="exec",
                    summary="ls /var/www",
                )
            ],
        )
        resp = await faro_client.get(f"/api/bots/{bot_id}/faro", headers=auth(viewer_token))
        assert resp.status_code == 200
        body = resp.json()
        assert body["connected"] is True
        assert body["pendingApprovals"] == [
            {
                "requestId": "req-7",
                "sessionId": "s1",
                "sessionName": "prod",
                "kind": "exec",
                "summary": "ls /var/www",
            }
        ]
        assert TOKEN not in resp.text


async def _owner_id(bot_id: str) -> str:
    from cachibot.storage.user_repository import OwnershipRepository

    owner = await OwnershipRepository().get_bot_owner(bot_id)
    assert owner is not None
    return owner

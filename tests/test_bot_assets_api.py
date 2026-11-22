"""Tests for the bot-level assets endpoint.

Covers:
- GET /api/bots/{bot_id}/assets requires auth (401 without a token)
- It returns the repository rows as AssetResponse (ownerId = the chat)
- The limit param defaults to 200, is passed to the repository, and
  rejects values above the 500 cap with 422

The repository and the user lookup are mocked, so these tests run without
PostgreSQL.
"""

import uuid
from datetime import datetime, timezone

import pytest
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from httpx import ASGITransport, AsyncClient

from cachibot.api import auth as auth_mod
from cachibot.models.asset import Asset
from cachibot.models.auth import User, UserRole


def _asset(asset_id: str, chat_id: str, name: str, **kwargs: object) -> Asset:
    return Asset(
        id=asset_id,
        owner_type="chat",
        owner_id=chat_id,
        name=name,
        original_filename=name,
        content_type="text/html",
        size_bytes=42,
        storage_path=f"/tmp/{asset_id}",
        created_at=datetime.now(timezone.utc),
        **kwargs,
    )


class _FakeAssetRepo:
    """Records calls and returns canned rows for get_by_bot."""

    def __init__(self, rows: list[Asset]) -> None:
        self.rows = rows
        self.calls: list[tuple[str, int]] = []

    async def get_by_bot(self, bot_id: str, limit: int = 200) -> list[Asset]:
        self.calls.append((bot_id, limit))
        return self.rows[:limit]


@pytest.fixture
def fake_repo() -> _FakeAssetRepo:
    return _FakeAssetRepo(
        [
            _asset("asset-2", "chat-1", "index.html", uploaded_by_bot_id="bot-1"),
            _asset("asset-1", "chat-2", "notes.csv", uploaded_by_user_id="user-1"),
        ]
    )


@pytest.fixture
async def bot_assets_client(monkeypatch, fake_repo: _FakeAssetRepo):
    """Client with the assets router mounted; repo + auth user mocked."""
    from cachibot.api.routes import assets as assets_routes

    monkeypatch.setattr(assets_routes, "asset_repo", fake_repo)

    fake_user = User(
        id=str(uuid.uuid4()),
        email="viewer@test.com",
        username="viewer",
        role=UserRole.ADMIN,  # admins bypass the ownership lookup (no DB)
        created_at=datetime.now(timezone.utc),
    )

    async def fake_get_current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(auth_mod.security),
    ) -> User:
        if credentials is None:
            raise HTTPException(status_code=401, detail="Not authenticated")
        return fake_user

    app = FastAPI()
    app.include_router(assets_routes.chat_asset_router)
    app.dependency_overrides[auth_mod.get_current_user] = fake_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestListBotAssets:
    async def test_requires_auth(self, bot_assets_client):
        resp = await bot_assets_client.get(f"/api/bots/{uuid.uuid4()}/assets")
        assert resp.status_code == 401

    async def test_lists_assets(self, bot_assets_client, fake_repo: _FakeAssetRepo):
        bot_id = str(uuid.uuid4())
        resp = await bot_assets_client.get(
            f"/api/bots/{bot_id}/assets",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert [row["id"] for row in data] == ["asset-2", "asset-1"]
        # ownerId carries the chat id so the UI can group/download per chat
        assert data[0]["ownerId"] == "chat-1"
        assert data[0]["name"] == "index.html"
        assert data[0]["uploadedByBotId"] == "bot-1"
        assert data[1]["uploadedByUserId"] == "user-1"
        assert fake_repo.calls == [(bot_id, 200)]

    async def test_limit_is_passed_through(self, bot_assets_client, fake_repo: _FakeAssetRepo):
        bot_id = str(uuid.uuid4())
        resp = await bot_assets_client.get(
            f"/api/bots/{bot_id}/assets?limit=5",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 200
        assert fake_repo.calls == [(bot_id, 5)]

    @pytest.mark.parametrize("limit", ["0", "501"])
    async def test_limit_out_of_range_is_422(
        self, bot_assets_client, fake_repo: _FakeAssetRepo, limit: str
    ):
        resp = await bot_assets_client.get(
            f"/api/bots/{uuid.uuid4()}/assets?limit={limit}",
            headers={"Authorization": "Bearer test-token"},
        )
        assert resp.status_code == 422
        assert fake_repo.calls == []

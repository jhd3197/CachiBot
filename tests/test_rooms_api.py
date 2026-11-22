"""Tests for rooms API endpoints.

Covers:
- GET /api/rooms requires auth (401 without token)
- GET /api/rooms lists rooms with messageCount and lastMessage
- GET /api/rooms returns lastMessage=None for rooms with no messages
- GET /api/rooms/{room_id} includes the room's last message
- Non-members cannot read a room (404)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from httpx import ASGITransport, AsyncClient

from cachibot.models.room import (
    Room,
    RoomBot,
    RoomMember,
    RoomMemberRole,
    RoomMessage,
    RoomSenderType,
)
from cachibot.storage import db
from cachibot.storage.models.bot import Bot as BotModel
from cachibot.storage.room_repository import (
    RoomBotRepository,
    RoomMemberRepository,
    RoomMessageRepository,
    RoomRepository,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


@pytest.fixture
async def rooms_client(api_client, auth_service):
    """Async HTTP client with the rooms router mounted (mirrors api_client)."""
    from fastapi import FastAPI

    from cachibot.api.routes import rooms

    app = FastAPI()
    app.include_router(rooms.router, tags=["rooms"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def _seed_bot(bot_id: str) -> None:
    """Insert a bot row directly (rooms require 2-4 existing bots)."""
    now = datetime.now(timezone.utc)
    async with db.ensure_initialized()() as session:
        session.add(
            BotModel(
                id=bot_id,
                name=f"Bot {bot_id[:8]}",
                system_prompt="You are a test bot.",
                model="openai/gpt-4o",
                created_at=now,
                updated_at=now,
            )
        )
        await session.commit()


async def _seed_room(creator_id: str, creator_username: str) -> Room:
    """Create a room with the creator as member and two bots."""
    now = datetime.now(timezone.utc)
    room = Room(
        id=str(uuid.uuid4()),
        title=f"Room {now.microsecond}",
        description=None,
        creator_id=creator_id,
        max_bots=4,
        created_at=now,
        updated_at=now,
    )
    await RoomRepository().create_room(room)
    await RoomMemberRepository().add_member(
        RoomMember(
            room_id=room.id,
            user_id=creator_id,
            username=creator_username,
            role=RoomMemberRole.CREATOR,
            joined_at=now,
        )
    )
    bot_repo = RoomBotRepository()
    for _ in range(2):
        bot_id = str(uuid.uuid4())
        await _seed_bot(bot_id)
        await bot_repo.add_bot(
            RoomBot(room_id=room.id, bot_id=bot_id, bot_name="Test Bot", added_at=now)
        )
    return room


async def _seed_message(room_id: str, content: str, minutes_ago: int = 0) -> RoomMessage:
    """Insert a user message into a room."""
    message = RoomMessage(
        id=str(uuid.uuid4()),
        room_id=room_id,
        sender_type=RoomSenderType.USER,
        sender_id="user-1",
        sender_name="testuser",
        content=content,
        timestamp=datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
    )
    await RoomMessageRepository().save_message(message)
    return message


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TestRoomsAuth:
    async def test_list_rooms_requires_auth(self, rooms_client):
        resp = await rooms_client.get("/api/rooms")
        assert resp.status_code == 401

    async def test_get_room_requires_auth(self, rooms_client):
        resp = await rooms_client.get(f"/api/rooms/{uuid.uuid4()}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# List rooms
# ---------------------------------------------------------------------------


class TestListRooms:
    async def test_list_includes_last_message(self, rooms_client, regular_user_with_token):
        """GET /api/rooms returns the most recent message per room."""
        user, token = regular_user_with_token
        room = await _seed_room(user.id, user.username)
        await _seed_message(room.id, "older", minutes_ago=10)
        latest = await _seed_message(room.id, "newest", minutes_ago=1)

        resp = await rooms_client.get("/api/rooms", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1

        entry = data[0]
        assert entry["id"] == room.id
        assert entry["messageCount"] == 2
        assert entry["lastMessage"] is not None
        assert entry["lastMessage"]["id"] == latest.id
        assert entry["lastMessage"]["content"] == "newest"
        assert entry["lastMessage"]["senderName"] == "testuser"

    async def test_list_empty_room_has_no_last_message(self, rooms_client, regular_user_with_token):
        """Rooms without messages report lastMessage=None (never faked)."""
        user, token = regular_user_with_token
        await _seed_room(user.id, user.username)

        resp = await rooms_client.get("/api/rooms", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["messageCount"] == 0
        assert data[0]["lastMessage"] is None

    async def test_list_excludes_non_member_rooms(
        self, rooms_client, regular_user_with_token, admin_user_with_token
    ):
        """Rooms the user is not a member of are not listed."""
        admin, _ = admin_user_with_token
        user, token = regular_user_with_token
        await _seed_room(admin.id, admin.username)

        resp = await rooms_client.get("/api/rooms", headers=_auth(token))
        assert resp.status_code == 200
        assert resp.json() == []


# ---------------------------------------------------------------------------
# Get room
# ---------------------------------------------------------------------------


class TestGetRoom:
    async def test_get_room_includes_last_message(self, rooms_client, regular_user_with_token):
        user, token = regular_user_with_token
        room = await _seed_room(user.id, user.username)
        await _seed_message(room.id, "hello room")

        resp = await rooms_client.get(f"/api/rooms/{room.id}", headers=_auth(token))
        assert resp.status_code == 200
        data = resp.json()
        assert data["lastMessage"] is not None
        assert data["lastMessage"]["content"] == "hello room"

    async def test_get_room_not_member(self, rooms_client, regular_user_with_token, auth_service):
        """A user who is not a member gets 404 (no room existence leak)."""
        user, token = regular_user_with_token
        room = await _seed_room(user.id, user.username)

        from tests.conftest import create_test_user

        outsider, _ = await create_test_user(
            auth_service, email="outsider@test.com", username="outsider"
        )
        outsider_token = auth_service.create_access_token(outsider.id, outsider.role.value)

        resp = await rooms_client.get(f"/api/rooms/{room.id}", headers=_auth(outsider_token))
        assert resp.status_code == 404

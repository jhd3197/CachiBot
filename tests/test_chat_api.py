"""Tests for chat API endpoints.

Covers:
- Chat history retrieval (GET /chat/history)
- Chat history deletion returns 204 with no body (DELETE /chat/history)
- Auth is required for all chat endpoints (401 without token)
"""

import uuid
from datetime import datetime, timezone

from cachibot.models.chat import ChatMessage, MessageRole
from cachibot.storage.repository import MessageRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _seed_messages(count: int = 3) -> list[str]:
    """Insert test messages into the database. Returns list of message IDs."""
    repo = MessageRepository()
    ids = []
    for i in range(count):
        msg_id = str(uuid.uuid4())
        await repo.save_message(
            ChatMessage(
                id=msg_id,
                role=MessageRole.USER,
                content=f"Test message {i}",
                timestamp=datetime.now(timezone.utc),
            )
        )
        ids.append(msg_id)
    return ids


# ---------------------------------------------------------------------------
# Chat History
# ---------------------------------------------------------------------------


class TestChatHistory:
    """Test GET /chat/history endpoint."""

    async def test_get_history_returns_messages(self, api_client, regular_user_with_token):
        """GET /chat/history returns seeded messages."""
        _, token = regular_user_with_token

        # Seed some messages
        msg_ids = await _seed_messages(3)

        resp = await api_client.get(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "messages" in data
        assert "total" in data
        assert data["total"] >= 3

        # Verify our messages are in the response
        returned_ids = [m["id"] for m in data["messages"]]
        for mid in msg_ids:
            assert mid in returned_ids

    async def test_get_history_empty(self, api_client, regular_user_with_token):
        """GET /chat/history with no messages returns empty list."""
        _, token = regular_user_with_token

        resp = await api_client.get(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["messages"] == []
        assert data["total"] == 0


# ---------------------------------------------------------------------------
# Chat Deletion
# ---------------------------------------------------------------------------


class TestChatDeletion:
    """Test DELETE /chat/history endpoint."""

    async def test_delete_history_returns_204_no_body(self, api_client, regular_user_with_token):
        """DELETE /chat/history returns 204 with no response body."""
        _, token = regular_user_with_token

        # Seed messages so there's something to delete
        await _seed_messages(2)

        resp = await api_client.delete(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 204
        # 204 No Content must have no body (or empty body)
        assert resp.content == b""

        # Verify messages were actually deleted
        resp2 = await api_client.get(
            "/api/chat/history",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["total"] == 0


# ---------------------------------------------------------------------------
# Auth Required
# ---------------------------------------------------------------------------


class TestChatAuthRequired:
    """Test that chat endpoints require authentication."""

    async def test_get_history_without_token_returns_401(self, api_client):
        """GET /chat/history without Authorization header returns 401."""
        resp = await api_client.get("/api/chat/history")
        assert resp.status_code == 401

    async def test_delete_history_without_token_returns_401(self, api_client):
        """DELETE /chat/history without Authorization header returns 401."""
        resp = await api_client.delete("/api/chat/history")
        assert resp.status_code == 401

    async def test_post_chat_without_token_returns_401(self, api_client):
        """POST /chat without Authorization header returns 401."""
        resp = await api_client.post(
            "/api/chat",
            json={"message": "hello"},
        )
        assert resp.status_code == 401

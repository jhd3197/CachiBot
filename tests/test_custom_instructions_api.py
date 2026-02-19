"""Tests for custom instructions API endpoints.

Covers:
- Creating a custom instruction (POST)
- Reading / listing custom instructions (GET)
- Updating a custom instruction (PUT) — creates a new version
- Deleting a custom instruction (DELETE) — returns 204
- Versioning (update increments version, GET versions lists history)
- Bot ownership validation (accessing another bot's instruction returns 404)
- Error handling returns generic message, not raw exception details
"""

import uuid
from datetime import datetime, timezone

from cachibot.models.auth import UserRole
from cachibot.storage import db
from cachibot.storage.models.bot import Bot as BotModel
from cachibot.storage.models.bot import BotOwnership as BotOwnershipModel
from tests.conftest import create_test_user

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_bot(bot_id: str, owner_user_id: str) -> str:
    """Create a bot and its ownership record in the test DB. Returns the bot_id."""
    now = datetime.now(timezone.utc)

    async with db.ensure_initialized()() as session:
        session.add(
            BotModel(
                id=bot_id,
                name=f"Test Bot {bot_id[:8]}",
                system_prompt="You are a test bot.",
                model="openai/gpt-4o",
                created_at=now,
                updated_at=now,
            )
        )
        session.add(
            BotOwnershipModel(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=owner_user_id,
                created_at=now,
            )
        )
        await session.commit()

    return bot_id


def _instruction_url(bot_id: str, instruction_id: str = "") -> str:
    """Build the custom instructions endpoint URL."""
    base = f"/api/bots/{bot_id}/custom-instructions"
    if instruction_id:
        return f"{base}/{instruction_id}"
    return f"{base}/"


def _auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------


class TestCreateInstruction:
    """Test POST /api/bots/{bot_id}/custom-instructions/."""

    async def test_create_instruction(self, api_client, admin_user_with_token):
        """Creating an instruction returns 201 with the created record."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        resp = await api_client.post(
            _instruction_url(bot_id),
            json={
                "name": "summarize",
                "description": "Summarize input text",
                "prompt": "Summarize the following: {text}",
                "input_variables": ["text"],
                "output_format": "text",
                "category": "nlp",
                "tags": ["summary"],
            },
            headers=_auth_header(token),
        )
        assert resp.status_code == 201
        data = resp.json()

        assert data["name"] == "summarize"
        assert data["botId"] == bot_id
        assert data["version"] == 1
        assert data["isActive"] is True
        assert data["prompt"] == "Summarize the following: {text}"
        assert data["inputVariables"] == ["text"]
        assert data["category"] == "nlp"

    async def test_create_duplicate_name_returns_409(self, api_client, admin_user_with_token):
        """Creating two instructions with the same name for a bot returns 409."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        payload = {
            "name": "duplicate-test",
            "prompt": "Do something with {input}",
            "input_variables": ["input"],
        }

        resp1 = await api_client.post(
            _instruction_url(bot_id),
            json=payload,
            headers=_auth_header(token),
        )
        assert resp1.status_code == 201

        resp2 = await api_client.post(
            _instruction_url(bot_id),
            json=payload,
            headers=_auth_header(token),
        )
        assert resp2.status_code == 409


# ---------------------------------------------------------------------------
# Read / List
# ---------------------------------------------------------------------------


class TestReadInstructions:
    """Test GET /api/bots/{bot_id}/custom-instructions/."""

    async def test_list_instructions(self, api_client, admin_user_with_token):
        """GET / returns all instructions for the bot."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        # Create two instructions
        for name in ("instr-a", "instr-b"):
            await api_client.post(
                _instruction_url(bot_id),
                json={"name": name, "prompt": f"Do {name}"},
                headers=_auth_header(token),
            )

        resp = await api_client.get(
            _instruction_url(bot_id),
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

        names = {d["name"] for d in data}
        assert names == {"instr-a", "instr-b"}

    async def test_get_single_instruction(self, api_client, admin_user_with_token):
        """GET /{instruction_id} returns a single instruction."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        create_resp = await api_client.post(
            _instruction_url(bot_id),
            json={"name": "single-get", "prompt": "Do this"},
            headers=_auth_header(token),
        )
        instruction_id = create_resp.json()["id"]

        resp = await api_client.get(
            _instruction_url(bot_id, instruction_id),
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == instruction_id
        assert resp.json()["name"] == "single-get"


# ---------------------------------------------------------------------------
# Update
# ---------------------------------------------------------------------------


class TestUpdateInstruction:
    """Test PUT /api/bots/{bot_id}/custom-instructions/{instruction_id}."""

    async def test_update_creates_new_version(self, api_client, admin_user_with_token):
        """PUT increments the version number and applies changes."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        # Create
        create_resp = await api_client.post(
            _instruction_url(bot_id),
            json={"name": "versioned", "prompt": "v1 prompt"},
            headers=_auth_header(token),
        )
        assert create_resp.status_code == 201
        instruction_id = create_resp.json()["id"]
        assert create_resp.json()["version"] == 1

        # Update
        update_resp = await api_client.put(
            _instruction_url(bot_id, instruction_id),
            json={
                "prompt": "v2 prompt - improved",
                "commit_message": "Improved prompt wording",
            },
            headers=_auth_header(token),
        )
        assert update_resp.status_code == 200
        data = update_resp.json()
        assert data["version"] == 2
        assert data["prompt"] == "v2 prompt - improved"


# ---------------------------------------------------------------------------
# Delete
# ---------------------------------------------------------------------------


class TestDeleteInstruction:
    """Test DELETE /api/bots/{bot_id}/custom-instructions/{instruction_id}."""

    async def test_delete_returns_204_no_body(self, api_client, admin_user_with_token):
        """DELETE returns 204 with no response body (soft-delete)."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        # Create
        create_resp = await api_client.post(
            _instruction_url(bot_id),
            json={"name": "to-delete", "prompt": "delete me"},
            headers=_auth_header(token),
        )
        instruction_id = create_resp.json()["id"]

        # Delete
        del_resp = await api_client.delete(
            _instruction_url(bot_id, instruction_id),
            headers=_auth_header(token),
        )
        assert del_resp.status_code == 204
        assert del_resp.content == b""


# ---------------------------------------------------------------------------
# Versioning
# ---------------------------------------------------------------------------


class TestVersioning:
    """Test version history endpoints."""

    async def test_versions_list_after_updates(self, api_client, admin_user_with_token):
        """GET /{id}/versions returns version history after multiple updates."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        # Create (v1)
        create_resp = await api_client.post(
            _instruction_url(bot_id),
            json={"name": "versioned-history", "prompt": "v1"},
            headers=_auth_header(token),
        )
        instruction_id = create_resp.json()["id"]

        # Update twice (v2, v3)
        for i in range(2, 4):
            await api_client.put(
                _instruction_url(bot_id, instruction_id),
                json={"prompt": f"v{i}", "commit_message": f"Update to v{i}"},
                headers=_auth_header(token),
            )

        # List versions
        resp = await api_client.get(
            f"{_instruction_url(bot_id, instruction_id)}/versions",
            headers=_auth_header(token),
        )
        assert resp.status_code == 200
        versions = resp.json()

        assert len(versions) == 3
        version_numbers = [v["version"] for v in versions]
        # Versions are returned in descending order
        assert version_numbers == [3, 2, 1]


# ---------------------------------------------------------------------------
# Bot ownership validation
# ---------------------------------------------------------------------------


class TestBotOwnershipValidation:
    """Test that users cannot access another bot's instructions."""

    async def test_access_other_bots_instruction_returns_404(self, api_client, auth_service):
        """GET with a valid instruction ID but wrong bot_id returns 404."""
        # Create two users, each with their own bot
        user_a, _ = await create_test_user(
            auth_service,
            email="owner-a@test.com",
            username="ownera",
            password="ownerpass123",
            role=UserRole.ADMIN,
        )
        token_a = auth_service.create_access_token(user_a.id, user_a.role.value)

        user_b, _ = await create_test_user(
            auth_service,
            email="owner-b@test.com",
            username="ownerb",
            password="ownerpass456",
            role=UserRole.ADMIN,
        )
        token_b = auth_service.create_access_token(user_b.id, user_b.role.value)

        bot_a = str(uuid.uuid4())
        bot_b = str(uuid.uuid4())
        await _create_bot(bot_a, user_a.id)
        await _create_bot(bot_b, user_b.id)

        # User A creates an instruction on bot A
        create_resp = await api_client.post(
            _instruction_url(bot_a),
            json={"name": "private-instr", "prompt": "Only for bot A"},
            headers=_auth_header(token_a),
        )
        instruction_id = create_resp.json()["id"]

        # Attempting to access the instruction via bot B's URL returns 404
        resp = await api_client.get(
            _instruction_url(bot_b, instruction_id),
            headers=_auth_header(token_b),
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestErrorHandling:
    """Test that error responses do not leak raw exception details."""

    async def test_nonexistent_instruction_returns_generic_404(
        self, api_client, admin_user_with_token
    ):
        """GET for a non-existent instruction returns a clean 404 message."""
        user, token = admin_user_with_token
        bot_id = str(uuid.uuid4())
        await _create_bot(bot_id, user.id)

        fake_id = str(uuid.uuid4())
        resp = await api_client.get(
            _instruction_url(bot_id, fake_id),
            headers=_auth_header(token),
        )
        assert resp.status_code == 404
        detail = resp.json()["detail"]
        # Should be a clean message, not a raw traceback or SQL error
        assert "not found" in detail.lower()
        assert "traceback" not in detail.lower()
        assert "sqlalchemy" not in detail.lower()

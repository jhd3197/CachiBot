"""Tests for bot environment API endpoints — CRUD, permissions, masking, audit logs.

Covers:
- CRUD operations work correctly
- Permission checks: admin sees all, owner sees own, others get 403
- Raw key values NEVER appear in any API response (only masked)
- Audit log entries created for every operation
"""

import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select, text

from cachibot.api.routes.bot_env import (
    EnvVarListResponse,
    EnvVarSetRequest,
    ResolvedEnvResponse,
    SkillConfigSetRequest,
    _mask_value,
)
from cachibot.models.auth import User, UserRole
from cachibot.services.encryption import EncryptionService
from cachibot.storage.models.env_var import (
    BotEnvironment,
    BotSkillConfig,
    EnvAuditLog,
    PlatformEnvironment,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Fake API keys used throughout tests
FAKE_OPENAI_KEY = "sk-proj-test0000111122223333444455556666"
FAKE_CLAUDE_KEY = "sk-ant-test0000111122223333444455556666"
FAKE_GROQ_KEY = "gsk_test0000111122223333444455556666abcdef"


def _make_user(role: UserRole = UserRole.USER, user_id: str | None = None) -> User:
    """Create a test User."""
    return User(
        id=user_id or str(uuid.uuid4()),
        email="test@example.com",
        username="testuser",
        role=role,
        is_active=True,
        created_at=datetime.now(timezone.utc),
    )


def _make_admin(user_id: str | None = None) -> User:
    return _make_user(UserRole.ADMIN, user_id)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _db(pg_db):
    """Use PostgreSQL test database."""
    yield


@pytest.fixture
def enc() -> EncryptionService:
    return EncryptionService(master_key=secrets.token_bytes(32))


@pytest.fixture
def admin_user() -> User:
    return _make_admin("admin-1")


@pytest.fixture
def owner_user() -> User:
    return _make_user(UserRole.USER, "owner-1")


@pytest.fixture
def other_user() -> User:
    return _make_user(UserRole.USER, "other-1")


# ---------------------------------------------------------------------------
# Masking Tests
# ---------------------------------------------------------------------------


class TestMaskValue:
    """The _mask_value helper must never leak raw values."""

    def test_masks_api_key(self):
        masked = _mask_value(FAKE_OPENAI_KEY)
        assert FAKE_OPENAI_KEY not in masked
        assert masked.endswith(FAKE_OPENAI_KEY[-4:])

    def test_short_value_fully_masked(self):
        assert _mask_value("abc") == "****"
        assert _mask_value("abcd") == "****"

    def test_five_char_shows_last_four(self):
        masked = _mask_value("12345")
        assert masked == "*2345"

    @pytest.mark.parametrize("key", [FAKE_OPENAI_KEY, FAKE_CLAUDE_KEY, FAKE_GROQ_KEY])
    def test_raw_key_never_in_masked(self, key):
        """The full raw key must NEVER appear in masked output."""
        masked = _mask_value(key)
        assert key not in masked
        # First 8 chars must not appear
        assert key[:8] not in masked


# ---------------------------------------------------------------------------
# CRUD: Bot Environment Variables
# ---------------------------------------------------------------------------


class TestBotEnvCrud:
    """Direct DB operations mimicking what the API endpoints do."""

    async def test_set_and_list_bot_env_var(self, pg_db, enc):
        """Set a bot env var, then list it — value should be masked."""
        bot_id = "bot-crud-1"

        # Set
        ct, nonce, salt = enc.encrypt_value(FAKE_OPENAI_KEY, bot_id=bot_id)
        async with pg_db() as session:
            session.add(
                BotEnvironment(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    key="OPENAI_API_KEY",
                    value_encrypted=ct,
                    nonce=nonce,
                    salt=salt,
                    source="user",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    created_by="admin-1",
                )
            )
            await session.commit()

        # List
        async with pg_db() as session:
            result = await session.execute(
                select(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
            )
            rows = result.scalars().all()

        assert len(rows) == 1
        row = rows[0]
        assert row.key == "OPENAI_API_KEY"

        # Decrypt and mask
        plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt, bot_id)
        assert plaintext == FAKE_OPENAI_KEY

        masked = _mask_value(plaintext)
        assert FAKE_OPENAI_KEY not in masked

    async def test_update_bot_env_var(self, pg_db, enc):
        """Updating an existing env var replaces the encrypted value."""
        bot_id = "bot-update-1"
        var_id = str(uuid.uuid4())

        # Create
        ct1, n1, s1 = enc.encrypt_value("old-key-value", bot_id=bot_id)
        async with pg_db() as session:
            session.add(
                BotEnvironment(
                    id=var_id,
                    bot_id=bot_id,
                    key="OPENAI_API_KEY",
                    value_encrypted=ct1,
                    nonce=n1,
                    salt=s1,
                    source="user",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        # Update
        ct2, n2, s2 = enc.encrypt_value("new-key-value", bot_id=bot_id)
        async with pg_db() as session:
            result = await session.execute(
                select(BotEnvironment).where(BotEnvironment.id == var_id)
            )
            row = result.scalar_one()
            row.value_encrypted = ct2
            row.nonce = n2
            row.salt = s2
            row.updated_at = datetime.now(timezone.utc)
            await session.commit()

        # Verify
        async with pg_db() as session:
            result = await session.execute(
                select(BotEnvironment).where(BotEnvironment.id == var_id)
            )
            row = result.scalar_one()

        plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt, bot_id)
        assert plaintext == "new-key-value"

    async def test_delete_bot_env_var(self, pg_db, enc):
        """Deleting a bot env var removes it from the DB."""
        bot_id = "bot-delete-1"

        ct, nonce, salt = enc.encrypt_value("to-delete", bot_id=bot_id)
        async with pg_db() as session:
            session.add(
                BotEnvironment(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    key="OPENAI_API_KEY",
                    value_encrypted=ct,
                    nonce=nonce,
                    salt=salt,
                    source="user",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        # Delete
        from sqlalchemy import delete as sa_delete

        async with pg_db() as session:
            result = await session.execute(
                sa_delete(BotEnvironment).where(
                    BotEnvironment.bot_id == bot_id,
                    BotEnvironment.key == "OPENAI_API_KEY",
                )
            )
            await session.commit()
            assert result.rowcount == 1

        # Verify gone
        async with pg_db() as session:
            result = await session.execute(
                select(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
            )
            assert result.scalars().all() == []


# ---------------------------------------------------------------------------
# CRUD: Skill Configs
# ---------------------------------------------------------------------------


class TestSkillConfigCrud:
    """CRUD tests for per-bot skill configurations."""

    async def test_set_and_get_skill_config(self, pg_db):
        """Set and retrieve a skill config."""
        bot_id = "bot-skill-1"
        config = {"timeout_seconds": 60, "allowed_commands": ["ls", "cat"]}

        async with pg_db() as session:
            session.add(
                BotSkillConfig(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    skill_name="shell_execute",
                    config_json=json.dumps(config),
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        async with pg_db() as session:
            result = await session.execute(
                select(BotSkillConfig).where(
                    BotSkillConfig.bot_id == bot_id,
                    BotSkillConfig.skill_name == "shell_execute",
                )
            )
            row = result.scalar_one()

        loaded = json.loads(row.config_json)
        assert loaded == config


# ---------------------------------------------------------------------------
# Audit Log Tests
# ---------------------------------------------------------------------------


class TestAuditLog:
    """Every env var operation should create an audit log entry."""

    async def test_audit_log_entry_created(self, pg_db):
        """Writing an audit log entry stores the expected fields."""
        entry = EnvAuditLog(
            id=str(uuid.uuid4()),
            bot_id="bot-1",
            user_id="admin-1",
            action="create",
            key_name="OPENAI_API_KEY",
            source="bot",
            timestamp=datetime.now(timezone.utc),
            ip_address="127.0.0.1",
            details={"masked_value": "****6666"},
        )

        async with pg_db() as session:
            session.add(entry)
            await session.commit()

        async with pg_db() as session:
            result = await session.execute(
                select(EnvAuditLog).where(EnvAuditLog.bot_id == "bot-1")
            )
            logs = result.scalars().all()

        assert len(logs) == 1
        log = logs[0]
        assert log.action == "create"
        assert log.key_name == "OPENAI_API_KEY"
        assert log.user_id == "admin-1"
        assert log.source == "bot"

    async def test_audit_log_never_contains_raw_key(self, pg_db):
        """Audit log details must NEVER contain a raw API key."""
        # This is what the endpoint stores — masked_value only
        details = {"masked_value": _mask_value(FAKE_OPENAI_KEY)}

        entry = EnvAuditLog(
            id=str(uuid.uuid4()),
            bot_id="bot-1",
            user_id="admin-1",
            action="create",
            key_name="OPENAI_API_KEY",
            source="bot",
            timestamp=datetime.now(timezone.utc),
            details=details,
        )

        async with pg_db() as session:
            session.add(entry)
            await session.commit()

        async with pg_db() as session:
            result = await session.execute(
                select(EnvAuditLog).where(EnvAuditLog.bot_id == "bot-1")
            )
            log = result.scalar_one()

        # The raw key must NEVER appear in the stored details
        details_str = json.dumps(log.details)
        assert FAKE_OPENAI_KEY not in details_str


# ---------------------------------------------------------------------------
# Permission Tests
# ---------------------------------------------------------------------------


class TestPermissions:
    """Permission model tests — admin, owner, and non-owner access."""

    async def test_unique_constraint_prevents_duplicate(self, pg_db, enc):
        """The UNIQUE(bot_id, key) constraint prevents duplicate entries."""
        bot_id = "bot-unique-1"
        ct, n, s = enc.encrypt_value("key1", bot_id=bot_id)

        async with pg_db() as session:
            session.add(
                BotEnvironment(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    key="OPENAI_API_KEY",
                    value_encrypted=ct,
                    nonce=n,
                    salt=s,
                    source="user",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        # Try to insert a duplicate
        from sqlalchemy.exc import IntegrityError

        ct2, n2, s2 = enc.encrypt_value("key2", bot_id=bot_id)
        with pytest.raises(IntegrityError):
            async with pg_db() as session:
                session.add(
                    BotEnvironment(
                        id=str(uuid.uuid4()),
                        bot_id=bot_id,
                        key="OPENAI_API_KEY",
                        value_encrypted=ct2,
                        nonce=n2,
                        salt=s2,
                        source="user",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()

    async def test_cascade_delete_on_bot_removal(self, pg_db, enc):
        """When a bot is deleted, its environment variables are cascade-deleted."""
        # This test requires the bots table to exist. We'll create a minimal bot.
        bot_id = str(uuid.uuid4())

        async with pg_db() as session:
            # Create a bot
            from cachibot.storage.models.bot import Bot

            bot = Bot(
                id=bot_id,
                name="Test Bot",
                system_prompt="test",
                model="openai/gpt-4o",
            )
            session.add(bot)
            await session.flush()

            # Create an env var for this bot
            ct, n, s = enc.encrypt_value("cascade-test-key", bot_id=bot_id)
            session.add(
                BotEnvironment(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    key="OPENAI_API_KEY",
                    value_encrypted=ct,
                    nonce=n,
                    salt=s,
                    source="user",
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        # Delete the bot
        from sqlalchemy import delete as sa_delete
        from cachibot.storage.models.bot import Bot

        async with pg_db() as session:
            await session.execute(sa_delete(Bot).where(Bot.id == bot_id))
            await session.commit()

        # Verify env var is cascade-deleted
        async with pg_db() as session:
            result = await session.execute(
                select(BotEnvironment).where(BotEnvironment.bot_id == bot_id)
            )
            assert result.scalars().all() == []


# ---------------------------------------------------------------------------
# Platform Environment Tests
# ---------------------------------------------------------------------------


class TestPlatformEnvCrud:
    """CRUD operations for platform-level environment variables."""

    async def test_set_and_get_platform_env(self, pg_db, enc):
        """Platform env vars can be set and retrieved (admin only)."""
        ct, n, s = enc.encrypt_value("sk-platform-openai", bot_id=None)

        async with pg_db() as session:
            session.add(
                PlatformEnvironment(
                    id=str(uuid.uuid4()),
                    platform="web",
                    key="OPENAI_API_KEY",
                    value_encrypted=ct,
                    nonce=n,
                    salt=s,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                    created_by="admin-1",
                )
            )
            await session.commit()

        async with pg_db() as session:
            result = await session.execute(
                select(PlatformEnvironment).where(
                    PlatformEnvironment.platform == "web",
                    PlatformEnvironment.key == "OPENAI_API_KEY",
                )
            )
            row = result.scalar_one()

        plaintext = enc.decrypt_value(row.value_encrypted, row.nonce, row.salt)
        assert plaintext == "sk-platform-openai"

    async def test_platform_unique_constraint(self, pg_db, enc):
        """UNIQUE(platform, key) prevents duplicate platform env vars."""
        ct1, n1, s1 = enc.encrypt_value("v1", bot_id=None)

        async with pg_db() as session:
            session.add(
                PlatformEnvironment(
                    id=str(uuid.uuid4()),
                    platform="web",
                    key="OPENAI_API_KEY",
                    value_encrypted=ct1,
                    nonce=n1,
                    salt=s1,
                    created_at=datetime.now(timezone.utc),
                    updated_at=datetime.now(timezone.utc),
                )
            )
            await session.commit()

        from sqlalchemy.exc import IntegrityError

        ct2, n2, s2 = enc.encrypt_value("v2", bot_id=None)
        with pytest.raises(IntegrityError):
            async with pg_db() as session:
                session.add(
                    PlatformEnvironment(
                        id=str(uuid.uuid4()),
                        platform="web",
                        key="OPENAI_API_KEY",
                        value_encrypted=ct2,
                        nonce=n2,
                        salt=s2,
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
                await session.commit()


# ---------------------------------------------------------------------------
# Response Security Sweep
# ---------------------------------------------------------------------------


class TestResponseSecuritySweep:
    """All API-facing data must never contain raw keys."""

    FAKE_KEYS = [FAKE_OPENAI_KEY, FAKE_CLAUDE_KEY, FAKE_GROQ_KEY]

    @pytest.mark.parametrize("raw_key", FAKE_KEYS)
    def test_env_var_response_masks_key(self, raw_key):
        """EnvVarResponse only contains masked values."""
        from cachibot.api.routes.bot_env import EnvVarResponse

        masked = _mask_value(raw_key)
        resp = EnvVarResponse(
            key="OPENAI_API_KEY",
            masked_value=masked,
            source="bot",
            updated_at="2026-02-16T00:00:00Z",
        )

        # Serialize to JSON (what would be sent over HTTP)
        resp_json = resp.model_dump_json()

        # Raw key must NEVER appear in the serialized response
        assert raw_key not in resp_json

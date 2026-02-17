"""Tests for BotEnvironmentService — resolution order, isolation, concurrent requests.

Covers:
- Bot A with custom OpenAI key, Bot B with platform key -> both resolve correctly
- Resolution order: Request > Skill > Bot > Platform > Global
- Missing layers fall through correctly
- Concurrent requests from Bot A and Bot B -> keys are isolated
- BotEnvironmentContext async context manager
"""

import asyncio
import json
import os
import secrets
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from cachibot.services.bot_environment import (
    BotEnvironmentContext,
    BotEnvironmentService,
)
from cachibot.services.encryption import EncryptionService
from cachibot.storage.models.env_var import (
    BotEnvironment,
    BotSkillConfig,
    PlatformEnvironment,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _master_key() -> bytes:
    return secrets.token_bytes(32)


def _make_encryption_service(master: bytes | None = None) -> EncryptionService:
    return EncryptionService(master_key=master or _master_key())


async def _seed_bot_env(
    session: AsyncSession,
    enc: EncryptionService,
    bot_id: str,
    key: str,
    value: str,
) -> None:
    """Insert an encrypted bot environment variable."""
    ct, nonce, salt = enc.encrypt_value(value, bot_id=bot_id)
    row = BotEnvironment(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        key=key,
        value_encrypted=ct,
        nonce=nonce,
        salt=salt,
        source="user",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()


async def _seed_platform_env(
    session: AsyncSession,
    enc: EncryptionService,
    platform: str,
    key: str,
    value: str,
) -> None:
    """Insert an encrypted platform environment variable."""
    ct, nonce, salt = enc.encrypt_value(value, bot_id=None)
    row = PlatformEnvironment(
        id=str(uuid.uuid4()),
        platform=platform,
        key=key,
        value_encrypted=ct,
        nonce=nonce,
        salt=salt,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()


async def _seed_skill_config(
    session: AsyncSession,
    bot_id: str,
    skill_name: str,
    config: dict,
) -> None:
    """Insert a bot skill config."""
    row = BotSkillConfig(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        skill_name=skill_name,
        config_json=json.dumps(config),
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    session.add(row)
    await session.flush()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _db(pg_db):
    """Use PostgreSQL test database for all environment tests."""
    yield


@pytest.fixture
def master() -> bytes:
    return _master_key()


@pytest.fixture
def enc(master) -> EncryptionService:
    return _make_encryption_service(master)


# ---------------------------------------------------------------------------
# Resolution Order Tests
# ---------------------------------------------------------------------------


class TestResolutionOrder:
    """Test that layers are merged in the correct priority order:
    Request > Skill > Bot > Platform > Global.
    """

    async def test_global_defaults_loaded(self, pg_db, enc):
        """Layer 1: Global defaults from os.environ are loaded."""
        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-global-key"}):
                env = await svc.resolve("bot-1")

            assert env.provider_keys.get("openai") == "sk-global-key"
            assert env.sources.get("openai_api_key") == "global"

    async def test_platform_overrides_global(self, pg_db, enc):
        """Layer 2: Platform defaults override global."""
        async with pg_db() as session:
            await _seed_platform_env(session, enc, "web", "OPENAI_API_KEY", "sk-platform-key")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-global-key"}):
                env = await svc.resolve("bot-1", platform="web")

            assert env.provider_keys.get("openai") == "sk-platform-key"
            assert env.sources.get("openai_api_key") == "platform"

    async def test_bot_overrides_platform(self, pg_db, enc):
        """Layer 3: Bot overrides override platform."""
        async with pg_db() as session:
            await _seed_platform_env(session, enc, "web", "OPENAI_API_KEY", "sk-platform-key")
            await _seed_bot_env(session, enc, "bot-1", "OPENAI_API_KEY", "sk-bot-key")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-global-key"}):
                env = await svc.resolve("bot-1", platform="web")

            assert env.provider_keys.get("openai") == "sk-bot-key"
            assert env.sources.get("openai_api_key") == "bot"

    async def test_request_overrides_bot(self, pg_db, enc):
        """Layer 5: Request overrides take highest priority for settings."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-1", "model", "openai/gpt-4o")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            env = await svc.resolve(
                "bot-1",
                request_overrides={"model": "claude/claude-opus-4-6", "temperature": 0.9},
            )

            assert env.model == "claude/claude-opus-4-6"
            assert env.temperature == 0.9
            assert env.sources.get("model") == "request"
            assert env.sources.get("temperature") == "request"

    async def test_skill_configs_loaded(self, pg_db, enc):
        """Layer 4: Skill configs are loaded from the database."""
        async with pg_db() as session:
            await _seed_skill_config(session, "bot-1", "shell_execute", {"timeout_seconds": 60})
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)
            env = await svc.resolve("bot-1")

            assert "shell_execute" in env.skill_configs
            assert env.skill_configs["shell_execute"]["timeout_seconds"] == 60


# ---------------------------------------------------------------------------
# Fallthrough Tests
# ---------------------------------------------------------------------------


class TestFallthrough:
    """Missing layers should fall through to the next lower layer."""

    async def test_no_bot_env_falls_to_platform(self, pg_db, enc):
        """If no bot env var, platform value is used."""
        async with pg_db() as session:
            await _seed_platform_env(session, enc, "web", "GROQ_API_KEY", "gsk_platform")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)
            env = await svc.resolve("bot-no-groq", platform="web")

            assert env.provider_keys.get("groq") == "gsk_platform"

    async def test_no_platform_env_falls_to_global(self, pg_db, enc):
        """If no platform env var, global os.environ is used."""
        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_global"}):
                env = await svc.resolve("bot-1", platform="web")

            assert env.provider_keys.get("groq") == "gsk_global"

    async def test_no_config_at_all(self, pg_db, enc):
        """If no config at any layer, provider key is absent."""
        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {}, clear=False):
                # Remove any test keys from env
                os.environ.pop("GROQ_API_KEY", None)
                env = await svc.resolve("bot-no-keys")

            assert env.provider_keys.get("groq") is None

    async def test_request_overrides_merge_tool_configs(self, pg_db, enc):
        """Request tool_configs merge with (not replace) skill configs."""
        async with pg_db() as session:
            await _seed_skill_config(
                session, "bot-1", "shell_execute", {"timeout_seconds": 30, "allowed_dir": "/tmp"}
            )
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)
            env = await svc.resolve(
                "bot-1",
                request_overrides={
                    "tool_configs": {"shell_execute": {"timeout_seconds": 120}},
                },
            )

            # Request override should update timeout but keep allowed_dir
            assert env.skill_configs["shell_execute"]["timeout_seconds"] == 120
            assert env.skill_configs["shell_execute"]["allowed_dir"] == "/tmp"


# ---------------------------------------------------------------------------
# Isolation Tests
# ---------------------------------------------------------------------------


class TestIsolation:
    """Concurrent requests from different bots must be isolated."""

    async def test_two_bots_different_keys(self, pg_db, enc):
        """Bot A and Bot B resolve different keys for the same provider."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-a", "OPENAI_API_KEY", "sk-AAA")
            await _seed_bot_env(session, enc, "bot-b", "OPENAI_API_KEY", "sk-BBB")
            await session.commit()

        # Resolve in parallel
        async with pg_db() as session_a, pg_db() as session_b:
            svc_a = BotEnvironmentService(session_a, enc)
            svc_b = BotEnvironmentService(session_b, enc)

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                env_a, env_b = await asyncio.gather(
                    svc_a.resolve("bot-a"),
                    svc_b.resolve("bot-b"),
                )

            assert env_a.provider_keys["openai"] == "sk-AAA"
            assert env_b.provider_keys["openai"] == "sk-BBB"

    async def test_resolved_envs_are_independent_objects(self, pg_db, enc):
        """Mutating one resolved env does not affect another."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-a", "OPENAI_API_KEY", "sk-AAA")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                env_a = await svc.resolve("bot-a")
                env_b = await svc.resolve("bot-a")

            # Mutate env_a
            env_a.provider_keys["openai"] = "MUTATED"

            # env_b should be unaffected
            assert env_b.provider_keys["openai"] == "sk-AAA"


# ---------------------------------------------------------------------------
# BotEnvironmentContext Tests
# ---------------------------------------------------------------------------


class TestBotEnvironmentContext:
    """Tests for the async context manager."""

    async def test_context_provides_keys(self, pg_db, enc):
        """Keys are available inside the context."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-1", "OPENAI_API_KEY", "sk-ctx-key")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                async with BotEnvironmentContext("bot-1", svc) as ctx:
                    assert ctx.get("openai") == "sk-ctx-key"

    async def test_context_clears_on_exit(self, pg_db, enc):
        """Keys are cleared after exiting the context."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-1", "OPENAI_API_KEY", "sk-temp-key")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                ctx = BotEnvironmentContext("bot-1", svc)
                async with ctx:
                    assert ctx.get("openai") == "sk-temp-key"

                # After exit, keys should be cleared
                assert ctx.get("openai") is None

    async def test_context_resolved_raises_outside(self, pg_db, enc):
        """Accessing .resolved outside the context raises RuntimeError."""
        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)
            ctx = BotEnvironmentContext("bot-1", svc)

            with pytest.raises(RuntimeError, match="not active"):
                _ = ctx.resolved

    async def test_keys_never_in_os_environ(self, pg_db, enc):
        """Per-bot keys must NEVER be placed in os.environ."""
        async with pg_db() as session:
            await _seed_bot_env(session, enc, "bot-1", "OPENAI_API_KEY", "sk-never-in-environ")
            await session.commit()

        async with pg_db() as session:
            svc = BotEnvironmentService(session, enc)

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("OPENAI_API_KEY", None)
                async with BotEnvironmentContext("bot-1", svc) as ctx:
                    # The key should be accessible via ctx.get but NOT in os.environ
                    assert ctx.get("openai") == "sk-never-in-environ"
                    assert os.environ.get("OPENAI_API_KEY") != "sk-never-in-environ"

"""
Per-bot environment resolution service.

Merges five configuration layers (Global -> Platform -> Bot -> Skill -> Request)
to produce a fully-resolved environment for a single bot request. API keys are
decrypted from the database per-request and NEVER placed in ``os.environ``.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cachibot.api.routes.providers import PROVIDERS
from cachibot.services.encryption import EncryptionService
from cachibot.storage.models.env_var import BotEnvironment as BotEnvironmentModel
from cachibot.storage.models.env_var import BotSkillConfig, PlatformEnvironment

logger = logging.getLogger(__name__)

# Mapping from provider name to the os.environ key used by global config
_PROVIDER_ENV_KEYS: dict[str, str] = {name: info["env_key"] for name, info in PROVIDERS.items()}


@dataclass
class ResolvedEnvironment:
    """The fully-resolved configuration for a specific bot + request."""

    provider_keys: dict[str, str] = field(default_factory=dict)
    model: str = ""
    temperature: float = 0.6
    max_tokens: int = 4096
    max_iterations: int = 20
    utility_model: str = ""
    skill_configs: dict[str, dict[str, Any]] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)


class BotEnvironmentService:
    """Resolves the effective environment for a bot by merging all 5 layers.

    v1 design: per-request DB lookup, no caching. The overhead is <2ms
    compared to 200-5000ms LLM API calls.
    """

    def __init__(self, db_session: AsyncSession, encryption_service: EncryptionService) -> None:
        self._db = db_session
        self._encryption = encryption_service

    async def resolve(
        self,
        bot_id: str,
        platform: str = "web",
        request_overrides: dict[str, Any] | None = None,
    ) -> ResolvedEnvironment:
        """Resolve the full environment for a bot.

        Args:
            bot_id: The bot's unique ID.
            platform: Platform name (``"web"``, ``"telegram"``, ``"discord"``, etc.).
            request_overrides: Per-request overrides from the WebSocket/API payload.

        Returns:
            A ``ResolvedEnvironment`` with all layers merged.
        """
        # Layer 1: Global (os.environ / Config defaults)
        env = self._load_global_defaults()

        # Layer 2: Platform defaults
        platform_overrides = await self._load_platform_env(platform)
        env = self._merge(env, platform_overrides, source="platform")

        # Layer 3: Bot overrides
        bot_overrides = await self._load_bot_env(bot_id)
        env = self._merge(env, bot_overrides, source="bot")

        # Layer 4: Skill configs
        env.skill_configs = await self._load_skill_configs(bot_id)

        # Layer 5: Request overrides
        if request_overrides:
            env = self._apply_request_overrides(env, request_overrides)

        return env

    def invalidate(self, bot_id: str) -> None:
        """Invalidate cache when admin updates a bot's environment.

        v1: no-op (per-request DB lookup, no cache).
        v2: will implement TTL-based cache invalidation.
        """

    # ── Layer loaders ─────────────────────────────────────────────────────

    def _load_global_defaults(self) -> ResolvedEnvironment:
        """Layer 1: Load global defaults from os.environ and config."""
        env = ResolvedEnvironment()

        # Load provider API keys from os.environ
        for provider_name, env_key in _PROVIDER_ENV_KEYS.items():
            value = os.environ.get(env_key)
            if value:
                env.provider_keys[provider_name] = value
                env.sources[env_key.lower()] = "global"

        # Load agent defaults from config
        try:
            from cachibot.config import Config

            config = Config.load()
            env.model = config.agent.model
            env.temperature = config.agent.temperature
            env.max_tokens = config.agent.max_tokens
            env.max_iterations = config.agent.max_iterations
            env.utility_model = config.agent.utility_model
        except Exception:
            logger.debug("Could not load Config defaults, using ResolvedEnvironment defaults")

        env.sources["model"] = "global"
        env.sources["temperature"] = "global"
        env.sources["max_tokens"] = "global"
        env.sources["max_iterations"] = "global"

        return env

    async def _load_platform_env(self, platform: str) -> dict[str, Any]:
        """Layer 2: Load per-platform defaults from the DB."""
        result = await self._db.execute(
            select(PlatformEnvironment).where(PlatformEnvironment.platform == platform)
        )
        rows = result.scalars().all()

        overrides: dict[str, Any] = {}
        for row in rows:
            try:
                value = self._encryption.decrypt_value(
                    row.value_encrypted, row.nonce, row.salt, bot_id=None
                )
                overrides[row.key] = value
            except Exception:
                logger.warning("Failed to decrypt platform env key '%s'", row.key)

        return overrides

    async def _load_bot_env(self, bot_id: str) -> dict[str, Any]:
        """Layer 3: Load per-bot overrides from the DB."""
        result = await self._db.execute(
            select(BotEnvironmentModel).where(BotEnvironmentModel.bot_id == bot_id)
        )
        rows = result.scalars().all()

        overrides: dict[str, Any] = {}
        for row in rows:
            try:
                value = self._encryption.decrypt_value(
                    row.value_encrypted, row.nonce, row.salt, bot_id=bot_id
                )
                overrides[row.key] = value
            except Exception:
                logger.warning("Failed to decrypt bot env key '%s' for bot %s", row.key, bot_id)

        return overrides

    async def _load_skill_configs(self, bot_id: str) -> dict[str, dict[str, Any]]:
        """Layer 4: Load per-bot skill configurations."""
        result = await self._db.execute(
            select(BotSkillConfig).where(BotSkillConfig.bot_id == bot_id)
        )
        rows = result.scalars().all()

        configs: dict[str, dict[str, Any]] = {}
        for row in rows:
            try:
                configs[row.skill_name] = json.loads(row.config_json)
            except (json.JSONDecodeError, TypeError):
                logger.warning(
                    "Invalid JSON in skill config '%s' for bot %s", row.skill_name, bot_id
                )

        return configs

    # ── Merge helpers ─────────────────────────────────────────────────────

    def _merge(
        self,
        base: ResolvedEnvironment,
        overrides: dict[str, Any],
        source: str,
    ) -> ResolvedEnvironment:
        """Merge an overrides dict into the resolved environment.

        Recognises provider env var keys (e.g. ``OPENAI_API_KEY``), agent
        settings (``model``, ``temperature``, etc.), and records the source
        of each override for debugging.
        """
        # Build a reverse map: env_key -> provider_name
        env_key_to_provider = {v: k for k, v in _PROVIDER_ENV_KEYS.items()}

        for key, value in overrides.items():
            upper_key = key.upper()

            # Check if it's a provider API key
            if upper_key in env_key_to_provider:
                provider = env_key_to_provider[upper_key]
                base.provider_keys[provider] = value
                base.sources[upper_key.lower()] = source
            elif key.lower() == "model":
                base.model = str(value)
                base.sources["model"] = source
            elif key.lower() == "temperature":
                try:
                    base.temperature = float(value)
                    base.sources["temperature"] = source
                except (ValueError, TypeError):
                    pass
            elif key.lower() == "max_tokens":
                try:
                    base.max_tokens = int(value)
                    base.sources["max_tokens"] = source
                except (ValueError, TypeError):
                    pass
            elif key.lower() == "max_iterations":
                try:
                    base.max_iterations = int(value)
                    base.sources["max_iterations"] = source
                except (ValueError, TypeError):
                    pass
            elif key.lower() == "utility_model":
                base.utility_model = str(value)
                base.sources["utility_model"] = source
            else:
                # Unknown key — store in sources for traceability
                base.sources[key.lower()] = source

        return base

    def _apply_request_overrides(
        self,
        env: ResolvedEnvironment,
        overrides: dict[str, Any],
    ) -> ResolvedEnvironment:
        """Layer 5: Apply per-request overrides (from WebSocket/API payload)."""
        if "model" in overrides:
            env.model = str(overrides["model"])
            env.sources["model"] = "request"
        if "temperature" in overrides:
            try:
                env.temperature = float(overrides["temperature"])
                env.sources["temperature"] = "request"
            except (ValueError, TypeError):
                pass
        if "max_tokens" in overrides:
            try:
                env.max_tokens = int(overrides["max_tokens"])
                env.sources["max_tokens"] = "request"
            except (ValueError, TypeError):
                pass
        if "max_iterations" in overrides:
            try:
                env.max_iterations = int(overrides["max_iterations"])
                env.sources["max_iterations"] = "request"
            except (ValueError, TypeError):
                pass

        # Merge skill/tool configs from request
        if "tool_configs" in overrides and isinstance(overrides["tool_configs"], dict):
            for skill_name, config in overrides["tool_configs"].items():
                if isinstance(config, dict):
                    env.skill_configs.setdefault(skill_name, {}).update(config)

        return env


class BotEnvironmentContext:
    """Async context manager for scoped per-bot key access.

    Decrypts keys on entry, clears them on exit. Keys are NEVER placed
    in ``os.environ`` — they flow as constructor params to drivers only.

    Usage::

        async with BotEnvironmentContext(bot_id, env_service) as ctx:
            key = ctx.get("openai")
            driver = build_driver_with_key("openai/gpt-4o", api_key=key)
    """

    def __init__(
        self,
        bot_id: str,
        env_service: BotEnvironmentService,
        platform: str = "web",
        request_overrides: dict[str, Any] | None = None,
    ) -> None:
        self.bot_id = bot_id
        self._env_service = env_service
        self._platform = platform
        self._request_overrides = request_overrides
        self._resolved: ResolvedEnvironment | None = None

    async def __aenter__(self) -> BotEnvironmentContext:
        self._resolved = await self._env_service.resolve(
            self.bot_id,
            platform=self._platform,
            request_overrides=self._request_overrides,
        )
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self._resolved is not None:
            self._resolved.provider_keys.clear()
            self._resolved = None

    def get(self, provider_or_key: str) -> str | None:
        """Get a resolved provider key or setting.

        Args:
            provider_or_key: Provider name (e.g. ``"openai"``) to look up
                the API key, or a setting name.

        Returns:
            The resolved value, or ``None`` if not configured.
        """
        if self._resolved is None:
            return None
        return self._resolved.provider_keys.get(provider_or_key)

    @property
    def resolved(self) -> ResolvedEnvironment:
        """Access the full resolved environment (only valid inside the context)."""
        if self._resolved is None:
            raise RuntimeError("BotEnvironmentContext is not active — use 'async with'")
        return self._resolved

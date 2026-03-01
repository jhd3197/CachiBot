"""
Shared Agent Factory

Centralizes CachibotAgent construction so that the web UI (websocket.py),
platform providers (message_processor.py), and other call sites share a
single pipeline for environment resolution, model overrides, tool config
merging, context building, and dynamic instructions.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cachibot.models.workspace import WorkspaceConfig

from cachibot.agent import CachibotAgent, load_disabled_capabilities, load_dynamic_instructions
from cachibot.config import Config
from cachibot.services.context_builder import get_context_builder
from cachibot.services.driver_factory import build_driver_with_key

logger = logging.getLogger(__name__)


async def _resolve_public_id(model: str) -> str:
    """If *model* matches a public_id in model_toggles, return the real model_id.

    Uses a raw query against the shared model_toggles table (managed by the
    CachiBotWebsite codebase) so we don't need a full ORM model here.
    Returns *model* unchanged when there is no match.
    """
    try:
        from sqlalchemy import text as sa_text
        from cachibot.storage.db import ensure_initialized

        session_maker = ensure_initialized()
        async with session_maker() as session:
            result = await session.execute(
                sa_text("SELECT model_id FROM model_toggles WHERE public_id = :pid"),
                {"pid": model},
            )
            row = result.first()
            if row:
                logger.debug("Resolved public_id %r → %r", model, row[0])
                return row[0]
    except Exception:
        logger.debug("public_id resolution skipped for %r", model, exc_info=True)
    return model


# Instruction block appended to the system prompt when the codingAgent
# capability is enabled, telling the LLM how to handle @agent mentions.
CODING_AGENT_MENTION_INSTRUCTIONS = """

## Coding Agent @Mentions
When the user @mentions a coding agent in their message (e.g. @claude, @codex, @gemini), \
you MUST invoke the `coding_agent` tool with the matching `agent` parameter and pass the \
user's request as the `task`. For example, if the user writes "@claude refactor this file", \
call coding_agent(task="refactor this file", agent="claude"). If only "@" is used without a \
specific agent name, use the default agent (omit the agent parameter).
"""


async def resolve_bot_env(
    bot_id: str,
    platform: str = "web",
    effective_model: str = "",
    request_overrides: dict[str, Any] | None = None,
) -> tuple[Any, Any]:
    """Resolve per-bot environment and build a driver.

    Returns:
        A tuple of (ResolvedEnvironment | None, driver | None).
        On failure (DB unreachable, missing master key), returns (None, None)
        and logs a warning so the agent falls back to global keys.
    """
    try:
        from cachibot.services.bot_environment import BotEnvironmentService
        from cachibot.services.encryption import get_encryption_service
        from cachibot.storage.db import ensure_initialized

        session_maker = ensure_initialized()
        async with session_maker() as session:
            encryption = get_encryption_service()
            env_service = BotEnvironmentService(session, encryption)
            resolved = await env_service.resolve(
                bot_id, platform=platform, request_overrides=request_overrides
            )

        # Build a per-bot driver if we have a key for the effective provider
        driver = None
        if effective_model and "/" in effective_model:
            provider = effective_model.split("/", 1)[0].lower()
            api_key = resolved.provider_keys.get(provider)
            if api_key:
                extras = resolved.provider_extras.get(provider, {})
                driver = build_driver_with_key(effective_model, api_key=api_key, **extras)

        return resolved, driver
    except Exception:
        logger.warning(
            "Per-bot environment resolution failed for bot %s; falling back to global keys",
            bot_id,
            exc_info=True,
        )
        return None, None


def _inject_coding_agent_instructions(
    prompt: str | None,
    capabilities: dict[str, Any] | None,
    disabled_caps: set[str],
) -> str | None:
    """Append @mention usage instructions when codingAgent is enabled."""
    if not capabilities or not capabilities.get("codingAgent"):
        return prompt
    if "codingAgent" in disabled_caps:
        return prompt
    return (prompt or "") + CODING_AGENT_MENTION_INSTRUCTIONS


async def build_bot_agent(
    config: Config,
    *,
    # Identity
    bot_id: str | None = None,
    chat_id: str | None = None,
    # System prompt — base prompt before context enrichment
    base_system_prompt: str | None = None,
    # Context building (enabled when user_message is provided)
    user_message: str | None = None,
    include_contacts: bool = False,
    enabled_skills: list[str] | None = None,
    # Bot config
    capabilities: dict[str, Any] | None = None,
    bot_models: dict[str, Any] | None = None,
    tool_configs: dict[str, Any] | None = None,
    # Platform
    platform: str = "web",
    platform_metadata: dict[str, Any] | None = None,
    # Pre-resolved (skip internal resolution when caller already has these)
    driver: Any | None = None,
    provider_environment: Any | None = None,
    disabled_capabilities: set[str] | None = None,
    # Request overrides (web path passes per-request temp/max_tokens)
    request_overrides: dict[str, Any] | None = None,
    # Callbacks (passed through to CachibotAgent)
    on_approval_needed: Callable[..., Any] | None = None,
    on_instruction_delta: Callable[..., Any] | None = None,
    on_model_fallback: Callable[..., Any] | None = None,
    on_artifact: Callable[..., Any] | None = None,
    # Feature flags
    inject_coding_agent: bool = False,
    # Workspace mode
    workspace: str | None = None,
    workspace_config: "WorkspaceConfig | None" = None,
) -> CachibotAgent:
    """Build a fully-configured CachibotAgent.

    This is the single entry point for constructing an agent with the full
    shared pipeline: disabled-capability loading, model override, environment
    resolution, tool-config merging, context building, coding-agent injection,
    and dynamic instruction loading.
    """
    # 1. Disabled capabilities
    if disabled_capabilities is None:
        disabled_capabilities = await load_disabled_capabilities()

    # 1b. Inject official plugin capabilities for default bot
    if bot_id == "default":
        try:
            from cachibot.services.external_plugins import EXTERNAL_PLUGINS, OFFICIAL_PLUGIN_NAMES

            if capabilities is None:
                capabilities = {}
            for name in OFFICIAL_PLUGIN_NAMES:
                manifest = EXTERNAL_PLUGINS.get(name)
                if manifest:
                    cap_key = manifest.capability_key
                    capabilities.setdefault(cap_key, True)
        except Exception:
            pass

    # 2. Model override — resolve effective model from bot_models["default"]
    agent_config = config
    effective_model: str | None = None
    if bot_models and bot_models.get("default"):
        effective_model = bot_models["default"]

    # 2b. Resolve public_id → real model_id (white-label alias support)
    if effective_model:
        effective_model = await _resolve_public_id(effective_model)

    if effective_model:
        agent_config = copy.deepcopy(config)
        agent_config.agent.model = effective_model

    # 3. Environment resolution — if not pre-passed and bot_id exists
    resolved_env = provider_environment
    per_bot_driver = driver
    if bot_id and resolved_env is None and per_bot_driver is None:
        resolved_env, per_bot_driver = await resolve_bot_env(
            bot_id,
            platform=platform,
            effective_model=effective_model or agent_config.agent.model,
            request_overrides=request_overrides,
        )

    # 4. Tool config merging — merge resolved_env.skill_configs into tool_configs
    merged_tool_configs = dict(tool_configs) if tool_configs else {}
    if resolved_env and getattr(resolved_env, "skill_configs", None):
        for skill_name, skill_cfg in resolved_env.skill_configs.items():
            merged_tool_configs.setdefault(skill_name, {}).update(skill_cfg)

    # 5. Context building — if user_message is provided
    enhanced_prompt = base_system_prompt
    if user_message and bot_id:
        try:
            context_builder = get_context_builder()
            enhanced_prompt = await context_builder.build_enhanced_system_prompt(
                base_prompt=base_system_prompt,
                bot_id=bot_id,
                user_message=user_message,
                chat_id=chat_id,
                include_contacts=include_contacts,
                enabled_skills=enabled_skills,
            )
        except Exception as e:
            logger.warning(
                "Context building failed for bot %s chat %s: %s",
                bot_id,
                chat_id,
                e,
            )
            enhanced_prompt = base_system_prompt

    # 6. Coding agent injection
    if inject_coding_agent:
        enhanced_prompt = _inject_coding_agent_instructions(
            enhanced_prompt, capabilities, disabled_capabilities
        )

    # 6b. Workspace mode injection
    if workspace and workspace_config and workspace_config.system_prompt:
        enhanced_prompt = (enhanced_prompt or "") + (
            f"\n\n## Workspace Mode\n"
            f"You are in **{workspace_config.display_name}** mode.\n"
            f"{workspace_config.system_prompt}"
        )

    # 6c. External plugin tool hints — inject system_prompt from enabled ext_* capabilities
    if capabilities:
        try:
            from cachibot.services.external_plugins import EXTERNAL_PLUGINS

            for cap_key, enabled in capabilities.items():
                if not enabled or not cap_key.startswith("ext_"):
                    continue
                # Skip if already in workspace mode for this plugin (avoid double-injection)
                plugin_name = cap_key.removeprefix("ext_")
                if workspace and workspace == plugin_name:
                    continue
                manifest = EXTERNAL_PLUGINS.get(plugin_name)
                if manifest and manifest.workspace and manifest.workspace.system_prompt:
                    enhanced_prompt = (enhanced_prompt or "") + manifest.workspace.system_prompt
        except Exception:
            logger.debug("External plugin prompt injection skipped", exc_info=True)

    # 7. Construct CachibotAgent
    agent = CachibotAgent(
        config=agent_config,
        system_prompt_override=enhanced_prompt,
        capabilities=capabilities,
        bot_id=bot_id,
        chat_id=chat_id,
        bot_models=bot_models,
        tool_configs=merged_tool_configs,
        on_approval_needed=on_approval_needed,
        driver=per_bot_driver,
        provider_environment=resolved_env,
        disabled_capabilities=disabled_capabilities,
        on_instruction_delta=on_instruction_delta,
        on_model_fallback=on_model_fallback,
        on_artifact=on_artifact,
        platform_metadata=platform_metadata,
        workspace=workspace,
    )

    # 8. Dynamic instructions
    await load_dynamic_instructions(agent)

    # 9. Return agent
    return agent

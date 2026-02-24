"""
Cachibot Agent Engine

Uses Prompture for structured LLM interaction with tool support.
Tools are provided by Tukuy-based plugins via the PluginManager.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from prompture import (
    AgentCallbacks,
    AgentResult,
    ToolRegistry,
)
from prompture import (
    AsyncAgent as PromptureAgent,
)
from tukuy import PythonSandbox

from cachibot.config import Config
from cachibot.plugins.base import PluginContext
from cachibot.services.plugin_manager import build_registry

if TYPE_CHECKING:
    from cachibot.services.bot_environment import ResolvedEnvironment


@dataclass
class CachibotAgent:
    """
    The Cachibot agent.

    Uses Prompture for LLM interaction and tool execution
    with Python sandbox for safe code execution.
    Tools are loaded from Tukuy-based plugins, gated by capabilities.
    """

    config: Config
    registry: ToolRegistry = field(default_factory=ToolRegistry)
    sandbox: PythonSandbox | None = None
    _agent: PromptureAgent[Any] | None = None

    # Callbacks for UI integration
    on_thinking: Callable[[str], None] | None = None
    on_tool_start: Callable[[str, dict[str, Any]], None] | None = None
    on_tool_end: Callable[[str, Any], None] | None = None
    on_message: Callable[[str], None] | None = None
    on_approval_needed: Callable[[str, str, dict[str, Any]], bool] | None = None

    # Custom system prompt (overrides default CachiBot personality)
    system_prompt_override: str | None = None

    # Optional set of allowed tools (None = all tools allowed)
    # Acts as a secondary filter on top of capability-based plugin selection.
    allowed_tools: set[str] | None = None

    # Optional per-tool configuration (timeouts, limits, etc.)
    tool_configs: dict[str, Any] | None = None

    # Capability toggles (None = legacy/CLI mode, all plugins enabled)
    capabilities: dict[str, Any] | None = None

    # Bot identity (needed by work management and platform plugins)
    bot_id: str | None = None

    # Chat context (auto-captured for scheduling/reminders)
    chat_id: str | None = None

    # Multi-model slot configuration (e.g., {"default": "...", "image": "..."})
    bot_models: dict[str, Any] | None = None

    # Per-bot Prompture driver (bypasses global registry when provided)
    driver: Any | None = None

    # Per-bot resolved environment (temperature/max_tokens/etc. overrides)
    provider_environment: ResolvedEnvironment | None = None

    # Platform-level disabled capabilities (loaded by the caller from DB).
    # When provided, these capabilities are excluded even if the bot enables them.
    disabled_capabilities: set[str] | None = None

    # Platform metadata (platform name, chat_id, username) for system prompt enrichment.
    # Expected keys: "platform" (str), "platform_chat_id" (str), "username" (str).
    platform_metadata: dict[str, Any] | None = None

    # Async callback for streaming instruction LLM deltas via WebSocket.
    # Signature: async (tool_call_id: str, text: str) -> None
    # When set, instruction executions broadcast incremental text chunks.
    on_instruction_delta: Callable[..., Any] | None = None

    # Sync callback for budget-triggered model fallback notifications.
    # Signature: (old_model: str, new_model: str, budget_state: Any) -> None
    on_model_fallback: Callable[..., Any] | None = None

    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        self._setup_sandbox()
        self._build_registry_from_plugins()

        # Apply tool filtering if specified
        if self.allowed_tools is not None:
            valid_tools = self.allowed_tools & set(self.registry.names)
            self.registry = self.registry.subset(valid_tools)

        self._create_agent()

    def _setup_sandbox(self) -> None:
        """Set up the Python sandbox with restrictions."""
        workspace = str(self.config.workspace_path)

        # Get timeout from tool_configs or fall back to config defaults
        timeout = self.config.sandbox.timeout_seconds
        if self.tool_configs and "python_execute" in self.tool_configs:
            py_cfg = self.tool_configs["python_execute"]
            timeout = py_cfg.get("timeoutSeconds", timeout)

        self.sandbox = PythonSandbox(
            allowed_imports=self.config.sandbox.allowed_imports,
            timeout_seconds=timeout,
            allowed_read_paths=[workspace],
            allowed_write_paths=[workspace],
        )

    def _build_registry_from_plugins(self) -> None:
        """Build the tool registry from enabled plugins."""
        ctx = PluginContext(
            config=self.config,
            sandbox=self.sandbox,
            bot_id=self.bot_id,
            chat_id=self.chat_id,
            tool_configs=self.tool_configs or {},
            bot_models=self.bot_models,
            on_tool_output=self.on_instruction_delta,
        )

        # Build skill_config with llm_backend for instruction execution
        skill_config = self._build_skill_config()

        self.registry = build_registry(
            ctx,
            self.capabilities,
            self.disabled_capabilities,
            skill_config=skill_config,
        )

    def _build_skill_config(self) -> dict[str, Any] | None:
        """Build the config dict injected into Tukuy SkillContext for instructions.

        Creates a TukuyLLMBackend from the bot's provider environment and model
        configuration so that @instruction-decorated tools can call an LLM.
        Returns None if the backend cannot be created (graceful degradation).
        """
        try:
            from prompture.bridges import create_tukuy_backend

            # Determine the model to use for instructions
            model = None
            if self.bot_models and self.bot_models.get("default"):
                model = self.bot_models["default"]
            if not model and self.provider_environment and self.provider_environment.model:
                model = self.provider_environment.model
            if not model:
                model = self.config.agent.model
            if not model:
                return None

            # Build per-bot ProviderEnvironment for isolated API keys
            env = None
            if self.provider_environment and self.provider_environment.provider_keys:
                from prompture.infra.provider_env import ProviderEnvironment

                # Map CachiBotV2 provider names to ProviderEnvironment field names
                provider_to_field = {
                    "openai": "openai_api_key",
                    "claude": "claude_api_key",
                    "google": "google_api_key",
                    "groq": "groq_api_key",
                    "grok": "grok_api_key",
                    "openrouter": "openrouter_api_key",
                    "moonshot": "moonshot_api_key",
                    "zai": "zhipu_api_key",
                    "modelscope": "modelscope_api_key",
                    "cachibot": "cachibot_api_key",
                    "stability": "stability_api_key",
                    "elevenlabs": "elevenlabs_api_key",
                    "azure": "azure_api_key",
                    "ollama": "ollama_endpoint",
                    "lmstudio": "lmstudio_endpoint",
                }
                kwargs = {}
                for provider_name, api_key in self.provider_environment.provider_keys.items():
                    field_name = provider_to_field.get(provider_name)
                    if field_name:
                        kwargs[field_name] = api_key
                env = ProviderEnvironment(**kwargs) if kwargs else None

            # Create the backend with an on_complete callback for logging
            bot_id = self.bot_id
            chat_id = self.chat_id

            def _on_complete(result: dict[str, Any]) -> None:
                """Fire-and-forget logging for instruction LLM calls."""
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_log_instruction_completion(bot_id, chat_id, result))
                except RuntimeError:
                    pass  # No event loop — skip logging

            backend = create_tukuy_backend(
                model,
                env=env,
                on_complete=_on_complete,
            )

            config: dict[str, Any] = {"llm_backend": backend}

            # Wire instruction delta streaming when a WebSocket sender is set
            if self.on_instruction_delta is not None:
                config["on_instruction_delta"] = self.on_instruction_delta

            return config
        except Exception:
            import logging

            logging.getLogger(__name__).debug(
                "Could not create LLM backend for instructions; "
                "instruction tools will return errors if invoked",
                exc_info=True,
            )
            return None

    def _create_agent(self) -> None:
        """Create the Prompture agent with callbacks and SecurityContext."""

        # Build callbacks
        callbacks = AgentCallbacks(
            on_thinking=self.on_thinking,
            on_tool_start=self.on_tool_start,
            on_tool_end=self.on_tool_end,
            on_message=self.on_message,
            on_approval_needed=self._handle_approval,
        )

        # Build SecurityContext from sandbox so Tukuy's built-in plugins
        # are automatically scoped to the workspace, then harden it
        security_context = None
        if self.sandbox is not None:
            security_context = self.sandbox.to_security_context()
            self._harden_security_context(security_context)

        # Resolve effective agent parameters — provider_environment overrides
        # take precedence over global config values.
        env = self.provider_environment
        temperature = env.temperature if env else self.config.agent.temperature
        max_tokens = env.max_tokens if env else self.config.agent.max_tokens
        max_iterations = env.max_iterations if env else self.config.agent.max_iterations

        # Build kwargs for PromptureAgent
        agent_kwargs: dict[str, Any] = {
            "tools": self.registry,
            "system_prompt": self._get_system_prompt(),
            "agent_callbacks": callbacks,
            "max_iterations": max_iterations,
            "persistent_conversation": True,
            "security_context": security_context,
            "max_tool_result_length": self.config.agent.max_tool_result_length,
            "max_depth": self.config.agent.max_depth,
            "options": {
                "temperature": temperature,
                "max_tokens": max_tokens,
            },
        }

        # Wire budget enforcement from per-bot environment
        if env and env.budget_policy:
            from prompture.infra import BudgetPolicy

            try:
                agent_kwargs["budget_policy"] = BudgetPolicy(env.budget_policy)
            except ValueError:
                pass
            else:
                if env.budget_max_cost is not None:
                    agent_kwargs["max_cost"] = env.budget_max_cost
                if env.budget_max_tokens is not None:
                    agent_kwargs["max_tokens"] = env.budget_max_tokens
                if env.budget_fallback_models:
                    agent_kwargs["fallback_models"] = env.budget_fallback_models
                if self.on_model_fallback is not None:
                    agent_kwargs["on_model_fallback"] = self.on_model_fallback

        # When a per-bot driver is provided, pass it directly to bypass the
        # global Prompture registry.  Otherwise, use the model string.
        if self.driver is not None:
            agent_kwargs["driver"] = self.driver
        else:
            agent_kwargs["model"] = self.config.agent.model

        self._agent = PromptureAgent(**agent_kwargs)

    @staticmethod
    def _harden_security_context(ctx: object) -> None:
        """Add security restrictions to prevent secret leakage from bot agents.

        Blocks .env file access and dangerous shell commands that could
        expose environment variables or secrets.
        """
        # Block .env files via ignore patterns (matched against filename)
        ignore = getattr(ctx, "ignore_patterns", None)
        if ignore is not None:
            for pat in (".env", "*.env", ".env.*"):
                if pat not in ignore:
                    ignore.append(pat)

        # Block shell commands that dump environment variables
        blocked = getattr(ctx, "blocked_commands", None)
        if blocked is not None:
            for cmd in ("env", "printenv", "set", "export"):
                if cmd not in blocked:
                    blocked.append(cmd)

    def _get_system_prompt(self) -> str:
        """Generate the system prompt.

        Always appends tool list, platform context, and usage guidelines
        so the agent is aware of its environment regardless of whether
        a system_prompt_override is set.
        """
        base = self.system_prompt_override or self._build_default_prompt()

        # Always append tool + platform context
        sections: list[str] = []

        # Tool list
        tool_lines = "\n".join(f"- {name}" for name in sorted(self.registry.names))
        if tool_lines:
            sections.append(f"## Available Tools\n{tool_lines}")

        # Background jobs section
        job_section = self._get_job_tools_section()
        if job_section:
            sections.append(job_section.rstrip())

        # Platform context
        if self.platform_metadata:
            platform = self.platform_metadata.get("platform", "unknown")
            chat_id = self.platform_metadata.get("platform_chat_id")
            username = self.platform_metadata.get("username")

            ctx_lines = [f"- Platform: {platform.title()}"]
            if username:
                ctx_lines.append(f"- User: {username}")
            if chat_id:
                ctx_lines.append(f"- Chat ID: {chat_id}")
                send_tool = f"{platform}_send"
                if send_tool in self.registry.names:
                    ctx_lines.append(
                        f"- You can send messages to this chat using the `{send_tool}` "
                        f'tool with chat_id="{chat_id}"'
                    )
            sections.append("## Current Conversation Context\n" + "\n".join(ctx_lines))

        # Brief tool guidelines (only when override is set — the default already has these)
        if self.system_prompt_override and sections:
            sections.append(
                "## Tool Usage\n"
                "- Use your tools proactively when the user's request can be fulfilled by them\n"
                "- You have full access to the tools listed above — use them without hesitation\n"
                "- For scheduling, reminders, and todos, use the schedule/todo tools directly"
            )

        if sections:
            return base + "\n\n---\n\n" + "\n\n".join(sections)
        return base

    def _build_default_prompt(self) -> str:
        """Build the default CachiBot system prompt (used when no override is set)."""
        return f"""You are Cachibot, a helpful AI assistant that executes tasks safely.

## About Your Name
Cachibot is named after the Venezuelan *cachicamo* (armadillo) - a resilient,
armored creature known for its protective shell and methodical nature.
Like the cachicamo, you approach tasks with care, protection, and thoroughness.

## Creator
Cachibot was created by Juan Denis (juandenis.com).
When asked about your creator, always refer to him by his full name "Juan Denis".

## Environment
- Workspace: {self.config.workspace_path}
- All file and git operations are scoped to this workspace

## Guidelines
1. Be concise and helpful
2. Use tools when actions are needed
3. Explain what you're doing
4. Verify file paths are within the workspace
5. Call task_complete when you're done

## Important
- All tools are automatically scoped to the workspace for security
- Python code runs in a sandbox with restricted imports
"""

    def _get_job_tools_section(self) -> str:
        """Return system prompt section for background jobs, if tools are available."""
        job_tools = {"job_create", "job_status", "job_cancel", "job_list"}
        if job_tools & set(self.registry.names):
            return (
                "## Background Jobs\n"
                "You can create background jobs for long-running tasks using job_create.\n"
                "This allows you to run multi-step tasks asynchronously without blocking "
                "the conversation.\n"
                "Use job_status to check progress and job_cancel to stop a running job.\n\n"
            )
        return ""

    def _handle_approval(self, tool_name: str, action: str, details: dict[str, Any]) -> bool:
        """Handle approval requests."""
        if self.on_approval_needed:
            return self.on_approval_needed(tool_name, action, details)

        # Default: require approval if config says so
        if self.config.agent.approve_actions:
            return False  # Reject by default if no callback
        return True  # Auto-approve if approval not required

    async def run(
        self,
        user_message: str,
        *,
        images: list[Any] | None = None,
    ) -> AgentResult:
        """
        Process a user message and return the AgentResult.

        Args:
            user_message: The user's input
            images: Optional list of ImageInput for vision models.

        Returns:
            The AgentResult containing output_text, run_usage, steps, etc.
        """
        if self._agent is None:
            raise RuntimeError("Agent not initialized")
        return await self._agent.run(user_message, images=images)

    async def run_stream(
        self, user_message: str, *, images: list[Any] | None = None
    ) -> AsyncIterator[Any]:
        """
        Process a user message with streaming output.

        Args:
            user_message: The user's input
            images: Optional list of ImageInput for vision models.

        Yields:
            Stream events from the agent.
            The final event (StreamEventType.output) contains the complete AgentResult.
        """
        if self._agent is None:
            raise RuntimeError("Agent not initialized")
        async for event in self._agent.run_stream(user_message, images=images):
            yield event

    @property
    def conversation(self) -> Any:
        """Access the underlying agent's conversation history."""
        if self._agent is None:
            raise RuntimeError("Agent not initialized")
        return self._agent.conversation

    def clear_history(self) -> None:
        """Clear the conversation history."""
        if self._agent is None:
            raise RuntimeError("Agent not initialized")
        self._agent.clear_history()


async def load_dynamic_instructions(agent: CachibotAgent) -> None:
    """Load custom instructions from DB and add them to the agent's registry.

    Call this after constructing a ``CachibotAgent`` in an async context.
    Dynamic instructions are converted to Tukuy Instruction objects and
    registered as tools alongside static plugin skills.

    No-ops gracefully if the bot has no custom instructions or if the
    database is unavailable.
    """
    if not agent.bot_id:
        return

    try:
        from tukuy.instruction import Instruction, InstructionDescriptor

        from cachibot.storage.instruction_repository import InstructionRepository

        repo = InstructionRepository()
        records = await repo.get_by_bot(agent.bot_id)

        if not records:
            return

        # Get the skill_config (with llm_backend) from the agent
        skill_config = agent._build_skill_config()

        for record in records:
            if not record.is_active:
                continue

            descriptor = InstructionDescriptor(
                name=record.name,
                description=record.description or f"Custom instruction: {record.name}",
                prompt=record.prompt,
                system_prompt=record.system_prompt,
                output_format=record.output_format,
                model_hint=record.model_hint,
                temperature=record.temperature,
                max_tokens=record.max_tokens,
                few_shot_examples=record.few_shot_examples,
                category=record.category,
                tags=record.tags or [],
            )
            instr = Instruction(descriptor=descriptor, fn=None)
            agent.registry.add_tukuy_skill(instr, config=skill_config)

    except Exception:
        import logging

        logging.getLogger(__name__).debug(
            "Failed to load dynamic instructions for bot %s",
            agent.bot_id,
            exc_info=True,
        )


async def _log_instruction_completion(
    bot_id: str | None,
    chat_id: str | None,
    result: dict[str, Any],
) -> None:
    """Log an instruction LLM completion to the execution log.

    Called from the on_complete callback of the TukuyLLMBackend.
    Runs as a fire-and-forget task so it doesn't block the instruction.
    """
    if not bot_id:
        return

    import logging
    import uuid
    from datetime import datetime, timezone

    logger = logging.getLogger(__name__)
    try:
        from cachibot.models.automations import ExecutionLog, ExecutionStatus, TriggerType
        from cachibot.storage.automations_repository import ExecutionLogRepository

        meta = result.get("meta", {})
        log_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc)

        log = ExecutionLog(
            id=log_id,
            execution_type="instruction",
            source_type="instruction",
            source_id=None,
            source_name=meta.get("model", "unknown"),
            bot_id=bot_id,
            chat_id=chat_id,
            trigger=TriggerType.MANUAL,
            started_at=now,
            finished_at=now,
            duration_ms=0,
            status=ExecutionStatus.SUCCESS,
            credits_consumed=meta.get("cost", 0.0),
            tokens_used=meta.get("prompt_tokens", 0) + meta.get("completion_tokens", 0),
            prompt_tokens=meta.get("prompt_tokens", 0),
            completion_tokens=meta.get("completion_tokens", 0),
            llm_calls=1,
            metadata_json={"model": meta.get("model", "unknown")},
        )

        repo = ExecutionLogRepository()
        await repo.save(log)

        # Credit deduction
        cost = meta.get("cost", 0.0)
        if cost > 0:
            try:
                from cachibot.services.credit_guard import CreditGuard

                guard = CreditGuard()
                # We don't have user_id here, but the guard handles missing users gracefully
                await guard.deduct_after_execution(bot_id, cost)
            except Exception:
                logger.debug("Credit deduction skipped for instruction", exc_info=True)

    except Exception:
        logger.debug("Failed to log instruction completion", exc_info=True)


async def load_disabled_capabilities() -> set[str]:
    """Load globally disabled capabilities from the platform tool config.

    Call this from async agent-creation sites (websocket, message processor,
    job runner, etc.) and pass the result as ``disabled_capabilities`` when
    constructing a ``CachibotAgent``.

    Returns an empty set on any error (graceful degradation).
    """
    try:
        from cachibot.storage.repository import PlatformToolConfigRepository

        repo = PlatformToolConfigRepository()
        return set(await repo.get_disabled_capabilities())
    except Exception:
        return set()


# Backwards compatibility alias
Agent = CachibotAgent

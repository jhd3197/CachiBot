"""
Cachibot Agent Engine

Uses Prompture for structured LLM interaction with tool support.
Tools are provided by Tukuy-based plugins via the PluginManager.
"""

from __future__ import annotations

from collections.abc import Callable
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
    _agent: PromptureAgent | None = None

    # Callbacks for UI integration
    on_thinking: Callable[[str], None] | None = None
    on_tool_start: Callable[[str, dict[str, Any]], None] | None = None
    on_tool_end: Callable[[str, Any], None] | None = None
    on_message: Callable[[str], None] | None = None
    on_approval_needed: Callable[[str, str, dict], bool] | None = None

    # Custom system prompt (overrides default CachiBot personality)
    system_prompt_override: str | None = None

    # Optional set of allowed tools (None = all tools allowed)
    # Acts as a secondary filter on top of capability-based plugin selection.
    allowed_tools: set[str] | None = None

    # Optional per-tool configuration (timeouts, limits, etc.)
    tool_configs: dict | None = None

    # Capability toggles (None = legacy/CLI mode, all plugins enabled)
    capabilities: dict | None = None

    # Bot identity (needed by work management and platform plugins)
    bot_id: str | None = None

    # Chat context (auto-captured for scheduling/reminders)
    chat_id: str | None = None

    # Multi-model slot configuration (e.g., {"default": "...", "image": "..."})
    bot_models: dict | None = None

    # Per-bot Prompture driver (bypasses global registry when provided)
    driver: Any | None = None

    # Per-bot resolved environment (temperature/max_tokens/etc. overrides)
    provider_environment: ResolvedEnvironment | None = None

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
        )
        self.registry = build_registry(ctx, self.capabilities)

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
        """Generate the system prompt."""
        if self.system_prompt_override:
            return self.system_prompt_override

        # Build dynamic tool list from the actual registry
        tool_lines = "\n".join(f"- {name}" for name in sorted(self.registry.names))

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

## Available Tools
{tool_lines}

{self._get_job_tools_section()}## Important
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

    def _handle_approval(self, tool_name: str, action: str, details: dict) -> bool:
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
        return await self._agent.run(user_message, images=images)

    async def run_stream(self, user_message: str, *, images: list[Any] | None = None):
        """
        Process a user message with streaming output.

        Args:
            user_message: The user's input
            images: Optional list of ImageInput for vision models.

        Yields:
            Stream events from the agent.
            The final event (StreamEventType.output) contains the complete AgentResult.
        """
        async for event in self._agent.run_stream(user_message, images=images):
            yield event

    @property
    def conversation(self):
        """Access the underlying agent's conversation history."""
        return self._agent.conversation

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._agent.clear_history()


# Backwards compatibility alias
Agent = CachibotAgent

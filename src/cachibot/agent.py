"""
Cachibot Agent Engine

Uses Prompture for structured LLM interaction with tool support.
Tools are provided by Tukuy-based plugins via the PluginManager.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from prompture import (
    AgentCallbacks,
    AgentResult,
    PythonSandbox,
    ToolRegistry,
)
from prompture import (
    AsyncAgent as PromptureAgent,
)

from cachibot.config import Config
from cachibot.plugins.base import PluginContext
from cachibot.services.plugin_manager import build_registry


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

    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        self._last_result = None  # Store last AgentResult for usage tracking
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
            tool_configs=self.tool_configs or {},
        )
        self.registry = build_registry(ctx, self.capabilities)

    def _create_agent(self) -> None:
        """Create the Prompture agent with callbacks."""

        # Build callbacks
        callbacks = AgentCallbacks(
            on_thinking=self.on_thinking,
            on_tool_start=self.on_tool_start,
            on_tool_end=self.on_tool_end,
            on_message=self.on_message,
            on_approval_needed=self._handle_approval,
        )

        # Create agent
        self._agent = PromptureAgent(
            model=self.config.agent.model,
            tools=self.registry,
            system_prompt=self._get_system_prompt(),
            agent_callbacks=callbacks,
            max_iterations=self.config.agent.max_iterations,
            persistent_conversation=True,
            options={
                "temperature": self.config.agent.temperature,
                "max_tokens": self.config.agent.max_tokens,
            },
        )

    def _get_system_prompt(self) -> str:
        """Generate the system prompt."""
        if self.system_prompt_override:
            return self.system_prompt_override
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
- You can only access files within this workspace

## Guidelines
1. Be concise and helpful
2. Use tools when actions are needed
3. Explain what you're doing
4. Always use python_execute to run code (not shell commands)
5. Verify file paths are within the workspace
6. Call task_complete when you're done

## Available Tools
- python_execute: Run Python code safely
- file_read: Read file contents
- file_write: Create or update files
- file_list: List directory contents
- file_edit: Edit files by replacing text
- task_complete: Signal task completion

## Important
- All code runs in a Python sandbox with restricted imports
- You cannot use subprocess, os.system, or similar commands
- Focus on Python-based solutions
"""

    def _handle_approval(self, tool_name: str, action: str, details: dict) -> bool:
        """Handle approval requests."""
        if self.on_approval_needed:
            return self.on_approval_needed(tool_name, action, details)

        # Default: require approval if config says so
        if self.config.agent.approve_actions:
            return False  # Reject by default if no callback
        return True  # Auto-approve if approval not required

    async def run(self, user_message: str) -> str:
        """
        Process a user message and return the response.

        Args:
            user_message: The user's input

        Returns:
            The agent's response message
        """
        result: AgentResult = await self._agent.run(user_message)

        # Store result for usage tracking
        self._last_result = result

        return result.output_text or "Task completed."

    async def run_stream(self, user_message: str):
        """
        Process a user message with streaming output.

        Args:
            user_message: The user's input

        Yields:
            Stream events from the agent
        """
        async for event in self._agent.run_stream(user_message):
            yield event

    def get_usage(self) -> dict:
        """Get token usage and cost information."""
        if hasattr(self, "_last_result") and self._last_result:
            # Prompture 1.0.4+: run_usage now works correctly with tools
            # Use run_usage for session-level aggregated stats
            usage = self._last_result.run_usage
            return {
                "prompt_tokens": usage.get("prompt_tokens", 0),
                "completion_tokens": usage.get("completion_tokens", 0),
                "total_tokens": usage.get("total_tokens", 0),
                "total_cost": usage.get("cost", 0.0),
                "iterations": len(self._last_result.steps),
                # Timing data (Prompture 1.0.4+)
                "elapsed_ms": usage.get("total_elapsed_ms", 0.0),
                "tokens_per_second": usage.get("tokens_per_second", 0.0),
            }
        return {
            "prompt_tokens": 0,
            "completion_tokens": 0,
            "total_tokens": 0,
            "total_cost": 0.0,
            "iterations": 0,
            "elapsed_ms": 0.0,
            "tokens_per_second": 0.0,
        }

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._agent.clear_history()


# Backwards compatibility alias
Agent = CachibotAgent

"""
Cachibot Agent Engine

Uses Prompture for structured LLM interaction with tool support.
"""

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from prompture import (
    AsyncAgent as PromptureAgent,
)
from prompture import (
    AgentCallbacks,
    AgentResult,
    ApprovalRequired,
    PythonSandbox,
    RiskLevel,
    ToolRegistry,
    analyze_python,
)

from cachibot.config import Config


@dataclass
class CachibotAgent:
    """
    The Cachibot agent.

    Uses Prompture for LLM interaction and tool execution
    with Python sandbox for safe code execution.
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
    allowed_tools: set[str] | None = None

    # Optional per-tool configuration (timeouts, limits, etc.)
    tool_configs: dict | None = None

    def __post_init__(self) -> None:
        """Initialize after dataclass creation."""
        self._last_result = None  # Store last AgentResult for usage tracking
        self._setup_sandbox()
        self._register_tools()

        # Apply tool filtering if specified
        if self.allowed_tools is not None:
            # Only include tools that exist in the registry
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

    def _register_tools(self) -> None:
        """Register all tools with the registry."""

        @self.registry.register
        def python_execute(code: str) -> str:
            """
            Execute Python code safely in a sandbox.

            Use this to run Python scripts, calculations, data processing,
            or any Python code. The code runs in an isolated environment
            with restricted imports and filesystem access.

            Args:
                code: Python code to execute

            Returns:
                Output from the code execution (stdout + return value)
            """
            # Analyze code first
            analysis = analyze_python(code)

            # Check for risky code
            if analysis.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
                raise ApprovalRequired(
                    tool_name="python_execute",
                    action=f"Execute {analysis.risk_level.value}-risk Python code",
                    details={
                        "code": code,
                        "risk_level": analysis.risk_level.value,
                        "reasons": analysis.risk.reasons,
                        "imports": list(analysis.features.imports),
                    }
                )

            # Execute in sandbox
            result = self.sandbox.execute(code)

            # Get max output length from tool_configs or use default
            max_output_length = 10000
            if self.tool_configs and "python_execute" in self.tool_configs:
                py_cfg = self.tool_configs["python_execute"]
                max_output_length = py_cfg.get("maxOutputLength", max_output_length)

            if result.success:
                output = result.output.strip() if result.output else ""
                if result.return_value is not None:
                    if output:
                        output += f"\n\nReturn value: {result.return_value}"
                    else:
                        output = f"Return value: {result.return_value}"
                # Truncate output if it exceeds max length
                if len(output) > max_output_length:
                    output = output[:max_output_length]
                    output += f"\n\n... (output truncated at {max_output_length} chars)"
                return output or "Code executed successfully (no output)"
            else:
                return f"Error: {result.error}"

        @self.registry.register
        def file_read(path: str) -> str:
            """
            Read the contents of a file.

            Args:
                path: Path to the file (relative to workspace or absolute)

            Returns:
                File contents as string
            """
            full_path = self._resolve_path(path)

            if not self.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"

            try:
                return self.sandbox.read_file(str(full_path))
            except Exception as e:
                return f"Error reading file: {e}"

        @self.registry.register
        def file_write(path: str, content: str) -> str:
            """
            Write content to a file. Creates the file if it doesn't exist.

            Args:
                path: Path to the file (relative to workspace or absolute)
                content: Content to write

            Returns:
                Success message or error
            """
            full_path = self._resolve_path(path)

            if not self.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"

            try:
                # Create parent directories if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                self.sandbox.write_file(str(full_path), content)
                return f"Successfully wrote to {path}"
            except Exception as e:
                return f"Error writing file: {e}"

        @self.registry.register
        def file_list(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
            """
            List files in a directory.

            Args:
                path: Directory path (default: current workspace)
                pattern: Glob pattern to filter files (default: *)
                recursive: Include subdirectories (default: False)

            Returns:
                List of files matching the pattern
            """
            full_path = self._resolve_path(path)

            if not self.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"

            try:
                if not full_path.is_dir():
                    return f"Error: '{path}' is not a directory"

                if recursive:
                    files = list(full_path.rglob(pattern))
                else:
                    files = list(full_path.glob(pattern))

                # Filter out ignored patterns
                files = [
                    f for f in files
                    if not self.config.should_ignore(f)
                ]

                # Format output
                result = []
                for f in sorted(files)[:100]:  # Limit to 100 files
                    rel_path = f.relative_to(self.config.workspace_path)
                    prefix = "📁 " if f.is_dir() else "📄 "
                    result.append(f"{prefix}{rel_path}")

                if not result:
                    return "No files found matching the pattern"

                output = "\n".join(result)
                if len(files) > 100:
                    output += f"\n\n... and {len(files) - 100} more files"

                return output
            except Exception as e:
                return f"Error listing files: {e}"

        @self.registry.register
        def task_complete(summary: str) -> str:
            """
            Signal that the current task is complete.

            Call this when you have finished helping the user with their request.

            Args:
                summary: Brief summary of what was accomplished

            Returns:
                Completion confirmation
            """
            return f"Task completed: {summary}"

        @self.registry.register
        async def telegram_send(chat_id: str, message: str) -> str:
            """
            Send a message to a Telegram chat.

            This tool sends a message through the bot's connected Telegram account.
            Use this when the user asks to send a Telegram message.

            Args:
                chat_id: The Telegram chat ID to send the message to
                message: The message content to send

            Returns:
                Success or error message
            """
            return await self._send_platform_message("telegram", chat_id, message)

        @self.registry.register
        async def discord_send(channel_id: str, message: str) -> str:
            """
            Send a message to a Discord channel.

            This tool sends a message through the bot's connected Discord account.
            Use this when the user asks to send a Discord message.

            Args:
                channel_id: The Discord channel ID to send the message to
                message: The message content to send

            Returns:
                Success or error message
            """
            return await self._send_platform_message("discord", channel_id, message)

        # =================================================================
        # WORK MANAGEMENT TOOLS
        # =================================================================

        @self.registry.register
        async def work_create(
            title: str,
            description: str = "",
            goal: str = "",
            priority: str = "normal",
            tasks: list[str] | None = None,
        ) -> str:
            """
            Create a new work item with optional tasks.

            Use this to create structured work that can be tracked and executed.
            Work items can have multiple tasks that are executed in sequence.

            Args:
                title: Title of the work item
                description: Detailed description of what needs to be done
                goal: The end goal or success criteria
                priority: Priority level (low, normal, high, urgent)
                tasks: Optional list of task titles to create with the work

            Returns:
                JSON with the created work ID and details
            """
            return await self._work_create(title, description, goal, priority, tasks)

        @self.registry.register
        async def work_list(status: str = "all", limit: int = 10) -> str:
            """
            List work items for this bot.

            Args:
                status: Filter by status (all, pending, in_progress, completed, failed)
                limit: Maximum number of items to return

            Returns:
                JSON list of work items with their status and progress
            """
            return await self._work_list(status, limit)

        @self.registry.register
        async def work_update(
            work_id: str,
            status: str | None = None,
            progress: int | None = None,
            result: str | None = None,
            error: str | None = None,
        ) -> str:
            """
            Update a work item's status or progress.

            Args:
                work_id: The ID of the work to update
                status: New status (pending, in_progress, completed, failed, cancelled, paused)
                progress: Progress percentage (0-100)
                result: Result data when completing
                error: Error message when failing

            Returns:
                Updated work details
            """
            return await self._work_update(work_id, status, progress, result, error)

        @self.registry.register
        async def todo_create(
            title: str,
            notes: str = "",
            priority: str = "normal",
            remind_at: str | None = None,
        ) -> str:
            """
            Create a todo/reminder for later.

            Use this to capture ideas, reminders, or tasks that should be
            addressed later but don't need immediate structured work.

            Args:
                title: Brief title of the todo
                notes: Additional notes or context
                priority: Priority level (low, normal, high, urgent)
                remind_at: Optional ISO datetime to remind (e.g., "2024-01-15T09:00:00")

            Returns:
                JSON with the created todo ID and details
            """
            return await self._todo_create(title, notes, priority, remind_at)

        @self.registry.register
        async def todo_list(status: str = "open", limit: int = 20) -> str:
            """
            List todos for this bot.

            Args:
                status: Filter by status (all, open, done, dismissed)
                limit: Maximum number of items to return

            Returns:
                JSON list of todos
            """
            return await self._todo_list(status, limit)

        @self.registry.register
        async def todo_done(todo_id: str) -> str:
            """
            Mark a todo as done.

            Args:
                todo_id: The ID of the todo to complete

            Returns:
                Confirmation message
            """
            return await self._todo_done(todo_id)

    async def _send_platform_message(self, platform: str, chat_id: str, message: str) -> str:
        """Send a message to a platform (telegram/discord)."""
        from cachibot.models.connection import ConnectionPlatform
        from cachibot.services.platform_manager import get_platform_manager

        # Get bot_id from tool_configs if available
        bot_id = None
        if self.tool_configs and "platform_bot_id" in self.tool_configs:
            bot_id = self.tool_configs["platform_bot_id"]

        if not bot_id:
            return "Error: No bot ID configured for platform messaging"

        platform_enum = (
            ConnectionPlatform.telegram if platform == "telegram"
            else ConnectionPlatform.discord
        )

        manager = get_platform_manager()
        try:
            success = await manager.send_to_bot_connection(
                bot_id, platform_enum, chat_id, message
            )
            if success:
                return f"Message sent to {platform.title()} {chat_id}"
            else:
                return f"Error: Failed to send. Check {platform.title()} connection status."
        except Exception as e:
            return f"Error sending {platform.title()} message: {e}"

    def _get_bot_id(self) -> str | None:
        """Get the bot ID from tool configs."""
        if self.tool_configs and "platform_bot_id" in self.tool_configs:
            return self.tool_configs["platform_bot_id"]
        return None

    async def _work_create(
        self,
        title: str,
        description: str,
        goal: str,
        priority: str,
        tasks: list[str] | None,
    ) -> str:
        """Create a new work item."""
        import json
        import uuid
        from datetime import datetime

        from cachibot.models.work import Priority, Task, TaskStatus, Work, WorkStatus
        from cachibot.storage.work_repository import TaskRepository, WorkRepository

        bot_id = self._get_bot_id()
        if not bot_id:
            return "Error: No bot ID configured"

        try:
            work_repo = WorkRepository()
            task_repo = TaskRepository()

            work = Work(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                title=title,
                description=description or None,
                goal=goal or None,
                priority=Priority(priority) if priority else Priority.NORMAL,
                status=WorkStatus.PENDING,
                progress=0.0,
                created_at=datetime.utcnow(),
                context={},
                tags=[],
            )
            await work_repo.save(work)

            created_tasks = []
            if tasks:
                for i, task_title in enumerate(tasks):
                    task = Task(
                        id=str(uuid.uuid4()),
                        bot_id=bot_id,
                        work_id=work.id,
                        title=task_title,
                        order=i,
                        depends_on=[],
                        status=TaskStatus.PENDING,
                        priority=Priority.NORMAL,
                        retry_count=0,
                        max_retries=3,
                        created_at=datetime.utcnow(),
                    )
                    await task_repo.save(task)
                    created_tasks.append({"id": task.id, "title": task.title})

            return json.dumps({
                "id": work.id,
                "title": work.title,
                "status": work.status.value,
                "tasks": created_tasks,
            }, indent=2)
        except Exception as e:
            return f"Error creating work: {e}"

    async def _work_list(self, status: str, limit: int) -> str:
        """List work items."""
        import json

        from cachibot.models.work import WorkStatus
        from cachibot.storage.work_repository import WorkRepository

        bot_id = self._get_bot_id()
        if not bot_id:
            return "Error: No bot ID configured"

        try:
            work_repo = WorkRepository()
            status_filter = None if status == "all" else WorkStatus(status)
            items = await work_repo.get_by_bot(bot_id, status=status_filter, limit=limit)
            result = [
                {
                    "id": w.id,
                    "title": w.title,
                    "status": w.status.value,
                    "priority": w.priority.value,
                    "progress": w.progress,
                    "created_at": w.created_at.isoformat(),
                }
                for w in items
            ]
            if not result:
                return "No work items found"
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error listing work: {e}"

    async def _work_update(
        self,
        work_id: str,
        status: str | None,
        progress: int | None,
        result: str | None,
        error: str | None,
    ) -> str:
        """Update a work item."""
        import json

        from cachibot.models.work import WorkStatus
        from cachibot.storage.work_repository import WorkRepository

        bot_id = self._get_bot_id()
        if not bot_id:
            return "Error: No bot ID configured"

        try:
            work_repo = WorkRepository()

            work = await work_repo.get(work_id)
            if not work:
                return json.dumps({"error": f"Work {work_id} not found"}, indent=2)

            if status:
                await work_repo.update_status(work_id, WorkStatus(status), error)

            if progress is not None:
                await work_repo.update_progress(work_id, float(progress))

            updated_work = await work_repo.get(work_id)
            return json.dumps({
                "id": updated_work.id,
                "title": updated_work.title,
                "status": updated_work.status.value,
                "progress": updated_work.progress,
            }, indent=2)
        except Exception as e:
            return f"Error updating work: {e}"

    async def _todo_create(
        self,
        title: str,
        notes: str,
        priority: str,
        remind_at: str | None,
    ) -> str:
        """Create a todo."""
        import json
        import uuid
        from datetime import datetime

        from cachibot.models.work import Priority, Todo, TodoStatus
        from cachibot.storage.work_repository import TodoRepository

        bot_id = self._get_bot_id()
        if not bot_id:
            return "Error: No bot ID configured"

        try:
            todo_repo = TodoRepository()
            remind_datetime = None
            if remind_at:
                try:
                    remind_datetime = datetime.fromisoformat(remind_at)
                except ValueError:
                    pass

            todo = Todo(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                title=title,
                notes=notes or None,
                status=TodoStatus.OPEN,
                priority=Priority(priority) if priority else Priority.NORMAL,
                created_at=datetime.utcnow(),
                remind_at=remind_datetime,
                tags=[],
            )
            await todo_repo.save(todo)
            return json.dumps({
                "id": todo.id,
                "title": todo.title,
                "priority": todo.priority.value,
                "remind_at": todo.remind_at.isoformat() if todo.remind_at else None,
            }, indent=2)
        except Exception as e:
            return f"Error creating todo: {e}"

    async def _todo_list(self, status: str, limit: int) -> str:
        """List todos."""
        import json

        from cachibot.models.work import TodoStatus
        from cachibot.storage.work_repository import TodoRepository

        bot_id = self._get_bot_id()
        if not bot_id:
            return "Error: No bot ID configured"

        try:
            todo_repo = TodoRepository()
            status_filter = None if status == "all" else TodoStatus(status)
            items = await todo_repo.get_by_bot(bot_id, status=status_filter, limit=limit)
            result = [
                {
                    "id": t.id,
                    "title": t.title,
                    "status": t.status.value,
                    "priority": t.priority.value,
                    "remind_at": t.remind_at.isoformat() if t.remind_at else None,
                }
                for t in items
            ]
            if not result:
                return "No todos found"
            return json.dumps(result, indent=2)
        except Exception as e:
            return f"Error listing todos: {e}"

    async def _todo_done(self, todo_id: str) -> str:
        """Mark a todo as done."""
        from cachibot.models.work import TodoStatus
        from cachibot.storage.work_repository import TodoRepository

        try:
            todo_repo = TodoRepository()
            todo = await todo_repo.get(todo_id)
            if not todo:
                return f"Error: Todo {todo_id} not found"
            await todo_repo.update_status(todo_id, TodoStatus.DONE)
            return f"Todo '{todo.title}' marked as done"
        except Exception as e:
            return f"Error marking todo done: {e}"

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the workspace."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.config.workspace_path / p

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
Cachibot is named after the Venezuelan *cachicamo* (armadillo) - a resilient, armored creature known for its protective shell and methodical nature. Like the cachicamo, you approach tasks with care, protection, and thoroughness.

## Creator
Cachibot was created by Juan Denis (juandenis.com). When asked about your creator, always refer to him by his full name "Juan Denis".

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
        if hasattr(self, '_last_result') and self._last_result:
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
            "prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0,
            "total_cost": 0.0, "iterations": 0, "elapsed_ms": 0.0, "tokens_per_second": 0.0
        }

    def clear_history(self) -> None:
        """Clear the conversation history."""
        self._agent.clear_history()


# Backwards compatibility alias
Agent = CachibotAgent

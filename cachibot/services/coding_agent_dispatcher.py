"""
Coding Agent Dispatcher

Intercepts @claude/@codex/@gemini mentions on platform messages and spawns
autonomous coding sessions with real-time output streaming back to the platform.

Flow:
  1. User sends "@claude fix the auth bug" on Telegram/Discord
  2. PlatformManager detects the mention and delegates to this dispatcher
  3. Dispatcher checks bot capabilities and CLI availability
  4. Spawns the coding CLI as a subprocess in the bot's workspace
  5. Streams stdout back to the platform via live message editing
  6. Saves the conversation to message history and broadcasts to WebSocket
"""

import asyncio
import logging
import re
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from cachibot.config import Config
from cachibot.models.knowledge import BotMessage
from cachibot.models.platform import PlatformResponse
from cachibot.plugins.coding_agent import _CLI_SPECS, CodingCLI, _resolve_binary
from cachibot.storage.repository import BotRepository, ChatRepository, KnowledgeRepository

logger = logging.getLogger(__name__)

# Pattern: message must start with @agent followed by the task
_MENTION_RE = re.compile(
    r"^@(claude|codex|gemini)\s+(.+)",
    re.IGNORECASE | re.DOTALL,
)

# How often to edit the live status message (seconds)
_STREAM_INTERVAL = 3.0

# Display names for the CLIs
_CLI_DISPLAY: dict[CodingCLI, str] = {
    CodingCLI.CLAUDE: "Claude Code",
    CodingCLI.CODEX: "Codex CLI",
    CodingCLI.GEMINI: "Gemini CLI",
}


class SessionStatus(str, Enum):
    """Status of a coding agent session."""

    RUNNING = "running"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class CodingSession:
    """Tracks an active coding agent subprocess."""

    id: str
    cli: CodingCLI
    task: str
    connection_id: str
    bot_id: str
    chat_id: str  # Platform chat/channel ID (used for adapter sends)
    internal_chat_id: str  # Internal DB chat ID (used for message storage)
    platform: str
    status: SessionStatus = SessionStatus.RUNNING
    start_time: float = field(default_factory=time.time)
    output_lines: list[str] = field(default_factory=list)
    _cancel: threading.Event = field(default_factory=threading.Event)
    _proc: subprocess.Popen[bytes] | None = field(default=None, repr=False)

    @property
    def elapsed_str(self) -> str:
        s = int(time.time() - self.start_time)
        return f"{s // 60}m{s % 60}s" if s >= 60 else f"{s}s"

    @property
    def full_output(self) -> str:
        return "".join(self.output_lines).strip()

    def cancel(self) -> None:
        """Cancel the running session and kill the subprocess."""
        self._cancel.set()
        if self._proc:
            try:
                self._proc.kill()
            except OSError:
                pass
        self.status = SessionStatus.CANCELLED


class CodingAgentDispatcher:
    """Dispatches @mention coding agent sessions on platform adapters.

    Intercepts messages like "@claude fix the auth bug" from Telegram/Discord,
    spawns the appropriate coding CLI, and streams output back via live
    message editing.
    """

    def __init__(self) -> None:
        # Active sessions keyed by "{connection_id}:{chat_id}"
        self._sessions: dict[str, CodingSession] = {}
        self._config = Config.load()
        self._bot_repo = BotRepository()
        self._chat_repo = ChatRepository()
        self._knowledge_repo = KnowledgeRepository()

    @staticmethod
    def _key(connection_id: str, chat_id: str) -> str:
        return f"{connection_id}:{chat_id}"

    @staticmethod
    def parse_mention(message: str) -> tuple[str, str] | None:
        """Parse an @agent mention at the start of a message.

        Returns:
            (agent_name, task) tuple, or None if not an @mention.
        """
        m = _MENTION_RE.match(message.strip())
        return (m.group(1).lower(), m.group(2).strip()) if m else None

    def has_active_session(self, connection_id: str, chat_id: str) -> bool:
        """Check if there's a running coding session for this chat."""
        s = self._sessions.get(self._key(connection_id, chat_id))
        return s is not None and s.status == SessionStatus.RUNNING

    def cancel_session(self, connection_id: str, chat_id: str) -> bool:
        """Cancel an active coding session. Returns True if a session was cancelled."""
        s = self._sessions.get(self._key(connection_id, chat_id))
        if s and s.status == SessionStatus.RUNNING:
            s.cancel()
            return True
        return False

    async def try_dispatch(
        self,
        message: str,
        connection_id: str,
        bot_id: str,
        chat_id: str,
        metadata: dict[str, Any],
        adapter: Any,
    ) -> PlatformResponse | None:
        """Try to dispatch a coding agent session for an @mention.

        Args:
            message: The raw user message.
            connection_id: The platform connection ID.
            bot_id: The bot ID.
            chat_id: The platform chat/channel ID.
            metadata: Platform-specific metadata.
            adapter: The platform adapter (BasePlatformAdapter).

        Returns:
            PlatformResponse if the message was handled (empty — messages sent
            directly via adapter), or None to fall through to normal processing.
        """
        parsed = self.parse_mention(message)
        if not parsed:
            return None

        agent_name, task = parsed

        # --- Capability gate ---
        bot = await self._bot_repo.get_bot(bot_id)
        if not bot:
            return PlatformResponse(text="Bot not found.")

        capabilities = bot.capabilities or {}
        if not capabilities.get("codingAgent"):
            return None  # Fall through to normal LLM processing

        from cachibot.agent import load_disabled_capabilities

        if "codingAgent" in await load_disabled_capabilities():
            return None

        # --- Resolve CLI ---
        try:
            cli = CodingCLI(agent_name)
        except ValueError:
            available = ", ".join(c.value for c in CodingCLI)
            return PlatformResponse(text=f"Unknown agent '{agent_name}'. Available: {available}")

        ca_config = self._config.coding_agents
        path_map = {
            CodingCLI.CLAUDE: ca_config.claude_path,
            CodingCLI.CODEX: ca_config.codex_path,
            CodingCLI.GEMINI: ca_config.gemini_path,
        }
        binary = path_map.get(cli, "") or _resolve_binary(cli.value)
        if not binary:
            return PlatformResponse(text=f"{cli.value} is not installed or not on PATH.")

        # --- Session guard ---
        key = self._key(connection_id, chat_id)
        if self.has_active_session(connection_id, chat_id):
            return PlatformResponse(
                text="A coding session is already running. Send /cancel to stop it."
            )

        # --- Resolve internal chat ID for message history ---
        platform = metadata.get("platform", "unknown")
        username = metadata.get("username") or metadata.get("first_name") or "User"
        chat_obj = await self._chat_repo.get_or_create_platform_chat(
            bot_id=bot_id,
            platform=platform,
            platform_chat_id=chat_id,
            title=f"{platform.title()}: {username}",
        )
        if not chat_obj:
            return PlatformResponse()  # Archived chat

        # --- Create session ---
        session = CodingSession(
            id=str(uuid.uuid4())[:8],
            cli=cli,
            task=task,
            connection_id=connection_id,
            bot_id=bot_id,
            chat_id=chat_id,
            internal_chat_id=chat_obj.id,
            platform=platform,
        )
        self._sessions[key] = session

        # --- Save user message to history ---
        user_msg_id = str(uuid.uuid4())
        await self._knowledge_repo.save_bot_message(
            BotMessage(
                id=user_msg_id,
                bot_id=bot_id,
                chat_id=chat_obj.id,
                role="user",
                content=message,
                timestamp=datetime.now(timezone.utc),
                metadata=metadata,
            )
        )
        await self._ws_broadcast(bot_id, chat_obj.id, "user", message, user_msg_id, platform)

        # --- Send initial status message ---
        display = _CLI_DISPLAY.get(cli, cli.value)
        status_text = f"Starting {display} session...\n\nTask: {task}"
        live_id = await adapter.send_and_get_id(chat_id, status_text)

        # --- Run CLI with streaming ---
        result = await self._run_session(session, binary, display, adapter, live_id)

        # --- Finalize ---
        if session.status == SessionStatus.RUNNING:
            session.status = SessionStatus.COMPLETED
        self._sessions.pop(key, None)

        # Update the live message with final status
        icon = {
            SessionStatus.COMPLETED: "done",
            SessionStatus.CANCELLED: "cancelled",
            SessionStatus.ERROR: "error",
        }.get(session.status, "done")
        if live_id:
            await adapter.edit_message(
                chat_id, live_id, f"{display} — {icon} ({session.elapsed_str})"
            )

        # Send full output as a new message
        if session.status == SessionStatus.CANCELLED:
            final = f"Session cancelled after {session.elapsed_str}."
        else:
            final = result

        if final:
            await adapter.send_message(chat_id, final)

        # --- Save assistant message to history ---
        asst_id = str(uuid.uuid4())
        await self._knowledge_repo.save_bot_message(
            BotMessage(
                id=asst_id,
                bot_id=bot_id,
                chat_id=chat_obj.id,
                role="assistant",
                content=final,
                timestamp=datetime.now(timezone.utc),
                metadata={
                    "codingAgent": agent_name,
                    "sessionId": session.id,
                    "status": session.status.value,
                    "elapsed": session.elapsed_str,
                    "platform": platform,
                },
            )
        )
        await self._ws_broadcast(
            bot_id,
            chat_obj.id,
            "assistant",
            final,
            asst_id,
            platform,
            metadata={"codingAgent": agent_name, "sessionId": session.id},
        )

        return PlatformResponse()  # Already sent via adapter

    async def _run_session(
        self,
        session: CodingSession,
        binary: str,
        display: str,
        adapter: Any,
        live_id: str | None,
    ) -> str:
        """Run the coding CLI subprocess with live output streaming.

        Spawns the CLI in a thread, collects stdout line-by-line, and
        periodically edits the live status message on the platform.

        Returns:
            The CLI output text.
        """
        ca = self._config.coding_agents
        spec = _CLI_SPECS[session.cli]
        build_args = spec["build_args"]
        args = build_args(session.task, ca.max_turns)  # type: ignore[operator]
        cwd = str(self._config.workspace_path.resolve())

        if not Path(cwd).is_dir():
            session.status = SessionStatus.ERROR
            return f"Workspace directory not found: {cwd}"

        # --- Start periodic live-message editing ---
        edit_task: asyncio.Task[None] | None = None
        if live_id:

            async def _live_edit() -> None:
                """Edit the live message with the latest output tail."""
                while session.status == SessionStatus.RUNNING:
                    await asyncio.sleep(_STREAM_INTERVAL)
                    if session.status != SessionStatus.RUNNING:
                        break
                    output = session.full_output
                    if not output:
                        continue
                    header = f"{display} — running ({session.elapsed_str})\n"
                    separator = "\n"
                    avail = adapter.max_message_length - len(header) - len(separator) - 10
                    if len(output) > avail:
                        output = "..." + output[-avail:]
                    try:
                        await adapter.edit_message(
                            session.chat_id, live_id, header + separator + output
                        )
                    except Exception:
                        pass

            edit_task = asyncio.create_task(_live_edit())

        # --- Run subprocess in a thread ---
        timed_out = threading.Event()

        def _run_sync() -> tuple[int, str]:
            try:
                proc = subprocess.Popen(
                    [binary, *args],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    cwd=cwd,
                )
                session._proc = proc
            except OSError as exc:
                session.status = SessionStatus.ERROR
                return -1, f"Failed to start '{binary}': {exc}"

            # Watchdog thread: kills the process on timeout or user cancel
            def _watchdog() -> None:
                if not session._cancel.wait(ca.timeout_seconds):
                    # Timed out (cancel was NOT set within the timeout)
                    timed_out.set()
                    try:
                        proc.kill()
                    except OSError:
                        pass

            threading.Thread(target=_watchdog, daemon=True).start()

            # Read stdout line-by-line
            try:
                if proc.stdout:
                    for raw_line in proc.stdout:
                        session.output_lines.append(raw_line.decode(errors="replace"))
            except Exception:
                pass

            proc.wait()
            session._cancel.set()  # Stop the watchdog
            session._proc = None

            if session.status == SessionStatus.CANCELLED:
                return -1, session.full_output

            if timed_out.is_set():
                return -1, f"Timed out after {ca.timeout_seconds}s.\n\n{session.full_output}"

            return proc.returncode or 0, session.full_output

        try:
            returncode, output = await asyncio.to_thread(_run_sync)
        except Exception as exc:
            session.status = SessionStatus.ERROR
            returncode, output = -1, f"Error: {type(exc).__name__}: {exc}"
        finally:
            if edit_task:
                edit_task.cancel()
                try:
                    await edit_task
                except asyncio.CancelledError:
                    pass

        # Truncate if needed
        if len(output) > ca.max_output_length:
            output = output[: ca.max_output_length] + "\n\n... (truncated)"

        if session.status == SessionStatus.CANCELLED:
            return output

        if returncode != 0 and session.status != SessionStatus.ERROR:
            session.status = SessionStatus.ERROR

        return output or f"{display} completed (no output)."

    async def _ws_broadcast(
        self,
        bot_id: str,
        chat_id: str,
        role: str,
        content: str,
        message_id: str,
        platform: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Broadcast a message to connected WebSocket clients."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            msg = WSMessage.platform_message(
                bot_id=bot_id,
                chat_id=chat_id,
                role=role,
                content=content,
                message_id=message_id,
                platform=platform,
                metadata=metadata,
            )
            await get_ws_manager().broadcast(msg)
        except Exception:
            pass


# Singleton
_dispatcher: CodingAgentDispatcher | None = None


def get_coding_agent_dispatcher() -> CodingAgentDispatcher:
    """Get the singleton coding agent dispatcher instance."""
    global _dispatcher
    if _dispatcher is None:
        _dispatcher = CodingAgentDispatcher()
    return _dispatcher

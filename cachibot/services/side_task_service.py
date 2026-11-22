"""
Side Task Service

Runs side tasks: child chats of a parent chat that work in parallel and
report back. A side task runs through the agent in the background,
independent of any WebSocket, persisting its messages into its own chat.

Concurrency: at most MAX_RUNNING_PER_PARENT run at once per parent chat;
the rest queue in ``waiting_for_slot`` and are promoted FIFO when a slot
frees. On server startup, side tasks that were ``running`` are re-queued
and resumed from their persisted chat history; the limit still applies.

File isolation (git worktrees on ``side/<slug>`` branches) arrives in E2;
from E1 the workspace is required to be a git repo, and E2 only fills in
the worktree fields on the record.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Any

from cachibot.models.chat_model import Chat
from cachibot.models.knowledge import BotMessage
from cachibot.models.side_task import (
    SideTask,
    SideTaskKind,
    SideTaskStartedBy,
    SideTaskStatus,
)
from cachibot.models.work import Work, WorkStatus
from cachibot.storage.repository import ChatRepository, KnowledgeRepository
from cachibot.storage.side_task_repository import SideTaskRepository
from cachibot.storage.work_repository import WorkRepository

logger = logging.getLogger(__name__)

# Maximum side tasks running at once per parent chat
MAX_RUNNING_PER_PARENT = 4

# How much persisted chat history a resumed side task is seeded with
_RESUME_HISTORY_LIMIT = 100

# How long an approval request waits for a user answer over WebSocket
_APPROVAL_TIMEOUT_SECONDS = 300


class SideTaskStartError(ValueError):
    """Starting a side task failed (recoverable, maps to HTTP 400)."""


class SideTaskService:
    """Starts, queues, stops and resumes side tasks."""

    def __init__(self) -> None:
        self._repo = SideTaskRepository()
        self._chat_repo = ChatRepository()
        self._knowledge_repo = KnowledgeRepository()
        self._work_repo = WorkRepository()

        # side_task_id -> asyncio.Task for running turns
        self._running: dict[str, asyncio.Task[None]] = {}
        # side_task_id -> reason, for running turns paused with needs_you
        self._pending_needs_you: dict[str, str] = {}
        # Serializes slot allocation across starts/stops/finishes
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Starting
    # ------------------------------------------------------------------

    async def start(
        self,
        *,
        parent_chat_id: str,
        bot_id: str,
        prompt: str,
        title: str | None = None,
        started_by: SideTaskStartedBy = SideTaskStartedBy.USER,
        kind: SideTaskKind = SideTaskKind.SIDE,
        group_id: str | None = None,
    ) -> SideTask:
        """Create a side task for a parent chat and queue or run it.

        Raises:
            SideTaskStartError: If the parent chat is missing, is itself a
                side task, or the workspace isn't a git repo.
        """
        parent = await self._chat_repo.get_chat(parent_chat_id)
        if parent is None or parent.bot_id != bot_id:
            raise SideTaskStartError(f"Chat {parent_chat_id} not found for bot {bot_id}")
        if parent.parent_chat_id is not None:
            raise SideTaskStartError(
                "Side tasks are one level deep: a side task cannot have its own side task"
            )

        await self._ensure_git_workspace()

        side_task = SideTask(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            parent_chat_id=parent_chat_id,
            chat_id=str(uuid.uuid4()),  # the chat row created below uses this id
            title=title or _derive_title(prompt),
            prompt=prompt,
            kind=kind,
            group_id=group_id,
            started_by=started_by,
        )

        # The side task's own chat, nested under its parent (sidebar tree)
        now = datetime.now(timezone.utc)
        chat = Chat(
            id=side_task.chat_id,
            bot_id=bot_id,
            title=side_task.title,
            platform=None,
            platform_chat_id=None,
            pinned=False,
            archived=False,
            parent_chat_id=parent_chat_id,
            created_at=now,
            updated_at=now,
        )
        await self._chat_repo.create_chat(chat)

        # Link a Work row so Runs / job runner can see the side task
        work = Work(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            chat_id=chat.id,
            title=side_task.title,
            description=prompt,
            status=WorkStatus.PENDING,
        )
        await self._work_repo.save(work)
        side_task.work_id = work.id

        async with self._lock:
            running = await self._repo.get_running_for_parent(parent_chat_id)
            if len(running) < MAX_RUNNING_PER_PARENT:
                side_task.status = SideTaskStatus.RUNNING
                side_task.started_at = datetime.now(timezone.utc)
            else:
                side_task.status = SideTaskStatus.WAITING_FOR_SLOT
            await self._repo.save(side_task)
            await self._sync_work_status(side_task)

        await self._broadcast(side_task)
        if side_task.status == SideTaskStatus.RUNNING:
            self._launch(side_task)

        return side_task

    async def _ensure_git_workspace(self) -> None:
        """Side tasks require a git workspace (E2 creates the worktree)."""
        from cachibot.config import Config

        workspace = Config.load().workspace_path

        def _check() -> bool:
            try:
                result = subprocess.run(
                    ["git", "rev-parse", "--is-inside-work-tree"],
                    cwd=workspace,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
            except (OSError, subprocess.TimeoutExpired):
                return False
            return result.returncode == 0 and result.stdout.strip() == "true"

        # Run the subprocess off the event loop so a slow/hanging git
        # binary never blocks other coroutines.
        if not await asyncio.to_thread(_check):
            raise SideTaskStartError(
                "Side tasks need the workspace to be a git repository "
                f"({workspace} is not inside a git work tree)"
            )

    # ------------------------------------------------------------------
    # Stopping
    # ------------------------------------------------------------------

    async def stop(self, side_task_id: str) -> SideTask | None:
        """Stop a side task (running turn is cancelled, slot is freed)."""
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None
        await self._stop_one(side_task)
        return await self._repo.get(side_task_id)

    async def stop_all_for_parent(self, parent_chat_id: str) -> int:
        """Stop all active side tasks of a parent chat (e.g. parent cancelled).

        Returns the number of side tasks stopped.
        """
        active = await self._repo.get_active_for_parent(parent_chat_id)
        for side_task in active:
            await self._stop_one(side_task)
        return len(active)

    async def _stop_one(self, side_task: SideTask) -> None:
        """Stop one side task and promote the next waiting one."""
        if side_task.status in (
            SideTaskStatus.DONE,
            SideTaskStatus.MERGED,
            SideTaskStatus.FAILED,
            SideTaskStatus.STOPPED,
        ):
            return  # already terminal
        if side_task.status == SideTaskStatus.RUNNING:
            task = self._running.get(side_task.id)
            if task is not None:
                # The cancelled turn settles the record in _run()
                task.cancel()
            else:
                # Running in the DB but not in memory (e.g. lost handle) —
                # mark it stopped directly so it isn't resumed on restart.
                await self._transition(side_task, SideTaskStatus.STOPPED, finished=True)
                await self._promote(side_task.parent_chat_id)
        else:
            await self._transition(side_task, SideTaskStatus.STOPPED, finished=True)
            await self._promote(side_task.parent_chat_id)

    # ------------------------------------------------------------------
    # Needs you / resume
    # ------------------------------------------------------------------

    async def mark_needs_you(self, side_task_id: str, reason: str) -> SideTask | None:
        """Pause a running side task: it waits for the user.

        The current turn is cancelled; ``resume`` re-runs it from the
        persisted chat history.
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None or side_task.status != SideTaskStatus.RUNNING:
            return side_task

        task = self._running.get(side_task.id)
        if task is not None:
            # The cancelled turn settles the record in _run()
            self._pending_needs_you[side_task.id] = reason
            task.cancel()
        else:
            side_task.needs_you_reason = reason
            await self._transition(side_task, SideTaskStatus.NEEDS_YOU)
            await self._promote(side_task.parent_chat_id)
        return side_task

    async def resume(self, side_task_id: str) -> SideTask | None:
        """Resume a side task that is waiting for the user.

        Re-runs the turn from the persisted chat history (any messages the
        user sent in the side task chat while it waited are picked up).
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None or side_task.status != SideTaskStatus.NEEDS_YOU:
            return side_task
        side_task.needs_you_reason = None
        await self._transition(side_task, SideTaskStatus.RUNNING)
        self._launch(side_task)
        return side_task

    # ------------------------------------------------------------------
    # Restart resume
    # ------------------------------------------------------------------

    async def resume_on_startup(self) -> None:
        """Re-queue and resume side tasks after a server restart.

        Side tasks that were ``running`` are resumed (from persisted chat
        history), at most MAX_RUNNING_PER_PARENT per parent chat — extras go
        back to ``waiting_for_slot``. Waiting ones stay queued and are
        promoted FIFO as slots free.
        """
        interrupted = await self._repo.get_by_statuses([SideTaskStatus.RUNNING])
        # Group by parent chat so the per-parent limit still applies
        by_parent: dict[str, list[SideTask]] = {}
        for side_task in interrupted:
            by_parent.setdefault(side_task.parent_chat_id, []).append(side_task)

        for parent_chat_id, side_tasks in by_parent.items():
            side_tasks.sort(key=lambda st: st.created_at)
            for index, side_task in enumerate(side_tasks):
                if index < MAX_RUNNING_PER_PARENT:
                    logger.info("Resuming side task %s (%s)", side_task.id, side_task.title)
                    self._launch(side_task)
                else:
                    await self._transition(
                        side_task, SideTaskStatus.WAITING_FOR_SLOT, keep_started_at=True
                    )

        # Re-arm the waiting queues
        waiting = await self._repo.get_by_statuses([SideTaskStatus.WAITING_FOR_SLOT])
        waiting_parents = {st.parent_chat_id for st in waiting}
        for parent_chat_id in waiting_parents:
            await self._promote(parent_chat_id)

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _launch(self, side_task: SideTask) -> None:
        """Start the background turn for a running side task."""
        task = asyncio.create_task(self._run(side_task.id))
        self._running[side_task.id] = task
        task.add_done_callback(lambda _t: self._running.pop(side_task.id, None))

    async def _run(self, side_task_id: str) -> None:
        """Run one side task turn and move it to its terminal state."""
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return
        try:
            await self._execute_turn(side_task)
        except asyncio.CancelledError:
            needs_you_reason = self._pending_needs_you.pop(side_task_id, None)
            latest = await self._repo.get(side_task_id)
            if latest is not None and latest.status == SideTaskStatus.RUNNING:
                if needs_you_reason is not None:
                    latest.needs_you_reason = needs_you_reason
                    await self._transition(latest, SideTaskStatus.NEEDS_YOU)
                else:
                    await self._transition(latest, SideTaskStatus.STOPPED, finished=True)
                await self._sync_work_status(latest)
                await self._promote(latest.parent_chat_id)
            # If the record is no longer RUNNING someone else settled it.
            # If cancellation came from server shutdown the record stays
            # RUNNING so resume_on_startup picks it back up.
            raise
        except Exception as exc:
            logger.exception("Side task %s failed", side_task_id)
            latest = await self._repo.get(side_task_id)
            if latest is not None:
                latest.error = str(exc)
                await self._transition(latest, SideTaskStatus.FAILED, finished=True)
                await self._sync_work_status(latest)
                await self._promote(latest.parent_chat_id)
            return

        # E2 inserts the merge step here: done -> merged, or needs_you on
        # merge conflict (recording merged_commit / merged_files).
        latest = await self._repo.get(side_task_id)
        if latest is not None and latest.status == SideTaskStatus.RUNNING:
            await self._transition(latest, SideTaskStatus.DONE, finished=True)
            await self._sync_work_status(latest)
            await self._promote(latest.parent_chat_id)

    async def _execute_turn(self, side_task: SideTask) -> None:
        """Run the side task's turn through the agent, persisting messages.

        History already in the side task's chat is seeded into the agent's
        conversation so a resumed turn continues where it left off.
        """
        from cachibot.config import Config
        from cachibot.services.agent_factory import build_bot_agent

        config = Config.load()
        agent = await build_bot_agent(
            config,
            bot_id=side_task.bot_id,
            chat_id=side_task.chat_id,
            user_message=side_task.prompt,
            platform="web",
            on_approval_needed=self._make_approval_handler(config, side_task.bot_id),
        )

        # Seed persisted history (already oldest-first). A trailing copy of
        # the prompt is dropped so it isn't replayed twice.
        history = await self._knowledge_repo.get_bot_messages(
            side_task.bot_id, side_task.chat_id, limit=_RESUME_HISTORY_LIMIT
        )
        prompt_already_persisted = False
        seeded_turns = False
        if history:
            # The prompt was persisted by a previous (interrupted) turn
            first_user = next((m for m in history if m.role == "user"), None)
            prompt_already_persisted = (
                first_user is not None and first_user.content == side_task.prompt
            )
            # Drop a trailing copy of the prompt so it isn't replayed twice
            if history[-1].role == "user" and history[-1].content == side_task.prompt:
                history = history[:-1]
            for msg in history:
                if msg.role in ("user", "assistant", "system"):
                    agent.conversation.add_context(msg.role, msg.content)
            seeded_turns = bool(history)

        # Persist the user prompt (skip on resume: the chat already has it)
        if not prompt_already_persisted:
            await self._persist_message(side_task, role="user", content=side_task.prompt)

        if seeded_turns:
            # Resumed mid-conversation (e.g. after needs_you): continue
            # from the seeded history instead of repeating the prompt cold.
            run_message = (
                "Continue this side task from where the conversation above left off.\n\n"
                f"Original task: {side_task.prompt}"
            )
        else:
            run_message = side_task.prompt

        result = await agent.run(run_message)

        response_text = result.output_text or ""
        if response_text:
            await self._persist_message(side_task, role="assistant", content=response_text)

    def _make_approval_handler(self, config: Any, bot_id: str) -> Any:
        """Approvals reuse the existing approval_needed WebSocket path.

        The request is sent only to clients with access to the bot; any of
        them can answer with the normal ``approval`` message, which resolves
        the pending request. When nobody answers in time, the agent's
        approval policy decides.
        """

        async def on_approval(tool_name: str, action: str, details: dict[str, Any]) -> bool:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            manager = get_ws_manager()
            approval_id = str(uuid.uuid4())
            event = asyncio.Event()
            manager.pending_approvals[approval_id] = event
            manager.approval_results[approval_id] = False
            await manager.broadcast_to_bot(
                WSMessage.approval_needed(approval_id, tool_name, action, details),
                bot_id,
            )
            try:
                await asyncio.wait_for(event.wait(), timeout=_APPROVAL_TIMEOUT_SECONDS)
                return bool(manager.approval_results.pop(approval_id, False))
            except TimeoutError:
                return not config.agent.approve_actions
            finally:
                manager.pending_approvals.pop(approval_id, None)
                manager.approval_results.pop(approval_id, None)

        return on_approval

    async def _persist_message(
        self,
        side_task: SideTask,
        *,
        role: str,
        content: str,
    ) -> None:
        """Write a message into the side task's own chat."""
        await self._knowledge_repo.save_bot_message(
            BotMessage(
                id=str(uuid.uuid4()),
                bot_id=side_task.bot_id,
                chat_id=side_task.chat_id,
                role=role,
                content=content,
                timestamp=datetime.now(timezone.utc),
            )
        )

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    async def _promote(self, parent_chat_id: str) -> None:
        """Promote waiting side tasks to running while a slot is free."""
        to_launch: list[SideTask] = []
        async with self._lock:
            running = await self._repo.get_running_for_parent(parent_chat_id)
            slots = MAX_RUNNING_PER_PARENT - len(running)
            while slots > 0:
                nxt = await self._repo.get_oldest_waiting_for_parent(parent_chat_id)
                if nxt is None:
                    break
                nxt.status = SideTaskStatus.RUNNING
                nxt.started_at = datetime.now(timezone.utc)
                await self._repo.update(nxt)
                await self._sync_work_status(nxt)
                to_launch.append(nxt)
                slots -= 1
        for side_task in to_launch:
            await self._broadcast(side_task)
            self._launch(side_task)

    async def _transition(
        self,
        side_task: SideTask,
        status: SideTaskStatus,
        *,
        finished: bool = False,
        keep_started_at: bool = False,
    ) -> None:
        """Move a side task to a new status and persist it."""
        side_task.status = status
        if status == SideTaskStatus.RUNNING and not keep_started_at:
            side_task.started_at = datetime.now(timezone.utc)
        if finished:
            side_task.finished_at = datetime.now(timezone.utc)
        side_task.updated_at = datetime.now(timezone.utc)
        await self._repo.update(side_task)
        await self._broadcast(side_task)

    async def _sync_work_status(self, side_task: SideTask) -> None:
        """Mirror the side task status onto its Work row (for Runs)."""
        if not side_task.work_id:
            return
        mapping = {
            SideTaskStatus.WAITING_FOR_SLOT: WorkStatus.PENDING,
            SideTaskStatus.RUNNING: WorkStatus.IN_PROGRESS,
            SideTaskStatus.NEEDS_YOU: WorkStatus.PAUSED,
            SideTaskStatus.DONE: WorkStatus.COMPLETED,
            SideTaskStatus.MERGED: WorkStatus.COMPLETED,
            SideTaskStatus.FAILED: WorkStatus.FAILED,
            SideTaskStatus.STOPPED: WorkStatus.CANCELLED,
        }
        try:
            await self._work_repo.update_status(
                side_task.work_id,
                mapping[side_task.status],
                error=side_task.error,
            )
        except Exception:
            logger.debug("Could not sync work status for side task %s", side_task.id)

    # ------------------------------------------------------------------
    # WebSocket broadcast
    # ------------------------------------------------------------------

    async def _broadcast(self, side_task: SideTask) -> None:
        """Broadcast the full side task record on every state change.

        Scoped to sockets whose user can view the bot, so side-task
        titles/prompts never leak to other users on a multi-user server.
        """
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            payload = side_task.model_dump(mode="json", by_alias=True)
            await get_ws_manager().broadcast_to_bot(
                WSMessage.side_task_update(payload), side_task.bot_id
            )
        except Exception:
            logger.debug("Could not broadcast side task update", exc_info=True)


def _derive_title(prompt: str) -> str:
    """Derive a short side task title from its prompt."""
    first_line = (prompt.strip().splitlines() or [""])[0].strip()
    if len(first_line) > 60:
        return first_line[:59].rstrip() + "…"
    return first_line or "Side task"


# Singleton
_side_task_service: SideTaskService | None = None


def get_side_task_service() -> SideTaskService:
    """Get the singleton side task service."""
    global _side_task_service
    if _side_task_service is None:
        _side_task_service = SideTaskService()
    return _side_task_service


__all__ = [
    "MAX_RUNNING_PER_PARENT",
    "SideTaskService",
    "SideTaskStartError",
    "get_side_task_service",
]

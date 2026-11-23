"""
Side Task Service

Runs side tasks: child chats of a parent chat that work in parallel and
report back. A side task runs through the agent in the background,
independent of any WebSocket, persisting its messages into its own chat.

Concurrency: at most MAX_RUNNING_PER_PARENT run at once per parent chat;
the rest queue in ``waiting_for_slot`` and are promoted FIFO when a slot
frees. On server startup, side tasks that were ``running`` are re-queued
and resumed from their persisted chat history; the limit still applies.

File isolation: each side task gets a git worktree on a
``side/<slug>-<short id>`` branch (created from the workspace HEAD when the
record first moves to running, reused across restarts). The workspace must
be a git repo or start fails with a clear error.

Bring-back: when the turn finishes successfully the side task's changes are
committed in the worktree and merged back into the parent workspace's
current branch automatically (``git merge --no-ff``). All git operations
that mutate a repository (worktree creation/removal, branch deletion,
merges) are serialized per repo — concurrent side tasks share one parent
workspace, and parallel ``git worktree add``/``remove`` on the same repo
can otherwise fail transiently.
A clean merge records ``merged_commit`` / ``merged_files`` and removes the
worktree and branch. No changes -> ``done`` with nothing to merge. A merge
conflict (or git refusing because the parent tree has local changes in the
same files) aborts the merge — the parent tree ends exactly as before — and
the side task becomes ``needs_you`` (reason ``merge_conflict``) with the
branch and worktree kept so no work is lost.

Thread replies: a side task records ``source_message_id`` — the parent-chat
message that started it (explicit for More > Do this on the side; otherwise
the latest user message in the parent chat, which is the message the
current turn is answering). While it waits or runs, the parent chat shows
only a quiet live indicator (from ``side_task_update``). When it settles
(merged / done / failed / stopped / needs_you), ONE assistant reply message
is persisted in the parent chat — quoting the source message, with the
outcome and the merge details in its metadata — and every later state
change (needs_you -> merged after Retry merge, discard, resume, a reply
that runs again) updates that same message in place. Bot-started helpers
share ONE group reply that updates as helpers progress. Clients are pushed
the create/update via the scoped ``message_update`` WebSocket event.

Replies (E6): an operator can answer inside the side task's own chat. The
reply is persisted there and the side task runs again in the same worktree
(a settled one is reused, recreated from its branch, or restarted on a
fresh branch from the parent's current HEAD), then merges back only the new
changes. Every turn also writes one execution-log row (trigger
``side_task``) with key step lines, so side tasks show up in Runs.
"""

from __future__ import annotations

import asyncio
import copy
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cachibot.config import Config
from cachibot.models.chat_model import Chat
from cachibot.models.knowledge import BotMessage
from cachibot.models.side_task import (
    SideTask,
    SideTaskGroupSummary,
    SideTaskKind,
    SideTaskStartedBy,
    SideTaskStatus,
)
from cachibot.models.work import Work, WorkStatus
from cachibot.services import side_task_worktrees as worktrees
from cachibot.storage.automations_repository import (
    ExecutionLogLineRepository,
    ExecutionLogRepository,
)
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

# Reason recorded on needs_you when an automatic merge back fails
NEEDS_YOU_MERGE_CONFLICT = "merge_conflict"

# Serializes git operations that mutate one repository (side tasks of one
# parent run concurrently, and retry-merge can arrive while another merge is
# running). Concurrent `git worktree add`/`worktree remove`/`branch -d` on
# the same repository transiently fail with errors like "failed to read
# .git/worktrees/<id>/commondir", which would surface as spurious side-task
# failures; every mutating git call runs under this per-repository lock.
# Read-only helpers (rev-parse, diff, merge-base, status) never take it.
_repo_git_locks: dict[Path, asyncio.Lock] = {}
_repo_git_locks_guard = asyncio.Lock()


async def _repo_git_lock_for(workspace: Path) -> asyncio.Lock:
    """Return the per-repository git-mutation lock for a workspace."""
    key = await asyncio.to_thread(worktrees.repo_toplevel, workspace)
    async with _repo_git_locks_guard:
        lock = _repo_git_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _repo_git_locks[key] = lock
    return lock


class SideTaskStartError(ValueError):
    """Starting a side task failed (recoverable, maps to HTTP 400)."""


class SideTaskReplyError(ValueError):
    """Replying inside a side task is not possible right now (HTTP 409)."""


class SideTaskService:
    """Starts, queues, stops and resumes side tasks."""

    def __init__(self) -> None:
        self._repo = SideTaskRepository()
        self._chat_repo = ChatRepository()
        self._knowledge_repo = KnowledgeRepository()
        self._work_repo = WorkRepository()
        self._exec_log_repo = ExecutionLogRepository()
        self._exec_line_repo = ExecutionLogLineRepository()

        # side_task_id -> asyncio.Task for running turns
        self._running: dict[str, asyncio.Task[None]] = {}
        # side_task_id -> reason, for running turns paused with needs_you
        self._pending_needs_you: dict[str, str] = {}
        # Serializes parent-chat reply create/update (concurrent finishes of
        # helpers in one group must not each create their own reply message)
        self._reply_lock = asyncio.Lock()
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
        group_title: str | None = None,
        source_message_id: str | None = None,
    ) -> SideTask:
        """Create a side task for a parent chat and queue or run it.

        ``source_message_id`` is the parent-chat message the side task is
        started from (for a reply in the parent chat). It must belong to the
        parent chat. When omitted, the latest user message in the parent chat
        is used — bot tools and the composer have no specific message, and
        the latest user message is the one the current turn is answering.

        Raises:
            SideTaskStartError: If the parent chat is missing, is itself a
                side task, the workspace isn't a git repo, or the source
                message doesn't belong to the parent chat.
        """
        parent = await self._chat_repo.get_chat(parent_chat_id)
        if parent is None or parent.bot_id != bot_id:
            raise SideTaskStartError(f"Chat {parent_chat_id} not found for bot {bot_id}")
        if parent.parent_chat_id is not None:
            raise SideTaskStartError(
                "Side tasks are one level deep: a side task cannot have its own side task"
            )

        await self._ensure_git_workspace()
        source_message_id = await self._resolve_source_message(
            bot_id, parent_chat_id, source_message_id
        )

        side_task = SideTask(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            parent_chat_id=parent_chat_id,
            chat_id=str(uuid.uuid4()),  # the chat row created below uses this id
            title=title or _derive_title(prompt),
            prompt=prompt,
            kind=kind,
            group_id=group_id,
            group_title=group_title,
            started_by=started_by,
            source_message_id=source_message_id,
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

    async def _resolve_source_message(
        self,
        bot_id: str,
        parent_chat_id: str,
        source_message_id: str | None,
    ) -> str | None:
        """Resolve and validate the parent-chat message a side task answers.

        An explicit id must belong to the parent chat. When omitted (composer
        start, or a bot tool that has no message reference), the latest user
        message in the parent chat is used — it is the message the current
        turn is answering. Returns None when the parent chat has no user
        message at all (replies then render without a quoted snippet).
        """
        if source_message_id:
            existing = await self._knowledge_repo.get_bot_message(source_message_id)
            if existing is None or existing.chat_id != parent_chat_id:
                raise SideTaskStartError(
                    f"Source message {source_message_id} does not belong to chat {parent_chat_id}"
                )
            return source_message_id
        messages = await self._knowledge_repo.get_bot_messages(bot_id, parent_chat_id, limit=200)
        last_user = next((m for m in reversed(messages) if m.role == "user"), None)
        return last_user.id if last_user is not None else None

    async def start_helpers(
        self,
        *,
        parent_chat_id: str,
        bot_id: str,
        items: list[dict[str, Any]],
        group_title: str | None = None,
        source_message_id: str | None = None,
    ) -> tuple[str, list[SideTask]]:
        """Start one helper per item, all in one new group (bot-started).

        Each item is ``{"title": ..., "prompt": ...}`` (title optional; it
        is derived from the prompt when missing). Helpers share the new
        ``group_id`` and the per-parent limit still applies: extras queue
        in ``waiting_for_slot`` and are promoted FIFO as slots free. All
        helpers share one ``source_message_id`` (see ``start``).

        Raises:
            SideTaskStartError: If the items are invalid or the parent chat
                cannot have side tasks.
        """
        if not items:
            raise SideTaskStartError("At least one helper item is required")
        normalized: list[dict[str, str | None]] = []
        for item in items:
            if not isinstance(item, dict):
                raise SideTaskStartError("Each helper item must be an object with a prompt")
            prompt = str(item.get("prompt") or "").strip()
            if not prompt:
                raise SideTaskStartError("Each helper item needs a prompt")
            raw_title = item.get("title")
            title = str(raw_title).strip() if raw_title else None
            normalized.append({"title": title or None, "prompt": prompt})

        # Validating up front (before any helper exists) keeps a bad group
        # from leaving partially started helpers behind.
        parent = await self._chat_repo.get_chat(parent_chat_id)
        if parent is None or parent.bot_id != bot_id:
            raise SideTaskStartError(f"Chat {parent_chat_id} not found for bot {bot_id}")
        if parent.parent_chat_id is not None:
            raise SideTaskStartError(
                "Side tasks are one level deep: a side task cannot have its own side task"
            )

        group_id = str(uuid.uuid4())
        started: list[SideTask] = []
        resolved_source = source_message_id
        for item in normalized:
            started.append(
                await self.start(
                    parent_chat_id=parent_chat_id,
                    bot_id=bot_id,
                    prompt=item["prompt"] or "",
                    title=item["title"],
                    started_by=SideTaskStartedBy.BOT,
                    kind=SideTaskKind.HELPER,
                    group_id=group_id,
                    group_title=group_title,
                    source_message_id=resolved_source,
                )
            )
            if resolved_source is None:
                # Share the fallback-resolved message across the group.
                resolved_source = started[-1].source_message_id
        try:
            async with self._reply_lock:
                await self._sync_group_reply(group_id)
        except Exception:
            logger.debug("Could not write helper group reply", exc_info=True)
        return group_id, started

    async def group_summary(self, group_id: str) -> SideTaskGroupSummary | None:
        """Aggregate one helper group from its real records.

        Returns None when no side task belongs to the group.
        """
        tasks = await self._repo.get_by_group(group_id)
        if not tasks:
            return None
        summary = SideTaskGroupSummary(group_id=group_id, total=len(tasks), items=tasks)
        for task in tasks:
            if summary.title is None and task.group_title:
                summary.title = task.group_title
            if task.status == SideTaskStatus.WAITING_FOR_SLOT:
                summary.waiting += 1
            elif task.status == SideTaskStatus.RUNNING:
                summary.running += 1
            elif task.status == SideTaskStatus.NEEDS_YOU:
                summary.needs_you += 1
            elif task.status in (SideTaskStatus.DONE, SideTaskStatus.MERGED):
                summary.done += 1
            elif task.status == SideTaskStatus.FAILED:
                summary.failed += 1
            # STOPPED helpers stay visible through items only: their parent
            # was stopped, so the group settles together with the parent.
        return summary

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

    async def shutdown(self) -> None:
        """Cancel every in-flight side-task turn and wait for it to settle.

        Used at app shutdown and by tests in teardown, so no background turn
        outlives the database/loop it was started with.
        """
        tasks = [t for t in self._running.values() if not t.done()]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

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

    async def retry_merge(self, side_task_id: str) -> SideTask | None:
        """Retry merging back a side task stuck on a merge conflict.

        For the user to call after fixing things in either tree (resolving
        in the side worktree, or changing the parent so it merges cleanly).
        Any pending changes in the worktree are committed first. On success
        the side task becomes ``merged`` and the worktree/branch are
        cleaned up; on another conflict it stays ``needs_you`` with the
        updated conflict paths. Work is never lost along the way.
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None
        if (
            side_task.status != SideTaskStatus.NEEDS_YOU
            or side_task.needs_you_reason != NEEDS_YOU_MERGE_CONFLICT
        ):
            raise SideTaskStartError(
                "retry-merge is only for a side task waiting on a merge conflict"
            )

        config = Config.load()
        workspace = Path(config.workspace_path)

        # The worktree may have been removed while the conflict waited;
        # recreate it from the branch when possible.
        await self._prepare_worktree(side_task)
        side_task = await self._repo.get(side_task_id)
        if side_task is None or not side_task.worktree_path or not side_task.branch:
            raise SideTaskStartError("Side task has no workspace to merge from")

        # Commit any changes the user made while resolving (in either tree's
        # favor); without this their edits would be left uncommitted.
        await asyncio.to_thread(
            worktrees.commit_all_changes,
            Path(side_task.worktree_path),
            f"Side task: {side_task.title}",
        )

        async with await _repo_git_lock_for(workspace):
            outcome = await asyncio.to_thread(worktrees.merge_side_branch, workspace, side_task)

        if outcome.merged:
            side_task.merged_commit = outcome.merged_commit
            side_task.merged_files = outcome.merged_files
            side_task.conflict_files = []
            side_task.needs_you_reason = None
            await self._cleanup_after_merge(workspace, side_task)
            await self._transition(side_task, SideTaskStatus.MERGED, finished=True)
            await self._sync_work_status(side_task)
            return await self._repo.get(side_task_id)

        if outcome.conflict_files:
            side_task.conflict_files = outcome.conflict_files
            await self._repo.update(side_task)
            await self._broadcast(side_task)
            return side_task

        if outcome.error and "no longer exists" in outcome.error:
            # The branch was merged or deleted by hand while it waited:
            # nothing left to bring back.
            await self._cleanup_after_merge(workspace, side_task)
            side_task.needs_you_reason = None
            await self._transition(side_task, SideTaskStatus.DONE, finished=True)
            await self._sync_work_status(side_task)
            return await self._repo.get(side_task_id)

        raise SideTaskStartError(outcome.error or "git merge failed")

    async def discard(self, side_task_id: str) -> SideTask | None:
        """Discard a stopped, failed or needs_you side task for good.

        Removes the worktree (force: the user explicitly threw the work
        away) and deletes the branch with -D — the only place a side branch
        is ever force-deleted. Running/waiting/merged side tasks cannot be
        discarded; stop them first.
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None
        if side_task.status not in (
            SideTaskStatus.STOPPED,
            SideTaskStatus.FAILED,
            SideTaskStatus.NEEDS_YOU,
        ):
            raise SideTaskStartError(
                "Only a stopped, failed or needs-you side task can be discarded"
            )

        config = Config.load()
        workspace = Path(config.workspace_path)

        # The user explicitly threw the work away; tolerate pieces that are
        # already gone (cleaned up by hand) and keep going. Both removals
        # mutate the repo: serialized with worktree creation and merges.
        async with await _repo_git_lock_for(workspace):
            if side_task.worktree_path:
                wt_path = Path(side_task.worktree_path)
                if worktrees.worktree_exists(wt_path):
                    try:
                        await asyncio.to_thread(
                            worktrees.remove_worktree, workspace, wt_path, force=True
                        )
                    except worktrees.WorktreeError:
                        logger.warning(
                            "Could not remove worktree %s while discarding",
                            wt_path,
                            exc_info=True,
                        )
            if side_task.branch:
                try:
                    await asyncio.to_thread(
                        worktrees.delete_branch, workspace, side_task.branch, force=True
                    )
                except worktrees.WorktreeError:
                    logger.warning(
                        "Could not delete branch %s while discarding",
                        side_task.branch,
                        exc_info=True,
                    )

        side_task.needs_you_reason = None
        await self._transition(side_task, SideTaskStatus.STOPPED, finished=True)
        await self._sync_work_status(side_task)
        return await self._repo.get(side_task_id)

    # ------------------------------------------------------------------
    # Replies inside the side task's own chat (E6)
    # ------------------------------------------------------------------

    async def reply(self, side_task_id: str, content: str) -> SideTask | None:
        """Reply inside a side task's own chat and continue its turn.

        The message is persisted into the side chat and the side task runs
        again in its own worktree (same tool/file sandboxing as the original
        run); when the turn settles its work is merged back automatically —
        only the changes since the previous bring-in — and the parent chat's
        thread reply is updated in place. The per-parent limit still
        applies: when 4 side tasks of the parent are running, the replied
        one waits for a slot.

        Allowed once the side task is settled: ``done``/``merged`` (a fresh
        branch is started from the parent's current HEAD, so only new work
        comes back), ``failed``/``stopped``/``needs_you`` (non-conflict)
        while the worktree or branch still exists (the existing work
        continues). A ``needs_you`` merge conflict must be resolved with
        retry-merge or discard first; running/waiting side tasks get
        ``SideTaskReplyError``.

        Raises:
            SideTaskReplyError: The side task cannot take a reply right now.
            SideTaskStartError: The workspace/branch needed to continue is
                gone for good (not a git repo, parent branch missing...).
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None
        content = content.strip()
        if not content:
            raise SideTaskReplyError("Reply content must not be empty")
        if side_task.status in (
            SideTaskStatus.RUNNING,
            SideTaskStatus.WAITING_FOR_SLOT,
        ):
            raise SideTaskReplyError(
                f'"{side_task.title}" is still working — reply once it settles'
            )
        if (
            side_task.status == SideTaskStatus.NEEDS_YOU
            and side_task.needs_you_reason == NEEDS_YOU_MERGE_CONFLICT
        ):
            raise SideTaskReplyError(
                "Resolve the merge conflict first (Retry merge or Discard), then reply"
            )
        if side_task.status not in (
            SideTaskStatus.DONE,
            SideTaskStatus.MERGED,
            SideTaskStatus.FAILED,
            SideTaskStatus.STOPPED,
            SideTaskStatus.NEEDS_YOU,
        ):
            raise SideTaskReplyError(f'"{side_task.title}" cannot take a reply right now')

        # Make sure there is a worktree to continue in: reuse the existing
        # one, recreate it from the surviving branch, or start a fresh
        # branch from the parent's current HEAD (done/merged/discarded).
        await self._prepare_worktree_for_reply(side_task)
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None

        # Persist the reply into the side task's own chat; _execute_turn
        # picks the newest user message as the input for the continued turn.
        await self._persist_message(side_task, role="user", content=content)

        async with self._lock:
            running = await self._repo.get_running_for_parent(side_task.parent_chat_id)
            side_task.finished_at = None
            side_task.error = None
            side_task.needs_you_reason = None
            if len(running) < MAX_RUNNING_PER_PARENT:
                side_task.status = SideTaskStatus.RUNNING
                side_task.started_at = datetime.now(timezone.utc)
            else:
                side_task.status = SideTaskStatus.WAITING_FOR_SLOT
            await self._repo.update(side_task)
            await self._sync_work_status(side_task)

        await self._broadcast(side_task)
        if side_task.status == SideTaskStatus.RUNNING:
            self._launch(side_task)
        # The parent reply must not keep offering the old settled state while
        # the continued turn runs (or waits for a slot): update it in place.
        await self._reply_in_parent_chat(side_task)
        return await self._repo.get(side_task_id)

    async def _prepare_worktree_for_reply(self, side_task: SideTask) -> None:
        """Ensure a settled side task has a worktree to continue in.

        - Worktree dir still there: continue in it (uncommitted work intact).
        - Worktree gone but the branch lives: recreate the checkout from it.
        - Neither (merged and cleaned up, or discarded): clear the recorded
          branch/base so a fresh ``side/<slug>-<short id>`` branch is created
          from the parent's current HEAD — the previous work already came
          back (or was thrown away), so only new changes may merge.

        Raises SideTaskStartError when the workspace is no longer a git repo
        or git cannot create the worktree.
        """
        if side_task.worktree_path and worktrees.worktree_exists(Path(side_task.worktree_path)):
            return
        config = Config.load()
        workspace = Path(config.workspace_path)
        if side_task.branch:
            try:
                branch_tip = await asyncio.to_thread(
                    worktrees.branch_sha, workspace, side_task.branch
                )
            except worktrees.WorktreeError:
                # The workspace itself is gone/unreadable — let the fresh
                # worktree attempt below surface the real error.
                branch_tip = None
            if branch_tip:
                await self._prepare_worktree(side_task)
                return
        side_task.worktree_path = None
        side_task.branch = None
        side_task.base_commit = None
        await self._prepare_worktree(side_task)

    async def diff(self, side_task_id: str) -> worktrees.SideTaskDiff | None:
        """The unified diff + per-file stats behind "View changes".

        None when the side task does not exist. Read-only: never creates a
        worktree and never touches the repository.
        """
        side_task = await self._repo.get(side_task_id)
        if side_task is None:
            return None
        config = Config.load()
        workspace = Path(config.workspace_path)
        return await asyncio.to_thread(worktrees.compute_diff, workspace, side_task)

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

        def _done(t: asyncio.Task[None], side_task_id: str = side_task.id) -> None:
            # Only drop the handle when it is still THIS turn: a resume or a
            # reply can launch the next turn before the cancelled previous
            # one finishes, and its done-callback must not evict the new
            # handle (Stop would then lose the running turn and fall back to
            # the direct-transition path while it keeps working).
            if self._running.get(side_task_id) is t:
                self._running.pop(side_task_id, None)

        self._running[side_task.id] = task
        task.add_done_callback(_done)

    async def _run(self, side_task_id: str) -> None:
        """Run one side task turn and move it to its terminal state.

        Every turn (first run, resume, continuation after a reply) writes one
        execution-log row — with key step lines — so the side task shows up
        in Runs like any other background run. The whole body runs inside
        the cancellation handler: a turn cancelled at ANY point (including
        before its first database read) must still settle the record, or it
        would stay ``running`` forever.
        """
        exec_log_id: str | None = None
        try:
            side_task = await self._repo.get(side_task_id)
            if side_task is None:
                return
            exec_log_id = await self._start_execution_log(side_task)
            await self._prepare_worktree(side_task)
            # Re-fetch: _prepare_worktree persisted worktree_path/branch/base_commit
            latest = await self._repo.get(side_task_id)
            if latest is None:
                return
            if latest.worktree_path:
                await self._exec_line(
                    exec_log_id,
                    "info",
                    f"Worktree ready at {latest.worktree_path}"
                    + (f" on {latest.branch}" if latest.branch else ""),
                )
            await self._execute_turn(latest)
            await self._exec_line(exec_log_id, "info", "Turn finished")

            # The turn finished successfully: commit and merge the work back
            latest = await self._repo.get(side_task_id)
            if latest is not None and latest.status == SideTaskStatus.RUNNING:
                await self._finish_and_merge(latest)
                await self._promote(latest.parent_chat_id)
                settled = await self._repo.get(side_task_id)
                if settled is not None:
                    await self._exec_line(exec_log_id, "info", _settle_line(settled))
                    await self._finish_execution_log(exec_log_id, settled)
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
                settled = await self._repo.get(side_task_id)
                if settled is not None:
                    await self._exec_line(exec_log_id, "info", _settle_line(settled))
                    await self._finish_execution_log(exec_log_id, settled)
            # If the record is no longer RUNNING someone else settled it.
            # If cancellation came from server shutdown the record stays
            # RUNNING so resume_on_startup picks it back up. The worktree
            # is left in place: a cancelled turn may have uncommitted work.
            raise
        except Exception as exc:
            logger.exception("Side task %s failed", side_task_id)
            latest = await self._repo.get(side_task_id)
            if latest is not None:
                latest.error = str(exc)
                await self._transition(latest, SideTaskStatus.FAILED, finished=True)
                await self._sync_work_status(latest)
                await self._promote(latest.parent_chat_id)
                await self._exec_line(exec_log_id, "error", f"Failed: {_one_line(str(exc), 300)}")
                await self._finish_execution_log(exec_log_id, latest)

    # ------------------------------------------------------------------
    # Execution logs (Runs)
    # ------------------------------------------------------------------

    async def _start_execution_log(self, side_task: SideTask) -> str | None:
        """Open the Runs row for one turn of a side task.

        The row links the parent chat (``chat_id``) and records both the
        side task and its own chat id in the metadata, so Runs can group the
        run under the parent chat and link straight into the side chat.
        """
        try:
            from cachibot.models.automations import ExecutionLog, TriggerType

            log = ExecutionLog(
                id=str(uuid.uuid4()),
                execution_type="side_task",
                source_type="side_task",
                source_id=side_task.id,
                source_name=side_task.title,
                bot_id=side_task.bot_id,
                chat_id=side_task.parent_chat_id,
                trigger=TriggerType.SIDE_TASK,
                work_id=side_task.work_id,
                metadata_json={
                    "side_task_id": side_task.id,
                    "side_task_chat_id": side_task.chat_id,
                    "side_task_kind": side_task.kind.value,
                    "side_task_group_id": side_task.group_id,
                    "side_task_group_title": side_task.group_title,
                    "parent_chat_id": side_task.parent_chat_id,
                },
            )
            await self._exec_log_repo.save(log)
            return log.id
        except Exception:
            logger.debug("Could not create side-task execution log", exc_info=True)
            return None

    async def _exec_line(
        self,
        exec_log_id: str | None,
        level: str,
        content: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """Append one step line to a run row (best effort, never raises)."""
        if not exec_log_id:
            return
        try:
            await self._exec_line_repo.append(exec_log_id, level, content, data)
        except Exception:
            logger.debug("Could not append side-task execution line", exc_info=True)

    async def _finish_execution_log(self, exec_log_id: str | None, settled: SideTask) -> None:
        """Close the run row with the settled side task's real outcome."""
        if not exec_log_id:
            return
        status = "success"
        if settled.status == SideTaskStatus.FAILED:
            status = "error"
        elif settled.status in (
            SideTaskStatus.STOPPED,
            SideTaskStatus.NEEDS_YOU,
        ):
            status = "cancelled"
        try:
            await self._exec_log_repo.complete(
                exec_log_id,
                status=status,
                output=_settle_line(settled),
            )
        except Exception:
            logger.debug("Could not complete side-task execution log", exc_info=True)

    async def _prepare_worktree(self, side_task: SideTask) -> None:
        """Create the side task's worktree on first run, reuse it after.

        Worktrees survive restarts: on resume the existing worktree is
        reused; it is recreated from the recorded branch only when missing.
        Raises SideTaskStartError when the workspace is no longer a git
        repo or the recorded branch is gone.
        """
        config = Config.load()
        workspace = Path(config.workspace_path)

        def _prepare() -> tuple[Path, str, str]:
            return worktrees.create_worktree(workspace, side_task)

        try:
            # Serialized with every other git mutation on this repo: side
            # tasks of one parent create/remove worktrees concurrently.
            async with await _repo_git_lock_for(workspace):
                path, branch, base_commit = await asyncio.to_thread(_prepare)
        except worktrees.WorktreeError as exc:
            raise SideTaskStartError(str(exc)) from exc

        if (
            side_task.worktree_path != str(path)
            or side_task.branch != branch
            or side_task.base_commit != base_commit
        ):
            side_task.worktree_path = str(path)
            side_task.branch = branch
            side_task.base_commit = base_commit
            await self._repo.update(side_task)

    async def _cleanup_after_merge(self, workspace: Path, side_task: SideTask) -> None:
        """Remove the worktree and delete the merged branch.

        Mutates the repository, so it runs under the same per-repo lock as
        worktree creation and merges (a promoted side task may be creating
        its worktree while this one is being cleaned up).
        """
        async with await _repo_git_lock_for(workspace):
            await asyncio.to_thread(worktrees.cleanup_after_merge, workspace, side_task)

    async def _finish_and_merge(self, side_task: SideTask) -> None:
        """Commit the side task's work and merge it back automatically.

        No changes -> ``done`` (nothing to merge), worktree removed, branch
        deleted. Clean merge -> ``merged`` with ``merged_commit`` /
        ``merged_files`` recorded, worktree removed, branch deleted.
        Conflict or refusal -> merge aborted (parent tree untouched),
        ``needs_you`` with reason ``merge_conflict`` and ``conflict_files``
        recorded; worktree and branch kept so no work is lost.
        """
        config = Config.load()
        workspace = Path(config.workspace_path)

        if not side_task.worktree_path or not side_task.branch:
            # A turn that never got a worktree (shouldn't happen) — done
            await self._transition(side_task, SideTaskStatus.DONE, finished=True)
            await self._sync_work_status(side_task)
            return

        commit = await asyncio.to_thread(
            worktrees.commit_all_changes,
            Path(side_task.worktree_path),
            f"Side task: {side_task.title}",
        )
        if commit is None:
            # Nothing new to commit. If a previous run already committed on
            # the branch and merged it (e.g. cancelled mid-merge), record
            # the merge instead of reporting "nothing happened". A fresh
            # branch with no commits of its own is trivially an ancestor of
            # HEAD: that means "no changes" -> done. But a branch that has
            # commits of its own and is NOT merged yet carries work from a
            # stopped or failed turn the user continued with a reply — fall
            # through and merge it back instead of leaving it behind.
            tip = await asyncio.to_thread(worktrees.branch_sha, workspace, side_task.branch)
            recorded_base = side_task.base_commit
            already_merged = (
                tip is not None
                and recorded_base is not None
                and tip != recorded_base
                and await asyncio.to_thread(worktrees.is_branch_merged, workspace, side_task.branch)
            )
            nothing_to_merge = tip is None or recorded_base is None or tip == recorded_base
            if already_merged and recorded_base is not None:
                side_task.merged_commit = await asyncio.to_thread(worktrees.head_sha, workspace)
                side_task.merged_files = await asyncio.to_thread(
                    worktrees.changed_files_vs_base,
                    workspace,
                    recorded_base,
                    side_task.branch,
                )
                side_task.conflict_files = []
                await self._cleanup_after_merge(workspace, side_task)
                await self._transition(side_task, SideTaskStatus.MERGED, finished=True)
                await self._sync_work_status(side_task)
                return
            if nothing_to_merge:
                await self._cleanup_after_merge(workspace, side_task)
                side_task.merged_files = []
                await self._transition(side_task, SideTaskStatus.DONE, finished=True)
                await self._sync_work_status(side_task)
                return
            # else: unmerged commits on the branch — merge them back below.

        async with await _repo_git_lock_for(workspace):
            outcome = await asyncio.to_thread(worktrees.merge_side_branch, workspace, side_task)

        if outcome.merged:
            side_task.merged_commit = outcome.merged_commit
            side_task.merged_files = outcome.merged_files
            side_task.conflict_files = []
            side_task.needs_you_reason = None
            await self._cleanup_after_merge(workspace, side_task)
            await self._transition(side_task, SideTaskStatus.MERGED, finished=True)
            await self._sync_work_status(side_task)
            logger.info(
                "Side task %s merged into %s as %s (%d files)",
                side_task.id,
                workspace,
                outcome.merged_commit,
                len(outcome.merged_files),
            )
            return

        if outcome.conflict_files:
            # Never lose work: keep branch + worktree, surface the conflict
            side_task.needs_you_reason = NEEDS_YOU_MERGE_CONFLICT
            side_task.conflict_files = outcome.conflict_files
            await self._transition(side_task, SideTaskStatus.NEEDS_YOU)
            await self._sync_work_status(side_task)
            logger.info(
                "Side task %s needs you: merge conflict in %s",
                side_task.id,
                ", ".join(outcome.conflict_files),
            )
            return

        raise worktrees.WorktreeError(outcome.error or "git merge failed")

    def _config_for(self, side_task: SideTask) -> Any:
        """Global config with the workspace pointed at the side task's worktree.

        Every tool the agent can call (file ops, python execution, coding
        agents) resolves paths against ``config.workspace_path`` and the
        sandbox allows reads/writes only inside it, so a config copy scoped
        to the worktree keeps the side task fully isolated from the parent
        workspace — nothing the side task does can write to the parent's
        files. The global config object is never mutated.
        """
        config = Config.load()
        if not side_task.worktree_path:
            return config
        scoped = copy.deepcopy(config)
        scoped.workspace_path = Path(side_task.worktree_path)
        return scoped

    async def _execute_turn(self, side_task: SideTask) -> None:
        """Run the side task's turn through the agent, persisting messages.

        History already in the side task's chat is seeded into the agent's
        conversation so a resumed turn continues where it left off. The
        newest user message drives the turn: the original prompt on a first
        run, or — after a reply inside the side chat (``reply`` persists it
        before launching) — that reply, so the continued turn answers it in
        the same worktree.
        """
        from cachibot.services.agent_factory import build_bot_agent

        config = self._config_for(side_task)
        agent = await build_bot_agent(
            config,
            bot_id=side_task.bot_id,
            chat_id=side_task.chat_id,
            user_message=side_task.prompt,
            platform="web",
            on_approval_needed=self._make_approval_handler(config, side_task.bot_id),
        )

        # Seed persisted history (already oldest-first).
        history = await self._knowledge_repo.get_bot_messages(
            side_task.bot_id, side_task.chat_id, limit=_RESUME_HISTORY_LIMIT
        )
        last_user = next((m for m in reversed(history) if m.role == "user"), None)
        # A reply the user sent while the task waited settles the continued
        # turn; it is already persisted, so it must not be replayed twice.
        continuation = (
            last_user.content
            if last_user is not None and last_user.content != side_task.prompt
            else None
        )
        prompt_already_persisted = last_user is not None and last_user.content == side_task.prompt

        # Drop the message that drives this turn from the seeded context:
        # the prompt is replayed via run_message, a reply stays persisted.
        seeded = list(history)
        if (
            seeded
            and seeded[-1].role == "user"
            and (continuation is not None or seeded[-1].content == side_task.prompt)
        ):
            seeded = seeded[:-1]
        seeded_turns = False
        for msg in seeded:
            if msg.role in ("user", "assistant", "system"):
                agent.conversation.add_context(msg.role, msg.content)
                seeded_turns = True

        # Persist the user prompt (skip on resume: the chat already has it)
        if not prompt_already_persisted and continuation is None:
            await self._persist_message(side_task, role="user", content=side_task.prompt)

        if continuation is not None:
            run_message = continuation
        elif seeded_turns:
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
            except asyncio.TimeoutError:
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
        await self._reply_in_parent_chat(side_task)

    # ------------------------------------------------------------------
    # Parent-chat thread replies (E5)
    # ------------------------------------------------------------------

    async def _reply_in_parent_chat(self, side_task: SideTask) -> None:
        """Keep the parent chat's thread reply in sync with a state change.

        One reply per side task (and one per helper group), always: the first
        qualifying transition creates it, later transitions update it in
        place — a settled side task never leaves a stale amber reply behind,
        and there is never a duplicate. While a side task merely waits or
        runs, the chat shows the quiet live indicator instead (rendered from
        ``side_task_update``), so nothing is persisted here for those states
        — except a resume, which must clear a previous needs-you reply.
        """
        try:
            async with self._reply_lock:
                if side_task.group_id:
                    await self._sync_group_reply(side_task.group_id)
                    return
                if side_task.status in _SINGLE_REPLY_STATUSES or side_task.reply_message_id:
                    await self._sync_single_reply(side_task)
        except Exception:
            logger.debug(
                "Could not sync parent-chat reply for side task %s",
                side_task.id,
                exc_info=True,
            )

    async def _sync_single_reply(self, side_task: SideTask) -> None:
        """Create or update the one parent-chat reply for a side task.

        Callers must hold ``self._reply_lock``. A caller may hold a stale
        copy from before the first reply was persisted (``_transition`` saves
        the status first, the reply id afterwards) — the record is re-read in
        that case so a stale ``reply_message_id=None`` can never duplicate
        the reply.
        """
        message_id = side_task.reply_message_id
        if not message_id:
            fresh = await self._repo.get(side_task.id)
            if fresh is not None and fresh.reply_message_id:
                message_id = fresh.reply_message_id
                side_task.reply_message_id = fresh.reply_message_id

        summary = await self._side_chat_summary(side_task)
        content = _single_reply_content(side_task, summary)
        metadata: dict[str, Any] = {
            "kind": "side_task_reply",
            "sideTaskId": side_task.id,
            "title": side_task.title,
            "chatId": side_task.chat_id,
            "status": side_task.status.value,
        }
        if side_task.source_message_id:
            metadata["replyTo"] = side_task.source_message_id
        if side_task.status == SideTaskStatus.MERGED:
            metadata["mergedFiles"] = side_task.merged_files
            if side_task.merged_commit:
                metadata["mergedCommit"] = side_task.merged_commit
        if side_task.status == SideTaskStatus.FAILED and side_task.error:
            metadata["error"] = _one_line(side_task.error, 300)
        if side_task.status == SideTaskStatus.NEEDS_YOU:
            if side_task.needs_you_reason:
                metadata["needsYouReason"] = side_task.needs_you_reason
            if side_task.conflict_files:
                metadata["conflictFiles"] = side_task.conflict_files
        message = await self._publish_reply(
            bot_id=side_task.bot_id,
            parent_chat_id=side_task.parent_chat_id,
            message_id=message_id,
            content=content,
            metadata=metadata,
            reply_to_id=side_task.source_message_id,
        )
        if message_id is None and message.id != side_task.reply_message_id:
            # We created the reply: stamp the record so later syncs update it.
            # Targeted write only — this copy is stale by now (the transition
            # that published the reply may be superseded by a newer one, e.g.
            # a needs_you -> running resume, and a full-row update here would
            # clobber it).
            side_task.reply_message_id = message.id
            await self._repo.set_reply_message_id(side_task.id, message.id)

    async def _sync_group_reply(self, group_id: str) -> None:
        """Create or update the ONE parent-chat reply for a helper group.

        Callers must hold ``self._reply_lock`` (fresh records are read from
        the repository, so a stale caller cannot duplicate the message).

        The message carries live counts and the per-helper list (ids, titles,
        statuses, child chat ids — all real record data) so the UI can expand
        a helper row without another round trip.
        """
        tasks = await self._repo.get_by_group(group_id)
        if not tasks:
            return
        first = tasks[0]
        total = len(tasks)
        waiting = sum(1 for t in tasks if t.status == SideTaskStatus.WAITING_FOR_SLOT)
        running = sum(1 for t in tasks if t.status == SideTaskStatus.RUNNING)
        needs_you = sum(1 for t in tasks if t.status == SideTaskStatus.NEEDS_YOU)
        failed = sum(1 for t in tasks if t.status == SideTaskStatus.FAILED)
        done = total - waiting - running - needs_you - failed  # done + merged + stopped
        title = first.group_title or f"{total} helpers"
        if needs_you:
            status = "needs_you"
        elif failed:
            status = "failed"
        elif running or waiting:
            status = "running"
        else:
            status = "settled"
        metadata: dict[str, Any] = {
            "kind": "side_task_group_reply",
            "groupId": group_id,
            "title": title,
            "status": status,
            "total": total,
            "done": done,
            "failed": failed,
            "running": running,
            "waiting": waiting,
            "needsYou": needs_you,
            "items": [
                {"id": t.id, "title": t.title, "status": t.status.value, "chatId": t.chat_id}
                for t in tasks
            ],
        }
        reply_to_id = next((t.source_message_id for t in tasks if t.source_message_id), None)
        if reply_to_id:
            metadata["replyTo"] = reply_to_id
        existing_id = next((t.reply_message_id for t in tasks if t.reply_message_id), None)
        message = await self._publish_reply(
            bot_id=first.bot_id,
            parent_chat_id=first.parent_chat_id,
            message_id=existing_id,
            content=_group_reply_content(title, total, done, running, waiting, needs_you, failed),
            metadata=metadata,
            reply_to_id=reply_to_id,
        )
        if existing_id is None:
            await self._repo.set_reply_message_for_group(group_id, message.id)

    async def _publish_reply(
        self,
        *,
        bot_id: str,
        parent_chat_id: str,
        message_id: str | None,
        content: str,
        metadata: dict[str, Any],
        reply_to_id: str | None,
    ) -> BotMessage:
        """Create the parent-chat reply, or update it in place when it exists.

        Updating in place (same id, chat and timestamp) is what keeps the
        reply unique per side task / group across every state change.
        """
        if message_id:
            existing = await self._knowledge_repo.get_bot_message(message_id)
            if existing is not None and existing.chat_id == parent_chat_id:
                existing.content = content
                existing.metadata = metadata
                existing.reply_to_id = reply_to_id
                await self._knowledge_repo.update_bot_message(existing)
                await self._notify_message_update(bot_id, existing)
                return existing
        message = BotMessage(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            chat_id=parent_chat_id,
            role="assistant",
            content=content,
            timestamp=datetime.now(timezone.utc),
            metadata=metadata,
            reply_to_id=reply_to_id,
        )
        await self._knowledge_repo.save_bot_message(message)
        await self._notify_message_update(bot_id, message)
        return message

    async def _side_chat_summary(self, side_task: SideTask) -> str | None:
        """The side chat's last assistant message, trimmed to one short line."""
        messages = await self._knowledge_repo.get_bot_messages(
            side_task.bot_id, side_task.chat_id, limit=_RESUME_HISTORY_LIMIT
        )
        last_assistant = next((m for m in reversed(messages) if m.role == "assistant"), None)
        if last_assistant is None:
            return None
        return _one_line(last_assistant.content, 200) or None

    async def _notify_message_update(self, bot_id: str, message: BotMessage) -> None:
        """Push a created/updated parent-chat message to clients with bot access."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            payload = {
                "id": message.id,
                "chatId": message.chat_id,
                "role": message.role,
                "content": message.content,
                "timestamp": message.timestamp.isoformat(),
                "metadata": message.metadata,
                "replyToId": message.reply_to_id,
            }
            await get_ws_manager().broadcast_to_bot(
                WSMessage.message_update(message.chat_id, payload), bot_id
            )
        except Exception:
            logger.debug("Could not broadcast message update", exc_info=True)

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


def _one_line(text: str, limit: int = 200) -> str:
    """Collapse whitespace and cap length for a single chat line."""
    return " ".join(text.split())[:limit]


def _settle_line(side_task: SideTask) -> str:
    """One line describing a settled side task (run output / step line)."""
    if side_task.status == SideTaskStatus.MERGED:
        count = len(side_task.merged_files)
        suffix = f" · {_files_label(count)}" if count else ""
        commit = side_task.merged_commit
        tail = f" as {commit[:7]}" if commit else ""
        return f"Merged back{tail}{suffix}"
    if side_task.status == SideTaskStatus.DONE:
        return "Finished with no changes to bring back"
    if side_task.status == SideTaskStatus.FAILED:
        return f"Failed: {_one_line(side_task.error or 'unknown error', 300)}"
    if side_task.status == SideTaskStatus.NEEDS_YOU:
        reason = side_task.needs_you_reason or "see the side task"
        return f"Needs you: {_one_line(reason, 300)}"
    return "Stopped"


# States that get a persisted parent-chat reply for a single (ungrouped)
# side task. Waiting/running show the quiet live indicator instead — except
# when a reply already exists (a settled side task that resumes or gets a
# reply runs again): it is updated in place so a stale needs-you reply never
# keeps offering actions.
_SINGLE_REPLY_STATUSES = (
    SideTaskStatus.NEEDS_YOU,
    SideTaskStatus.DONE,
    SideTaskStatus.MERGED,
    SideTaskStatus.FAILED,
    SideTaskStatus.STOPPED,
)


def _files_label(count: int) -> str:
    return "1 file" if count == 1 else f"{count} files"


def _single_reply_content(side_task: SideTask, summary: str | None) -> str:
    """The reply body: what the side task did, or a short record-derived line."""
    if summary:
        return summary
    title = side_task.title
    if side_task.status == SideTaskStatus.MERGED:
        count = len(side_task.merged_files)
        suffix = f" · {_files_label(count)} changed" if count else ""
        return f'Brought in "{title}"{suffix}'
    if side_task.status == SideTaskStatus.DONE:
        return f'"{title}" finished with no changes to bring back'
    if side_task.status == SideTaskStatus.FAILED:
        return f'"{title}" failed: {_one_line(side_task.error or "unknown error", 120)}'
    if side_task.status == SideTaskStatus.STOPPED:
        return f'"{title}" stopped'
    if side_task.status == SideTaskStatus.NEEDS_YOU:
        reason = side_task.needs_you_reason or "see the side task"
        return f'"{title}" needs you: {_one_line(reason, 120)}'
    if side_task.status == SideTaskStatus.WAITING_FOR_SLOT:
        return f'"{title}" is waiting for a slot'
    return f'"{title}" is working again'


def _group_reply_content(
    title: str,
    total: int,
    done: int,
    running: int,
    waiting: int,
    needs_you: int,
    failed: int,
) -> str:
    """One line for a helper group, e.g. "Tests: 2 of 3 done · 1 running"."""
    if done == total:
        return f'"{title}": all {total} done'
    parts = [f"{done} of {total} done"]
    if running:
        parts.append(f"{running} running")
    if waiting:
        parts.append(f"{waiting} waiting for a slot")
    if needs_you:
        parts.append(f"{needs_you} needs you")
    if failed:
        parts.append(f"{failed} failed")
    return f'"{title}": ' + " · ".join(parts)


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
    "SideTaskReplyError",
    "SideTaskService",
    "SideTaskStartError",
    "get_side_task_service",
]

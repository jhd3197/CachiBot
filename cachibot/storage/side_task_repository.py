"""
Repository for side tasks: child chats of a parent chat run in parallel.
"""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, update

from cachibot.models.side_task import SideTask, SideTaskStatus
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.side_task import SideTask as SideTaskModel


class SideTaskRepository(BaseRepository[SideTaskModel, SideTask]):
    """Repository for side tasks."""

    _model = SideTaskModel

    async def save(self, side_task: SideTask) -> None:
        """Save a new side task."""
        await self._add(
            SideTaskModel(
                id=side_task.id,
                bot_id=side_task.bot_id,
                parent_chat_id=side_task.parent_chat_id,
                chat_id=side_task.chat_id,
                title=side_task.title,
                prompt=side_task.prompt,
                kind=side_task.kind.value,
                group_id=side_task.group_id,
                group_title=side_task.group_title,
                status=side_task.status.value,
                needs_you_reason=side_task.needs_you_reason,
                started_by=side_task.started_by.value,
                worktree_path=side_task.worktree_path,
                branch=side_task.branch,
                base_commit=side_task.base_commit,
                merged_commit=side_task.merged_commit,
                merged_files=side_task.merged_files,
                conflict_files=side_task.conflict_files,
                source_message_id=side_task.source_message_id,
                reply_message_id=side_task.reply_message_id,
                error=side_task.error,
                work_id=side_task.work_id,
                created_at=side_task.created_at,
                started_at=side_task.started_at,
                finished_at=side_task.finished_at,
                updated_at=side_task.updated_at,
            )
        )

    async def update(self, side_task: SideTask) -> None:
        """Update an existing side task.

        ``reply_message_id`` is sticky: a None in the caller's copy means
        "this writer doesn't know it", never "clear it" — the group reply
        stamp is written behind the back of in-memory copies, and a stale
        transition must not clobber it.
        """
        values: dict[str, Any] = dict(
            title=side_task.title,
            prompt=side_task.prompt,
            kind=side_task.kind.value,
            group_id=side_task.group_id,
            group_title=side_task.group_title,
            status=side_task.status.value,
            needs_you_reason=side_task.needs_you_reason,
            worktree_path=side_task.worktree_path,
            branch=side_task.branch,
            base_commit=side_task.base_commit,
            merged_commit=side_task.merged_commit,
            merged_files=side_task.merged_files,
            conflict_files=side_task.conflict_files,
            source_message_id=side_task.source_message_id,
            error=side_task.error,
            work_id=side_task.work_id,
            started_at=side_task.started_at,
            finished_at=side_task.finished_at,
            updated_at=datetime.now(timezone.utc),
        )
        if side_task.reply_message_id is not None:
            values["reply_message_id"] = side_task.reply_message_id
        await self._update(
            update(SideTaskModel).where(SideTaskModel.id == side_task.id).values(**values)
        )

    async def get(self, side_task_id: str) -> SideTask | None:
        """Get a side task by ID."""
        return await self.get_by_id(side_task_id)

    async def get_by_bot(
        self,
        bot_id: str,
        parent_chat_id: str | None = None,
        limit: int = 100,
    ) -> list[SideTask]:
        """Get side tasks for a bot, optionally filtered by parent chat."""
        stmt = select(SideTaskModel).where(SideTaskModel.bot_id == bot_id)
        if parent_chat_id:
            stmt = stmt.where(SideTaskModel.parent_chat_id == parent_chat_id)
        stmt = stmt.order_by(SideTaskModel.created_at.asc()).limit(limit)
        return await self._fetch_all(stmt)

    async def get_by_chat(self, chat_id: str) -> SideTask | None:
        """Get the side task that owns a chat (if the chat is a side task)."""
        return await self._fetch_one(select(SideTaskModel).where(SideTaskModel.chat_id == chat_id))

    async def get_by_group(self, group_id: str) -> list[SideTask]:
        """Get all side tasks of one helper group, oldest first."""
        return await self._fetch_all(
            select(SideTaskModel)
            .where(SideTaskModel.group_id == group_id)
            .order_by(SideTaskModel.created_at.asc())
        )

    async def get_by_statuses(self, statuses: list[SideTaskStatus]) -> list[SideTask]:
        """Get side tasks in any of the given statuses (all bots)."""
        return await self._fetch_all(
            select(SideTaskModel)
            .where(SideTaskModel.status.in_([s.value for s in statuses]))
            .order_by(SideTaskModel.created_at.asc())
        )

    async def get_active_for_parent(self, parent_chat_id: str) -> list[SideTask]:
        """Get active (waiting/running/needs_you) side tasks of a parent chat."""
        return await self._fetch_all(
            select(SideTaskModel)
            .where(
                SideTaskModel.parent_chat_id == parent_chat_id,
                SideTaskModel.status.in_(
                    [
                        SideTaskStatus.WAITING_FOR_SLOT.value,
                        SideTaskStatus.RUNNING.value,
                        SideTaskStatus.NEEDS_YOU.value,
                    ]
                ),
            )
            .order_by(SideTaskModel.created_at.asc())
        )

    async def get_running_for_parent(self, parent_chat_id: str) -> list[SideTask]:
        """Get running side tasks of a parent chat."""
        return await self._fetch_all(
            select(SideTaskModel)
            .where(
                SideTaskModel.parent_chat_id == parent_chat_id,
                SideTaskModel.status == SideTaskStatus.RUNNING.value,
            )
            .order_by(SideTaskModel.created_at.asc())
        )

    async def get_oldest_waiting_for_parent(self, parent_chat_id: str) -> SideTask | None:
        """Get the oldest waiting-for-slot side task of a parent chat (FIFO)."""
        return await self._fetch_one(
            select(SideTaskModel)
            .where(
                SideTaskModel.parent_chat_id == parent_chat_id,
                SideTaskModel.status == SideTaskStatus.WAITING_FOR_SLOT.value,
            )
            .order_by(SideTaskModel.created_at.asc())
            .limit(1)
        )

    async def set_reply_message_for_group(self, group_id: str, message_id: str) -> None:
        """Stamp the shared parent-chat reply message on every helper of a group.

        A helper group surfaces as ONE reply message in the parent chat; all
        its records point at it so any helper transition can update it in
        place.
        """
        await self._update(
            update(SideTaskModel)
            .where(SideTaskModel.group_id == group_id)
            .values(reply_message_id=message_id)
        )

    def _row_to_entity(self, row: SideTaskModel) -> SideTask:
        """Convert database row to SideTask."""
        return SideTask(
            id=row.id,
            bot_id=row.bot_id,
            parent_chat_id=row.parent_chat_id,
            chat_id=row.chat_id,
            title=row.title,
            prompt=row.prompt,
            kind=row.kind,  # type: ignore[arg-type]
            group_id=row.group_id,
            group_title=row.group_title,
            status=row.status,  # type: ignore[arg-type]
            needs_you_reason=row.needs_you_reason,
            started_by=row.started_by,  # type: ignore[arg-type]
            worktree_path=row.worktree_path,
            branch=row.branch,
            base_commit=row.base_commit,
            merged_commit=row.merged_commit,
            merged_files=row.merged_files if row.merged_files else [],
            conflict_files=row.conflict_files if row.conflict_files else [],
            source_message_id=row.source_message_id,
            reply_message_id=row.reply_message_id,
            error=row.error,
            work_id=row.work_id,
            created_at=row.created_at,
            started_at=row.started_at,
            finished_at=row.finished_at,
            updated_at=row.updated_at,
        )

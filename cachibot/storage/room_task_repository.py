"""Repository for room tasks (shared kanban board)."""

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update

from cachibot.models.room_task import RoomTask, RoomTaskPriority, RoomTaskStatus
from cachibot.storage.base import BaseRepository
from cachibot.storage.models.room_task import RoomTask as RoomTaskModel


class RoomTaskRepository(BaseRepository[RoomTaskModel, RoomTask]):
    """Repository for room task CRUD operations."""

    _model = RoomTaskModel

    async def create(self, task: RoomTask) -> None:
        """Create a new room task."""
        await self._add(
            RoomTaskModel(
                id=task.id,
                room_id=task.room_id,
                title=task.title,
                description=task.description,
                status=task.status.value
                if isinstance(task.status, RoomTaskStatus)
                else task.status,
                priority=task.priority.value
                if isinstance(task.priority, RoomTaskPriority)
                else task.priority,
                position=task.position,
                assigned_to_bot_id=task.assigned_to_bot_id,
                assigned_to_user_id=task.assigned_to_user_id,
                created_by_user_id=task.created_by_user_id,
                created_by_bot_id=task.created_by_bot_id,
                tags=task.tags,
                due_at=task.due_at,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
        )

    async def get(self, task_id: str) -> RoomTask | None:
        """Get a task by ID."""
        return await self.get_by_id(task_id)

    async def get_by_room(self, room_id: str, status: str | None = None) -> list[RoomTask]:
        """Get all tasks for a room, optionally filtered by status."""
        stmt = select(RoomTaskModel).where(RoomTaskModel.room_id == room_id)
        if status:
            stmt = stmt.where(RoomTaskModel.status == status)
        stmt = stmt.order_by(RoomTaskModel.status, RoomTaskModel.position)
        return await self._fetch_all(stmt)

    async def update(self, task_id: str, **kwargs: Any) -> RoomTask | None:
        """Update task fields."""
        fields: dict[str, Any] = {}
        for key in (
            "title",
            "description",
            "status",
            "priority",
            "position",
            "assigned_to_bot_id",
            "assigned_to_user_id",
            "tags",
            "due_at",
        ):
            if key in kwargs and kwargs[key] is not None:
                val = kwargs[key]
                if isinstance(val, RoomTaskStatus):
                    val = val.value
                elif isinstance(val, RoomTaskPriority):
                    val = val.value
                fields[key] = val
        if not fields:
            return await self.get(task_id)
        fields["updated_at"] = datetime.now(tz=timezone.utc)

        await self._update(
            update(RoomTaskModel).where(RoomTaskModel.id == task_id).values(**fields)
        )
        return await self.get(task_id)

    async def reorder(self, task_id: str, status: str, position: float) -> RoomTask | None:
        """Move a task to a new status column and position."""
        now = datetime.now(tz=timezone.utc)
        count = await self._update(
            update(RoomTaskModel)
            .where(RoomTaskModel.id == task_id)
            .values(status=status, position=position, updated_at=now)
        )
        if count == 0:
            return None
        return await self.get(task_id)

    async def delete(self, task_id: str) -> bool:
        """Delete a task. Returns True if deleted."""
        return await self.delete_by_id(task_id)

    async def get_max_position(self, room_id: str, status: str) -> float:
        """Get the maximum position value for a given room and status."""
        val = await self._scalar(
            select(sa_func.max(RoomTaskModel.position)).where(
                RoomTaskModel.room_id == room_id,
                RoomTaskModel.status == status,
            )
        )
        return float(val) if val is not None else 0.0

    def _row_to_entity(self, row: RoomTaskModel) -> RoomTask:
        """Convert a database row to a RoomTask entity."""
        return RoomTask(
            id=row.id,
            room_id=row.room_id,
            title=row.title,
            description=row.description,
            status=RoomTaskStatus(row.status),
            priority=RoomTaskPriority(row.priority),
            position=row.position,
            assigned_to_bot_id=row.assigned_to_bot_id,
            assigned_to_user_id=row.assigned_to_user_id,
            created_by_user_id=row.created_by_user_id,
            created_by_bot_id=row.created_by_bot_id,
            tags=row.tags if row.tags else [],
            due_at=row.due_at,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

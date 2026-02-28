"""Repository for room task events (activity history)."""

from sqlalchemy import select

from cachibot.models.room_task import RoomTaskEvent, RoomTaskEventAction
from cachibot.storage import db
from cachibot.storage.models.room_task_event import RoomTaskEvent as RoomTaskEventModel


class RoomTaskEventRepository:
    """Repository for room task event CRUD operations."""

    async def create(self, event: RoomTaskEvent) -> None:
        """Create a single event."""
        async with db.ensure_initialized()() as session:
            obj = RoomTaskEventModel(
                id=event.id,
                task_id=event.task_id,
                room_id=event.room_id,
                action=event.action.value
                if isinstance(event.action, RoomTaskEventAction)
                else event.action,
                field=event.field,
                old_value=event.old_value,
                new_value=event.new_value,
                actor_user_id=event.actor_user_id,
                actor_bot_id=event.actor_bot_id,
                created_at=event.created_at,
            )
            session.add(obj)
            await session.commit()

    async def create_many(self, events: list[RoomTaskEvent]) -> None:
        """Create multiple events in a single transaction."""
        if not events:
            return
        async with db.ensure_initialized()() as session:
            for event in events:
                session.add(
                    RoomTaskEventModel(
                        id=event.id,
                        task_id=event.task_id,
                        room_id=event.room_id,
                        action=event.action.value
                        if isinstance(event.action, RoomTaskEventAction)
                        else event.action,
                        field=event.field,
                        old_value=event.old_value,
                        new_value=event.new_value,
                        actor_user_id=event.actor_user_id,
                        actor_bot_id=event.actor_bot_id,
                        created_at=event.created_at,
                    )
                )
            await session.commit()

    async def get_by_task(
        self, task_id: str, limit: int = 50, offset: int = 0
    ) -> list[RoomTaskEvent]:
        """Get events for a task, most recent first."""
        stmt = (
            select(RoomTaskEventModel)
            .where(RoomTaskEventModel.task_id == task_id)
            .order_by(RoomTaskEventModel.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_entity(row) for row in rows]

    def _row_to_entity(self, row: RoomTaskEventModel) -> RoomTaskEvent:
        """Convert a database row to a RoomTaskEvent entity."""
        return RoomTaskEvent(
            id=row.id,
            task_id=row.task_id,
            room_id=row.room_id,
            action=RoomTaskEventAction(row.action),
            field=row.field,
            old_value=row.old_value,
            new_value=row.new_value,
            actor_user_id=row.actor_user_id,
            actor_bot_id=row.actor_bot_id,
            created_at=row.created_at,
        )

"""Room task event model for activity history."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["RoomTaskEvent"]


class RoomTaskEvent(Base):
    """A single activity event on a room task."""

    __tablename__ = "room_task_events"
    __table_args__ = (
        Index("idx_room_task_events_task", "task_id"),
        Index("idx_room_task_events_task_created", "task_id", "created_at"),
        Index("idx_room_task_events_room", "room_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(
        String, ForeignKey("room_tasks.id", ondelete="CASCADE"), nullable=False
    )
    room_id: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str | None] = mapped_column(String, nullable=True)
    old_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    new_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_bot_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

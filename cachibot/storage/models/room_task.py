"""Room task model for shared kanban board."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["RoomTask"]


class RoomTask(Base):
    """A task on a room's shared kanban board."""

    __tablename__ = "room_tasks"
    __table_args__ = (
        Index("idx_room_tasks_room", "room_id"),
        Index("idx_room_tasks_room_status", "room_id", "status"),
        Index("idx_room_tasks_room_status_pos", "room_id", "status", "position"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    room_id: Mapped[str] = mapped_column(
        String, ForeignKey("rooms.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="todo")
    priority: Mapped[str] = mapped_column(String, nullable=False, server_default="normal")
    position: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    assigned_to_bot_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by_bot_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("bots.id", ondelete="SET NULL"), nullable=True
    )
    tags: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

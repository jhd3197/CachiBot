"""
Bot computer model: one Vela container per bot, managed by CachiBot.

One row per bot (``bot_id`` is the primary key). The row survives container
lifecycles: it records the desired lifecycle state, the pinned image and the
last activity/error, so the UI and the idle loop can reason about a computer
whose container does not exist.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["BotComputer"]


def ensure_aware(dt: datetime | None) -> datetime | None:
    """SQLite drops the tzinfo on read — domain records are always aware."""
    if dt is not None and dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


class BotComputer(Base):
    """A bot's computer: state, pinned image and last activity/error."""

    __tablename__ = "bot_computers"

    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String, nullable=False, server_default="off")
    container_name: Mapped[str | None] = mapped_column(String, nullable=True)
    host_port: Mapped[int | None] = mapped_column(nullable=True)
    image_tag: Mapped[str] = mapped_column(String, nullable=False)
    vela_version: Mapped[str] = mapped_column(String, nullable=False)
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

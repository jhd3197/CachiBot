"""
Bot Faro connection model: the per-bot opt-in flag for the Faro bridge.

One row per bot (``bot_id`` is the primary key). The row holds only a
non-secret boolean — the bridge token never leaves Faro's discovery file,
so there is nothing else to persist.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["BotFaroConnection"]


class BotFaroConnection(Base):
    """A bot's Faro connection: nothing but the opt-in flag and timestamps."""

    __tablename__ = "bot_faro_connections"

    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True
    )
    connected: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

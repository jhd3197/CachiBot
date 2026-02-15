"""
BotContact model.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["BotContact"]


class BotContact(Base):
    """Contact entry associated with a bot."""

    __tablename__ = "bot_contacts"
    __table_args__ = (Index("idx_bot_contacts_bot", "bot_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

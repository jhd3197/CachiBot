"""
Message and BotMessage models.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.job import Job

__all__ = ["Message", "BotMessage"]


class Message(Base):
    """Global message store (CLI / single-agent mode)."""

    __tablename__ = "messages"
    __table_args__ = (Index("idx_messages_timestamp", "timestamp"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, server_default="{}"
    )

    # Relationships
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="message")


class BotMessage(Base):
    """Bot-scoped conversation message within a chat."""

    __tablename__ = "bot_messages"
    __table_args__ = (
        Index("idx_bot_messages_bot_chat", "bot_id", "chat_id"),
        Index("idx_bot_messages_timestamp", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str] = mapped_column(
        String, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, server_default="{}"
    )
    reply_to_id: Mapped[str | None] = mapped_column(String, nullable=True)

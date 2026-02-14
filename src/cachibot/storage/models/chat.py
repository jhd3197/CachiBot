"""
Chat model.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.bot import Bot

__all__ = ["Chat"]


class Chat(Base):
    """Chat / conversation within a bot (supports platform conversations)."""

    __tablename__ = "chats"
    __table_args__ = (
        Index("idx_chats_bot", "bot_id"),
        Index(
            "idx_chats_platform",
            "bot_id",
            "platform",
            "platform_chat_id",
            unique=True,
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    platform_chat_id: Mapped[Optional[str]] = mapped_column(
        String, nullable=True
    )
    pinned: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    archived: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    bot: Mapped[Bot] = relationship(
        "Bot", back_populates="chats",
        primaryjoin="Chat.bot_id == Bot.id",
        foreign_keys=[bot_id],
    )

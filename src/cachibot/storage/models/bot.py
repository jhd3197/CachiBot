"""
Bot and BotOwnership models.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.chat import Chat
    from cachibot.storage.models.user import User

__all__ = ["Bot", "BotOwnership"]


class Bot(Base):
    """Bot configuration (synced from frontend)."""

    __tablename__ = "bots"
    # GIN indexes on JSONB columns are PostgreSQL-only; omitted for cross-dialect compat.
    __table_args__: tuple = ()

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    color: Mapped[str | None] = mapped_column(String, nullable=True)
    model: Mapped[str] = mapped_column(String, nullable=False)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    capabilities: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    models: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    ownership: Mapped[BotOwnership | None] = relationship(
        "BotOwnership", back_populates="bot", uselist=False
    )
    chats: Mapped[list[Chat]] = relationship("Chat", back_populates="bot")


class BotOwnership(Base):
    """Links a bot to its owning user."""

    __tablename__ = "bot_ownership"
    __table_args__ = (
        Index("idx_bot_ownership_user", "user_id"),
        Index("idx_bot_ownership_bot", "bot_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped[User] = relationship("User", back_populates="bot_ownerships")
    bot: Mapped[Bot] = relationship(
        "Bot",
        back_populates="ownership",
        primaryjoin="BotOwnership.bot_id == Bot.id",
        foreign_keys=[bot_id],
    )

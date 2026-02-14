"""
BotConnection model (platform integrations: Telegram, Discord, etc.).
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Index, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["BotConnection"]


class BotConnection(Base):
    """Platform integration connection for a bot."""

    __tablename__ = "bot_connections"
    __table_args__ = (
        Index("idx_bot_connections_bot", "bot_id"),
        Index("idx_bot_connections_status", "status"),
        Index(
            "idx_bot_connections_config_encrypted",
            "config_encrypted",
            postgresql_using="gin",
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="disconnected"
    )
    config_encrypted: Mapped[dict] = mapped_column(
        JSONB, nullable=False
    )
    message_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    last_activity: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

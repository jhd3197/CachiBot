"""Artifact model — server-side store for rich content blocks.

Artifacts (code, HTML previews, email templates, …) were originally a
browser-only construct (zustand/localStorage). This table makes them
durable server-side so manual click-to-edit saves survive reloads and the
agent's next turn can read the current source.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["Artifact"]


class Artifact(Base):
    """A structured content block owned by a bot, optionally tied to a chat."""

    __tablename__ = "artifacts"
    __table_args__ = (
        Index("idx_artifacts_bot", "bot_id"),
        Index("idx_artifacts_bot_chat", "bot_id", "chat_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    type: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str | None] = mapped_column(String, nullable=True)
    plugin: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

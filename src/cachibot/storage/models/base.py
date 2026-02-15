"""
Base class and common mixins for CachiBot ORM models.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["Base", "TimestampMixin", "BotScopedMixin"]


class TimestampMixin:
    """Mixin that adds created_at and updated_at timestamp columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        onupdate=func.now(),
    )


class BotScopedMixin:
    """Mixin for tables that are scoped to a specific bot via bot_id."""

    bot_id: Mapped[str] = mapped_column(
        String,
        nullable=False,
        index=True,
    )

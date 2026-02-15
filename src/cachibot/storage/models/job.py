"""
Job model (global job queue for CLI/single-agent mode).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.message import Message

__all__ = ["Job"]


class Job(Base):
    """Background job tied to a message."""

    __tablename__ = "jobs"
    __table_args__ = (
        Index("idx_jobs_status", "status"),
        Index("idx_jobs_message", "message_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    message_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("messages.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    progress: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")

    # Relationships
    message: Mapped[Message | None] = relationship("Message", back_populates="jobs")

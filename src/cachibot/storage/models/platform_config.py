"""
Platform-wide tool visibility configuration.

Single-row table storing which capabilities and skills are globally disabled.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["PlatformToolConfig"]


class PlatformToolConfig(Base):
    """Global tool visibility — capabilities and skills disabled platform-wide."""

    __tablename__ = "platform_tool_config"

    id: Mapped[str] = mapped_column(String, primary_key=True, server_default="default")
    disabled_capabilities: Mapped[list] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )
    disabled_skills: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_by: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id"), nullable=True
    )

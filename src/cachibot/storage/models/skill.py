"""
Skill and BotSkill models.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

__all__ = ["Skill", "BotSkill"]


class Skill(Base):
    """Reusable behavior module that can be activated on bots."""

    __tablename__ = "skills"
    __table_args__ = (Index("idx_skills_source", "source"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String, nullable=False, server_default="1.0.0")
    author: Mapped[str | None] = mapped_column(String, nullable=True)
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    requires_tools: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    instructions: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="local")
    filepath: Mapped[str | None] = mapped_column(String, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    bot_skills: Mapped[list[BotSkill]] = relationship(
        "BotSkill", back_populates="skill", cascade="all, delete-orphan"
    )


class BotSkill(Base):
    """Association between a bot and an activated skill (composite PK)."""

    __tablename__ = "bot_skills"
    __table_args__ = (
        Index("idx_bot_skills_bot", "bot_id"),
        Index("idx_bot_skills_skill", "skill_id"),
    )

    bot_id: Mapped[str] = mapped_column(String, primary_key=True)
    skill_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("skills.id", ondelete="CASCADE"),
        primary_key=True,
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    activated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    skill: Mapped[Skill] = relationship("Skill", back_populates="bot_skills")

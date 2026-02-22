"""
Group and bot access ORM models: Group, GroupMember, BotGroupAccess.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.user import User

__all__ = ["Group", "GroupMember", "BotGroupAccess"]


class Group(Base):
    """User group for organizing access."""

    __tablename__ = "groups"
    __table_args__ = (Index("idx_groups_created_by", "created_by"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    name: Mapped[str] = mapped_column(String, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    creator: Mapped[User] = relationship("User", foreign_keys=[created_by])
    members: Mapped[list[GroupMember]] = relationship(
        "GroupMember", back_populates="group", cascade="all, delete-orphan"
    )
    bot_access: Mapped[list[BotGroupAccess]] = relationship(
        "BotGroupAccess", back_populates="group", cascade="all, delete-orphan"
    )


class GroupMember(Base):
    """User membership in a group (composite PK)."""

    __tablename__ = "group_members"
    __table_args__ = (
        Index("idx_group_members_user", "user_id"),
        Index("idx_group_members_group", "group_id"),
    )

    group_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("groups.id", ondelete="CASCADE"),
        primary_key=True,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
    )
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="member")
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    group: Mapped[Group] = relationship("Group", back_populates="members")
    user: Mapped[User] = relationship("User")


class BotGroupAccess(Base):
    """Bot access granted to a group."""

    __tablename__ = "bot_group_access"
    __table_args__ = (
        UniqueConstraint("bot_id", "group_id", name="uq_bot_group_access"),
        Index("idx_bot_group_access_bot", "bot_id"),
        Index("idx_bot_group_access_group", "group_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("bots.id", ondelete="CASCADE"),
        nullable=False,
    )
    group_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("groups.id", ondelete="CASCADE"),
        nullable=False,
    )
    access_level: Mapped[str] = mapped_column(String, nullable=False, server_default="viewer")
    granted_by: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    group: Mapped[Group] = relationship("Group", back_populates="bot_access")

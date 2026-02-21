"""
Multi-agent room models: Room, RoomMember, RoomBot, RoomMessage.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.user import User

__all__ = ["Room", "RoomMember", "RoomBot", "RoomMessage"]


class Room(Base):
    """Multi-agent room where multiple bots can interact."""

    __tablename__ = "rooms"
    __table_args__ = (Index("idx_rooms_creator", "creator_id"),)

    id: Mapped[str] = mapped_column(String, primary_key=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    creator_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    max_bots: Mapped[int] = mapped_column(Integer, nullable=False, server_default="4")
    settings: Mapped[dict[str, Any]] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    creator: Mapped[User] = relationship("User", back_populates="created_rooms")
    members: Mapped[list[RoomMember]] = relationship(
        "RoomMember", back_populates="room", cascade="all, delete-orphan"
    )
    bots: Mapped[list[RoomBot]] = relationship(
        "RoomBot", back_populates="room", cascade="all, delete-orphan"
    )
    messages: Mapped[list[RoomMessage]] = relationship(
        "RoomMessage", back_populates="room", cascade="all, delete-orphan"
    )


class RoomMember(Base):
    """User membership in a room (composite PK)."""

    __tablename__ = "room_members"
    __table_args__ = (
        Index("idx_room_members_user", "user_id"),
        Index("idx_room_members_room", "room_id"),
    )

    room_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("rooms.id", ondelete="CASCADE"),
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
    room: Mapped[Room] = relationship("Room", back_populates="members")
    user: Mapped[User] = relationship("User", back_populates="room_memberships")


class RoomBot(Base):
    """Bot assignment to a room (composite PK)."""

    __tablename__ = "room_bots"
    __table_args__ = (
        Index("idx_room_bots_room", "room_id"),
        Index("idx_room_bots_bot", "bot_id"),
    )

    room_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        primary_key=True,
    )
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), primary_key=True
    )
    added_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="'default'")

    # Relationships
    room: Mapped[Room] = relationship("Room", back_populates="bots")


class RoomMessage(Base):
    """Message within a room (from a user or bot)."""

    __tablename__ = "room_messages"
    __table_args__ = (
        Index("idx_room_messages_room", "room_id"),
        Index("idx_room_messages_room_timestamp", "room_id", "timestamp"),
        Index("idx_room_messages_sender", "sender_type", "sender_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    room_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("rooms.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender_type: Mapped[str] = mapped_column(String, nullable=False)
    sender_id: Mapped[str] = mapped_column(String, nullable=False)
    sender_name: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(
        "metadata", sa.JSON, nullable=False, server_default="{}"
    )
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    room: Mapped[Room] = relationship("Room", back_populates="messages")

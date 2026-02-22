"""
Unified User model for CachiBot platform and website.

Merges columns from:
- CachiBotV2 platform: id (text PK), email, username, password_hash, role,
  is_active, created_at, created_by, last_login
- CachiBot website: id (int PK), email, hashed_password, is_active, is_verified,
  is_admin, tier, verification/reset tokens, credit_balance, timestamps,
  relationships to api_keys/payments/credits

Unified decisions:
- PK is String (UUID) to match CachiBotV2's existing data and bot_ownership FK
- password_hash (platform name) kept; website's hashed_password mapped to same column
- Both role (platform) and is_admin (website) coexist
- All website billing/verification columns preserved
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Float, Index, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

if TYPE_CHECKING:
    from cachibot.storage.models.bot import BotOwnership
    from cachibot.storage.models.room import Room, RoomMember

__all__ = ["User"]


class User(Base):
    """Unified user model for both CachiBot platform and website."""

    __tablename__ = "users"
    __table_args__ = (
        Index("idx_users_email", "email"),
        Index("idx_users_username", "username"),
        Index("idx_users_role", "role"),
        Index("idx_users_verification_token_hint", "verification_token_hint"),
        Index("idx_users_reset_token_hint", "reset_token_hint"),
        Index("idx_users_website_user_id", "website_user_id"),
    )

    # --- Primary key (UUID string to match CachiBotV2 existing data) ---
    id: Mapped[str] = mapped_column(String, primary_key=True)

    # --- Website link (INT user ID from CachiBot website) ---
    website_user_id: Mapped[int | None] = mapped_column(Integer, unique=True, nullable=True)

    # --- Core identity (both systems) ---
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    username: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String, nullable=False)

    # --- Authorization ---
    role: Mapped[str] = mapped_column(String, nullable=False, server_default="user")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    # --- Tier (from website) ---
    tier: Mapped[str] = mapped_column(String, nullable=False, server_default="free")

    # --- Email verification (from website) ---
    verification_token: Mapped[str | None] = mapped_column(String, nullable=True)
    verification_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_token_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- Password reset (from website) ---
    reset_token: Mapped[str | None] = mapped_column(String, nullable=True)
    reset_token_expires: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    reset_token_hint: Mapped[str | None] = mapped_column(String(16), nullable=True)

    # --- Password change tracking (from website, for JWT invalidation) ---
    password_changed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Billing (from website) ---
    credit_balance: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    low_balance_alerted: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )

    # --- Platform-specific fields ---
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- Timestamps ---
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=func.now()
    )

    # --- Relationships ---
    bot_ownerships: Mapped[list[BotOwnership]] = relationship(
        "BotOwnership", back_populates="user", cascade="all, delete-orphan"
    )
    created_rooms: Mapped[list[Room]] = relationship(
        "Room", back_populates="creator", cascade="all, delete-orphan"
    )
    room_memberships: Mapped[list[RoomMember]] = relationship(
        "RoomMember", back_populates="user", cascade="all, delete-orphan"
    )
    # NOTE: Website-only relationships (api_keys, payments, credit_transactions)
    # are defined in the website codebase. If those models are imported into
    # a shared context, the relationships should be added here as well.

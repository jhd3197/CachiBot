"""
Per-bot environment variable models.

Four tables supporting the per-bot environment system:
- BotEnvironment: per-bot env var overrides (Layer 3)
- PlatformEnvironment: per-platform defaults (Layer 2)
- BotSkillConfig: per-bot skill configuration (Layer 4)
- EnvAuditLog: audit trail for all env var operations
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["BotEnvironment", "PlatformEnvironment", "BotSkillConfig", "EnvAuditLog"]


class BotEnvironment(Base):
    """Per-bot environment variable override (encrypted)."""

    __tablename__ = "bot_environments"
    __table_args__ = (
        UniqueConstraint("bot_id", "key", name="uq_bot_env_bot_key"),
        Index("idx_bot_env_bot", "bot_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String, nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(Text, nullable=False)
    salt: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False, server_default="user")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class PlatformEnvironment(Base):
    """Per-platform environment variable default (encrypted)."""

    __tablename__ = "platform_environments"
    __table_args__ = (
        UniqueConstraint("platform", "key", name="uq_platform_env_platform_key"),
        Index("idx_platform_env_platform", "platform"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    platform: Mapped[str] = mapped_column(String, nullable=False)
    key: Mapped[str] = mapped_column(String, nullable=False)
    value_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    nonce: Mapped[str] = mapped_column(Text, nullable=False)
    salt: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)


class BotSkillConfig(Base):
    """Per-bot skill configuration override (JSON)."""

    __tablename__ = "bot_skill_configs"
    __table_args__ = (
        UniqueConstraint("bot_id", "skill_name", name="uq_bot_skill_config_bot_skill"),
        Index("idx_bot_skill_config_bot", "bot_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    skill_name: Mapped[str] = mapped_column(String, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class EnvAuditLog(Base):
    """Audit trail for environment variable operations."""

    __tablename__ = "env_audit_log"
    __table_args__ = (
        Index("idx_env_audit_bot", "bot_id"),
        Index("idx_env_audit_time", "timestamp"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str | None] = mapped_column(String, nullable=True)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String, nullable=False)
    key_name: Mapped[str] = mapped_column(String, nullable=False)
    source: Mapped[str] = mapped_column(String, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    ip_address: Mapped[str | None] = mapped_column(String, nullable=True)
    details: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")

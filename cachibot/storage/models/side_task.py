"""
Side task model: a child chat of a parent chat that works in parallel.

Workspace columns (worktree_path, branch, base_commit) and merge result
columns (merged_commit, merged_files) are filled in by E2; they exist from
E1 so E2 only writes values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from cachibot.storage.db import Base

__all__ = ["SideTask"]


class SideTask(Base):
    """A side task run in a child chat of a parent chat."""

    __tablename__ = "side_tasks"
    __table_args__ = (
        Index("idx_side_tasks_bot", "bot_id"),
        Index("idx_side_tasks_parent", "parent_chat_id"),
        Index("idx_side_tasks_chat", "chat_id"),
        Index("idx_side_tasks_status", "status"),
        Index("idx_side_tasks_group", "group_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    parent_chat_id: Mapped[str] = mapped_column(
        String, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )
    chat_id: Mapped[str] = mapped_column(
        String, ForeignKey("chats.id", ondelete="CASCADE"), nullable=False
    )

    # Identity
    title: Mapped[str] = mapped_column(String, nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String, nullable=False, server_default="side")
    group_id: Mapped[str | None] = mapped_column(String, nullable=True)
    group_title: Mapped[str | None] = mapped_column(String, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="waiting_for_slot")
    needs_you_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_by: Mapped[str] = mapped_column(String, nullable=False, server_default="user")

    # Workspace (E2: git worktree on a side/<slug> branch)
    worktree_path: Mapped[str | None] = mapped_column(String, nullable=True)
    branch: Mapped[str | None] = mapped_column(String, nullable=True)
    base_commit: Mapped[str | None] = mapped_column(String, nullable=True)

    # Merge result (E2)
    merged_commit: Mapped[str | None] = mapped_column(String, nullable=True)
    merged_files: Mapped[list[dict[str, Any]]] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )
    conflict_files: Mapped[list[str]] = mapped_column(sa.JSON, nullable=False, server_default="[]")

    # Thread reply (E5): the parent-chat message that started the side task,
    # and the single parent-chat reply message (updated in place).
    source_message_id: Mapped[str | None] = mapped_column(String, nullable=True)
    reply_message_id: Mapped[str | None] = mapped_column(String, nullable=True)

    # Results
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Link to the Work row (Runs / job runner integration)
    work_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("work.id", ondelete="SET NULL"), nullable=True
    )

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

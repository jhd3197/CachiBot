"""
Automation system models: Script, ScriptVersion, ExecutionLog, ExecutionLogLine,
TimelineEvent, ExecutionDailySummary.
"""

from __future__ import annotations

from datetime import date, datetime

import sqlalchemy as sa
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

__all__ = [
    "Script",
    "ScriptVersion",
    "ExecutionLog",
    "ExecutionLogLine",
    "TimelineEvent",
    "ExecutionDailySummary",
]


class Script(Base):
    """Versioned Python code entity owned by a bot."""

    __tablename__ = "scripts"
    __table_args__ = (
        Index("idx_scripts_bot", "bot_id"),
        Index("idx_scripts_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )

    # Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Code
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, server_default="python")

    # Status: draft -> active -> disabled -> archived
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")

    # Current version pointer
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # Metadata
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_by: Mapped[str] = mapped_column(
        String, nullable=False, server_default="user"
    )  # "user", "bot:{bot_id}", "system"

    # Execution config
    timeout_seconds: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="300"
    )
    max_memory_mb: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="256"
    )
    allowed_imports: Mapped[list] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )

    # Stats
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    success_rate: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )

    # Relationships
    versions: Mapped[list[ScriptVersion]] = relationship(
        "ScriptVersion",
        back_populates="script",
        cascade="all, delete-orphan",
        order_by="ScriptVersion.version_number",
    )


class ScriptVersion(Base):
    """Git-like version history per script."""

    __tablename__ = "script_versions"
    __table_args__ = (
        Index("idx_script_versions_script", "script_id"),
        UniqueConstraint("script_id", "version_number", name="uq_script_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    script_id: Mapped[str] = mapped_column(
        String, ForeignKey("scripts.id", ondelete="CASCADE"), nullable=False
    )

    # Version identity
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    diff_from_previous: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authorship
    author_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "user", "bot", "system"
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Approval workflow
    approved: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="false"
    )
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Metadata
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    script: Mapped[Script] = relationship("Script", back_populates="versions")


class ExecutionLog(Base):
    """Unified execution tracking for all automation types."""

    __tablename__ = "execution_logs"
    __table_args__ = (
        Index("idx_exec_log_bot", "bot_id"),
        Index("idx_exec_log_user", "user_id"),
        Index("idx_exec_log_type", "execution_type"),
        Index("idx_exec_log_status", "status"),
        Index("idx_exec_log_source", "source_type", "source_id"),
        Index("idx_exec_log_started", "started_at"),
        Index("idx_exec_log_bot_started", "bot_id", "started_at"),
        Index("idx_exec_log_bot_type_status", "bot_id", "execution_type", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)

    # What ran
    execution_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "work", "script", "schedule", "job"
    source_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "function", "schedule", "script", "manual", "api", "job"
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_name: Mapped[str] = mapped_column(
        String, nullable=False
    )  # denormalized for display

    # Who/where
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    chat_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True
    )

    # How it was triggered
    trigger: Mapped[str] = mapped_column(
        String, nullable=False, server_default="manual"
    )  # "cron", "manual", "event", "api", "schedule", "retry"

    # Timing
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="running"
    )  # "running", "success", "error", "timeout", "cancelled", "credit_exhausted"

    # Output
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cost tracking
    credits_consumed: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    tokens_used: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    prompt_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    completion_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    llm_calls: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Linkage to existing work system
    work_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("work.id", ondelete="SET NULL"), nullable=True
    )
    work_job_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("work_jobs.id", ondelete="SET NULL"), nullable=True
    )

    # Flexible metadata
    metadata_json: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, server_default="{}"
    )

    # Soft-delete for retention
    retained: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default="true"
    )

    # Relationships
    log_lines: Mapped[list[ExecutionLogLine]] = relationship(
        "ExecutionLogLine",
        back_populates="execution_log",
        cascade="all, delete-orphan",
        order_by="ExecutionLogLine.seq",
    )


class ExecutionLogLine(Base):
    """Structured log lines per execution."""

    __tablename__ = "execution_log_lines"
    __table_args__ = (
        Index("idx_log_lines_exec", "execution_log_id"),
        Index("idx_log_lines_exec_seq", "execution_log_id", "seq"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    execution_log_id: Mapped[str] = mapped_column(
        String, ForeignKey("execution_logs.id", ondelete="CASCADE"), nullable=False
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    level: Mapped[str] = mapped_column(
        String, nullable=False, server_default="info"
    )  # "debug", "info", "warn", "error", "stdout", "stderr"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    # Relationships
    execution_log: Mapped[ExecutionLog] = relationship(
        "ExecutionLog", back_populates="log_lines"
    )


class TimelineEvent(Base):
    """Materialized timeline entries for audit/history."""

    __tablename__ = "timeline_events"
    __table_args__ = (
        Index("idx_timeline_source", "source_type", "source_id"),
        Index("idx_timeline_bot", "bot_id"),
        Index("idx_timeline_ts", "event_at"),
        Index("idx_timeline_source_ts", "source_type", "source_id", "event_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )

    # What entity this event belongs to
    source_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "function", "schedule", "script", "work"
    source_id: Mapped[str] = mapped_column(String, nullable=False)

    # Event type
    event_type: Mapped[str] = mapped_column(
        String, nullable=False
    )  # "created", "edited", "version", "execution", "enabled", "disabled", "deleted"

    # Timing
    event_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Who did it
    actor_type: Mapped[str] = mapped_column(
        String, nullable=False, server_default="user"
    )  # "user", "bot", "system", "cron"
    actor_id: Mapped[str | None] = mapped_column(String, nullable=True)
    actor_name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Event details
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    diff: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Link to execution log (if event_type == "execution")
    execution_log_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("execution_logs.id", ondelete="SET NULL"), nullable=True
    )

    # Version info (if event_type == "version" or "edited")
    version_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    commit_message: Mapped[str | None] = mapped_column(String, nullable=True)

    metadata_json: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, server_default="{}"
    )


class ExecutionDailySummary(Base):
    """Aggregated daily stats for retention."""

    __tablename__ = "execution_daily_summaries"
    __table_args__ = (
        Index("idx_exec_summary_bot_date", "bot_id", "summary_date"),
        Index(
            "idx_exec_summary_source", "source_type", "source_id", "summary_date"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[str | None] = mapped_column(
        String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    execution_type: Mapped[str] = mapped_column(String, nullable=False)

    summary_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Aggregates
    total_runs: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    success_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    error_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    timeout_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    cancelled_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    avg_duration_ms: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    total_credits: Mapped[float] = mapped_column(
        Float, nullable=False, server_default="0.0"
    )
    total_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )

    # Top errors
    error_types: Mapped[dict] = mapped_column(
        sa.JSON, nullable=False, server_default="{}"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

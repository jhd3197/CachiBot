"""
Work management models: Function, Schedule, Work, Task, WorkJob, Todo.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

__all__ = ["Function", "Schedule", "Work", "Task", "WorkJob", "Todo"]


class Function(Base):
    """Reusable function template / procedure for a bot."""

    __tablename__ = "functions"
    __table_args__ = (
        Index("idx_functions_bot", "bot_id"),
        Index("idx_functions_name", "bot_id", "name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    version: Mapped[str] = mapped_column(String, nullable=False, server_default="1.0.0")
    steps: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    parameters: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")

    # Relationships
    schedules: Mapped[list[Schedule]] = relationship("Schedule", back_populates="function")
    work_items: Mapped[list[Work]] = relationship("Work", back_populates="function")


class Schedule(Base):
    """Cron/timer/event trigger that runs a function."""

    __tablename__ = "schedules"
    __table_args__ = (
        Index("idx_schedules_bot", "bot_id"),
        Index("idx_schedules_enabled", "enabled"),
        Index("idx_schedules_next_run", "next_run_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    function_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("functions.id", ondelete="SET NULL"),
        nullable=True,
    )
    function_params: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    schedule_type: Mapped[str] = mapped_column(String, nullable=False, server_default="cron")
    cron_expression: Mapped[str | None] = mapped_column(String, nullable=True)
    interval_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    event_trigger: Mapped[str | None] = mapped_column(String, nullable=True)
    timezone: Mapped[str] = mapped_column(String, nullable=False, server_default="UTC")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    max_concurrent: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    catch_up: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Relationships
    function: Mapped[Function | None] = relationship("Function", back_populates="schedules")
    work_items: Mapped[list[Work]] = relationship("Work", back_populates="schedule")


class Work(Base):
    """High-level work objective that contains tasks."""

    __tablename__ = "work"
    __table_args__ = (
        Index("idx_work_bot", "bot_id"),
        Index("idx_work_status", "status"),
        Index("idx_work_schedule", "schedule_id"),
        Index("idx_work_parent", "parent_work_id"),
        Index("idx_work_chat", "bot_id", "chat_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    goal: Mapped[str | None] = mapped_column(Text, nullable=True)
    function_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("functions.id", ondelete="SET NULL"),
        nullable=True,
    )
    schedule_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("schedules.id", ondelete="SET NULL"),
        nullable=True,
    )
    parent_work_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("work.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    priority: Mapped[str] = mapped_column(String, nullable=False, server_default="normal")
    progress: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    context: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")

    # Relationships
    function: Mapped[Function | None] = relationship("Function", back_populates="work_items")
    schedule: Mapped[Schedule | None] = relationship("Schedule", back_populates="work_items")
    parent_work: Mapped[Work | None] = relationship(
        "Work", remote_side="Work.id", back_populates="child_work"
    )
    child_work: Mapped[list[Work]] = relationship("Work", back_populates="parent_work")
    tasks: Mapped[list[Task]] = relationship(
        "Task", back_populates="work", cascade="all, delete-orphan"
    )
    work_jobs: Mapped[list[WorkJob]] = relationship(
        "WorkJob",
        back_populates="work",
        cascade="all, delete-orphan",
        foreign_keys="[WorkJob.work_id]",
    )
    # Todos that were converted to this work
    converted_todos: Mapped[list[Todo]] = relationship(
        "Todo",
        back_populates="converted_to_work",
        foreign_keys="[Todo.converted_to_work_id]",
    )


class Task(Base):
    """Step within a work item."""

    __tablename__ = "tasks"
    __table_args__ = (
        Index("idx_tasks_bot", "bot_id"),
        Index("idx_tasks_work", "work_id"),
        Index("idx_tasks_status", "status"),
        Index("idx_tasks_order", "work_id", "task_order"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    work_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("work.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    action: Mapped[str | None] = mapped_column(Text, nullable=True)
    task_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    depends_on: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    priority: Mapped[str] = mapped_column(String, nullable=False, server_default="normal")
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    max_retries: Mapped[int] = mapped_column(Integer, nullable=False, server_default="3")
    timeout_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    work: Mapped[Work] = relationship("Work", back_populates="tasks")
    work_jobs: Mapped[list[WorkJob]] = relationship(
        "WorkJob", back_populates="task", cascade="all, delete-orphan"
    )
    # Todos that were converted to this task
    converted_todos: Mapped[list[Todo]] = relationship(
        "Todo",
        back_populates="converted_to_task",
        foreign_keys="[Todo.converted_to_task_id]",
    )


class WorkJob(Base):
    """Execution attempt for a task within the work system."""

    __tablename__ = "work_jobs"
    __table_args__ = (
        Index("idx_work_jobs_bot", "bot_id"),
        Index("idx_work_jobs_task", "task_id"),
        Index("idx_work_jobs_work", "work_id"),
        Index("idx_work_jobs_status", "status"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    task_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("tasks.id", ondelete="CASCADE"),
        nullable=False,
    )
    work_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("work.id", ondelete="CASCADE"),
        nullable=False,
    )
    chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="pending")
    attempt: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    progress: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    logs: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")

    # Relationships
    task: Mapped[Task] = relationship("Task", back_populates="work_jobs")
    work: Mapped[Work] = relationship("Work", back_populates="work_jobs")


class Todo(Base):
    """Reminder / note that can be converted to work or tasks."""

    __tablename__ = "todos"
    __table_args__ = (
        Index("idx_todos_bot", "bot_id"),
        Index("idx_todos_status", "status"),
        Index("idx_todos_remind", "remind_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    chat_id: Mapped[str | None] = mapped_column(String, nullable=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="open")
    priority: Mapped[str] = mapped_column(String, nullable=False, server_default="normal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remind_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    converted_to_work_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("work.id", ondelete="SET NULL"),
        nullable=True,
    )
    converted_to_task_id: Mapped[str | None] = mapped_column(
        String,
        ForeignKey("tasks.id", ondelete="SET NULL"),
        nullable=True,
    )
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")

    # Relationships
    converted_to_work: Mapped[Work | None] = relationship("Work", back_populates="converted_todos")
    converted_to_task: Mapped[Task | None] = relationship("Task", back_populates="converted_todos")

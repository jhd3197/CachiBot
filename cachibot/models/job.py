"""
Job-related Pydantic models.

.. deprecated::
    This module is part of the legacy job system. Use ``cachibot.models.work``
    (Work, Task, Job) and ``cachibot.models.automations`` (ExecutionLog, Script)
    instead. This file will be removed in a future release.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Job(BaseModel):
    """A background job/task."""

    id: str = Field(description="Unique job ID")
    status: JobStatus = Field(default=JobStatus.PENDING)
    message_id: str | None = Field(default=None, description="Related message ID")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)
    progress: float = Field(default=0.0, ge=0.0, le=1.0)


class JobList(BaseModel):
    """List of jobs."""

    jobs: list[Job] = Field(default_factory=list)
    total: int = Field(default=0)

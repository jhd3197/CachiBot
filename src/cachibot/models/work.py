"""Work management models: Functions, Schedules, Work, Tasks, Jobs, Todos."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# =============================================================================
# ENUMS
# =============================================================================


class WorkStatus(str, Enum):
    """Work execution status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    READY = "ready"  # All dependencies met, can run
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"  # Waiting on dependencies
    SKIPPED = "skipped"


class JobStatus(str, Enum):
    """Job execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TodoStatus(str, Enum):
    """Todo status."""

    OPEN = "open"
    DONE = "done"
    DISMISSED = "dismissed"


class Priority(str, Enum):
    """Priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ScheduleType(str, Enum):
    """Schedule trigger types."""

    CRON = "cron"  # Cron expression
    INTERVAL = "interval"  # Every N seconds/minutes/hours
    ONCE = "once"  # One-time scheduled execution
    EVENT = "event"  # Triggered by an event


class FailureAction(str, Enum):
    """What to do when a step fails."""

    STOP = "stop"
    CONTINUE = "continue"
    SKIP_DEPENDENTS = "skip_dependents"


# =============================================================================
# FUNCTION (Reusable Template/Procedure)
# =============================================================================


class FunctionStep(BaseModel):
    """A step within a function template."""

    order: int = Field(description="Execution order (1-based)")
    name: str = Field(description="Step name")
    description: str | None = Field(default=None)
    action: str = Field(description="What to do (natural language or tool call)")
    depends_on: list[int] = Field(
        default_factory=list, description="Step orders this depends on"
    )
    retry_count: int = Field(default=0, description="Number of retries on failure")
    timeout_seconds: int | None = Field(default=None, description="Step timeout")
    on_failure: FailureAction = Field(
        default=FailureAction.STOP, description="What to do on failure"
    )


class FunctionParameter(BaseModel):
    """Parameter definition for a function."""

    name: str = Field(description="Parameter name")
    type: str = Field(default="string", description="Parameter type")
    default: Any | None = Field(default=None, description="Default value")
    required: bool = Field(default=True, description="Whether required")
    description: str | None = Field(default=None)


class BotFunction(BaseModel):
    """A reusable procedure/template that can be instantiated as Work."""

    id: str = Field(description="Unique function ID")
    bot_id: str = Field(description="Bot that owns this function")
    name: str = Field(description="Function name")
    description: str | None = Field(default=None)
    version: str = Field(default="1.0.0")

    # Steps
    steps: list[FunctionStep] = Field(default_factory=list)

    # Parameters (inputs when instantiating)
    parameters: list[FunctionParameter] = Field(default_factory=list)

    # Metadata
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Stats
    run_count: int = Field(default=0)
    last_run_at: datetime | None = Field(default=None)
    success_rate: float = Field(default=0.0)


# =============================================================================
# SCHEDULE (Cron/Timer)
# =============================================================================


class Schedule(BaseModel):
    """A schedule for triggering Work."""

    id: str = Field(description="Unique schedule ID")
    bot_id: str = Field(description="Bot that owns this schedule")
    name: str = Field(description="Schedule name")
    description: str | None = Field(default=None)

    # What to run
    function_id: str | None = Field(
        default=None, description="Function to instantiate"
    )
    function_params: dict[str, Any] = Field(
        default_factory=dict, description="Parameters for function"
    )

    # When to run
    schedule_type: ScheduleType = Field(default=ScheduleType.CRON)
    cron_expression: str | None = Field(
        default=None, description="Cron expression (if type=cron)"
    )
    interval_seconds: int | None = Field(
        default=None, description="Interval in seconds (if type=interval)"
    )
    run_at: datetime | None = Field(
        default=None, description="One-time run datetime (if type=once)"
    )
    event_trigger: str | None = Field(
        default=None, description="Event name (if type=event)"
    )
    timezone: str = Field(default="UTC")

    # Constraints
    enabled: bool = Field(default=True)
    max_concurrent: int = Field(default=1, description="Max concurrent Work instances")
    catch_up: bool = Field(
        default=False, description="Run missed executions on startup"
    )

    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    next_run_at: datetime | None = Field(default=None)
    last_run_at: datetime | None = Field(default=None)
    run_count: int = Field(default=0)


# =============================================================================
# WORK (Objective/Goal)
# =============================================================================


class Work(BaseModel):
    """A high-level objective the bot needs to accomplish."""

    id: str = Field(description="Unique work ID")
    bot_id: str = Field(description="Bot assigned to this work")
    chat_id: str | None = Field(default=None, description="Related chat context")

    # Identity
    title: str = Field(description="Work title")
    description: str | None = Field(default=None)
    goal: str | None = Field(
        default=None, description="Success criteria / definition of done"
    )

    # Source
    function_id: str | None = Field(
        default=None, description="Source function template"
    )
    schedule_id: str | None = Field(
        default=None, description="Source schedule (if recurring)"
    )
    parent_work_id: str | None = Field(
        default=None, description="Parent work (for sub-work)"
    )

    # Status
    status: WorkStatus = Field(default=WorkStatus.PENDING)
    priority: Priority = Field(default=Priority.NORMAL)
    progress: float = Field(
        default=0.0, ge=0.0, le=1.0, description="0.0-1.0 derived from tasks"
    )

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    due_at: datetime | None = Field(default=None)

    # Results
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)

    # Context (parameters passed when instantiating)
    context: dict[str, Any] = Field(default_factory=dict)

    # Metadata
    tags: list[str] = Field(default_factory=list)


# =============================================================================
# TASK (Step within Work)
# =============================================================================


class Task(BaseModel):
    """A discrete, completable step within Work."""

    id: str = Field(description="Unique task ID")
    bot_id: str = Field(description="Bot assigned to this task")
    work_id: str = Field(description="Parent work")
    chat_id: str | None = Field(default=None)

    # Identity
    title: str = Field(description="Task title")
    description: str | None = Field(default=None)
    action: str | None = Field(default=None, description="Specific action to perform")

    # Ordering & Dependencies
    order: int = Field(default=0, description="Execution order within work")
    depends_on: list[str] = Field(
        default_factory=list, description="Task IDs this depends on"
    )

    # Status
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    priority: Priority = Field(default=Priority.NORMAL)

    # Execution config
    retry_count: int = Field(default=0)
    max_retries: int = Field(default=3)
    timeout_seconds: int | None = Field(default=None)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Results
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)


# =============================================================================
# JOB (Execution attempt of Task)
# =============================================================================


class Job(BaseModel):
    """A single execution attempt of a Task."""

    id: str = Field(description="Unique job ID")
    bot_id: str = Field(description="Bot running this job")
    task_id: str = Field(description="Task being executed")
    work_id: str = Field(description="Parent work")
    chat_id: str | None = Field(default=None)

    # Status
    status: JobStatus = Field(default=JobStatus.PENDING)
    attempt: int = Field(default=1, description="Attempt number (1, 2, 3...)")
    progress: float = Field(default=0.0, ge=0.0, le=1.0)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)

    # Results
    result: Any | None = Field(default=None)
    error: str | None = Field(default=None)

    # Logs
    logs: list[dict] = Field(default_factory=list, description="Execution logs")


class JobLog(BaseModel):
    """A log entry for a job."""

    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: str = Field(default="info", description="debug, info, warn, error")
    message: str = Field(description="Log message")
    data: Any | None = Field(default=None, description="Additional data")


# =============================================================================
# TODO (Reminder/Note)
# =============================================================================


class Todo(BaseModel):
    """A lightweight reminder or note."""

    id: str = Field(description="Unique todo ID")
    bot_id: str = Field(description="Bot this todo belongs to")
    chat_id: str | None = Field(default=None, description="Related chat")

    # Content
    title: str = Field(description="Todo title")
    notes: str | None = Field(default=None)

    # Status
    status: TodoStatus = Field(default=TodoStatus.OPEN)
    priority: Priority = Field(default=Priority.NORMAL)

    # Timing
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: datetime | None = Field(default=None)
    remind_at: datetime | None = Field(
        default=None, description="Optional reminder time"
    )

    # Conversion tracking
    converted_to_work_id: str | None = Field(default=None)
    converted_to_task_id: str | None = Field(default=None)

    # Metadata
    tags: list[str] = Field(default_factory=list)


# =============================================================================
# LIST RESPONSE MODELS
# =============================================================================


class WorkList(BaseModel):
    """List of work items."""

    items: list[Work] = Field(default_factory=list)
    total: int = Field(default=0)


class TaskList(BaseModel):
    """List of tasks."""

    items: list[Task] = Field(default_factory=list)
    total: int = Field(default=0)


class JobList(BaseModel):
    """List of jobs."""

    items: list[Job] = Field(default_factory=list)
    total: int = Field(default=0)


class TodoList(BaseModel):
    """List of todos."""

    items: list[Todo] = Field(default_factory=list)
    total: int = Field(default=0)


class FunctionList(BaseModel):
    """List of functions."""

    items: list[BotFunction] = Field(default_factory=list)
    total: int = Field(default=0)


class ScheduleList(BaseModel):
    """List of schedules."""

    items: list[Schedule] = Field(default_factory=list)
    total: int = Field(default=0)

"""Automation system Pydantic models: Scripts, Versions, Execution Logs, Timeline."""

from datetime import date, datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# =============================================================================
# ENUMS
# =============================================================================


class ScriptStatus(str, Enum):
    """Script lifecycle status."""

    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"


class AuthorType(str, Enum):
    """Who authored a script version."""

    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class ExecutionType(str, Enum):
    """How a function executes."""

    AGENT = "agent"
    SCRIPT = "script"
    HYBRID = "hybrid"


class ExecutionStatus(str, Enum):
    """Execution log status."""

    RUNNING = "running"
    SUCCESS = "success"
    ERROR = "error"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    CREDIT_EXHAUSTED = "credit_exhausted"


class TriggerType(str, Enum):
    """How an execution was triggered."""

    CRON = "cron"
    MANUAL = "manual"
    EVENT = "event"
    API = "api"
    SCHEDULE = "schedule"
    RETRY = "retry"


class LogLevel(str, Enum):
    """Execution log line levels."""

    DEBUG = "debug"
    INFO = "info"
    WARN = "warn"
    ERROR = "error"
    STDOUT = "stdout"
    STDERR = "stderr"


# =============================================================================
# SCRIPT
# =============================================================================


class Script(BaseModel):
    """A versioned Python code entity owned by a bot."""

    id: str = Field(description="Unique script ID")
    bot_id: str = Field(description="Bot that owns this script")
    name: str = Field(description="Script name")
    description: str | None = Field(default=None)
    source_code: str = Field(description="Current source code")
    language: str = Field(default="python")
    status: ScriptStatus = Field(default=ScriptStatus.DRAFT)
    current_version: int = Field(default=1)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = Field(default="user")
    timeout_seconds: int = Field(default=300)
    max_memory_mb: int = Field(default=256)
    allowed_imports: list[str] = Field(default_factory=list)
    run_count: int = Field(default=0)
    last_run_at: datetime | None = Field(default=None)
    success_rate: float = Field(default=0.0)


class ScriptVersion(BaseModel):
    """A single version in a script's history."""

    id: str = Field(description="Unique version ID")
    script_id: str = Field(description="Parent script")
    version_number: int = Field(description="Sequential version number")
    source_code: str = Field(description="Source code at this version")
    diff_from_previous: str | None = Field(default=None)
    author_type: AuthorType = Field(description="Who authored this version")
    author_id: str | None = Field(default=None)
    commit_message: str = Field(description="Description of changes")
    approved: bool = Field(default=False)
    approved_by: str | None = Field(default=None)
    approved_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# EXECUTION LOG
# =============================================================================


class ExecutionLogLine(BaseModel):
    """A single log line in an execution."""

    id: str = Field(description="Unique log line ID")
    execution_log_id: str = Field(description="Parent execution log")
    seq: int = Field(description="Sequence number for ordering")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    level: LogLevel = Field(default=LogLevel.INFO)
    content: str = Field(description="Log content")
    data: dict[str, Any] | None = Field(default=None)


class ExecutionLog(BaseModel):
    """Unified execution tracking for all automation types."""

    id: str = Field(description="Unique execution log ID")
    execution_type: str = Field(description="Type: work, script, schedule, job")
    source_type: str = Field(description="Source: function, schedule, script, manual, api, job")
    source_id: str | None = Field(default=None)
    source_name: str = Field(description="Human-readable source name")
    bot_id: str = Field(description="Bot that ran this")
    user_id: str | None = Field(default=None)
    chat_id: str | None = Field(default=None)
    trigger: TriggerType = Field(default=TriggerType.MANUAL)
    started_at: datetime = Field(default_factory=datetime.utcnow)
    finished_at: datetime | None = Field(default=None)
    duration_ms: int | None = Field(default=None)
    status: ExecutionStatus = Field(default=ExecutionStatus.RUNNING)
    output: str | None = Field(default=None)
    error: str | None = Field(default=None)
    exit_code: int | None = Field(default=None)
    credits_consumed: float = Field(default=0.0)
    tokens_used: int = Field(default=0)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    llm_calls: int = Field(default=0)
    work_id: str | None = Field(default=None)
    work_job_id: str | None = Field(default=None)
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    retained: bool = Field(default=True)


# =============================================================================
# TIMELINE
# =============================================================================


class TimelineEvent(BaseModel):
    """A materialized timeline entry for audit/history."""

    id: str = Field(description="Unique event ID")
    bot_id: str = Field(description="Bot this event belongs to")
    source_type: str = Field(description="Entity type: function, schedule, script, work")
    source_id: str = Field(description="Entity ID")
    event_type: str = Field(
        description="Event: created, edited, version, execution, enabled, disabled, deleted"
    )
    event_at: datetime = Field(default_factory=datetime.utcnow)
    actor_type: str = Field(default="user")
    actor_id: str | None = Field(default=None)
    actor_name: str | None = Field(default=None)
    title: str = Field(description="Event title")
    description: str | None = Field(default=None)
    diff: str | None = Field(default=None)
    execution_log_id: str | None = Field(default=None)
    version_number: int | None = Field(default=None)
    commit_message: str | None = Field(default=None)
    metadata_json: dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# DAILY SUMMARY
# =============================================================================


class ExecutionDailySummary(BaseModel):
    """Aggregated daily stats for retention."""

    id: str = Field(description="Unique summary ID")
    bot_id: str
    user_id: str | None = None
    source_type: str
    source_id: str
    execution_type: str
    summary_date: date
    total_runs: int = 0
    success_count: int = 0
    error_count: int = 0
    timeout_count: int = 0
    cancelled_count: int = 0
    total_duration_ms: int = 0
    avg_duration_ms: int = 0
    total_credits: float = 0.0
    total_tokens: int = 0
    error_types: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)


# =============================================================================
# CREATE/UPDATE SCHEMAS
# =============================================================================


class CreateScriptRequest(BaseModel):
    """Request to create a new script."""

    name: str = Field(description="Script name")
    description: str | None = Field(default=None)
    source_code: str = Field(description="Initial source code")
    language: str = Field(default="python")
    tags: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=300)
    max_memory_mb: int = Field(default=256)
    allowed_imports: list[str] = Field(default_factory=list)
    commit_message: str = Field(default="Initial version")


class UpdateScriptRequest(BaseModel):
    """Request to update an existing script."""

    name: str | None = None
    description: str | None = None
    source_code: str | None = None
    tags: list[str] | None = None
    timeout_seconds: int | None = None
    max_memory_mb: int | None = None
    allowed_imports: list[str] | None = None
    commit_message: str | None = None


class CreateScriptVersionRequest(BaseModel):
    """Request to create a new version of a script."""

    source_code: str = Field(description="New source code")
    commit_message: str = Field(description="Description of changes")
    author_type: AuthorType = Field(default=AuthorType.USER)
    author_id: str | None = None


class ScriptValidationResult(BaseModel):
    """Result of script save-time validation."""

    allowed: bool = Field(description="Whether the script is allowed")
    reason: str | None = Field(default=None, description="Rejection reason if not allowed")
    risk_level: str | None = Field(default=None)
    warnings: list[str] = Field(default_factory=list)

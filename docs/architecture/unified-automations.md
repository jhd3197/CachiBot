# Unified Automations System Design

> **Status**: Design Complete — Ready for Implementation
> **Date**: 2026-02-17
> **Scope**: CachiBotV2, Tukuy, Prompture

---

## Table of Contents

1. [Executive Summary](#1-executive-summary)
2. [Investigation Findings](#2-investigation-findings)
   - [Jobs System](#21-jobs-system-legacy)
   - [Works System](#22-works-system-active)
   - [Tukuy & Prompture Integration](#23-tukuy--prompture-integration)
3. [Architecture Decision](#3-architecture-decision)
4. [Data Model](#4-data-model)
   - [New Tables](#41-new-tables)
   - [Modified Tables](#42-modified-tables)
   - [Deprecated Tables](#43-deprecated-tables)
5. [Script System](#5-script-system)
6. [Execution Log System](#6-execution-log-system)
7. [Security & Sandbox](#7-security--sandbox)
8. [Frontend Design](#8-frontend-design)
9. [API Endpoints](#9-api-endpoints)
10. [Migration Path](#10-migration-path)

---

## 1. Executive Summary

CachiBotV2 has **two separate automation systems** — Legacy Jobs and the Work system — that need to be mapped, unified, and wired into a single execution log. This document defines the complete architecture for:

- **Consolidating** Legacy Jobs into the Work system (which is already comprehensive)
- **Adding a Script system** with git-like version history and bot/user authorship
- **Building a unified execution log** that tracks every run with duration, status, credits, tokens, and output
- **Designing the security model** for unattended automated execution
- **Designing the frontend** for a unified "Automations" view, script editor, timeline, and admin dashboard

### Key Numbers

| Metric | Value |
|--------|-------|
| New database tables | 6 |
| Modified database tables | 2 |
| Deprecated database tables | 1 |
| New backend files | ~8 |
| New frontend files | 13 |
| Modified frontend files | 10 |
| New API endpoints | ~36 |
| New frontend dependency | 1 (`@monaco-editor/react`) |
| Existing security infrastructure reused | ~70% |

---

## 2. Investigation Findings

### 2.1 Jobs System (Legacy)

**Key files:**
- `src/cachibot/models/job.py` — Pydantic model
- `src/cachibot/storage/models/job.py` — SQLAlchemy ORM (`jobs` table)
- `src/cachibot/storage/repository.py` — `JobRepository` (legacy)
- `frontend/src/components/views/JobsView.tsx` — Frontend view

**What it is:** A simple flat job model tied to a message. Fields: `id`, `status`, `message_id`, `created_at`, `started_at`, `completed_at`, `result`, `error`, `progress`.

**Problems:**
- No runner, no executor — the model exists but nothing executes it
- Imported only as `LegacyJob` alias in `models/__init__.py`
- No scheduling, no hierarchy, no retry logic
- No execution logging whatsoever
- Completely superseded by the Work system

**Verdict:** Dead code. Should be deprecated and removed after data migration.

### 2.2 Works System (Active)

**Key files:**
- `src/cachibot/models/work.py` — Pydantic models for all 6 entities
- `src/cachibot/storage/models/work.py` — SQLAlchemy ORM (6 tables)
- `src/cachibot/storage/work_repository.py` — 6 repository classes with full CRUD
- `src/cachibot/api/routes/work.py` — 1648 lines, ~50 REST endpoints
- `src/cachibot/services/job_runner.py` — Async background loop (polls every 10s, max 5 concurrent)
- `src/cachibot/services/scheduler_service.py` — Async background loop (polls every 30s)
- `src/cachibot/plugins/work_management.py` — Agent tools (work_create, work_list, etc.)
- `src/cachibot/plugins/job_tools.py` — Agent tools (job_create, job_status, etc. — wraps Work system)

**What it is:** A 4-level hierarchy for bot automation:

```
BotFunction (table: functions)     — Reusable procedure templates with steps, parameters, version, tags
    |
Schedule (table: schedules)        — Cron/interval/once/event triggers with timezone, catch-up, concurrency
    |
Work (table: work)                 — High-level objectives with title, description, goal, priority, progress
    |
Task (table: tasks)                — Steps within Work with ordering, dependencies, retry config, timeout
    |
WorkJob (table: work_jobs)         — Execution attempts with attempt number, logs, status
    |
Todo (table: todos)                — Lightweight reminders, promotable to Work/Tasks
```

**Execution flow:**
1. `SchedulerService` polls every 30s for due schedules and todo reminders
2. When a schedule fires, it delivers messages via platform and/or WebSocket
3. `JobRunnerService` polls every 10s for pending Work, resolves ready Tasks, creates WorkJobs
4. Each WorkJob execution creates a `CachibotAgent` and runs `agent.run(action)` — sends a prompt to an LLM
5. WebSocket broadcasting for real-time status updates (`JOB_UPDATE`, `SCHEDULED_NOTIFICATION`)

**Frontend:**
- `WorkView.tsx` — Work management with master-detail layout
- `JobsView.tsx` — Job list with log viewer
- `TasksView.tsx` — Kanban board (disconnected from Work Task hierarchy)
- `SchedulesView.tsx` — Schedule management

**Problems found:**
1. `SchedulerService` fires messages only, does NOT create Work items from functions (incomplete)
2. Schedule create form has `// TODO: Implement create schedule API call`
3. No frontend for BotFunction management (templates)
4. WorkJob logs stored as append-only JSON column (performance risk)
5. No "Run" button in WorkView — works only created via API or agent tools
6. Progress scale mismatch (0.0-1.0 backend vs 0-100 frontend)
7. Two overlapping plugins: `WorkManagementPlugin` and `JobToolsPlugin` both create/manage Work items
8. Frontend TasksView (Kanban) uses different statuses than Work Task hierarchy

### 2.3 Tukuy & Prompture Integration

**How they connect:**
- CachiBot plugins are built on Tukuy's `@skill` decorator and `TransformerPlugin` base class
- `plugin_manager.py` bridges Tukuy skills to Prompture's `ToolRegistry` via `add_tukuy_skill()`
- `CachibotAgent` wraps Prompture's `AsyncAgent` with sandbox, security, and capability gating
- `driver_factory.py` builds Prompture async drivers with per-bot API keys (bypassing global registry)

**API key flow (interactive):**
```
WebSocket → _resolve_bot_env() → 5-layer merge (Global/Platform/Bot/Skill/Request)
→ encrypted DB keys → build_driver_with_key() → driver injected into agent
```

**7 Critical Gaps:**

| # | Gap | Impact |
|---|-----|--------|
| 1 | Job runner ignores per-bot API keys | `_run_agent_for_task()` doesn't call `_resolve_bot_env()`, background jobs use global keys only |
| 2 | Zero token/cost tracking | Prompture has `UsageSession` (in-memory) and `UsageTracker` (SQLite with budget), CachiBot uses neither |
| 3 | No execution mode context | Skills can't know if they're running from user chat or automated job |
| 4 | No LLM rate limiting | Only `_MAX_CONCURRENT_JOBS = 5` global concurrency, no per-bot or per-period limits |
| 5 | Budget system exists but unused | `UsageTracker.check_budget()` / `BudgetExceededError` in Prompture, not wired in |
| 6 | No scripts concept | Users can only create SKILL.md definitions and cron schedules that deliver messages |
| 7 | Scheduler is message-only | `SchedulerService` delivers text via WebSocket/platform, never invokes agent actions |

**Recommendations:**
- Wire `UsageTracker` into `CachibotAgent` via `as_callbacks()` for automatic tracking
- Add `execution_context` field to `SkillContext` (in Tukuy) to differentiate interactive/automated
- Fix job runner to use `_resolve_bot_env()` for per-bot keys
- Use `UsageTracker.check_budget()` as pre-call guard in both job runner and scheduler
- Extend scheduler to support "run agent action" in addition to "deliver message"

---

## 3. Architecture Decision

### Option A-Modified: Consolidate + Add Scripts

**Keep the Work system as the foundation. Deprecate Legacy Jobs. Add Scripts on top.**

Rationale:
1. The Legacy Job system is a dead-simple subset of WorkJobs — just status tracking on messages with no scheduling, no hierarchy, no retry logic
2. The Work system is already comprehensive and well-designed — it has the full hierarchy
3. The naming is confusing: "Job" means two different things depending on which module you import
4. Scripts are a new entity that plugs into the existing Function → Schedule → Work pipeline

### Entity Hierarchy (after unification)

```
Script (Python code with versioning)                                    ← NEW
    |
BotFunction (reusable procedure template — NL steps OR script ref)      ← MODIFIED
    |
Schedule (cron/interval/once/event trigger)                             ← UNCHANGED
    |
Work (high-level objective / execution instance)                        ← MODIFIED
    |
Task (discrete step within work)                                        ← UNCHANGED
    |
WorkJob (single execution attempt of a task)                            ← UNCHANGED
    |
ExecutionLog (structured log per execution)                             ← NEW
```

**Where Scripts fit:** A Script is a **sibling to BotFunction** — a reusable piece of executable code that can be:
1. Referenced by a BotFunction (`function.script_id`): The function becomes a script-execution wrapper
2. Attached to a Schedule via a function that references the script
3. Run manually: User clicks "Run Script", which creates a Work → Task → WorkJob

---

## 4. Data Model

### 4.1 New Tables

#### `scripts`

```python
class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id", ondelete="CASCADE"))

    # Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Code
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    language: Mapped[str] = mapped_column(String, nullable=False, server_default="python")

    # Status: draft -> active -> disabled -> archived
    # Bot creates -> draft. User approves -> active. User disables -> disabled.
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="draft")

    # Current version pointer
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")

    # Metadata
    tags: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_by: Mapped[str] = mapped_column(String, nullable=False)  # "user", "bot:{bot_id}", "system"

    # Execution config
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, server_default="300")
    max_memory_mb: Mapped[int] = mapped_column(Integer, nullable=False, server_default="256")
    allowed_imports: Mapped[list] = mapped_column(JSON, nullable=False, server_default="[]")

    # Stats
    run_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    success_rate: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
```

#### `script_versions`

```python
class ScriptVersion(Base):
    __tablename__ = "script_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    script_id: Mapped[str] = mapped_column(String, ForeignKey("scripts.id", ondelete="CASCADE"))

    # Version identity
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)

    # Content
    source_code: Mapped[str] = mapped_column(Text, nullable=False)
    diff_from_previous: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Authorship
    author_type: Mapped[str] = mapped_column(String, nullable=False)  # "user", "bot", "system"
    author_id: Mapped[str | None] = mapped_column(String, nullable=True)
    commit_message: Mapped[str] = mapped_column(Text, nullable=False)

    # Approval workflow
    approved: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    approved_by: Mapped[str | None] = mapped_column(String, nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("idx_script_versions_script", "script_id"),
        sa.UniqueConstraint("script_id", "version_number", name="uq_script_version"),
    )
```

#### `execution_logs`

```python
class ExecutionLog(Base):
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
    execution_type: Mapped[str] = mapped_column(String, nullable=False)
    # Values: "work", "script", "schedule", "job" (legacy)
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    # Values: "function", "schedule", "script", "manual", "api", "job"
    source_id: Mapped[str | None] = mapped_column(String, nullable=True)
    source_name: Mapped[str] = mapped_column(String, nullable=False)  # denormalized for display

    # Who/where
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String, ForeignKey("chats.id", ondelete="SET NULL"), nullable=True)

    # How it was triggered
    trigger: Mapped[str] = mapped_column(String, nullable=False, server_default="manual")
    # Values: "cron", "manual", "event", "api", "schedule", "retry"

    # Timing
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String, nullable=False, server_default="running")
    # Values: "running", "success", "error", "timeout", "cancelled", "credit_exhausted"

    # Output
    output: Mapped[str | None] = mapped_column(Text, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Cost tracking
    credits_consumed: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    llm_calls: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Linkage to existing work system
    work_id: Mapped[str | None] = mapped_column(String, ForeignKey("work.id", ondelete="SET NULL"), nullable=True)
    work_job_id: Mapped[str | None] = mapped_column(String, ForeignKey("work_jobs.id", ondelete="SET NULL"), nullable=True)

    # Flexible metadata (model used, script version, provider, adapter, etc.)
    metadata_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")

    # Soft-delete for retention
    retained: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Relationships
    log_lines: Mapped[list[ExecutionLogLine]] = relationship(
        "ExecutionLogLine", back_populates="execution_log",
        cascade="all, delete-orphan", order_by="ExecutionLogLine.seq"
    )
```

#### `execution_log_lines`

```python
class ExecutionLogLine(Base):
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
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    level: Mapped[str] = mapped_column(String, nullable=False, server_default="info")
    # Values: "debug", "info", "warn", "error", "stdout", "stderr"
    content: Mapped[str] = mapped_column(Text, nullable=False)
    data: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    execution_log: Mapped[ExecutionLog] = relationship("ExecutionLog", back_populates="log_lines")
```

#### `timeline_events`

```python
class TimelineEvent(Base):
    __tablename__ = "timeline_events"
    __table_args__ = (
        Index("idx_timeline_source", "source_type", "source_id"),
        Index("idx_timeline_bot", "bot_id"),
        Index("idx_timeline_ts", "event_at"),
        Index("idx_timeline_source_ts", "source_type", "source_id", "event_at"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)

    # What entity this event belongs to
    source_type: Mapped[str] = mapped_column(String, nullable=False)
    # Values: "function", "schedule", "script", "work"
    source_id: Mapped[str] = mapped_column(String, nullable=False)

    # Event type
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    # Values: "created", "edited", "version", "execution", "enabled", "disabled", "deleted"

    # Timing
    event_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    # Who did it
    actor_type: Mapped[str] = mapped_column(String, nullable=False, server_default="user")
    # Values: "user", "bot", "system", "cron"
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

    metadata_json: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")
```

#### `execution_daily_summaries`

```python
class ExecutionDailySummary(Base):
    __tablename__ = "execution_daily_summaries"
    __table_args__ = (
        Index("idx_exec_summary_bot_date", "bot_id", "summary_date"),
        Index("idx_exec_summary_source", "source_type", "source_id", "summary_date"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False)
    user_id: Mapped[str | None] = mapped_column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    source_type: Mapped[str] = mapped_column(String, nullable=False)
    source_id: Mapped[str] = mapped_column(String, nullable=False)
    execution_type: Mapped[str] = mapped_column(String, nullable=False)

    summary_date: Mapped[date] = mapped_column(Date, nullable=False)

    # Aggregates
    total_runs: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    success_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    timeout_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    cancelled_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    avg_duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    total_credits: Mapped[float] = mapped_column(Float, nullable=False, server_default="0.0")
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    # Top errors: {"TypeError: ...": 3, "TimeoutError": 1}
    error_types: Mapped[dict] = mapped_column(sa.JSON, nullable=False, server_default="{}")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
```

### 4.2 Modified Tables

#### `functions` — Add script reference

```python
# Add to existing Function model in storage/models/work.py:
script_id: Mapped[str | None] = mapped_column(
    String, ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True
)
execution_type: Mapped[str] = mapped_column(
    String, nullable=False, server_default="agent"
)
# execution_type values:
#   "agent"  — current behavior, NL steps through CachibotAgent
#   "script" — execute the referenced script in sandbox
#   "hybrid" — future, script that can call agent
```

#### `work` — Add script execution tracking

```python
# Add to existing Work model in storage/models/work.py:
script_id: Mapped[str | None] = mapped_column(
    String, ForeignKey("scripts.id", ondelete="SET NULL"), nullable=True
)
script_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
# Records which exact script version was used for this execution
```

### 4.3 Deprecated Tables

| Table/File | Action |
|------------|--------|
| `models/job.py` (Pydantic model) | Deprecate, then remove after migration |
| `storage/models/job.py` (ORM) | Deprecate, then remove after migration |
| `storage/repository.py` `JobRepository` | Deprecate, then remove after migration |
| `LegacyJob` alias in `models/__init__.py` | Remove |

---

## 5. Script System

### 5.1 Script Lifecycle

```
User/Bot creates Script
    → status = "draft"
    → ScriptVersion v1 created (author_type = "user" or "bot")
    → If bot-created: approved = False, needs user approval

User approves Script
    → ScriptVersion.approved = True
    → Script.status = "active"
    → Can now be scheduled or run

User edits Script
    → New ScriptVersion created (v2, v3, ...)
    → diff_from_previous computed
    → Script.source_code updated to new version
    → Script.current_version incremented

Bot edits Script
    → New ScriptVersion created (author_type = "bot", approved = False)
    → Script.source_code NOT updated until approved
    → User notified: "Bot suggested edit, please review"

User rolls back
    → New ScriptVersion created (copies code from target version)
    → commit_message = "Rollback to v{N}"
    → Script.source_code updated
```

### 5.2 Script Execution Flow

```
Schedule fires (or user clicks "Run Now")
    → SchedulerService/API creates Work with script_id + script_version
    → JobRunnerService picks up Work → creates Task → creates WorkJob
    → WorkJob execution checks function.execution_type:
        if "script":
            → ScriptSandbox.execute(source_code, context)
            → Capture stdout, stderr, return value
            → Record in ExecutionLog + TimelineEvent
        if "agent":
            → Existing CachibotAgent flow (unchanged)
```

### 5.3 Pydantic Models

```python
class ScriptStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"
    ARCHIVED = "archived"

class AuthorType(str, Enum):
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"

class ExecutionType(str, Enum):
    AGENT = "agent"
    SCRIPT = "script"
    HYBRID = "hybrid"

class Script(BaseModel):
    id: str
    bot_id: str
    name: str
    description: str | None = None
    source_code: str
    language: str = "python"
    status: ScriptStatus = ScriptStatus.DRAFT
    current_version: int = 1
    tags: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime
    created_by: str
    timeout_seconds: int = 300
    max_memory_mb: int = 256
    allowed_imports: list[str] = Field(default_factory=list)
    run_count: int = 0
    last_run_at: datetime | None = None
    success_rate: float = 0.0

class ScriptVersion(BaseModel):
    id: str
    script_id: str
    version_number: int
    source_code: str
    diff_from_previous: str | None = None
    author_type: AuthorType
    author_id: str | None = None
    commit_message: str
    approved: bool = False
    approved_by: str | None = None
    approved_at: datetime | None = None
    created_at: datetime
```

### 5.4 JobRunnerService Modifications

```python
# In JobRunnerService._execute_job():
async def _execute_job(self, job, task, work):
    # Determine execution type
    function = None
    if work.function_id:
        function = await self._function_repo.get(work.function_id)

    if function and function.execution_type == "script" and function.script_id:
        result_text = await self._run_script_for_task(job, task, work, function)
    else:
        result_text = await self._run_agent_for_task(job, task)

async def _run_script_for_task(self, job, task, work, function):
    """Execute a script in the sandbox."""
    script = await self._script_repo.get(function.script_id)
    if not script or script.status != "active":
        raise RuntimeError(f"Script {function.script_id} not found or not active")

    sandbox = ScriptSandbox(
        bot_id=task.bot_id,
        timeout_seconds=script.timeout_seconds,
        max_memory_mb=script.max_memory_mb,
        allowed_imports=script.allowed_imports,
    )

    context = {
        "work_id": work.id,
        "task_id": task.id,
        "job_id": job.id,
        "params": work.context,
        "bot_id": task.bot_id,
    }

    result = await sandbox.execute(script.source_code, context)
    return result.output
```

---

## 6. Execution Log System

### 6.1 Design Principles

1. **Separate table, not extending WorkJob**: ExecutionLog is its own first-class table because it tracks things that are NOT work jobs (scripts, legacy jobs, scheduled messages)
2. **ExecutionLogLine for streaming**: Instead of appending to a JSON array (like `WorkJob.logs`), log lines are separate rows — enables pagination, real-time streaming, and database-level ordering
3. **TimelineEvent as a separate table**: Materialized on write, not computed at query time — fast reads
4. **Tier-based retention in code**: Enforced by daily background service, not DB triggers — allows aggregation before deletion
5. **Credits/tokens per execution**: Enables cost analysis without external billing table joins
6. **`source_name` denormalized**: Stored directly on the log for display, avoiding JOINs on every list query

### 6.2 Integration with Work System

```python
# In JobRunnerService._execute_job():
async def _execute_job(self, job, task, work):
    # 1. Create execution log entry
    exec_log = ExecutionLog(
        id=str(uuid.uuid4()),
        execution_type="work",
        source_type="function" if work.function_id else "manual",
        source_id=work.function_id or work.id,
        source_name=work.title,
        bot_id=task.bot_id,
        trigger="cron" if work.schedule_id else "manual",
        work_id=work.id,
        work_job_id=job.id,
    )
    await exec_log_repo.save(exec_log)

    try:
        # 2. Run the agent (existing code)
        result = await self._run_agent_for_task(job, task)

        # 3. Complete execution log
        await exec_log_repo.complete(
            exec_log.id,
            status="success",
            output=result,
            credits=session.total_cost,
            tokens=session.total_tokens,
        )
    except Exception as exc:
        await exec_log_repo.complete(
            exec_log.id,
            status="error",
            error=str(exc),
        )
```

### 6.3 Log Retention Policy

| Tier | Per-Item Max Logs | Global Max Days | Log Lines Kept Per Execution |
|------|-------------------|-----------------|------------------------------|
| free | 25 | 7 | 50 |
| starter | 50 | 14 | 200 |
| pro | 100 | 30 | 1,000 |
| enterprise | 500 | 90 | unlimited |

**Retention service** runs daily as a background task:
1. Gets all users and their tiers
2. Finds expired logs beyond the tier's retention window
3. Groups expired logs by (source_type, source_id, date)
4. Creates `ExecutionDailySummary` records with aggregated counts, durations, credits, top errors
5. Deletes the individual log lines first, then the log records
6. Never deletes logs with `status = "running"`

### 6.4 Real-Time WebSocket

New WebSocket message types (add to existing `WSMessageType`):

```python
EXECUTION_START = "execution_start"       # New execution began
EXECUTION_LOG = "execution_log"           # Live log line
EXECUTION_PROGRESS = "execution_progress" # Progress update
EXECUTION_END = "execution_end"           # Execution completed/failed
```

Frontend subscribes to execution output:
```json
// Subscribe
{"type": "subscribe", "channel": "execution:{execution_log_id}"}

// Server pushes log lines
{
    "type": "execution_log",
    "payload": {
        "executionLogId": "...",
        "seq": 42,
        "level": "info",
        "content": "Processing batch 3/10...",
        "timestamp": "2026-02-17T05:30:00Z"
    }
}
```

### 6.5 Repository

```python
class ExecutionLogRepository:
    async def save(self, log: ExecutionLog) -> None: ...
    async def complete(self, log_id, status, output=None, error=None,
                       credits=0.0, tokens=0, prompt_tokens=0,
                       completion_tokens=0, llm_calls=0) -> None: ...
    async def append_line(self, log_id, level, content, data=None) -> None: ...
    async def get(self, log_id) -> ExecutionLog | None: ...
    async def get_by_bot(self, bot_id, filters, limit=50, offset=0) -> list: ...
    async def get_running(self, bot_id=None) -> list: ...
    async def get_global(self, filters, limit=50, offset=0) -> list: ...
    async def get_error_spotlight(self, days=7) -> list[dict]: ...
    async def get_cost_analysis(self, days=30, limit=20) -> list[dict]: ...
    async def get_stats(self, bot_id=None, period="24h") -> dict: ...
    async def cancel(self, log_id) -> bool: ...
    async def export_csv(self, filters) -> str: ...

class TimelineEventRepository:
    async def save(self, event: TimelineEvent) -> None: ...
    async def get_timeline(self, source_type, source_id,
                           event_types=None, limit=50, offset=0) -> list: ...
```

---

## 7. Security & Sandbox

### 7.1 Existing Infrastructure (reused as-is)

| Layer | Location | What It Does |
|-------|----------|-------------|
| `PythonSandbox` | `tukuy/sandbox/sandbox.py` | `RestrictedImporter`, `RestrictedOpen`, `ResourceContext`, safe builtins dict, `ALWAYS_BLOCKED_IMPORTS` (60+ modules), `SAFE_IMPORTS` (~35 modules), output truncation, pre-execution AST validation |
| `SecurityContext` | `tukuy/safety.py` | Path/host/command restrictions, `contextvars` for async-safe isolation, `check_read_path()`, `check_write_path()`, `check_host()`, `check_command()` |
| `SafetyPolicy` | `tukuy/safety.py` | Skill-level policy enforcement, `SafetyError` for violations |
| `PythonSandboxPlugin` | `plugins/python_sandbox.py` | Pre-execution risk analysis via `analyze_python()`, `ApprovalRequired` for HIGH/CRITICAL risk code |
| `CachibotAgent` hardening | `agent.py` | Sandbox scoped to workspace, `_harden_security_context()` blocks `.env` files and env-dumping commands |

### 7.2 Gaps for Unattended Execution

| Aspect | Interactive (Current) | Unattended (Needed) |
|--------|----------------------|---------------------|
| Human approval gate | `ApprovalRequired` → user approves/denies | No user watching — must auto-deny |
| Credit consumption | Not tracked per execution | Must check credits before/during |
| Consecutive failures | No circuit breaker | Must auto-pause after N failures |
| Data isolation | Per-workspace (per-bot) | Must isolate per-automation |
| Max concurrency | `_MAX_CONCURRENT_JOBS = 5` global | Must be per-user, per-tier |
| Bot-created scripts | Analyzed at execution time only | Must analyze at save time too |

### 7.3 Import Whitelist (Automation-Specific)

Stricter than interactive mode — removes `zipfile`/`tarfile` (archive extraction risk):

```python
AUTOMATION_ALLOWED_IMPORTS = [
    "json", "csv", "re", "string", "textwrap",
    "math", "statistics", "decimal", "fractions", "random",
    "collections", "itertools", "functools", "operator",
    "datetime", "time", "calendar",
    "dataclasses", "enum", "typing",
    "copy", "pprint", "bisect", "heapq",
    "base64", "hashlib", "hmac",
]
```

`io.StringIO` is provided as a pre-injected global (since the `io` module is in `ALWAYS_BLOCKED_IMPORTS`):
```python
import io
exec_globals["StringIO"] = io.StringIO
```

Network access is ONLY possible through Tukuy skills (`requires_network=True`) and Prompture driver calls. Raw HTTP is impossible from sandboxed code.

### 7.4 Resource Limits Per Execution

```python
@dataclass
class AutomationResourceLimits:
    max_cpu_seconds: float = 30.0
    max_memory_bytes: int = 256 * 1024 * 1024  # 256 MB
    max_output_bytes: int = 1024 * 1024         # 1 MB
    max_output_chars: int = 10_000              # For LLM-visible output
    max_agent_iterations: int = 10              # Tighter than interactive (20)
    max_wall_seconds: float = 300.0             # 5 minutes total
```

**Tier-specific limits:**

| Tier | CPU (s) | Memory (MB) | Wall Time (s) |
|------|---------|-------------|----------------|
| free | 30 | 128 | 120 |
| starter | 60 | 256 | 300 |
| pro | 120 | 512 | 600 |
| enterprise | 300 | 1024 | 1800 |

### 7.5 Credit Guard

```python
class CreditGuard:
    async def check_before_execution(self, user_id: str, estimated_cost: float) -> bool:
        """Returns True if user has sufficient credits. Raises InsufficientCredits otherwise."""
        user = await self._user_repo.get(user_id)
        if user.credit_balance < estimated_cost:
            return False
        return True

    async def deduct_after_execution(self, user_id: str, actual_cost: float) -> None:
        """Deduct actual cost. If balance hits zero, pause all user automations."""
        await self._user_repo.deduct_credits(user_id, actual_cost)
        updated = await self._user_repo.get(user_id)
        if updated.credit_balance <= 0:
            await self._pause_user_automations(user_id, reason="insufficient credits")
```

Integration: In `JobRunnerService._execute_job()`:
1. Before creating agent: `credit_guard.check_before_execution()`
2. After completion: `credit_guard.deduct_after_execution()` using Prompture's cost from `UsageSession`
3. Mid-execution check between agent iterations — graceful stop with "insufficient credits" log

### 7.6 Circuit Breaker (Auto-Pause on Consecutive Failures)

```python
@dataclass
class CircuitBreakerConfig:
    max_consecutive_failures: int = 5
    cooldown_seconds: int = 3600  # 1 hour

class AutomationCircuitBreaker:
    async def record_outcome(self, automation_id: str, success: bool) -> None:
        if success:
            await self._reset_counter(automation_id)
        else:
            count = await self._increment_failure(automation_id)
            if count >= self._config.max_consecutive_failures:
                await self._pause_automation(
                    automation_id,
                    reason=f"Auto-paused: {count} consecutive failures"
                )
                # Notify user via WebSocket + email
```

### 7.7 Per-Automation Data Isolation

```
workspace/
  automations/
    {automation_id}/
      runs/
        {run_id}/
          input/     # Read-only: input data copied here
          output/    # Write-allowed: results go here
          temp/      # Scratch space, cleaned after execution
```

One automation's code cannot read/write another automation's directory. `PathRestrictions` already enforce this.

### 7.8 Bot-Created Scripts: Save-Time Validation

```python
async def validate_script_before_save(code: str) -> ScriptValidationResult:
    # 1. Syntax check
    analysis = analyze_python(code)
    if not analysis.syntax_valid:
        return ScriptValidationResult(allowed=False, reason=f"Syntax error: {analysis.syntax_error}")

    # 2. Risk assessment
    if analysis.risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
        return ScriptValidationResult(allowed=False, reason=f"{analysis.risk_level.value}-risk: {analysis.risk.reasons}")

    # 3. Import check
    for imp in analysis.features.imports:
        if imp not in AUTOMATION_ALLOWED_IMPORTS_SET:
            return ScriptValidationResult(allowed=False, reason=f"Import '{imp}' not allowed")

    # 4. No dynamic execution
    if analysis.features.exec_eval_usage:
        return ScriptValidationResult(allowed=False, reason="exec/eval/compile not allowed")

    return ScriptValidationResult(allowed=True)
```

Uses Tukuy's existing `analyze_python()` — no new analysis code needed.

### 7.9 Unattended Execution: Auto-Deny Approval Requests

```python
async def _handle_approval_unattended(tool_name: str, action: str, details: dict) -> bool:
    """Auto-deny all approval requests in unattended mode."""
    logger.warning("Automation auto-denied: tool=%s action=%s", tool_name, action)
    await self._log_repo.append(
        automation_id=self.automation_id,
        level="warn",
        message=f"Auto-denied risky operation: {action}",
        data=details,
    )
    return False  # Always deny
```

HIGH/CRITICAL risk code is blocked at two levels:
1. At save time (static analysis rejects it)
2. At runtime (ApprovalRequired auto-denied, sandbox blocks imports anyway)

### 7.10 Tier Limits

| Tier | Max Automations | Min Interval | Max Concurrent |
|------|----------------|--------------|----------------|
| free | 3 | 1 hour | 1 |
| starter | 10 | 5 minutes | 2 |
| pro | 50 | 1 minute | 5 |
| enterprise | 200 | 10 seconds | 20 |

Enforcement points:
- `max_automations`: Checked when creating/enabling a new automation
- `min_interval_seconds`: Checked when setting schedule frequency
- `max_concurrent_runs`: Checked in `JobRunnerService._process_work()` before dispatching
- Resource limits: Applied via `PythonSandbox` and `ResourceContext`

### 7.11 Admin Controls

```python
class AdminExecutionControls:
    async def kill_execution(self, job_id: str) -> bool: ...
    async def pause_automation(self, automation_id: str) -> None: ...
    async def pause_all_user_automations(self, user_id: str) -> int: ...
    async def global_kill_switch(self) -> None:
        """Emergency: stop ALL running jobs and pause ALL automations."""
        runner = get_job_runner()
        for job_id in list(runner._running_jobs.keys()):
            await runner.cancel_job(job_id)
        await self._config_repo.set("automations.global_pause", True)
```

---

## 8. Frontend Design

### 8.1 Existing Stack

- **Framework**: React 19 + TypeScript + Vite
- **Styling**: Tailwind CSS 3 with dark mode (`class` strategy), zinc-based color palette, CSS variable accent colors
- **State**: Zustand with `persist` middleware (localStorage)
- **Routing**: react-router-dom v7, URL pattern `/:botId/:view/:itemId?`
- **Icons**: lucide-react
- **Data fetching**: @tanstack/react-query + fetch API client
- **Notifications**: sonner
- **Layout**: 3-column — BotRail (72px) | BotSidebar (272px collapsible) | Main content

### 8.2 Navigation Changes

Replace separate Work + Schedules nav items with unified "Automations":

```typescript
const navItems = [
  { id: 'chats', label: 'Chats', icon: MessageSquare },
  { id: 'rooms', label: 'Rooms', icon: DoorOpen },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },        // keep: manual kanban
  { id: 'automations', label: 'Automations', icon: Workflow }, // NEW: replaces work + schedules
  { id: 'voice', label: 'Voice', icon: Mic },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'settings', label: 'Settings', icon: Settings },
]
```

Sidebar sections for Automations view:
```
All Automations | Jobs | Works | Scripts | Errors | + Create New
```

New routes:
```
/:botId/automations                    → AutomationsView (list)
/:botId/automations/:automationId      → AutomationDetailView
/:botId/automations/new                → CreateAutomationView
/:botId/automations/:id/edit           → ScriptEditorView (for scripts)
/:botId/automations/:id/timeline       → TimelineView
/admin/logs                            → GlobalLogView (admin only)
```

### 8.3 Automations List Page

Unified view of all jobs, works, and scripts. Header + filter bar + master-detail layout.

**Each automation card shows:**
- Name + icon
- Type badge: `JOB` (blue), `WORK` (purple), `SCRIPT` (amber)
- Status badge: `Active` (green), `Paused` (yellow), `Error` (red, pulsing dot), `Draft` (zinc), `Running` (blue, spin animation)
- Schedule expression
- Last run: time ago + status + duration
- Next scheduled run
- Credits consumed (last 24h)

**Quick actions on hover:** Play/pause toggle, "Run Now" (lightning bolt), three-dot menu (Delete, Duplicate, View Timeline)

**"Create New" dropdown:** Create Job | Create Work | Create Script

**Detail panel tabs:** Overview | Timeline | Settings

### 8.4 Script Editor Page

Full-screen split layout:

```
+--------------------------------------------------------------+
| < Back to Automations   "price_checker.py" v3   [Run] [Save] |
+--------------------------------------------------------------+
|                                    |                          |
|   Monaco Editor                    |  Settings Sidebar        |
|   - Python syntax highlighting     |  - Name, Description     |
|   - Line numbers, dark theme       |  - Schedule type/expr    |
|   - Auto-indent                    |  - Config variables      |
|   - zinc-900 bg                    |  - [Ask Bot to Edit]     |
|                                    |                          |
+--------------------------------------------------------------+
|  Console Output                                [Clear] [^]    |
|  > Running price_checker.py...                                |
|  > Fetched 15 prices                                          |
|  > Completed in 1.2s (0.5 credits)                           |
+--------------------------------------------------------------+
```

- **Editor**: `@monaco-editor/react`, theme `vs-dark`, language `python`, no minimap
- **Sidebar**: 300px fixed-width, settings cards matching existing patterns
- **Console**: Bottom panel, collapsible (200px default), font-mono, WebSocket streaming
- **"Ask Bot to Edit"**: Slide-over chat panel from right, uses existing chat infrastructure
- **Auto-save**: Every save creates a new version. Save button shows version number.

### 8.5 Unified Timeline Tab

Reusable component (`TimelineTab.tsx`) for any automation's detail view:

```
Timeline                     [All] [Edits Only] [Runs Only] [Errors]

Feb 17, 2026

3:00pm  [run]  Ran — Success (1.2s, 0.5 credits)               [>]
                Output: "Fetched 15 prices, 2 alerts sent"

2:45pm  [edit] v3 edited by Bot: "Added error handling"    [diff] [rollback]

8:00am  [run]  Ran — Error (0.3s, 0.1 credits)                 [>]
                Error: "ConnectionTimeout: API unreachable"

Feb 16, 2026

8:00am  [run]  Ran — Success (1.1s, 0.5 credits)               [>]

Feb 15, 2026

11:30am [edit] v2 edited by Juan: "Changed schedule"       [diff] [rollback]
10:00am [edit] v1 created by Juan                          [diff]
```

- **Version events**: `GitCommit` icon in `text-purple-400`, bg `purple-500/5`
- **Execution events**: `Play` (green), `XCircle` (red), `Clock` (blue+spin)
- **Diff modal**: Full-screen overlay, side-by-side old vs new
- **Rollback**: Creates new version with code from target version

### 8.6 Global Log Page (Admin)

Admin-only route at `/admin/logs`:

**Stats bar** (4 horizontal stat cards):
- Executions today (Activity icon, blue)
- Errors today (AlertTriangle icon, red)
- Credits consumed (Zap icon, amber)
- Avg duration (Clock icon, green)

**Charts**: Inline SVG (no charting library), executions per hour (24h), error rate line, credits bars

**Execution stream** (table, reverse chronological, real-time via WebSocket):
- Columns: Time | Bot | Automation | Type | Status | Duration | Credits | Trigger | User
- Clickable rows expand to show full output/error (accordion)
- Running items pulse with blue animation
- Errors highlighted with `bg-red-500/5` row background

**Filters**: Type, Status, Bot, Trigger, Date range (dropdowns)

**Admin actions**: Kill button on running executions (with confirmation), Export CSV, Cancel All (emergency)

### 8.7 New Files

```
frontend/src/components/views/AutomationsView.tsx       — Main unified list
frontend/src/components/views/ScriptEditorView.tsx       — Monaco-based editor
frontend/src/components/views/GlobalLogView.tsx           — Admin log dashboard
frontend/src/components/automations/TimelineTab.tsx       — Reusable timeline
frontend/src/components/automations/VersionDiffModal.tsx  — Diff viewer modal
frontend/src/components/automations/AutomationCard.tsx    — List item card
frontend/src/components/automations/ConsoleOutput.tsx     — Script console panel
frontend/src/components/automations/BotEditPanel.tsx      — "Ask bot to edit" slide-over
frontend/src/stores/automations.ts                        — Zustand store
frontend/src/api/automations.ts                           — API client for automations
frontend/src/api/execution-log.ts                         — API client for global log
```

### 8.8 Modified Files

```
frontend/src/App.tsx                          — Add new routes
frontend/src/types/index.ts                   — Add Automation, Script, ExecutionLog types
frontend/src/components/views/index.ts        — Export new views
frontend/src/components/layout/BotSidebar.tsx — Replace work+schedules with automations
frontend/src/components/layout/BotRail.tsx    — Add admin logs icon
frontend/src/components/layout/MainLayout.tsx — Add automations view rendering
frontend/src/stores/ui.ts                     — Add AutomationSection type
frontend/src/components/views/JobsView.tsx    — Add Timeline tab
frontend/src/components/views/WorkView.tsx    — Add Timeline tab + credits
frontend/package.json                         — Add @monaco-editor/react
```

### 8.9 New TypeScript Types

```typescript
export type AutomationType = 'job' | 'work' | 'script'
export type AutomationStatus = 'active' | 'paused' | 'error' | 'draft'
export type AutomationSection = 'all' | 'jobs' | 'works' | 'scripts' | 'errors' | 'create'

export interface Automation {
  id: string
  botId: string
  name: string
  description?: string
  type: AutomationType
  status: AutomationStatus
  scheduleId?: string
  schedule?: Schedule
  createdAt: string
  updatedAt: string
  lastRunAt?: string
  nextRunAt?: string
  createdBy: string
  lastEditedBy: string
  creditsConsumed24h: number
  lastExecution?: ExecutionSummary
  currentVersion: number
  jobId?: string
  workId?: string
  scriptId?: string
}

export interface Script {
  id: string
  botId: string
  name: string
  description?: string
  code: string
  language: 'python'
  currentVersion: number
  versions: ScriptVersion[]
  configVars: Record<string, string>
  scheduleId?: string
  triggerType: 'cron' | 'interval' | 'once' | 'event' | 'manual'
}

export interface ScriptVersion {
  version: number
  code: string
  author: string
  authorType: 'user' | 'bot' | 'system'
  message: string
  createdAt: string
  diff?: string
}

export interface ExecutionLog {
  id: string
  automationId: string
  automationType: AutomationType
  botId: string
  userId?: string
  trigger: 'cron' | 'manual' | 'event' | 'api'
  startedAt: string
  finishedAt?: string
  durationMs?: number
  status: 'running' | 'success' | 'error' | 'timeout' | 'cancelled'
  output?: string
  error?: string
  creditsConsumed: number
  tokensUsed: number
  metadata?: Record<string, unknown>
  scriptVersion?: number
}

export interface ExecutionSummary {
  id: string
  status: 'running' | 'success' | 'error' | 'timeout' | 'cancelled'
  startedAt: string
  finishedAt?: string
  durationMs?: number
  creditsConsumed: number
  outputPreview?: string
  errorPreview?: string
}

export type TimelineEventType = 'version' | 'execution'

export interface TimelineEvent {
  id: string
  type: TimelineEventType
  timestamp: string
  version?: ScriptVersion
  execution?: ExecutionLog
}
```

---

## 9. API Endpoints

### 9.1 Script CRUD

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bots/{bot_id}/scripts` | List scripts |
| POST | `/api/bots/{bot_id}/scripts` | Create script |
| GET | `/api/bots/{bot_id}/scripts/{script_id}` | Get script |
| PATCH | `/api/bots/{bot_id}/scripts/{script_id}` | Update script |
| DELETE | `/api/bots/{bot_id}/scripts/{script_id}` | Delete script |
| POST | `/api/bots/{bot_id}/scripts/{script_id}/run` | Run script (creates Work) |
| POST | `/api/bots/{bot_id}/scripts/{script_id}/activate` | Set status to active |
| POST | `/api/bots/{bot_id}/scripts/{script_id}/disable` | Set status to disabled |

### 9.2 Script Versions

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bots/{bot_id}/scripts/{script_id}/versions` | List versions |
| GET | `/api/bots/{bot_id}/scripts/{script_id}/versions/{v}` | Get specific version |
| POST | `/api/bots/{bot_id}/scripts/{script_id}/versions/{v}/approve` | Approve version |
| POST | `/api/bots/{bot_id}/scripts/{script_id}/versions/{v}/rollback` | Rollback to version |

### 9.3 Per-Bot Execution Logs

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bots/{bot_id}/executions` | List executions (paginated, filterable) |
| GET | `/api/bots/{bot_id}/executions/{exec_id}` | Get execution detail |
| GET | `/api/bots/{bot_id}/executions/{exec_id}/output` | Get output (streamed if running) |
| GET | `/api/bots/{bot_id}/executions/{exec_id}/lines` | Get log lines (paginated) |
| POST | `/api/bots/{bot_id}/executions/{exec_id}/cancel` | Cancel running execution |
| GET | `/api/bots/{bot_id}/executions/running` | Get currently running |
| GET | `/api/bots/{bot_id}/executions/stats` | Stats (24h, 7d, 30d) |

**Query parameters for GET `/executions`:**
- `type` — filter by execution_type
- `status` — filter by status
- `trigger` — filter by trigger type
- `source_id` — filter by source
- `from_date` / `to_date` — date range
- `limit` (default 50, max 200) / `offset`
- `sort` — `started_at_desc` (default), `started_at_asc`, `duration_desc`, `credits_desc`

### 9.4 Timeline

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/bots/{bot_id}/timeline/{source_type}/{source_id}` | Combined timeline (edits + executions) |

### 9.5 Admin Global Log

All require `require_admin` dependency:

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/admin/executions` | Global log across ALL bots/users |
| GET | `/api/admin/executions/errors` | Error spotlight (grouped by type) |
| GET | `/api/admin/executions/costs` | Cost analysis (ranked by credits) |
| GET | `/api/admin/executions/stats` | Global stats |
| POST | `/api/admin/executions/{exec_id}/cancel` | Admin kill switch |
| GET | `/api/admin/executions/export` | CSV export with filters |
| GET | `/api/admin/executions/running` | All running across all bots |
| POST | `/api/admin/executions/cancel-all` | Emergency: cancel ALL |

---

## 10. Migration Path

### Phase 1: Database Schema

Add new tables and columns via Alembic migration:
- Create `scripts`, `script_versions`, `execution_logs`, `execution_log_lines`, `timeline_events`, `execution_daily_summaries` tables
- Add `script_id` + `execution_type` columns to `functions` table
- Add `script_id` + `script_version` columns to `work` table
- Mark `models/job.py` and `storage/models/job.py` as deprecated with comments

### Phase 2: Execution Log Wiring

- Wire `ExecutionLog` creation into `JobRunnerService._execute_job()`
- Wire Prompture `UsageTracker` into `CachibotAgent` via `as_callbacks()` for automatic token/cost tracking
- Fix job runner to use `_resolve_bot_env()` for per-bot API keys
- Extend `SchedulerService` to support "run agent action" (not just deliver messages)
- Add WebSocket message types for execution streaming

### Phase 3: Security Layer

- Build `ScriptSandbox` service (wrapping Tukuy's `PythonSandbox`)
- Build `CreditGuard` (check/deduct in execution loop)
- Build `AutomationCircuitBreaker` (auto-pause after N failures)
- Add per-automation data isolation (subdirectory scoping)
- Add save-time AST validation for bot-created scripts
- Add auto-deny callback for unattended `ApprovalRequired`
- Implement tier limits config and enforcement

### Phase 4: Script System + API

- Build `ScriptRepository` and `ScriptVersionRepository`
- Add script CRUD and version management API endpoints
- Add `_run_script_for_task()` execution path to `JobRunnerService`
- Add execution log API endpoints (per-bot and admin)
- Add timeline API endpoints
- Build `LogRetentionService` (daily background task)

### Phase 5: Frontend

- Build `AutomationsView`, `ScriptEditorView`, `GlobalLogView`
- Build `TimelineTab`, `VersionDiffModal`, `AutomationCard`, `ConsoleOutput`, `BotEditPanel`
- Build `automations` Zustand store and API clients
- Update `BotSidebar` (replace work+schedules with automations)
- Update `BotRail` (add admin logs icon)
- Update `App.tsx` routes
- Add `@monaco-editor/react` dependency
- Add Timeline tab + credits tracking to existing `JobsView` and `WorkView`

### Phase 6: Legacy Cleanup

- Migrate any existing legacy `jobs` data into `work` table:
  - Each legacy Job becomes a Work with a single Task
  - `job.message_id` → `work.context = {"legacy_message_id": job.message_id}`
- Remove `models/job.py`, `storage/models/job.py`, `LegacyJob` alias
- Remove legacy `JobRepository` from `storage/repository.py`
- Merge overlapping plugins (`WorkManagementPlugin` + `JobToolsPlugin`)
- Drop `jobs` table via Alembic migration

"""
Work Management API Routes

Endpoints for managing work, tasks, jobs, todos, functions, and schedules.
"""

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cachibot.api.auth import get_current_user, require_bot_access
from cachibot.models.auth import User
from cachibot.models.work import (
    BotFunction,
    FailureAction,
    FunctionParameter,
    FunctionStep,
    Job,
    JobStatus,
    Priority,
    Schedule,
    ScheduleType,
    Task,
    TaskStatus,
    Todo,
    TodoStatus,
    Work,
    WorkStatus,
)
from cachibot.storage.work_repository import (
    FunctionRepository,
    ScheduleRepository,
    TaskRepository,
    TodoRepository,
    WorkJobRepository,
    WorkRepository,
)

router = APIRouter(prefix="/api/bots/{bot_id}", tags=["work"])

# Repository instances
function_repo = FunctionRepository()
schedule_repo = ScheduleRepository()
work_repo = WorkRepository()
task_repo = TaskRepository()
job_repo = WorkJobRepository()
todo_repo = TodoRepository()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class FunctionStepResponse(BaseModel):
    """Response model for a function step."""

    order: int
    name: str
    description: str | None
    action: str
    dependsOn: list[int]
    retryCount: int
    timeoutSeconds: int | None
    onFailure: str


class FunctionParameterResponse(BaseModel):
    """Response model for a function parameter."""

    name: str
    type: str
    default: Any | None
    required: bool
    description: str | None


class FunctionResponse(BaseModel):
    """Response model for a function."""

    id: str
    botId: str
    name: str
    description: str | None
    version: str
    steps: list[FunctionStepResponse]
    parameters: list[FunctionParameterResponse]
    tags: list[str]
    createdAt: str
    updatedAt: str
    runCount: int
    lastRunAt: str | None
    successRate: float

    @classmethod
    def from_function(cls, fn: BotFunction) -> "FunctionResponse":
        return cls(
            id=fn.id,
            botId=fn.bot_id,
            name=fn.name,
            description=fn.description,
            version=fn.version,
            steps=[
                FunctionStepResponse(
                    order=s.order,
                    name=s.name,
                    description=s.description,
                    action=s.action,
                    dependsOn=s.depends_on,
                    retryCount=s.retry_count,
                    timeoutSeconds=s.timeout_seconds,
                    onFailure=s.on_failure.value,
                )
                for s in fn.steps
            ],
            parameters=[
                FunctionParameterResponse(
                    name=p.name,
                    type=p.type,
                    default=p.default,
                    required=p.required,
                    description=p.description,
                )
                for p in fn.parameters
            ],
            tags=fn.tags,
            createdAt=fn.created_at.isoformat(),
            updatedAt=fn.updated_at.isoformat(),
            runCount=fn.run_count,
            lastRunAt=fn.last_run_at.isoformat() if fn.last_run_at else None,
            successRate=fn.success_rate,
        )


class ScheduleResponse(BaseModel):
    """Response model for a schedule."""

    id: str
    botId: str
    name: str
    description: str | None
    functionId: str | None
    functionParams: dict[str, Any]
    scheduleType: str
    cronExpression: str | None
    intervalSeconds: int | None
    runAt: str | None
    eventTrigger: str | None
    timezone: str
    enabled: bool
    maxConcurrent: int
    catchUp: bool
    createdAt: str
    updatedAt: str
    nextRunAt: str | None
    lastRunAt: str | None
    runCount: int

    @classmethod
    def from_schedule(cls, s: Schedule) -> "ScheduleResponse":
        return cls(
            id=s.id,
            botId=s.bot_id,
            name=s.name,
            description=s.description,
            functionId=s.function_id,
            functionParams=s.function_params,
            scheduleType=s.schedule_type.value,
            cronExpression=s.cron_expression,
            intervalSeconds=s.interval_seconds,
            runAt=s.run_at.isoformat() if s.run_at else None,
            eventTrigger=s.event_trigger,
            timezone=s.timezone,
            enabled=s.enabled,
            maxConcurrent=s.max_concurrent,
            catchUp=s.catch_up,
            createdAt=s.created_at.isoformat(),
            updatedAt=s.updated_at.isoformat(),
            nextRunAt=s.next_run_at.isoformat() if s.next_run_at else None,
            lastRunAt=s.last_run_at.isoformat() if s.last_run_at else None,
            runCount=s.run_count,
        )


class WorkResponse(BaseModel):
    """Response model for work."""

    id: str
    botId: str
    chatId: str | None
    title: str
    description: str | None
    goal: str | None
    functionId: str | None
    scheduleId: str | None
    parentWorkId: str | None
    status: str
    priority: str
    progress: float
    createdAt: str
    startedAt: str | None
    completedAt: str | None
    dueAt: str | None
    result: Any | None
    error: str | None
    context: dict[str, Any]
    tags: list[str]
    taskCount: int | None = None
    completedTaskCount: int | None = None

    @classmethod
    def from_work(
        cls,
        w: Work,
        task_count: int | None = None,
        completed_count: int | None = None,
    ) -> "WorkResponse":
        return cls(
            id=w.id,
            botId=w.bot_id,
            chatId=w.chat_id,
            title=w.title,
            description=w.description,
            goal=w.goal,
            functionId=w.function_id,
            scheduleId=w.schedule_id,
            parentWorkId=w.parent_work_id,
            status=w.status.value,
            priority=w.priority.value,
            progress=w.progress,
            createdAt=w.created_at.isoformat(),
            startedAt=w.started_at.isoformat() if w.started_at else None,
            completedAt=w.completed_at.isoformat() if w.completed_at else None,
            dueAt=w.due_at.isoformat() if w.due_at else None,
            result=w.result,
            error=w.error,
            context=w.context,
            tags=w.tags,
            taskCount=task_count,
            completedTaskCount=completed_count,
        )


class TaskResponse(BaseModel):
    """Response model for a task."""

    id: str
    botId: str
    workId: str
    chatId: str | None
    title: str
    description: str | None
    action: str | None
    order: int
    dependsOn: list[str]
    status: str
    priority: str
    retryCount: int
    maxRetries: int
    timeoutSeconds: int | None
    createdAt: str
    startedAt: str | None
    completedAt: str | None
    result: Any | None
    error: str | None

    @classmethod
    def from_task(cls, t: Task) -> "TaskResponse":
        return cls(
            id=t.id,
            botId=t.bot_id,
            workId=t.work_id,
            chatId=t.chat_id,
            title=t.title,
            description=t.description,
            action=t.action,
            order=t.order,
            dependsOn=t.depends_on,
            status=t.status.value,
            priority=t.priority.value,
            retryCount=t.retry_count,
            maxRetries=t.max_retries,
            timeoutSeconds=t.timeout_seconds,
            createdAt=t.created_at.isoformat(),
            startedAt=t.started_at.isoformat() if t.started_at else None,
            completedAt=t.completed_at.isoformat() if t.completed_at else None,
            result=t.result,
            error=t.error,
        )


class JobLogResponse(BaseModel):
    """Response model for a job log entry."""

    timestamp: str
    level: str
    message: str
    data: Any | None


class JobResponse(BaseModel):
    """Response model for a job."""

    id: str
    botId: str
    taskId: str
    workId: str
    chatId: str | None
    status: str
    attempt: int
    progress: float
    createdAt: str
    startedAt: str | None
    completedAt: str | None
    result: Any | None
    error: str | None
    logs: list[JobLogResponse]

    @classmethod
    def from_job(cls, j: Job) -> "JobResponse":
        return cls(
            id=j.id,
            botId=j.bot_id,
            taskId=j.task_id,
            workId=j.work_id,
            chatId=j.chat_id,
            status=j.status.value,
            attempt=j.attempt,
            progress=j.progress,
            createdAt=j.created_at.isoformat(),
            startedAt=j.started_at.isoformat() if j.started_at else None,
            completedAt=j.completed_at.isoformat() if j.completed_at else None,
            result=j.result,
            error=j.error,
            logs=[
                JobLogResponse(
                    timestamp=log.get("timestamp", ""),
                    level=log.get("level", "info"),
                    message=log.get("message", ""),
                    data=log.get("data"),
                )
                for log in j.logs
            ],
        )


class TodoResponse(BaseModel):
    """Response model for a todo."""

    id: str
    botId: str
    chatId: str | None
    title: str
    notes: str | None
    status: str
    priority: str
    createdAt: str
    completedAt: str | None
    remindAt: str | None
    convertedToWorkId: str | None
    convertedToTaskId: str | None
    tags: list[str]

    @classmethod
    def from_todo(cls, t: Todo) -> "TodoResponse":
        return cls(
            id=t.id,
            botId=t.bot_id,
            chatId=t.chat_id,
            title=t.title,
            notes=t.notes,
            status=t.status.value,
            priority=t.priority.value,
            createdAt=t.created_at.isoformat(),
            completedAt=t.completed_at.isoformat() if t.completed_at else None,
            remindAt=t.remind_at.isoformat() if t.remind_at else None,
            convertedToWorkId=t.converted_to_work_id,
            convertedToTaskId=t.converted_to_task_id,
            tags=t.tags,
        )


# =============================================================================
# REQUEST MODELS
# =============================================================================


class CreateFunctionStepRequest(BaseModel):
    """Request model for creating a function step."""

    name: str
    description: str | None = None
    action: str
    dependsOn: list[int] = Field(default_factory=list)
    retryCount: int = 0
    timeoutSeconds: int | None = None
    onFailure: str = "stop"


class CreateFunctionParameterRequest(BaseModel):
    """Request model for creating a function parameter."""

    name: str
    type: str = "string"
    default: Any | None = None
    required: bool = True
    description: str | None = None


class CreateFunctionRequest(BaseModel):
    """Request model for creating a function."""

    name: str
    description: str | None = None
    steps: list[CreateFunctionStepRequest] = Field(default_factory=list)
    parameters: list[CreateFunctionParameterRequest] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class UpdateFunctionRequest(BaseModel):
    """Request model for updating a function."""

    name: str | None = None
    description: str | None = None
    steps: list[CreateFunctionStepRequest] | None = None
    parameters: list[CreateFunctionParameterRequest] | None = None
    tags: list[str] | None = None


class CreateScheduleRequest(BaseModel):
    """Request model for creating a schedule."""

    name: str
    description: str | None = None
    functionId: str | None = None
    functionParams: dict[str, Any] = Field(default_factory=dict)
    scheduleType: str = "cron"
    cronExpression: str | None = None
    intervalSeconds: int | None = None
    runAt: str | None = None
    eventTrigger: str | None = None
    timezone: str = "UTC"
    maxConcurrent: int = 1
    catchUp: bool = False


class UpdateScheduleRequest(BaseModel):
    """Request model for updating a schedule."""

    name: str | None = None
    description: str | None = None
    functionId: str | None = None
    functionParams: dict[str, Any] | None = None
    cronExpression: str | None = None
    intervalSeconds: int | None = None
    runAt: str | None = None
    eventTrigger: str | None = None
    timezone: str | None = None
    enabled: bool | None = None
    maxConcurrent: int | None = None
    catchUp: bool | None = None


class CreateWorkRequest(BaseModel):
    """Request model for creating work."""

    title: str
    description: str | None = None
    goal: str | None = None
    chatId: str | None = None
    functionId: str | None = None
    scheduleId: str | None = None
    parentWorkId: str | None = None
    priority: str = "normal"
    dueAt: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    # Inline tasks to create with the work
    tasks: list["CreateTaskRequest"] | None = None


class UpdateWorkRequest(BaseModel):
    """Request model for updating work."""

    title: str | None = None
    description: str | None = None
    goal: str | None = None
    status: str | None = None
    priority: str | None = None
    progress: float | None = None
    dueAt: str | None = None
    result: Any | None = None
    error: str | None = None
    context: dict[str, Any] | None = None
    tags: list[str] | None = None


class CreateTaskRequest(BaseModel):
    """Request model for creating a task."""

    title: str
    description: str | None = None
    action: str | None = None
    order: int | None = None
    dependsOn: list[str] = Field(default_factory=list)
    priority: str = "normal"
    maxRetries: int = 3
    timeoutSeconds: int | None = None


class UpdateTaskRequest(BaseModel):
    """Request model for updating a task."""

    title: str | None = None
    description: str | None = None
    action: str | None = None
    order: int | None = None
    dependsOn: list[str] | None = None
    status: str | None = None
    priority: str | None = None
    maxRetries: int | None = None
    timeoutSeconds: int | None = None
    result: Any | None = None
    error: str | None = None


class CreateTodoRequest(BaseModel):
    """Request model for creating a todo."""

    title: str
    notes: str | None = None
    chatId: str | None = None
    priority: str = "normal"
    remindAt: str | None = None
    tags: list[str] = Field(default_factory=list)


class UpdateTodoRequest(BaseModel):
    """Request model for updating a todo."""

    title: str | None = None
    notes: str | None = None
    status: str | None = None
    priority: str | None = None
    remindAt: str | None = None
    tags: list[str] | None = None


class ConvertTodoRequest(BaseModel):
    """Request model for converting a todo to work."""

    toWork: bool = True
    workTitle: str | None = None
    workDescription: str | None = None
    priority: str | None = None


class AppendJobLogRequest(BaseModel):
    """Request model for appending a job log."""

    level: str = "info"
    message: str
    data: Any | None = None


# =============================================================================
# FUNCTION ROUTES
# =============================================================================


@router.get("/functions")
async def list_functions(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[FunctionResponse]:
    """Get all functions for a bot."""
    functions = await function_repo.get_by_bot(bot_id)
    return [FunctionResponse.from_function(fn) for fn in functions]


@router.post("/functions", status_code=201)
async def create_function(
    bot_id: str,
    request: CreateFunctionRequest,
    user: User = Depends(require_bot_access),
) -> FunctionResponse:
    """Create a new function."""
    now = datetime.utcnow()
    fn = BotFunction(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        name=request.name,
        description=request.description,
        version="1.0.0",
        steps=[
            FunctionStep(
                order=i + 1,
                name=s.name,
                description=s.description,
                action=s.action,
                depends_on=s.dependsOn,
                retry_count=s.retryCount,
                timeout_seconds=s.timeoutSeconds,
                on_failure=FailureAction(s.onFailure),
            )
            for i, s in enumerate(request.steps)
        ],
        parameters=[
            FunctionParameter(
                name=p.name,
                type=p.type,
                default=p.default,
                required=p.required,
                description=p.description,
            )
            for p in request.parameters
        ],
        tags=request.tags,
        created_at=now,
        updated_at=now,
    )
    await function_repo.save(fn)
    return FunctionResponse.from_function(fn)


@router.get("/functions/{function_id}")
async def get_function(
    bot_id: str,
    function_id: str,
    user: User = Depends(require_bot_access),
) -> FunctionResponse:
    """Get a function by ID."""
    fn = await function_repo.get(function_id)
    if fn is None or fn.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Function not found")
    return FunctionResponse.from_function(fn)


@router.patch("/functions/{function_id}")
async def update_function(
    bot_id: str,
    function_id: str,
    request: UpdateFunctionRequest,
    user: User = Depends(require_bot_access),
) -> FunctionResponse:
    """Update a function."""
    fn = await function_repo.get(function_id)
    if fn is None or fn.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Function not found")

    if request.name is not None:
        fn.name = request.name
    if request.description is not None:
        fn.description = request.description
    if request.tags is not None:
        fn.tags = request.tags
    if request.steps is not None:
        fn.steps = [
            FunctionStep(
                order=i + 1,
                name=s.name,
                description=s.description,
                action=s.action,
                depends_on=s.dependsOn,
                retry_count=s.retryCount,
                timeout_seconds=s.timeoutSeconds,
                on_failure=FailureAction(s.onFailure),
            )
            for i, s in enumerate(request.steps)
        ]
    if request.parameters is not None:
        fn.parameters = [
            FunctionParameter(
                name=p.name,
                type=p.type,
                default=p.default,
                required=p.required,
                description=p.description,
            )
            for p in request.parameters
        ]

    fn.updated_at = datetime.utcnow()
    await function_repo.update(fn)
    return FunctionResponse.from_function(fn)


@router.delete("/functions/{function_id}", status_code=204)
async def delete_function(
    bot_id: str,
    function_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a function."""
    fn = await function_repo.get(function_id)
    if fn is None or fn.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Function not found")
    await function_repo.delete(function_id)


@router.post("/functions/{function_id}/run", status_code=201)
async def run_function(
    bot_id: str,
    function_id: str,
    params: dict[str, Any] | None = None,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Instantiate a function as work."""
    fn = await function_repo.get(function_id)
    if fn is None or fn.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Function not found")

    now = datetime.utcnow()
    work_id = str(uuid.uuid4())

    # Create work from function
    work = Work(
        id=work_id,
        bot_id=bot_id,
        title=f"Run: {fn.name}",
        description=fn.description,
        function_id=function_id,
        status=WorkStatus.PENDING,
        priority=Priority.NORMAL,
        context=params or {},
        created_at=now,
    )
    await work_repo.save(work)

    # Create tasks from function steps
    tasks = []
    step_to_task_id: dict[int, str] = {}

    for step in fn.steps:
        task_id = str(uuid.uuid4())
        step_to_task_id[step.order] = task_id

        # Convert step dependencies to task dependencies
        depends_on = [step_to_task_id[dep] for dep in step.depends_on if dep in step_to_task_id]

        task = Task(
            id=task_id,
            bot_id=bot_id,
            work_id=work_id,
            title=step.name,
            description=step.description,
            action=step.action,
            order=step.order,
            depends_on=depends_on,
            status=TaskStatus.PENDING,
            priority=Priority.NORMAL,
            max_retries=step.retry_count,
            timeout_seconds=step.timeout_seconds,
            created_at=now,
        )
        tasks.append(task)

    if tasks:
        await task_repo.save_batch(tasks)

    return WorkResponse.from_work(work, task_count=len(tasks), completed_count=0)


# =============================================================================
# SCHEDULE ROUTES
# =============================================================================


@router.get("/schedules")
async def list_schedules(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[ScheduleResponse]:
    """Get all schedules for a bot."""
    schedules = await schedule_repo.get_by_bot(bot_id)
    return [ScheduleResponse.from_schedule(s) for s in schedules]


@router.post("/schedules", status_code=201)
async def create_schedule(
    bot_id: str,
    request: CreateScheduleRequest,
    user: User = Depends(require_bot_access),
) -> ScheduleResponse:
    """Create a new schedule."""
    now = datetime.utcnow()
    schedule = Schedule(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        name=request.name,
        description=request.description,
        function_id=request.functionId,
        function_params=request.functionParams,
        schedule_type=ScheduleType(request.scheduleType),
        cron_expression=request.cronExpression,
        interval_seconds=request.intervalSeconds,
        run_at=datetime.fromisoformat(request.runAt) if request.runAt else None,
        event_trigger=request.eventTrigger,
        timezone=request.timezone,
        enabled=True,
        max_concurrent=request.maxConcurrent,
        catch_up=request.catchUp,
        created_at=now,
        updated_at=now,
    )
    await schedule_repo.save(schedule)
    return ScheduleResponse.from_schedule(schedule)


@router.get("/schedules/{schedule_id}")
async def get_schedule(
    bot_id: str,
    schedule_id: str,
    user: User = Depends(require_bot_access),
) -> ScheduleResponse:
    """Get a schedule by ID."""
    schedule = await schedule_repo.get(schedule_id)
    if schedule is None or schedule.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return ScheduleResponse.from_schedule(schedule)


@router.patch("/schedules/{schedule_id}")
async def update_schedule(
    bot_id: str,
    schedule_id: str,
    request: UpdateScheduleRequest,
    user: User = Depends(require_bot_access),
) -> ScheduleResponse:
    """Update a schedule."""
    schedule = await schedule_repo.get(schedule_id)
    if schedule is None or schedule.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    if request.name is not None:
        schedule.name = request.name
    if request.description is not None:
        schedule.description = request.description
    if request.functionId is not None:
        schedule.function_id = request.functionId
    if request.functionParams is not None:
        schedule.function_params = request.functionParams
    if request.cronExpression is not None:
        schedule.cron_expression = request.cronExpression
    if request.intervalSeconds is not None:
        schedule.interval_seconds = request.intervalSeconds
    if request.runAt is not None:
        schedule.run_at = datetime.fromisoformat(request.runAt)
    if request.eventTrigger is not None:
        schedule.event_trigger = request.eventTrigger
    if request.timezone is not None:
        schedule.timezone = request.timezone
    if request.enabled is not None:
        schedule.enabled = request.enabled
    if request.maxConcurrent is not None:
        schedule.max_concurrent = request.maxConcurrent
    if request.catchUp is not None:
        schedule.catch_up = request.catchUp

    schedule.updated_at = datetime.utcnow()
    await schedule_repo.update(schedule)
    return ScheduleResponse.from_schedule(schedule)


@router.post("/schedules/{schedule_id}/toggle")
async def toggle_schedule(
    bot_id: str,
    schedule_id: str,
    user: User = Depends(require_bot_access),
) -> ScheduleResponse:
    """Toggle schedule enabled state."""
    schedule = await schedule_repo.get(schedule_id)
    if schedule is None or schedule.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Schedule not found")

    await schedule_repo.toggle_enabled(schedule_id, not schedule.enabled)
    schedule = await schedule_repo.get(schedule_id)
    return ScheduleResponse.from_schedule(schedule)


@router.delete("/schedules/{schedule_id}", status_code=204)
async def delete_schedule(
    bot_id: str,
    schedule_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a schedule."""
    schedule = await schedule_repo.get(schedule_id)
    if schedule is None or schedule.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Schedule not found")
    await schedule_repo.delete(schedule_id)


# =============================================================================
# WORK ROUTES
# =============================================================================


@router.get("/work")
async def list_work(
    bot_id: str,
    status: str | None = None,
    limit: int = 50,
    user: User = Depends(require_bot_access),
) -> list[WorkResponse]:
    """Get all work for a bot."""
    if status:
        work_items = await work_repo.get_by_bot(bot_id, WorkStatus(status), limit)
    else:
        work_items = await work_repo.get_by_bot(bot_id, limit=limit)

    responses = []
    for w in work_items:
        tasks = await task_repo.get_by_work(w.id)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        responses.append(WorkResponse.from_work(w, len(tasks), completed))
    return responses


@router.get("/work/active")
async def get_active_work(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[WorkResponse]:
    """Get active (pending/in_progress) work for a bot."""
    work_items = await work_repo.get_active(bot_id)
    responses = []
    for w in work_items:
        tasks = await task_repo.get_by_work(w.id)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        responses.append(WorkResponse.from_work(w, len(tasks), completed))
    return responses


@router.post("/work", status_code=201)
async def create_work(
    bot_id: str,
    request: CreateWorkRequest,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Create new work."""
    now = datetime.utcnow()
    work_id = str(uuid.uuid4())

    work = Work(
        id=work_id,
        bot_id=bot_id,
        chat_id=request.chatId,
        title=request.title,
        description=request.description,
        goal=request.goal,
        function_id=request.functionId,
        schedule_id=request.scheduleId,
        parent_work_id=request.parentWorkId,
        status=WorkStatus.PENDING,
        priority=Priority(request.priority),
        due_at=datetime.fromisoformat(request.dueAt) if request.dueAt else None,
        context=request.context,
        tags=request.tags,
        created_at=now,
    )
    await work_repo.save(work)

    # Create inline tasks if provided
    task_count = 0
    if request.tasks:
        tasks = []
        for i, t in enumerate(request.tasks):
            task = Task(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                work_id=work_id,
                title=t.title,
                description=t.description,
                action=t.action,
                order=t.order if t.order is not None else i + 1,
                depends_on=t.dependsOn,
                status=TaskStatus.PENDING,
                priority=Priority(t.priority),
                max_retries=t.maxRetries,
                timeout_seconds=t.timeoutSeconds,
                created_at=now,
            )
            tasks.append(task)
        await task_repo.save_batch(tasks)
        task_count = len(tasks)

    return WorkResponse.from_work(work, task_count, 0)


@router.get("/work/{work_id}")
async def get_work(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Get work by ID."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    tasks = await task_repo.get_by_work(work_id)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    return WorkResponse.from_work(work, len(tasks), completed)


@router.patch("/work/{work_id}")
async def update_work(
    bot_id: str,
    work_id: str,
    request: UpdateWorkRequest,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Update work."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    if request.title is not None:
        work.title = request.title
    if request.description is not None:
        work.description = request.description
    if request.goal is not None:
        work.goal = request.goal
    if request.status is not None:
        work.status = WorkStatus(request.status)
    if request.priority is not None:
        work.priority = Priority(request.priority)
    if request.progress is not None:
        work.progress = request.progress
    if request.dueAt is not None:
        work.due_at = datetime.fromisoformat(request.dueAt)
    if request.result is not None:
        work.result = request.result
    if request.error is not None:
        work.error = request.error
    if request.context is not None:
        work.context = request.context
    if request.tags is not None:
        work.tags = request.tags

    await work_repo.update(work)

    tasks = await task_repo.get_by_work(work_id)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    return WorkResponse.from_work(work, len(tasks), completed)


@router.post("/work/{work_id}/start")
async def start_work(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Start work (set status to in_progress)."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    await work_repo.update_status(work_id, WorkStatus.IN_PROGRESS)
    work = await work_repo.get(work_id)

    tasks = await task_repo.get_by_work(work_id)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    return WorkResponse.from_work(work, len(tasks), completed)


@router.post("/work/{work_id}/complete")
async def complete_work(
    bot_id: str,
    work_id: str,
    result: Any | None = None,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Complete work."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    work.status = WorkStatus.COMPLETED
    work.completed_at = datetime.utcnow()
    work.progress = 1.0
    if result:
        work.result = result
    await work_repo.update(work)

    tasks = await task_repo.get_by_work(work_id)
    return WorkResponse.from_work(work, len(tasks), len(tasks))


@router.post("/work/{work_id}/fail")
async def fail_work(
    bot_id: str,
    work_id: str,
    error: str | None = None,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Mark work as failed."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    await work_repo.update_status(work_id, WorkStatus.FAILED, error)
    work = await work_repo.get(work_id)

    tasks = await task_repo.get_by_work(work_id)
    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
    return WorkResponse.from_work(work, len(tasks), completed)


@router.delete("/work/{work_id}", status_code=204)
async def delete_work(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete work (cascades to tasks and jobs)."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")
    await work_repo.delete(work_id)


# =============================================================================
# TASK ROUTES
# =============================================================================


@router.get("/work/{work_id}/tasks")
async def list_tasks(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> list[TaskResponse]:
    """Get all tasks for work."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    tasks = await task_repo.get_by_work(work_id)
    return [TaskResponse.from_task(t) for t in tasks]


@router.get("/work/{work_id}/tasks/ready")
async def get_ready_tasks(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> list[TaskResponse]:
    """Get tasks ready to run (all dependencies met)."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    tasks = await task_repo.get_ready_tasks(work_id)
    return [TaskResponse.from_task(t) for t in tasks]


@router.post("/work/{work_id}/tasks", status_code=201)
async def create_task(
    bot_id: str,
    work_id: str,
    request: CreateTaskRequest,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Create a new task."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    # Auto-assign order if not provided
    order = request.order
    if order is None:
        existing_tasks = await task_repo.get_by_work(work_id)
        order = max((t.order for t in existing_tasks), default=0) + 1

    now = datetime.utcnow()
    task = Task(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        work_id=work_id,
        title=request.title,
        description=request.description,
        action=request.action,
        order=order,
        depends_on=request.dependsOn,
        status=TaskStatus.PENDING,
        priority=Priority(request.priority),
        max_retries=request.maxRetries,
        timeout_seconds=request.timeoutSeconds,
        created_at=now,
    )
    await task_repo.save(task)
    return TaskResponse.from_task(task)


@router.get("/tasks/{task_id}")
async def get_task(
    bot_id: str,
    task_id: str,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Get a task by ID."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.from_task(task)


@router.patch("/tasks/{task_id}")
async def update_task(
    bot_id: str,
    task_id: str,
    request: UpdateTaskRequest,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Update a task."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")

    if request.title is not None:
        task.title = request.title
    if request.description is not None:
        task.description = request.description
    if request.action is not None:
        task.action = request.action
    if request.order is not None:
        task.order = request.order
    if request.dependsOn is not None:
        task.depends_on = request.dependsOn
    if request.status is not None:
        task.status = TaskStatus(request.status)
    if request.priority is not None:
        task.priority = Priority(request.priority)
    if request.maxRetries is not None:
        task.max_retries = request.maxRetries
    if request.timeoutSeconds is not None:
        task.timeout_seconds = request.timeoutSeconds
    if request.result is not None:
        task.result = request.result
    if request.error is not None:
        task.error = request.error

    await task_repo.update(task)
    return TaskResponse.from_task(task)


@router.post("/tasks/{task_id}/start")
async def start_task(
    bot_id: str,
    task_id: str,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Start a task (creates a job)."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_repo.update_status(task_id, TaskStatus.IN_PROGRESS)

    # Get attempt number
    existing_jobs = await job_repo.get_by_task(task_id)
    attempt = len(existing_jobs) + 1

    # Create job
    now = datetime.utcnow()
    job = Job(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        task_id=task_id,
        work_id=task.work_id,
        status=JobStatus.RUNNING,
        attempt=attempt,
        created_at=now,
        started_at=now,
    )
    await job_repo.save(job)

    task = await task_repo.get(task_id)
    return TaskResponse.from_task(task)


@router.post("/tasks/{task_id}/complete")
async def complete_task(
    bot_id: str,
    task_id: str,
    result: Any | None = None,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Complete a task."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_repo.update_status(task_id, TaskStatus.COMPLETED, result=result)

    # Update latest job
    latest_job = await job_repo.get_latest_for_task(task_id)
    if latest_job:
        await job_repo.update_status(latest_job.id, JobStatus.COMPLETED, result=result)

    # Update work progress
    work = await work_repo.get(task.work_id)
    if work:
        tasks = await task_repo.get_by_work(work.id)
        completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
        progress = completed / len(tasks) if tasks else 0
        await work_repo.update_progress(work.id, progress)

    task = await task_repo.get(task_id)
    return TaskResponse.from_task(task)


@router.post("/tasks/{task_id}/fail")
async def fail_task(
    bot_id: str,
    task_id: str,
    error: str | None = None,
    user: User = Depends(require_bot_access),
) -> TaskResponse:
    """Fail a task."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")

    # Check if we can retry
    if task.retry_count < task.max_retries:
        await task_repo.increment_retry(task_id)
        await task_repo.update_status(task_id, TaskStatus.PENDING, error=error)
    else:
        await task_repo.update_status(task_id, TaskStatus.FAILED, error=error)

    # Update latest job
    latest_job = await job_repo.get_latest_for_task(task_id)
    if latest_job:
        await job_repo.update_status(latest_job.id, JobStatus.FAILED, error=error)

    task = await task_repo.get(task_id)
    return TaskResponse.from_task(task)


@router.delete("/tasks/{task_id}", status_code=204)
async def delete_task(
    bot_id: str,
    task_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a task."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")
    await task_repo.delete(task_id)


# =============================================================================
# JOB ROUTES
# =============================================================================


@router.get("/tasks/{task_id}/jobs")
async def list_jobs_for_task(
    bot_id: str,
    task_id: str,
    user: User = Depends(require_bot_access),
) -> list[JobResponse]:
    """Get all jobs for a task."""
    task = await task_repo.get(task_id)
    if task is None or task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Task not found")

    jobs = await job_repo.get_by_task(task_id)
    return [JobResponse.from_job(j) for j in jobs]


@router.get("/work/{work_id}/jobs")
async def list_jobs_for_work(
    bot_id: str,
    work_id: str,
    user: User = Depends(require_bot_access),
) -> list[JobResponse]:
    """Get all jobs for work."""
    work = await work_repo.get(work_id)
    if work is None or work.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Work not found")

    jobs = await job_repo.get_by_work(work_id)
    return [JobResponse.from_job(j) for j in jobs]


@router.get("/jobs/running")
async def list_running_jobs(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[JobResponse]:
    """Get all running jobs for a bot."""
    jobs = await job_repo.get_running(bot_id)
    return [JobResponse.from_job(j) for j in jobs]


@router.get("/jobs/{job_id}")
async def get_job(
    bot_id: str,
    job_id: str,
    user: User = Depends(require_bot_access),
) -> JobResponse:
    """Get a job by ID."""
    job = await job_repo.get(job_id)
    if job is None or job.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobResponse.from_job(job)


@router.post("/jobs/{job_id}/log")
async def append_job_log(
    bot_id: str,
    job_id: str,
    request: AppendJobLogRequest,
    user: User = Depends(require_bot_access),
) -> JobResponse:
    """Append a log entry to a job."""
    job = await job_repo.get(job_id)
    if job is None or job.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Job not found")

    await job_repo.append_log(job_id, request.level, request.message, request.data)
    job = await job_repo.get(job_id)
    return JobResponse.from_job(job)


@router.patch("/jobs/{job_id}/progress")
async def update_job_progress(
    bot_id: str,
    job_id: str,
    progress: float,
    user: User = Depends(require_bot_access),
) -> JobResponse:
    """Update job progress."""
    job = await job_repo.get(job_id)
    if job is None or job.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Job not found")

    await job_repo.update_progress(job_id, progress)
    job = await job_repo.get(job_id)
    return JobResponse.from_job(job)


# =============================================================================
# TODO ROUTES
# =============================================================================


@router.get("/todos")
async def list_todos(
    bot_id: str,
    status: str | None = None,
    limit: int = 50,
    user: User = Depends(require_bot_access),
) -> list[TodoResponse]:
    """Get all todos for a bot."""
    if status:
        todos = await todo_repo.get_by_bot(bot_id, TodoStatus(status), limit)
    else:
        todos = await todo_repo.get_by_bot(bot_id, limit=limit)
    return [TodoResponse.from_todo(t) for t in todos]


@router.get("/todos/open")
async def list_open_todos(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[TodoResponse]:
    """Get open todos for a bot."""
    todos = await todo_repo.get_open(bot_id)
    return [TodoResponse.from_todo(t) for t in todos]


@router.post("/todos", status_code=201)
async def create_todo(
    bot_id: str,
    request: CreateTodoRequest,
    user: User = Depends(require_bot_access),
) -> TodoResponse:
    """Create a new todo."""
    now = datetime.utcnow()
    todo = Todo(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        chat_id=request.chatId,
        title=request.title,
        notes=request.notes,
        status=TodoStatus.OPEN,
        priority=Priority(request.priority),
        remind_at=datetime.fromisoformat(request.remindAt) if request.remindAt else None,
        tags=request.tags,
        created_at=now,
    )
    await todo_repo.save(todo)
    return TodoResponse.from_todo(todo)


@router.get("/todos/{todo_id}")
async def get_todo(
    bot_id: str,
    todo_id: str,
    user: User = Depends(require_bot_access),
) -> TodoResponse:
    """Get a todo by ID."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")
    return TodoResponse.from_todo(todo)


@router.patch("/todos/{todo_id}")
async def update_todo(
    bot_id: str,
    todo_id: str,
    request: UpdateTodoRequest,
    user: User = Depends(require_bot_access),
) -> TodoResponse:
    """Update a todo."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    if request.title is not None:
        todo.title = request.title
    if request.notes is not None:
        todo.notes = request.notes
    if request.status is not None:
        todo.status = TodoStatus(request.status)
    if request.priority is not None:
        todo.priority = Priority(request.priority)
    if request.remindAt is not None:
        todo.remind_at = datetime.fromisoformat(request.remindAt)
    if request.tags is not None:
        todo.tags = request.tags

    await todo_repo.update(todo)
    return TodoResponse.from_todo(todo)


@router.post("/todos/{todo_id}/done")
async def mark_todo_done(
    bot_id: str,
    todo_id: str,
    user: User = Depends(require_bot_access),
) -> TodoResponse:
    """Mark a todo as done."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    await todo_repo.update_status(todo_id, TodoStatus.DONE)
    todo = await todo_repo.get(todo_id)
    return TodoResponse.from_todo(todo)


@router.post("/todos/{todo_id}/dismiss")
async def dismiss_todo(
    bot_id: str,
    todo_id: str,
    user: User = Depends(require_bot_access),
) -> TodoResponse:
    """Dismiss a todo."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    await todo_repo.update_status(todo_id, TodoStatus.DISMISSED)
    todo = await todo_repo.get(todo_id)
    return TodoResponse.from_todo(todo)


@router.post("/todos/{todo_id}/convert", status_code=201)
async def convert_todo_to_work(
    bot_id: str,
    todo_id: str,
    request: ConvertTodoRequest,
    user: User = Depends(require_bot_access),
) -> WorkResponse:
    """Convert a todo to work."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")

    now = datetime.utcnow()
    work = Work(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        chat_id=todo.chat_id,
        title=request.workTitle or todo.title,
        description=request.workDescription or todo.notes,
        status=WorkStatus.PENDING,
        priority=Priority(request.priority) if request.priority else todo.priority,
        tags=todo.tags,
        created_at=now,
    )
    await work_repo.save(work)

    # Mark todo as converted
    await todo_repo.mark_converted(todo_id, work_id=work.id)

    return WorkResponse.from_work(work, 0, 0)


@router.delete("/todos/{todo_id}", status_code=204)
async def delete_todo(
    bot_id: str,
    todo_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a todo."""
    todo = await todo_repo.get(todo_id)
    if todo is None or todo.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Todo not found")
    await todo_repo.delete(todo_id)

"""
Repository Classes for Work Management System

Provides async CRUD operations using SQLAlchemy ORM with AsyncSession.
Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0.
"""

from datetime import datetime, timezone

from sqlalchemy import delete, select, update

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
from cachibot.storage.db import async_session_maker
from cachibot.storage.models.work import (
    Function as FunctionModel,
)
from cachibot.storage.models.work import (
    Schedule as ScheduleModel,
)
from cachibot.storage.models.work import (
    Task as TaskModel,
)
from cachibot.storage.models.work import (
    Todo as TodoModel,
)
from cachibot.storage.models.work import (
    Work as WorkModel,
)
from cachibot.storage.models.work import (
    WorkJob as WorkJobModel,
)


class FunctionRepository:
    """Repository for bot functions (reusable templates)."""

    async def save(self, fn: BotFunction) -> None:
        """Save a new function."""
        async with async_session_maker() as session:
            obj = FunctionModel(
                id=fn.id,
                bot_id=fn.bot_id,
                name=fn.name,
                description=fn.description,
                version=fn.version,
                steps=[s.model_dump() for s in fn.steps],
                parameters=[p.model_dump() for p in fn.parameters],
                tags=fn.tags,
                created_at=fn.created_at,
                updated_at=fn.updated_at,
                run_count=fn.run_count,
                last_run_at=fn.last_run_at,
                success_rate=fn.success_rate,
            )
            session.add(obj)
            await session.commit()

    async def update(self, fn: BotFunction) -> None:
        """Update an existing function."""
        async with async_session_maker() as session:
            await session.execute(
                update(FunctionModel)
                .where(FunctionModel.id == fn.id)
                .values(
                    name=fn.name,
                    description=fn.description,
                    version=fn.version,
                    steps=[s.model_dump() for s in fn.steps],
                    parameters=[p.model_dump() for p in fn.parameters],
                    tags=fn.tags,
                    updated_at=fn.updated_at,
                    run_count=fn.run_count,
                    last_run_at=fn.last_run_at,
                    success_rate=fn.success_rate,
                )
            )
            await session.commit()

    async def get(self, function_id: str) -> BotFunction | None:
        """Get a function by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(FunctionModel).where(FunctionModel.id == function_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_function(row) if row else None

    async def get_by_bot(self, bot_id: str) -> list[BotFunction]:
        """Get all functions for a bot."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(FunctionModel)
                .where(FunctionModel.bot_id == bot_id)
                .order_by(FunctionModel.name)
            )
            rows = result.scalars().all()
        return [self._row_to_function(row) for row in rows]

    async def delete(self, function_id: str) -> bool:
        """Delete a function by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                delete(FunctionModel).where(FunctionModel.id == function_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def increment_run_count(self, function_id: str, success: bool) -> None:
        """Increment run count and update success rate."""
        now = datetime.now(timezone.utc)

        async with async_session_maker() as session:
            # Get current stats
            result = await session.execute(
                select(FunctionModel.run_count, FunctionModel.success_rate).where(
                    FunctionModel.id == function_id
                )
            )
            row = result.one_or_none()

            if row:
                old_count = row[0]
                old_rate = row[1]
                new_count = old_count + 1
                # Calculate new success rate
                old_successes = old_count * old_rate
                new_successes = old_successes + (1 if success else 0)
                new_rate = new_successes / new_count

                await session.execute(
                    update(FunctionModel)
                    .where(FunctionModel.id == function_id)
                    .values(
                        run_count=new_count,
                        success_rate=new_rate,
                        last_run_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

    def _row_to_function(self, row: FunctionModel) -> BotFunction:
        """Convert database row to BotFunction."""
        steps_data = row.steps if row.steps else []
        params_data = row.parameters if row.parameters else []

        return BotFunction(
            id=row.id,
            bot_id=row.bot_id,
            name=row.name,
            description=row.description,
            version=row.version,
            steps=[
                FunctionStep(
                    order=s["order"],
                    name=s["name"],
                    description=s.get("description"),
                    action=s["action"],
                    depends_on=s.get("depends_on", []),
                    retry_count=s.get("retry_count", 0),
                    timeout_seconds=s.get("timeout_seconds"),
                    on_failure=FailureAction(s.get("on_failure", "stop")),
                )
                for s in steps_data
            ],
            parameters=[
                FunctionParameter(
                    name=p["name"],
                    type=p.get("type", "string"),
                    default=p.get("default"),
                    required=p.get("required", True),
                    description=p.get("description"),
                )
                for p in params_data
            ],
            tags=row.tags if row.tags else [],
            created_at=row.created_at,
            updated_at=row.updated_at,
            run_count=row.run_count,
            last_run_at=row.last_run_at,
            success_rate=row.success_rate,
        )


class ScheduleRepository:
    """Repository for schedules (cron/timer triggers)."""

    async def save(self, schedule: Schedule) -> None:
        """Save a new schedule."""
        async with async_session_maker() as session:
            obj = ScheduleModel(
                id=schedule.id,
                bot_id=schedule.bot_id,
                name=schedule.name,
                description=schedule.description,
                function_id=schedule.function_id,
                function_params=schedule.function_params,
                schedule_type=schedule.schedule_type.value,
                cron_expression=schedule.cron_expression,
                interval_seconds=schedule.interval_seconds,
                run_at=schedule.run_at,
                event_trigger=schedule.event_trigger,
                timezone=schedule.timezone,
                enabled=schedule.enabled,
                max_concurrent=schedule.max_concurrent,
                catch_up=schedule.catch_up,
                created_at=schedule.created_at,
                updated_at=schedule.updated_at,
                next_run_at=schedule.next_run_at,
                last_run_at=schedule.last_run_at,
                run_count=schedule.run_count,
            )
            session.add(obj)
            await session.commit()

    async def update(self, schedule: Schedule) -> None:
        """Update an existing schedule."""
        async with async_session_maker() as session:
            await session.execute(
                update(ScheduleModel)
                .where(ScheduleModel.id == schedule.id)
                .values(
                    name=schedule.name,
                    description=schedule.description,
                    function_id=schedule.function_id,
                    function_params=schedule.function_params,
                    schedule_type=schedule.schedule_type.value,
                    cron_expression=schedule.cron_expression,
                    interval_seconds=schedule.interval_seconds,
                    run_at=schedule.run_at,
                    event_trigger=schedule.event_trigger,
                    timezone=schedule.timezone,
                    enabled=schedule.enabled,
                    max_concurrent=schedule.max_concurrent,
                    catch_up=schedule.catch_up,
                    updated_at=schedule.updated_at,
                    next_run_at=schedule.next_run_at,
                    last_run_at=schedule.last_run_at,
                    run_count=schedule.run_count,
                )
            )
            await session.commit()

    async def get(self, schedule_id: str) -> Schedule | None:
        """Get a schedule by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduleModel).where(ScheduleModel.id == schedule_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_schedule(row) if row else None

    async def get_by_bot(self, bot_id: str) -> list[Schedule]:
        """Get all schedules for a bot."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduleModel)
                .where(ScheduleModel.bot_id == bot_id)
                .order_by(ScheduleModel.name)
            )
            rows = result.scalars().all()
        return [self._row_to_schedule(row) for row in rows]

    async def get_due_schedules(self) -> list[Schedule]:
        """Get all enabled schedules that are due to run."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            result = await session.execute(
                select(ScheduleModel)
                .where(
                    ScheduleModel.enabled.is_(True),
                    ScheduleModel.next_run_at.isnot(None),
                    ScheduleModel.next_run_at <= now,
                )
                .order_by(ScheduleModel.next_run_at)
            )
            rows = result.scalars().all()
        return [self._row_to_schedule(row) for row in rows]

    async def toggle_enabled(self, schedule_id: str, enabled: bool) -> None:
        """Enable or disable a schedule."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            await session.execute(
                update(ScheduleModel)
                .where(ScheduleModel.id == schedule_id)
                .values(enabled=enabled, updated_at=now)
            )
            await session.commit()

    async def update_next_run(self, schedule_id: str, next_run_at: datetime | None) -> None:
        """Update the next run time for a schedule."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            await session.execute(
                update(ScheduleModel)
                .where(ScheduleModel.id == schedule_id)
                .values(next_run_at=next_run_at, updated_at=now)
            )
            await session.commit()

    async def record_run(self, schedule_id: str) -> None:
        """Record that a schedule has run."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            await session.execute(
                update(ScheduleModel)
                .where(ScheduleModel.id == schedule_id)
                .values(
                    run_count=ScheduleModel.run_count + 1,
                    last_run_at=now,
                    updated_at=now,
                )
            )
            await session.commit()

    async def delete(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        async with async_session_maker() as session:
            result = await session.execute(
                delete(ScheduleModel).where(ScheduleModel.id == schedule_id)
            )
            await session.commit()
            return result.rowcount > 0

    def _row_to_schedule(self, row: ScheduleModel) -> Schedule:
        """Convert database row to Schedule."""
        return Schedule(
            id=row.id,
            bot_id=row.bot_id,
            name=row.name,
            description=row.description,
            function_id=row.function_id,
            function_params=row.function_params if row.function_params else {},
            schedule_type=ScheduleType(row.schedule_type),
            cron_expression=row.cron_expression,
            interval_seconds=row.interval_seconds,
            run_at=row.run_at,
            event_trigger=row.event_trigger,
            timezone=row.timezone,
            enabled=row.enabled,
            max_concurrent=row.max_concurrent,
            catch_up=row.catch_up,
            created_at=row.created_at,
            updated_at=row.updated_at,
            next_run_at=row.next_run_at,
            last_run_at=row.last_run_at,
            run_count=row.run_count,
        )


class WorkRepository:
    """Repository for work (high-level objectives)."""

    async def save(self, work: Work) -> None:
        """Save a new work item."""
        async with async_session_maker() as session:
            obj = WorkModel(
                id=work.id,
                bot_id=work.bot_id,
                chat_id=work.chat_id,
                title=work.title,
                description=work.description,
                goal=work.goal,
                function_id=work.function_id,
                schedule_id=work.schedule_id,
                parent_work_id=work.parent_work_id,
                status=work.status.value,
                priority=work.priority.value,
                progress=work.progress,
                created_at=work.created_at,
                started_at=work.started_at,
                completed_at=work.completed_at,
                due_at=work.due_at,
                result=work.result,
                error=work.error,
                context=work.context,
                tags=work.tags,
            )
            session.add(obj)
            await session.commit()

    async def update(self, work: Work) -> None:
        """Update an existing work item."""
        async with async_session_maker() as session:
            await session.execute(
                update(WorkModel)
                .where(WorkModel.id == work.id)
                .values(
                    title=work.title,
                    description=work.description,
                    goal=work.goal,
                    status=work.status.value,
                    priority=work.priority.value,
                    progress=work.progress,
                    started_at=work.started_at,
                    completed_at=work.completed_at,
                    due_at=work.due_at,
                    result=work.result,
                    error=work.error,
                    context=work.context,
                    tags=work.tags,
                )
            )
            await session.commit()

    async def update_status(
        self,
        work_id: str,
        status: WorkStatus,
        error: str | None = None,
    ) -> None:
        """Update work status."""
        now = datetime.now(timezone.utc)
        values: dict = {"status": status.value}

        if status == WorkStatus.IN_PROGRESS:
            values["started_at"] = now
        elif status in (WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLED):
            values["completed_at"] = now
            values["error"] = error

        async with async_session_maker() as session:
            await session.execute(update(WorkModel).where(WorkModel.id == work_id).values(**values))
            await session.commit()

    async def update_progress(self, work_id: str, progress: float) -> None:
        """Update work progress."""
        async with async_session_maker() as session:
            await session.execute(
                update(WorkModel).where(WorkModel.id == work_id).values(progress=progress)
            )
            await session.commit()

    async def get(self, work_id: str) -> Work | None:
        """Get a work item by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(WorkModel).where(WorkModel.id == work_id))
            row = result.scalar_one_or_none()
        return self._row_to_work(row) if row else None

    async def get_by_bot(
        self,
        bot_id: str,
        status: WorkStatus | None = None,
        limit: int = 50,
    ) -> list[Work]:
        """Get work items for a bot."""
        stmt = select(WorkModel).where(WorkModel.bot_id == bot_id)
        if status:
            stmt = stmt.where(WorkModel.status == status.value)
        stmt = stmt.order_by(WorkModel.created_at.desc()).limit(limit)

        async with async_session_maker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_work(row) for row in rows]

    async def get_active(self, bot_id: str) -> list[Work]:
        """Get active (pending/in_progress) work for a bot."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkModel)
                .where(
                    WorkModel.bot_id == bot_id,
                    WorkModel.status.in_([WorkStatus.PENDING.value, WorkStatus.IN_PROGRESS.value]),
                )
                .order_by(WorkModel.priority.desc(), WorkModel.created_at.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_work(row) for row in rows]

    async def get_by_schedule(self, schedule_id: str) -> list[Work]:
        """Get work items created by a schedule."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkModel)
                .where(WorkModel.schedule_id == schedule_id)
                .order_by(WorkModel.created_at.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_work(row) for row in rows]

    async def get_children(self, parent_work_id: str) -> list[Work]:
        """Get child work items."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkModel)
                .where(WorkModel.parent_work_id == parent_work_id)
                .order_by(WorkModel.created_at.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_work(row) for row in rows]

    async def delete(self, work_id: str) -> bool:
        """Delete a work item (cascades to tasks and jobs)."""
        async with async_session_maker() as session:
            result = await session.execute(delete(WorkModel).where(WorkModel.id == work_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_work(self, row: WorkModel) -> Work:
        """Convert database row to Work."""
        return Work(
            id=row.id,
            bot_id=row.bot_id,
            chat_id=row.chat_id,
            title=row.title,
            description=row.description,
            goal=row.goal,
            function_id=row.function_id,
            schedule_id=row.schedule_id,
            parent_work_id=row.parent_work_id,
            status=WorkStatus(row.status),
            priority=Priority(row.priority),
            progress=row.progress,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            due_at=row.due_at,
            result=row.result,
            error=row.error,
            context=row.context if row.context else {},
            tags=row.tags if row.tags else [],
        )


class TaskRepository:
    """Repository for tasks (steps within work)."""

    async def save(self, task: Task) -> None:
        """Save a new task."""
        async with async_session_maker() as session:
            obj = TaskModel(
                id=task.id,
                bot_id=task.bot_id,
                work_id=task.work_id,
                chat_id=task.chat_id,
                title=task.title,
                description=task.description,
                action=task.action,
                task_order=task.order,
                depends_on=task.depends_on,
                status=task.status.value,
                priority=task.priority.value,
                retry_count=task.retry_count,
                max_retries=task.max_retries,
                timeout_seconds=task.timeout_seconds,
                created_at=task.created_at,
                started_at=task.started_at,
                completed_at=task.completed_at,
                result=task.result,
                error=task.error,
            )
            session.add(obj)
            await session.commit()

    async def save_batch(self, tasks: list[Task]) -> None:
        """Save multiple tasks at once."""
        if not tasks:
            return
        async with async_session_maker() as session:
            session.add_all(
                [
                    TaskModel(
                        id=task.id,
                        bot_id=task.bot_id,
                        work_id=task.work_id,
                        chat_id=task.chat_id,
                        title=task.title,
                        description=task.description,
                        action=task.action,
                        task_order=task.order,
                        depends_on=task.depends_on,
                        status=task.status.value,
                        priority=task.priority.value,
                        retry_count=task.retry_count,
                        max_retries=task.max_retries,
                        timeout_seconds=task.timeout_seconds,
                        created_at=task.created_at,
                        started_at=task.started_at,
                        completed_at=task.completed_at,
                        result=task.result,
                        error=task.error,
                    )
                    for task in tasks
                ]
            )
            await session.commit()

    async def update(self, task: Task) -> None:
        """Update an existing task."""
        async with async_session_maker() as session:
            await session.execute(
                update(TaskModel)
                .where(TaskModel.id == task.id)
                .values(
                    title=task.title,
                    description=task.description,
                    action=task.action,
                    task_order=task.order,
                    depends_on=task.depends_on,
                    status=task.status.value,
                    priority=task.priority.value,
                    retry_count=task.retry_count,
                    max_retries=task.max_retries,
                    timeout_seconds=task.timeout_seconds,
                    started_at=task.started_at,
                    completed_at=task.completed_at,
                    result=task.result,
                    error=task.error,
                )
            )
            await session.commit()

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
        result: any = None,
    ) -> None:
        """Update task status."""
        now = datetime.now(timezone.utc)
        values: dict = {"status": status.value}

        if status == TaskStatus.IN_PROGRESS:
            values["started_at"] = now
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED):
            values["completed_at"] = now
            values["error"] = error
            values["result"] = result

        async with async_session_maker() as session:
            await session.execute(update(TaskModel).where(TaskModel.id == task_id).values(**values))
            await session.commit()

    async def increment_retry(self, task_id: str) -> int:
        """Increment retry count and return new value."""
        async with async_session_maker() as session:
            await session.execute(
                update(TaskModel)
                .where(TaskModel.id == task_id)
                .values(retry_count=TaskModel.retry_count + 1)
            )
            await session.commit()

            result = await session.execute(
                select(TaskModel.retry_count).where(TaskModel.id == task_id)
            )
            row = result.scalar_one_or_none()
        return row if row else 0

    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(TaskModel).where(TaskModel.id == task_id))
            row = result.scalar_one_or_none()
        return self._row_to_task(row) if row else None

    async def get_by_work(self, work_id: str) -> list[Task]:
        """Get all tasks for a work item."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(TaskModel)
                .where(TaskModel.work_id == work_id)
                .order_by(TaskModel.task_order.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_task(row) for row in rows]

    async def get_ready_tasks(self, work_id: str) -> list[Task]:
        """Get tasks that are ready to run (all dependencies complete)."""
        # Get all tasks for this work
        all_tasks = await self.get_by_work(work_id)

        # Find completed task IDs
        completed_ids = {t.id for t in all_tasks if t.status == TaskStatus.COMPLETED}

        # Filter to pending tasks whose dependencies are all complete
        ready = []
        for task in all_tasks:
            if task.status != TaskStatus.PENDING:
                continue
            if all(dep_id in completed_ids for dep_id in task.depends_on):
                ready.append(task)

        return ready

    async def get_by_bot(
        self,
        bot_id: str,
        status: TaskStatus | None = None,
        limit: int = 50,
    ) -> list[Task]:
        """Get tasks for a bot."""
        stmt = select(TaskModel).where(TaskModel.bot_id == bot_id)
        if status:
            stmt = stmt.where(TaskModel.status == status.value)
        stmt = stmt.order_by(TaskModel.created_at.desc()).limit(limit)

        async with async_session_maker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_task(row) for row in rows]

    async def delete(self, task_id: str) -> bool:
        """Delete a task (cascades to jobs)."""
        async with async_session_maker() as session:
            result = await session.execute(delete(TaskModel).where(TaskModel.id == task_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_task(self, row: TaskModel) -> Task:
        """Convert database row to Task."""
        return Task(
            id=row.id,
            bot_id=row.bot_id,
            work_id=row.work_id,
            chat_id=row.chat_id,
            title=row.title,
            description=row.description,
            action=row.action,
            order=row.task_order,
            depends_on=row.depends_on if row.depends_on else [],
            status=TaskStatus(row.status),
            priority=Priority(row.priority),
            retry_count=row.retry_count,
            max_retries=row.max_retries,
            timeout_seconds=row.timeout_seconds,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            result=row.result,
            error=row.error,
        )


class WorkJobRepository:
    """Repository for work jobs (execution attempts)."""

    async def save(self, job: Job) -> None:
        """Save a new job."""
        async with async_session_maker() as session:
            obj = WorkJobModel(
                id=job.id,
                bot_id=job.bot_id,
                task_id=job.task_id,
                work_id=job.work_id,
                chat_id=job.chat_id,
                status=job.status.value,
                attempt=job.attempt,
                progress=job.progress,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                result=job.result,
                error=job.error,
                logs=job.logs,
            )
            session.add(obj)
            await session.commit()

    async def update(self, job: Job) -> None:
        """Update an existing job."""
        async with async_session_maker() as session:
            await session.execute(
                update(WorkJobModel)
                .where(WorkJobModel.id == job.id)
                .values(
                    status=job.status.value,
                    progress=job.progress,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    result=job.result,
                    error=job.error,
                    logs=job.logs,
                )
            )
            await session.commit()

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        result: any = None,
    ) -> None:
        """Update job status."""
        now = datetime.now(timezone.utc)
        values: dict = {"status": status.value}

        if status == JobStatus.RUNNING:
            values["started_at"] = now
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            values["completed_at"] = now
            values["error"] = error
            values["result"] = result

        async with async_session_maker() as session:
            await session.execute(
                update(WorkJobModel).where(WorkJobModel.id == job_id).values(**values)
            )
            await session.commit()

    async def update_progress(self, job_id: str, progress: float) -> None:
        """Update job progress."""
        async with async_session_maker() as session:
            await session.execute(
                update(WorkJobModel).where(WorkJobModel.id == job_id).values(progress=progress)
            )
            await session.commit()

    async def append_log(
        self,
        job_id: str,
        level: str,
        message: str,
        data: any = None,
    ) -> None:
        """Append a log entry to a job."""
        async with async_session_maker() as session:
            # Get current logs
            result = await session.execute(
                select(WorkJobModel.logs).where(WorkJobModel.id == job_id)
            )
            row = result.scalar_one_or_none()

            if row is not None:
                logs = row if row else []
                logs.append(
                    {
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "level": level,
                        "message": message,
                        "data": data,
                    }
                )

                await session.execute(
                    update(WorkJobModel).where(WorkJobModel.id == job_id).values(logs=logs)
                )
                await session.commit()

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(WorkJobModel).where(WorkJobModel.id == job_id))
            row = result.scalar_one_or_none()
        return self._row_to_job(row) if row else None

    async def get_by_task(self, task_id: str) -> list[Job]:
        """Get all jobs for a task."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkJobModel)
                .where(WorkJobModel.task_id == task_id)
                .order_by(WorkJobModel.attempt.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_job(row) for row in rows]

    async def get_by_work(self, work_id: str) -> list[Job]:
        """Get all jobs for a work item."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkJobModel)
                .where(WorkJobModel.work_id == work_id)
                .order_by(WorkJobModel.created_at.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_job(row) for row in rows]

    async def get_latest_for_task(self, task_id: str) -> Job | None:
        """Get the latest job for a task."""
        async with async_session_maker() as session:
            result = await session.execute(
                select(WorkJobModel)
                .where(WorkJobModel.task_id == task_id)
                .order_by(WorkJobModel.attempt.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        return self._row_to_job(row) if row else None

    async def get_running(self, bot_id: str | None = None) -> list[Job]:
        """Get all running jobs, optionally filtered by bot."""
        stmt = select(WorkJobModel).where(WorkJobModel.status == JobStatus.RUNNING.value)
        if bot_id:
            stmt = stmt.where(WorkJobModel.bot_id == bot_id)
        stmt = stmt.order_by(WorkJobModel.started_at.asc())

        async with async_session_maker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_job(row) for row in rows]

    async def delete(self, job_id: str) -> bool:
        """Delete a job."""
        async with async_session_maker() as session:
            result = await session.execute(delete(WorkJobModel).where(WorkJobModel.id == job_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_job(self, row: WorkJobModel) -> Job:
        """Convert database row to Job."""
        return Job(
            id=row.id,
            bot_id=row.bot_id,
            task_id=row.task_id,
            work_id=row.work_id,
            chat_id=row.chat_id,
            status=JobStatus(row.status),
            attempt=row.attempt,
            progress=row.progress,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            result=row.result,
            error=row.error,
            logs=row.logs if row.logs else [],
        )


class TodoRepository:
    """Repository for todos (reminders/notes)."""

    async def save(self, todo: Todo) -> None:
        """Save a new todo."""
        async with async_session_maker() as session:
            obj = TodoModel(
                id=todo.id,
                bot_id=todo.bot_id,
                chat_id=todo.chat_id,
                title=todo.title,
                notes=todo.notes,
                status=todo.status.value,
                priority=todo.priority.value,
                created_at=todo.created_at,
                completed_at=todo.completed_at,
                remind_at=todo.remind_at,
                converted_to_work_id=todo.converted_to_work_id,
                converted_to_task_id=todo.converted_to_task_id,
                tags=todo.tags,
            )
            session.add(obj)
            await session.commit()

    async def update(self, todo: Todo) -> None:
        """Update an existing todo."""
        async with async_session_maker() as session:
            await session.execute(
                update(TodoModel)
                .where(TodoModel.id == todo.id)
                .values(
                    title=todo.title,
                    notes=todo.notes,
                    status=todo.status.value,
                    priority=todo.priority.value,
                    completed_at=todo.completed_at,
                    remind_at=todo.remind_at,
                    converted_to_work_id=todo.converted_to_work_id,
                    converted_to_task_id=todo.converted_to_task_id,
                    tags=todo.tags,
                )
            )
            await session.commit()

    async def update_status(self, todo_id: str, status: TodoStatus) -> None:
        """Update todo status."""
        now = datetime.now(timezone.utc)
        values: dict = {"status": status.value}

        if status == TodoStatus.DONE:
            values["completed_at"] = now
        else:
            values["completed_at"] = None

        async with async_session_maker() as session:
            await session.execute(update(TodoModel).where(TodoModel.id == todo_id).values(**values))
            await session.commit()

    async def mark_converted(
        self,
        todo_id: str,
        work_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Mark a todo as converted to work or task."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            await session.execute(
                update(TodoModel)
                .where(TodoModel.id == todo_id)
                .values(
                    status=TodoStatus.DONE.value,
                    completed_at=now,
                    converted_to_work_id=work_id,
                    converted_to_task_id=task_id,
                )
            )
            await session.commit()

    async def get(self, todo_id: str) -> Todo | None:
        """Get a todo by ID."""
        async with async_session_maker() as session:
            result = await session.execute(select(TodoModel).where(TodoModel.id == todo_id))
            row = result.scalar_one_or_none()
        return self._row_to_todo(row) if row else None

    async def get_by_bot(
        self,
        bot_id: str,
        status: TodoStatus | None = None,
        limit: int = 50,
    ) -> list[Todo]:
        """Get todos for a bot."""
        stmt = select(TodoModel).where(TodoModel.bot_id == bot_id)
        if status:
            stmt = stmt.where(TodoModel.status == status.value)
        stmt = stmt.order_by(TodoModel.priority.desc(), TodoModel.created_at.desc()).limit(limit)

        async with async_session_maker() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_todo(row) for row in rows]

    async def get_open(self, bot_id: str) -> list[Todo]:
        """Get open todos for a bot."""
        return await self.get_by_bot(bot_id, status=TodoStatus.OPEN)

    async def get_due_reminders(self) -> list[Todo]:
        """Get todos with reminders that are due."""
        now = datetime.now(timezone.utc)
        async with async_session_maker() as session:
            result = await session.execute(
                select(TodoModel)
                .where(
                    TodoModel.status == TodoStatus.OPEN.value,
                    TodoModel.remind_at.isnot(None),
                    TodoModel.remind_at <= now,
                )
                .order_by(TodoModel.remind_at.asc())
            )
            rows = result.scalars().all()
        return [self._row_to_todo(row) for row in rows]

    async def delete(self, todo_id: str) -> bool:
        """Delete a todo."""
        async with async_session_maker() as session:
            result = await session.execute(delete(TodoModel).where(TodoModel.id == todo_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_todo(self, row: TodoModel) -> Todo:
        """Convert database row to Todo."""
        return Todo(
            id=row.id,
            bot_id=row.bot_id,
            chat_id=row.chat_id,
            title=row.title,
            notes=row.notes,
            status=TodoStatus(row.status),
            priority=Priority(row.priority),
            created_at=row.created_at,
            completed_at=row.completed_at,
            remind_at=row.remind_at,
            converted_to_work_id=row.converted_to_work_id,
            converted_to_task_id=row.converted_to_task_id,
            tags=row.tags if row.tags else [],
        )

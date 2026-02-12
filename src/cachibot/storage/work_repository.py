"""
Repository Classes for Work Management System

Provides async CRUD operations for functions, schedules, work, tasks, jobs, and todos.
"""

import json
from datetime import datetime

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
from cachibot.storage.database import get_db


class FunctionRepository:
    """Repository for bot functions (reusable templates)."""

    async def save(self, fn: BotFunction) -> None:
        """Save a new function."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO functions
            (id, bot_id, name, description, version, steps, parameters, tags,
             created_at, updated_at, run_count, last_run_at, success_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                fn.id,
                fn.bot_id,
                fn.name,
                fn.description,
                fn.version,
                json.dumps([s.model_dump() for s in fn.steps]),
                json.dumps([p.model_dump() for p in fn.parameters]),
                json.dumps(fn.tags),
                fn.created_at.isoformat(),
                fn.updated_at.isoformat(),
                fn.run_count,
                fn.last_run_at.isoformat() if fn.last_run_at else None,
                fn.success_rate,
            ),
        )
        await db.commit()

    async def update(self, fn: BotFunction) -> None:
        """Update an existing function."""
        db = await get_db()
        await db.execute(
            """
            UPDATE functions SET
                name = ?, description = ?, version = ?, steps = ?, parameters = ?,
                tags = ?, updated_at = ?, run_count = ?, last_run_at = ?, success_rate = ?
            WHERE id = ?
            """,
            (
                fn.name,
                fn.description,
                fn.version,
                json.dumps([s.model_dump() for s in fn.steps]),
                json.dumps([p.model_dump() for p in fn.parameters]),
                json.dumps(fn.tags),
                fn.updated_at.isoformat(),
                fn.run_count,
                fn.last_run_at.isoformat() if fn.last_run_at else None,
                fn.success_rate,
                fn.id,
            ),
        )
        await db.commit()

    async def get(self, function_id: str) -> BotFunction | None:
        """Get a function by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM functions WHERE id = ?",
            (function_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_function(row) if row else None

    async def get_by_bot(self, bot_id: str) -> list[BotFunction]:
        """Get all functions for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM functions WHERE bot_id = ? ORDER BY name",
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_function(row) for row in rows]

    async def delete(self, function_id: str) -> bool:
        """Delete a function by ID."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM functions WHERE id = ?",
            (function_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def increment_run_count(self, function_id: str, success: bool) -> None:
        """Increment run count and update success rate."""
        db = await get_db()
        now = datetime.utcnow()

        # Get current stats
        async with db.execute(
            "SELECT run_count, success_rate FROM functions WHERE id = ?",
            (function_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            old_count = row["run_count"]
            old_rate = row["success_rate"]
            new_count = old_count + 1
            # Calculate new success rate
            old_successes = old_count * old_rate
            new_successes = old_successes + (1 if success else 0)
            new_rate = new_successes / new_count

            await db.execute(
                """
                UPDATE functions SET
                    run_count = ?, success_rate = ?, last_run_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (new_count, new_rate, now.isoformat(), now.isoformat(), function_id),
            )
            await db.commit()

    def _row_to_function(self, row) -> BotFunction:
        """Convert database row to BotFunction."""
        steps_data = json.loads(row["steps"]) if row["steps"] else []
        params_data = json.loads(row["parameters"]) if row["parameters"] else []
        last_run = row["last_run_at"]

        return BotFunction(
            id=row["id"],
            bot_id=row["bot_id"],
            name=row["name"],
            description=row["description"],
            version=row["version"],
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
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            run_count=row["run_count"],
            last_run_at=datetime.fromisoformat(last_run) if last_run else None,
            success_rate=row["success_rate"],
        )


class ScheduleRepository:
    """Repository for schedules (cron/timer triggers)."""

    async def save(self, schedule: Schedule) -> None:
        """Save a new schedule."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO schedules
            (id, bot_id, name, description, function_id, function_params,
             schedule_type, cron_expression, interval_seconds, run_at,
             event_trigger, timezone, enabled, max_concurrent, catch_up,
             created_at, updated_at, next_run_at, last_run_at, run_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                schedule.id,
                schedule.bot_id,
                schedule.name,
                schedule.description,
                schedule.function_id,
                json.dumps(schedule.function_params),
                schedule.schedule_type.value,
                schedule.cron_expression,
                schedule.interval_seconds,
                schedule.run_at.isoformat() if schedule.run_at else None,
                schedule.event_trigger,
                schedule.timezone,
                1 if schedule.enabled else 0,
                schedule.max_concurrent,
                1 if schedule.catch_up else 0,
                schedule.created_at.isoformat(),
                schedule.updated_at.isoformat(),
                schedule.next_run_at.isoformat() if schedule.next_run_at else None,
                schedule.last_run_at.isoformat() if schedule.last_run_at else None,
                schedule.run_count,
            ),
        )
        await db.commit()

    async def update(self, schedule: Schedule) -> None:
        """Update an existing schedule."""
        db = await get_db()
        await db.execute(
            """
            UPDATE schedules SET
                name = ?, description = ?, function_id = ?, function_params = ?,
                schedule_type = ?, cron_expression = ?, interval_seconds = ?,
                run_at = ?, event_trigger = ?, timezone = ?, enabled = ?,
                max_concurrent = ?, catch_up = ?, updated_at = ?,
                next_run_at = ?, last_run_at = ?, run_count = ?
            WHERE id = ?
            """,
            (
                schedule.name,
                schedule.description,
                schedule.function_id,
                json.dumps(schedule.function_params),
                schedule.schedule_type.value,
                schedule.cron_expression,
                schedule.interval_seconds,
                schedule.run_at.isoformat() if schedule.run_at else None,
                schedule.event_trigger,
                schedule.timezone,
                1 if schedule.enabled else 0,
                schedule.max_concurrent,
                1 if schedule.catch_up else 0,
                schedule.updated_at.isoformat(),
                schedule.next_run_at.isoformat() if schedule.next_run_at else None,
                schedule.last_run_at.isoformat() if schedule.last_run_at else None,
                schedule.run_count,
                schedule.id,
            ),
        )
        await db.commit()

    async def get(self, schedule_id: str) -> Schedule | None:
        """Get a schedule by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM schedules WHERE id = ?",
            (schedule_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_schedule(row) if row else None

    async def get_by_bot(self, bot_id: str) -> list[Schedule]:
        """Get all schedules for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM schedules WHERE bot_id = ? ORDER BY name",
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_schedule(row) for row in rows]

    async def get_due_schedules(self) -> list[Schedule]:
        """Get all enabled schedules that are due to run."""
        db = await get_db()
        now = datetime.utcnow().isoformat()
        async with db.execute(
            """
            SELECT * FROM schedules
            WHERE enabled = 1 AND next_run_at IS NOT NULL AND next_run_at <= ?
            ORDER BY next_run_at
            """,
            (now,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_schedule(row) for row in rows]

    async def toggle_enabled(self, schedule_id: str, enabled: bool) -> None:
        """Enable or disable a schedule."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            "UPDATE schedules SET enabled = ?, updated_at = ? WHERE id = ?",
            (1 if enabled else 0, now.isoformat(), schedule_id),
        )
        await db.commit()

    async def update_next_run(self, schedule_id: str, next_run_at: datetime | None) -> None:
        """Update the next run time for a schedule."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            "UPDATE schedules SET next_run_at = ?, updated_at = ? WHERE id = ?",
            (
                next_run_at.isoformat() if next_run_at else None,
                now.isoformat(),
                schedule_id,
            ),
        )
        await db.commit()

    async def record_run(self, schedule_id: str) -> None:
        """Record that a schedule has run."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            """
            UPDATE schedules SET
                run_count = run_count + 1, last_run_at = ?, updated_at = ?
            WHERE id = ?
            """,
            (now.isoformat(), now.isoformat(), schedule_id),
        )
        await db.commit()

    async def delete(self, schedule_id: str) -> bool:
        """Delete a schedule by ID."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM schedules WHERE id = ?",
            (schedule_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_schedule(self, row) -> Schedule:
        """Convert database row to Schedule."""
        run_at = row["run_at"]
        next_run = row["next_run_at"]
        last_run = row["last_run_at"]

        return Schedule(
            id=row["id"],
            bot_id=row["bot_id"],
            name=row["name"],
            description=row["description"],
            function_id=row["function_id"],
            function_params=json.loads(row["function_params"]) if row["function_params"] else {},
            schedule_type=ScheduleType(row["schedule_type"]),
            cron_expression=row["cron_expression"],
            interval_seconds=row["interval_seconds"],
            run_at=datetime.fromisoformat(run_at) if run_at else None,
            event_trigger=row["event_trigger"],
            timezone=row["timezone"],
            enabled=bool(row["enabled"]),
            max_concurrent=row["max_concurrent"],
            catch_up=bool(row["catch_up"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            next_run_at=datetime.fromisoformat(next_run) if next_run else None,
            last_run_at=datetime.fromisoformat(last_run) if last_run else None,
            run_count=row["run_count"],
        )


class WorkRepository:
    """Repository for work (high-level objectives)."""

    async def save(self, work: Work) -> None:
        """Save a new work item."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO work
            (id, bot_id, chat_id, title, description, goal, function_id,
             schedule_id, parent_work_id, status, priority, progress,
             created_at, started_at, completed_at, due_at, result, error,
             context, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                work.id,
                work.bot_id,
                work.chat_id,
                work.title,
                work.description,
                work.goal,
                work.function_id,
                work.schedule_id,
                work.parent_work_id,
                work.status.value,
                work.priority.value,
                work.progress,
                work.created_at.isoformat(),
                work.started_at.isoformat() if work.started_at else None,
                work.completed_at.isoformat() if work.completed_at else None,
                work.due_at.isoformat() if work.due_at else None,
                json.dumps(work.result) if work.result else None,
                work.error,
                json.dumps(work.context),
                json.dumps(work.tags),
            ),
        )
        await db.commit()

    async def update(self, work: Work) -> None:
        """Update an existing work item."""
        db = await get_db()
        await db.execute(
            """
            UPDATE work SET
                title = ?, description = ?, goal = ?, status = ?, priority = ?,
                progress = ?, started_at = ?, completed_at = ?, due_at = ?,
                result = ?, error = ?, context = ?, tags = ?
            WHERE id = ?
            """,
            (
                work.title,
                work.description,
                work.goal,
                work.status.value,
                work.priority.value,
                work.progress,
                work.started_at.isoformat() if work.started_at else None,
                work.completed_at.isoformat() if work.completed_at else None,
                work.due_at.isoformat() if work.due_at else None,
                json.dumps(work.result) if work.result else None,
                work.error,
                json.dumps(work.context),
                json.dumps(work.tags),
                work.id,
            ),
        )
        await db.commit()

    async def update_status(
        self,
        work_id: str,
        status: WorkStatus,
        error: str | None = None,
    ) -> None:
        """Update work status."""
        db = await get_db()
        now = datetime.utcnow()

        if status == WorkStatus.IN_PROGRESS:
            await db.execute(
                "UPDATE work SET status = ?, started_at = ? WHERE id = ?",
                (status.value, now.isoformat(), work_id),
            )
        elif status in (WorkStatus.COMPLETED, WorkStatus.FAILED, WorkStatus.CANCELLED):
            await db.execute(
                "UPDATE work SET status = ?, completed_at = ?, error = ? WHERE id = ?",
                (status.value, now.isoformat(), error, work_id),
            )
        else:
            await db.execute(
                "UPDATE work SET status = ? WHERE id = ?",
                (status.value, work_id),
            )
        await db.commit()

    async def update_progress(self, work_id: str, progress: float) -> None:
        """Update work progress."""
        db = await get_db()
        await db.execute(
            "UPDATE work SET progress = ? WHERE id = ?",
            (progress, work_id),
        )
        await db.commit()

    async def get(self, work_id: str) -> Work | None:
        """Get a work item by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM work WHERE id = ?",
            (work_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_work(row) if row else None

    async def get_by_bot(
        self,
        bot_id: str,
        status: WorkStatus | None = None,
        limit: int = 50,
    ) -> list[Work]:
        """Get work items for a bot."""
        db = await get_db()
        if status:
            async with db.execute(
                """
                SELECT * FROM work
                WHERE bot_id = ? AND status = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (bot_id, status.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM work
                WHERE bot_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (bot_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_work(row) for row in rows]

    async def get_active(self, bot_id: str) -> list[Work]:
        """Get active (pending/in_progress) work for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work
            WHERE bot_id = ? AND status IN (?, ?)
            ORDER BY priority DESC, created_at ASC
            """,
            (bot_id, WorkStatus.PENDING.value, WorkStatus.IN_PROGRESS.value),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_work(row) for row in rows]

    async def get_by_schedule(self, schedule_id: str) -> list[Work]:
        """Get work items created by a schedule."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work
            WHERE schedule_id = ?
            ORDER BY created_at DESC
            """,
            (schedule_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_work(row) for row in rows]

    async def get_children(self, parent_work_id: str) -> list[Work]:
        """Get child work items."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work
            WHERE parent_work_id = ?
            ORDER BY created_at ASC
            """,
            (parent_work_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_work(row) for row in rows]

    async def delete(self, work_id: str) -> bool:
        """Delete a work item (cascades to tasks and jobs)."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM work WHERE id = ?",
            (work_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_work(self, row) -> Work:
        """Convert database row to Work."""
        started = row["started_at"]
        completed = row["completed_at"]
        due = row["due_at"]

        return Work(
            id=row["id"],
            bot_id=row["bot_id"],
            chat_id=row["chat_id"],
            title=row["title"],
            description=row["description"],
            goal=row["goal"],
            function_id=row["function_id"],
            schedule_id=row["schedule_id"],
            parent_work_id=row["parent_work_id"],
            status=WorkStatus(row["status"]),
            priority=Priority(row["priority"]),
            progress=row["progress"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            due_at=datetime.fromisoformat(due) if due else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            context=json.loads(row["context"]) if row["context"] else {},
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )


class TaskRepository:
    """Repository for tasks (steps within work)."""

    async def save(self, task: Task) -> None:
        """Save a new task."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO tasks
            (id, bot_id, work_id, chat_id, title, description, action,
             task_order, depends_on, status, priority, retry_count,
             max_retries, timeout_seconds, created_at, started_at,
             completed_at, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                task.id,
                task.bot_id,
                task.work_id,
                task.chat_id,
                task.title,
                task.description,
                task.action,
                task.order,
                json.dumps(task.depends_on),
                task.status.value,
                task.priority.value,
                task.retry_count,
                task.max_retries,
                task.timeout_seconds,
                task.created_at.isoformat(),
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                json.dumps(task.result) if task.result else None,
                task.error,
            ),
        )
        await db.commit()

    async def save_batch(self, tasks: list[Task]) -> None:
        """Save multiple tasks at once."""
        if not tasks:
            return
        db = await get_db()
        await db.executemany(
            """
            INSERT INTO tasks
            (id, bot_id, work_id, chat_id, title, description, action,
             task_order, depends_on, status, priority, retry_count,
             max_retries, timeout_seconds, created_at, started_at,
             completed_at, result, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    task.id,
                    task.bot_id,
                    task.work_id,
                    task.chat_id,
                    task.title,
                    task.description,
                    task.action,
                    task.order,
                    json.dumps(task.depends_on),
                    task.status.value,
                    task.priority.value,
                    task.retry_count,
                    task.max_retries,
                    task.timeout_seconds,
                    task.created_at.isoformat(),
                    task.started_at.isoformat() if task.started_at else None,
                    task.completed_at.isoformat() if task.completed_at else None,
                    json.dumps(task.result) if task.result else None,
                    task.error,
                )
                for task in tasks
            ],
        )
        await db.commit()

    async def update(self, task: Task) -> None:
        """Update an existing task."""
        db = await get_db()
        await db.execute(
            """
            UPDATE tasks SET
                title = ?, description = ?, action = ?, task_order = ?,
                depends_on = ?, status = ?, priority = ?, retry_count = ?,
                max_retries = ?, timeout_seconds = ?, started_at = ?,
                completed_at = ?, result = ?, error = ?
            WHERE id = ?
            """,
            (
                task.title,
                task.description,
                task.action,
                task.order,
                json.dumps(task.depends_on),
                task.status.value,
                task.priority.value,
                task.retry_count,
                task.max_retries,
                task.timeout_seconds,
                task.started_at.isoformat() if task.started_at else None,
                task.completed_at.isoformat() if task.completed_at else None,
                json.dumps(task.result) if task.result else None,
                task.error,
                task.id,
            ),
        )
        await db.commit()

    async def update_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str | None = None,
        result: any = None,
    ) -> None:
        """Update task status."""
        db = await get_db()
        now = datetime.utcnow()

        if status == TaskStatus.IN_PROGRESS:
            await db.execute(
                "UPDATE tasks SET status = ?, started_at = ? WHERE id = ?",
                (status.value, now.isoformat(), task_id),
            )
        elif status in (TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.SKIPPED):
            await db.execute(
                """
                UPDATE tasks SET status = ?, completed_at = ?, error = ?, result = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    now.isoformat(),
                    error,
                    json.dumps(result) if result else None,
                    task_id,
                ),
            )
        else:
            await db.execute(
                "UPDATE tasks SET status = ? WHERE id = ?",
                (status.value, task_id),
            )
        await db.commit()

    async def increment_retry(self, task_id: str) -> int:
        """Increment retry count and return new value."""
        db = await get_db()
        await db.execute(
            "UPDATE tasks SET retry_count = retry_count + 1 WHERE id = ?",
            (task_id,),
        )
        await db.commit()

        async with db.execute(
            "SELECT retry_count FROM tasks WHERE id = ?",
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["retry_count"] if row else 0

    async def get(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM tasks WHERE id = ?",
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_task(row) if row else None

    async def get_by_work(self, work_id: str) -> list[Task]:
        """Get all tasks for a work item."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM tasks
            WHERE work_id = ?
            ORDER BY task_order ASC
            """,
            (work_id,),
        ) as cursor:
            rows = await cursor.fetchall()
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
        db = await get_db()
        if status:
            async with db.execute(
                """
                SELECT * FROM tasks
                WHERE bot_id = ? AND status = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (bot_id, status.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM tasks
                WHERE bot_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (bot_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_task(row) for row in rows]

    async def delete(self, task_id: str) -> bool:
        """Delete a task (cascades to jobs)."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM tasks WHERE id = ?",
            (task_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_task(self, row) -> Task:
        """Convert database row to Task."""
        started = row["started_at"]
        completed = row["completed_at"]

        return Task(
            id=row["id"],
            bot_id=row["bot_id"],
            work_id=row["work_id"],
            chat_id=row["chat_id"],
            title=row["title"],
            description=row["description"],
            action=row["action"],
            order=row["task_order"],
            depends_on=json.loads(row["depends_on"]) if row["depends_on"] else [],
            status=TaskStatus(row["status"]),
            priority=Priority(row["priority"]),
            retry_count=row["retry_count"],
            max_retries=row["max_retries"],
            timeout_seconds=row["timeout_seconds"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
        )


class WorkJobRepository:
    """Repository for work jobs (execution attempts)."""

    async def save(self, job: Job) -> None:
        """Save a new job."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO work_jobs
            (id, bot_id, task_id, work_id, chat_id, status, attempt,
             progress, created_at, started_at, completed_at, result,
             error, logs)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.bot_id,
                job.task_id,
                job.work_id,
                job.chat_id,
                job.status.value,
                job.attempt,
                job.progress,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                json.dumps(job.result) if job.result else None,
                job.error,
                json.dumps(job.logs),
            ),
        )
        await db.commit()

    async def update(self, job: Job) -> None:
        """Update an existing job."""
        db = await get_db()
        await db.execute(
            """
            UPDATE work_jobs SET
                status = ?, progress = ?, started_at = ?, completed_at = ?,
                result = ?, error = ?, logs = ?
            WHERE id = ?
            """,
            (
                job.status.value,
                job.progress,
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                json.dumps(job.result) if job.result else None,
                job.error,
                json.dumps(job.logs),
                job.id,
            ),
        )
        await db.commit()

    async def update_status(
        self,
        job_id: str,
        status: JobStatus,
        error: str | None = None,
        result: any = None,
    ) -> None:
        """Update job status."""
        db = await get_db()
        now = datetime.utcnow()

        if status == JobStatus.RUNNING:
            await db.execute(
                "UPDATE work_jobs SET status = ?, started_at = ? WHERE id = ?",
                (status.value, now.isoformat(), job_id),
            )
        elif status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
            await db.execute(
                """
                UPDATE work_jobs SET status = ?, completed_at = ?, error = ?, result = ?
                WHERE id = ?
                """,
                (
                    status.value,
                    now.isoformat(),
                    error,
                    json.dumps(result) if result else None,
                    job_id,
                ),
            )
        else:
            await db.execute(
                "UPDATE work_jobs SET status = ? WHERE id = ?",
                (status.value, job_id),
            )
        await db.commit()

    async def update_progress(self, job_id: str, progress: float) -> None:
        """Update job progress."""
        db = await get_db()
        await db.execute(
            "UPDATE work_jobs SET progress = ? WHERE id = ?",
            (progress, job_id),
        )
        await db.commit()

    async def append_log(
        self,
        job_id: str,
        level: str,
        message: str,
        data: any = None,
    ) -> None:
        """Append a log entry to a job."""
        db = await get_db()

        # Get current logs
        async with db.execute(
            "SELECT logs FROM work_jobs WHERE id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row:
            logs = json.loads(row["logs"]) if row["logs"] else []
            logs.append(
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "level": level,
                    "message": message,
                    "data": data,
                }
            )

            await db.execute(
                "UPDATE work_jobs SET logs = ? WHERE id = ?",
                (json.dumps(logs), job_id),
            )
            await db.commit()

    async def get(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM work_jobs WHERE id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_job(row) if row else None

    async def get_by_task(self, task_id: str) -> list[Job]:
        """Get all jobs for a task."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work_jobs
            WHERE task_id = ?
            ORDER BY attempt ASC
            """,
            (task_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    async def get_by_work(self, work_id: str) -> list[Job]:
        """Get all jobs for a work item."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work_jobs
            WHERE work_id = ?
            ORDER BY created_at DESC
            """,
            (work_id,),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    async def get_latest_for_task(self, task_id: str) -> Job | None:
        """Get the latest job for a task."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM work_jobs
            WHERE task_id = ?
            ORDER BY attempt DESC LIMIT 1
            """,
            (task_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_job(row) if row else None

    async def get_running(self, bot_id: str | None = None) -> list[Job]:
        """Get all running jobs, optionally filtered by bot."""
        db = await get_db()
        if bot_id:
            async with db.execute(
                """
                SELECT * FROM work_jobs
                WHERE bot_id = ? AND status = ?
                ORDER BY started_at ASC
                """,
                (bot_id, JobStatus.RUNNING.value),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM work_jobs
                WHERE status = ?
                ORDER BY started_at ASC
                """,
                (JobStatus.RUNNING.value,),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_job(row) for row in rows]

    async def delete(self, job_id: str) -> bool:
        """Delete a job."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM work_jobs WHERE id = ?",
            (job_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_job(self, row) -> Job:
        """Convert database row to Job."""
        started = row["started_at"]
        completed = row["completed_at"]

        return Job(
            id=row["id"],
            bot_id=row["bot_id"],
            task_id=row["task_id"],
            work_id=row["work_id"],
            chat_id=row["chat_id"],
            status=JobStatus(row["status"]),
            attempt=row["attempt"],
            progress=row["progress"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            logs=json.loads(row["logs"]) if row["logs"] else [],
        )


class TodoRepository:
    """Repository for todos (reminders/notes)."""

    async def save(self, todo: Todo) -> None:
        """Save a new todo."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO todos
            (id, bot_id, chat_id, title, notes, status, priority,
             created_at, completed_at, remind_at, converted_to_work_id,
             converted_to_task_id, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                todo.id,
                todo.bot_id,
                todo.chat_id,
                todo.title,
                todo.notes,
                todo.status.value,
                todo.priority.value,
                todo.created_at.isoformat(),
                todo.completed_at.isoformat() if todo.completed_at else None,
                todo.remind_at.isoformat() if todo.remind_at else None,
                todo.converted_to_work_id,
                todo.converted_to_task_id,
                json.dumps(todo.tags),
            ),
        )
        await db.commit()

    async def update(self, todo: Todo) -> None:
        """Update an existing todo."""
        db = await get_db()
        await db.execute(
            """
            UPDATE todos SET
                title = ?, notes = ?, status = ?, priority = ?,
                completed_at = ?, remind_at = ?, converted_to_work_id = ?,
                converted_to_task_id = ?, tags = ?
            WHERE id = ?
            """,
            (
                todo.title,
                todo.notes,
                todo.status.value,
                todo.priority.value,
                todo.completed_at.isoformat() if todo.completed_at else None,
                todo.remind_at.isoformat() if todo.remind_at else None,
                todo.converted_to_work_id,
                todo.converted_to_task_id,
                json.dumps(todo.tags),
                todo.id,
            ),
        )
        await db.commit()

    async def update_status(self, todo_id: str, status: TodoStatus) -> None:
        """Update todo status."""
        db = await get_db()
        now = datetime.utcnow()

        if status == TodoStatus.DONE:
            await db.execute(
                "UPDATE todos SET status = ?, completed_at = ? WHERE id = ?",
                (status.value, now.isoformat(), todo_id),
            )
        else:
            await db.execute(
                "UPDATE todos SET status = ?, completed_at = NULL WHERE id = ?",
                (status.value, todo_id),
            )
        await db.commit()

    async def mark_converted(
        self,
        todo_id: str,
        work_id: str | None = None,
        task_id: str | None = None,
    ) -> None:
        """Mark a todo as converted to work or task."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            """
            UPDATE todos SET
                status = ?, completed_at = ?,
                converted_to_work_id = ?, converted_to_task_id = ?
            WHERE id = ?
            """,
            (
                TodoStatus.DONE.value,
                now.isoformat(),
                work_id,
                task_id,
                todo_id,
            ),
        )
        await db.commit()

    async def get(self, todo_id: str) -> Todo | None:
        """Get a todo by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM todos WHERE id = ?",
            (todo_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return self._row_to_todo(row) if row else None

    async def get_by_bot(
        self,
        bot_id: str,
        status: TodoStatus | None = None,
        limit: int = 50,
    ) -> list[Todo]:
        """Get todos for a bot."""
        db = await get_db()
        if status:
            async with db.execute(
                """
                SELECT * FROM todos
                WHERE bot_id = ? AND status = ?
                ORDER BY priority DESC, created_at DESC LIMIT ?
                """,
                (bot_id, status.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM todos
                WHERE bot_id = ?
                ORDER BY priority DESC, created_at DESC LIMIT ?
                """,
                (bot_id, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        return [self._row_to_todo(row) for row in rows]

    async def get_open(self, bot_id: str) -> list[Todo]:
        """Get open todos for a bot."""
        return await self.get_by_bot(bot_id, status=TodoStatus.OPEN)

    async def get_due_reminders(self) -> list[Todo]:
        """Get todos with reminders that are due."""
        db = await get_db()
        now = datetime.utcnow().isoformat()
        async with db.execute(
            """
            SELECT * FROM todos
            WHERE status = ? AND remind_at IS NOT NULL AND remind_at <= ?
            ORDER BY remind_at ASC
            """,
            (TodoStatus.OPEN.value, now),
        ) as cursor:
            rows = await cursor.fetchall()
        return [self._row_to_todo(row) for row in rows]

    async def delete(self, todo_id: str) -> bool:
        """Delete a todo."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM todos WHERE id = ?",
            (todo_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_todo(self, row) -> Todo:
        """Convert database row to Todo."""
        completed = row["completed_at"]
        remind = row["remind_at"]

        return Todo(
            id=row["id"],
            bot_id=row["bot_id"],
            chat_id=row["chat_id"],
            title=row["title"],
            notes=row["notes"],
            status=TodoStatus(row["status"]),
            priority=Priority(row["priority"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=datetime.fromisoformat(completed) if completed else None,
            remind_at=datetime.fromisoformat(remind) if remind else None,
            converted_to_work_id=row["converted_to_work_id"],
            converted_to_task_id=row["converted_to_task_id"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
        )

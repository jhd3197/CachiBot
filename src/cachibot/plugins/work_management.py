"""
Work management plugin — work_create, work_list, work_update, todo_create, todo_list, todo_done.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class WorkManagementPlugin(CachibotPlugin):
    """Provides work items and todo management tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("work_management", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="work_management",
            display_name="Work Management",
            icon="briefcase",
            group="Core",
        )

    def _get_bot_id(self) -> str | None:
        return self.ctx.bot_id

    def _get_chat_id(self) -> str | None:
        return self.ctx.chat_id

    def _build_skills(self) -> dict[str, Skill]:
        get_bot_id = self._get_bot_id
        get_chat_id = self._get_chat_id

        @skill(
            name="work_create",
            description="Create a new work item with optional tasks. "
            "Use this to create structured work that can be tracked and executed.",
            category="work",
            tags=["work", "create"],
            is_async=True,
            side_effects=True,
            display_name="Create Work",
            icon="briefcase",
            risk_level=RiskLevel.SAFE,
        )
        async def work_create(
            title: str,
            description: str = "",
            goal: str = "",
            priority: str = "normal",
            tasks: list[str] | None = None,
        ) -> str:
            """Create a new work item with optional tasks.

            Args:
                title: Title of the work item
                description: Detailed description of what needs to be done
                goal: The end goal or success criteria
                priority: Priority level (low, normal, high, urgent)
                tasks: Optional list of task titles to create with the work

            Returns:
                JSON with the created work ID and details
            """
            import json
            import uuid
            from datetime import datetime

            from cachibot.models.work import Priority, Task, TaskStatus, Work, WorkStatus
            from cachibot.storage.work_repository import TaskRepository, WorkRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                work_repo = WorkRepository()
                task_repo = TaskRepository()

                work = Work(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    title=title,
                    description=description or None,
                    goal=goal or None,
                    priority=Priority(priority) if priority else Priority.NORMAL,
                    status=WorkStatus.PENDING,
                    progress=0.0,
                    created_at=datetime.utcnow(),
                    context={},
                    tags=[],
                )
                await work_repo.save(work)

                created_tasks = []
                if tasks:
                    for i, task_title in enumerate(tasks):
                        task = Task(
                            id=str(uuid.uuid4()),
                            bot_id=bot_id,
                            work_id=work.id,
                            title=task_title,
                            order=i,
                            depends_on=[],
                            status=TaskStatus.PENDING,
                            priority=Priority.NORMAL,
                            retry_count=0,
                            max_retries=3,
                            created_at=datetime.utcnow(),
                        )
                        await task_repo.save(task)
                        created_tasks.append({"id": task.id, "title": task.title})

                return json.dumps(
                    {
                        "id": work.id,
                        "title": work.title,
                        "status": work.status.value,
                        "tasks": created_tasks,
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error creating work: {e}"

        @skill(
            name="work_list",
            description="List work items for this bot.",
            category="work",
            tags=["work", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Work",
            icon="clipboard-list",
            risk_level=RiskLevel.SAFE,
        )
        async def work_list(status: str = "all", limit: int = 10) -> str:
            """List work items for this bot.

            Args:
                status: Filter by status (all, pending, in_progress, completed, failed)
                limit: Maximum number of items to return

            Returns:
                JSON list of work items with their status and progress
            """
            import json

            from cachibot.models.work import WorkStatus
            from cachibot.storage.work_repository import WorkRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                work_repo = WorkRepository()
                status_filter = None if status == "all" else WorkStatus(status)
                items = await work_repo.get_by_bot(bot_id, status=status_filter, limit=limit)
                result = [
                    {
                        "id": w.id,
                        "title": w.title,
                        "status": w.status.value,
                        "priority": w.priority.value,
                        "progress": w.progress,
                        "created_at": w.created_at.isoformat(),
                    }
                    for w in items
                ]
                if not result:
                    return "No work items found"
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing work: {e}"

        @skill(
            name="work_update",
            description="Update a work item's status or progress.",
            category="work",
            tags=["work", "update"],
            is_async=True,
            side_effects=True,
            display_name="Update Work",
            icon="clipboard-plus",
            risk_level=RiskLevel.SAFE,
        )
        async def work_update(
            work_id: str,
            status: str | None = None,
            progress: int | None = None,
            result: str | None = None,
            error: str | None = None,
        ) -> str:
            """Update a work item's status or progress.

            Args:
                work_id: The ID of the work to update
                status: New status (pending, in_progress, completed, failed, cancelled, paused)
                progress: Progress percentage (0-100)
                result: Result data when completing
                error: Error message when failing

            Returns:
                Updated work details
            """
            import json

            from cachibot.models.work import WorkStatus
            from cachibot.storage.work_repository import WorkRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                work_repo = WorkRepository()
                work = await work_repo.get(work_id)
                if not work:
                    return json.dumps({"error": f"Work {work_id} not found"}, indent=2)

                if status:
                    await work_repo.update_status(work_id, WorkStatus(status), error)

                if progress is not None:
                    await work_repo.update_progress(work_id, float(progress))

                updated_work = await work_repo.get(work_id)
                return json.dumps(
                    {
                        "id": updated_work.id,
                        "title": updated_work.title,
                        "status": updated_work.status.value,
                        "progress": updated_work.progress,
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error updating work: {e}"

        @skill(
            name="todo_create",
            description="Create a todo or timed reminder. "
            "Use this to capture ideas, reminders, or tasks for later. "
            "Set remind_at to get a notification delivered at a specific time.",
            category="work",
            tags=["todo", "create", "reminder"],
            is_async=True,
            side_effects=True,
            display_name="Create Todo",
            icon="list-todo",
            risk_level=RiskLevel.SAFE,
        )
        async def todo_create(
            title: str,
            notes: str = "",
            priority: str = "normal",
            remind_at: str | None = None,
        ) -> str:
            """Create a todo or timed reminder.

            Args:
                title: Brief title of the todo
                notes: Additional notes or context
                priority: Priority level (low, normal, high, urgent)
                remind_at: Optional ISO datetime to remind (e.g., "2024-01-15T09:00:00").
                    When set, a notification will be delivered at the specified time.

            Returns:
                JSON with the created todo ID and details
            """
            import json
            import uuid
            from datetime import datetime

            from cachibot.models.work import Priority, Todo, TodoStatus
            from cachibot.storage.work_repository import TodoRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                todo_repo = TodoRepository()
                remind_datetime = None
                if remind_at:
                    try:
                        remind_datetime = datetime.fromisoformat(remind_at)
                    except ValueError:
                        return f"Error: Invalid datetime format: {remind_at}"

                todo = Todo(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    chat_id=get_chat_id(),
                    title=title,
                    notes=notes or None,
                    status=TodoStatus.OPEN,
                    priority=Priority(priority) if priority else Priority.NORMAL,
                    created_at=datetime.utcnow(),
                    remind_at=remind_datetime,
                    tags=[],
                )
                await todo_repo.save(todo)
                result = {
                    "id": todo.id,
                    "title": todo.title,
                    "priority": todo.priority.value,
                    "remind_at": todo.remind_at.isoformat() if todo.remind_at else None,
                }
                if remind_datetime:
                    result["reminder_scheduled"] = True
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error creating todo: {e}"

        @skill(
            name="todo_list",
            description="List todos for this bot.",
            category="work",
            tags=["todo", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Todos",
            icon="list-checks",
            risk_level=RiskLevel.SAFE,
        )
        async def todo_list(status: str = "open", limit: int = 20) -> str:
            """List todos for this bot.

            Args:
                status: Filter by status (all, open, done, dismissed)
                limit: Maximum number of items to return

            Returns:
                JSON list of todos
            """
            import json

            from cachibot.models.work import TodoStatus
            from cachibot.storage.work_repository import TodoRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                todo_repo = TodoRepository()
                status_filter = None if status == "all" else TodoStatus(status)
                items = await todo_repo.get_by_bot(bot_id, status=status_filter, limit=limit)
                result = [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status.value,
                        "priority": t.priority.value,
                        "remind_at": t.remind_at.isoformat() if t.remind_at else None,
                    }
                    for t in items
                ]
                if not result:
                    return "No todos found"
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing todos: {e}"

        @skill(
            name="todo_done",
            description="Mark a todo as done.",
            category="work",
            tags=["todo", "done"],
            is_async=True,
            side_effects=True,
            display_name="Complete Todo",
            icon="circle-check",
            risk_level=RiskLevel.SAFE,
        )
        async def todo_done(todo_id: str) -> str:
            """Mark a todo as done.

            Args:
                todo_id: The ID of the todo to complete

            Returns:
                Confirmation message
            """
            from cachibot.models.work import TodoStatus
            from cachibot.storage.work_repository import TodoRepository

            try:
                todo_repo = TodoRepository()
                todo = await todo_repo.get(todo_id)
                if not todo:
                    return f"Error: Todo {todo_id} not found"
                await todo_repo.update_status(todo_id, TodoStatus.DONE)
                return f"Todo '{todo.title}' marked as done"
            except Exception as e:
                return f"Error marking todo done: {e}"

        @skill(
            name="schedule_create",
            description="Schedule a one-time or recurring action. "
            "Use this to set reminders, schedule messages, or plan future tasks. "
            "For one-time actions, provide run_at. For recurring, provide interval_seconds "
            "or cron_expression.",
            category="work",
            tags=["schedule", "create", "timer", "reminder", "cron"],
            is_async=True,
            side_effects=True,
            display_name="Create Schedule",
            icon="clock",
            risk_level=RiskLevel.SAFE,
        )
        async def schedule_create(
            name: str,
            message: str,
            run_at: str | None = None,
            interval_seconds: int | None = None,
            cron_expression: str | None = None,
        ) -> str:
            """Schedule a one-time or recurring action.

            Args:
                name: Name/title for this schedule
                message: The message to deliver when the schedule fires
                run_at: ISO datetime for one-time execution (e.g., "2024-01-15T09:00:00")
                interval_seconds: Repeat every N seconds (e.g., 3600 for hourly)
                cron_expression: Cron expression for complex schedules (e.g., "0 9 * * 1-5")

            Returns:
                JSON with the created schedule ID and details
            """
            import json
            import uuid
            from datetime import datetime, timedelta

            from cachibot.models.work import Schedule, ScheduleType
            from cachibot.storage.work_repository import ScheduleRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            # Determine schedule type and validate
            if run_at:
                schedule_type = ScheduleType.ONCE
                try:
                    run_at_dt = datetime.fromisoformat(run_at)
                except ValueError:
                    return f"Error: Invalid datetime format: {run_at}"
                next_run_at = run_at_dt
            elif interval_seconds:
                schedule_type = ScheduleType.INTERVAL
                if interval_seconds < 60:
                    return "Error: Minimum interval is 60 seconds"
                run_at_dt = None
                next_run_at = datetime.utcnow() + timedelta(seconds=interval_seconds)
            elif cron_expression:
                schedule_type = ScheduleType.CRON
                try:
                    from croniter import croniter

                    cron = croniter(cron_expression, datetime.utcnow())
                    next_run_at = cron.get_next(datetime)
                except (ValueError, KeyError) as e:
                    return f"Error: Invalid cron expression: {e}"
                run_at_dt = None
            else:
                return "Error: Provide run_at, interval_seconds, or cron_expression"

            try:
                schedule_repo = ScheduleRepository()
                now = datetime.utcnow()
                schedule = Schedule(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    name=name,
                    description=message,
                    function_id=None,
                    function_params={"message": message, "chat_id": get_chat_id()},
                    schedule_type=schedule_type,
                    cron_expression=cron_expression,
                    interval_seconds=interval_seconds,
                    run_at=run_at_dt,
                    timezone="UTC",
                    enabled=True,
                    max_concurrent=1,
                    catch_up=False,
                    created_at=now,
                    updated_at=now,
                    next_run_at=next_run_at,
                    last_run_at=None,
                    run_count=0,
                )
                await schedule_repo.save(schedule)
                return json.dumps(
                    {
                        "id": schedule.id,
                        "name": schedule.name,
                        "type": schedule.schedule_type.value,
                        "next_run_at": next_run_at.isoformat() if next_run_at else None,
                        "enabled": True,
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error creating schedule: {e}"

        @skill(
            name="schedule_list",
            description="List scheduled actions for this bot.",
            category="work",
            tags=["schedule", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Schedules",
            icon="clock",
            risk_level=RiskLevel.SAFE,
        )
        async def schedule_list(enabled_only: bool = False) -> str:
            """List scheduled actions for this bot.

            Args:
                enabled_only: If True, only show enabled schedules

            Returns:
                JSON list of schedules
            """
            import json

            from cachibot.storage.work_repository import ScheduleRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                schedule_repo = ScheduleRepository()
                items = await schedule_repo.get_by_bot(bot_id)
                if enabled_only:
                    items = [s for s in items if s.enabled]
                result = [
                    {
                        "id": s.id,
                        "name": s.name,
                        "type": s.schedule_type.value,
                        "enabled": s.enabled,
                        "next_run_at": s.next_run_at.isoformat() if s.next_run_at else None,
                        "run_count": s.run_count,
                    }
                    for s in items
                ]
                if not result:
                    return "No schedules found"
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing schedules: {e}"

        @skill(
            name="schedule_delete",
            description="Delete a scheduled action.",
            category="work",
            tags=["schedule", "delete"],
            is_async=True,
            side_effects=True,
            display_name="Delete Schedule",
            icon="clock",
            risk_level=RiskLevel.SAFE,
        )
        async def schedule_delete(schedule_id: str) -> str:
            """Delete a scheduled action.

            Args:
                schedule_id: The ID of the schedule to delete

            Returns:
                Confirmation message
            """
            from cachibot.storage.work_repository import ScheduleRepository

            try:
                schedule_repo = ScheduleRepository()
                deleted = await schedule_repo.delete(schedule_id)
                if deleted:
                    return f"Schedule {schedule_id} deleted"
                return f"Error: Schedule {schedule_id} not found"
            except Exception as e:
                return f"Error deleting schedule: {e}"

        return {
            "work_create": work_create.__skill__,
            "work_list": work_list.__skill__,
            "work_update": work_update.__skill__,
            "todo_create": todo_create.__skill__,
            "todo_list": todo_list.__skill__,
            "todo_done": todo_done.__skill__,
            "schedule_create": schedule_create.__skill__,
            "schedule_list": schedule_list.__skill__,
            "schedule_delete": schedule_delete.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

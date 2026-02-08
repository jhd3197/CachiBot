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

    def _build_skills(self) -> dict[str, Skill]:
        get_bot_id = self._get_bot_id

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
            description="Create a todo/reminder for later. "
            "Use this to capture ideas, reminders, or tasks that should be "
            "addressed later but don't need immediate structured work.",
            category="work",
            tags=["todo", "create"],
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
            """Create a todo/reminder for later.

            Args:
                title: Brief title of the todo
                notes: Additional notes or context
                priority: Priority level (low, normal, high, urgent)
                remind_at: Optional ISO datetime to remind (e.g., "2024-01-15T09:00:00")

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
                        pass

                todo = Todo(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    title=title,
                    notes=notes or None,
                    status=TodoStatus.OPEN,
                    priority=Priority(priority) if priority else Priority.NORMAL,
                    created_at=datetime.utcnow(),
                    remind_at=remind_datetime,
                    tags=[],
                )
                await todo_repo.save(todo)
                return json.dumps(
                    {
                        "id": todo.id,
                        "title": todo.title,
                        "priority": todo.priority.value,
                        "remind_at": todo.remind_at.isoformat() if todo.remind_at else None,
                    },
                    indent=2,
                )
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

        return {
            "work_create": work_create.__skill__,
            "work_list": work_list.__skill__,
            "work_update": work_update.__skill__,
            "todo_create": todo_create.__skill__,
            "todo_list": todo_list.__skill__,
            "todo_done": todo_done.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

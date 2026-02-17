"""
Job management plugin — job_create, job_status, job_cancel, job_list.

Provides LLM tools for creating and managing background jobs (Work + Tasks)
that the JobRunnerService picks up and executes asynchronously.

.. deprecated::
    This plugin overlaps with ``WorkManagementPlugin``. Its skills
    (job_create, job_status, job_cancel, job_list) will be merged into
    ``work_management.py`` in a future release. For new integrations,
    use the work management skills directly.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class JobToolsPlugin(CachibotPlugin):
    """Provides background job management tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("job_tools", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="job_tools",
            display_name="Job Tools",
            icon="play-circle",
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
            name="job_create",
            description="Create a background job (work item with tasks) that runs asynchronously. "
            "Use this for long-running or multi-step tasks that should not block the conversation.",
            category="work",
            tags=["job", "create", "background"],
            is_async=True,
            side_effects=True,
            display_name="Create Job",
            icon="play-circle",
            risk_level=RiskLevel.SAFE,
        )
        async def job_create(
            title: str,
            description: str = "",
            goal: str = "",
            priority: str = "normal",
            tasks: list[str] | None = None,
        ) -> str:
            """Create a background job with optional tasks.

            Args:
                title: Title of the job
                description: Detailed description of what needs to be done
                goal: The end goal or success criteria
                priority: Priority level (low, normal, high, urgent)
                tasks: List of task descriptions to execute in order

            Returns:
                JSON with the created work ID and task details
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
                    chat_id=get_chat_id(),
                    title=title,
                    description=description or None,
                    goal=goal or None,
                    priority=Priority(priority) if priority else Priority.NORMAL,
                    status=WorkStatus.PENDING,
                    progress=0.0,
                    created_at=datetime.utcnow(),
                    context={},
                    tags=["job"],
                )
                await work_repo.save(work)

                created_tasks = []
                if tasks:
                    for i, task_desc in enumerate(tasks):
                        task = Task(
                            id=str(uuid.uuid4()),
                            bot_id=bot_id,
                            work_id=work.id,
                            title=task_desc,
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
                        "priority": work.priority.value,
                        "tasks": created_tasks,
                        "message": "Job created. The runner will pick it up automatically.",
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error creating job: {e}"

        @skill(
            name="job_status",
            description="Check the status of a background job (work item) and its tasks.",
            category="work",
            tags=["job", "status"],
            is_async=True,
            idempotent=True,
            display_name="Job Status",
            icon="activity",
            risk_level=RiskLevel.SAFE,
        )
        async def job_status(work_id: str) -> str:
            """Check the status of a work item and its tasks/jobs.

            Args:
                work_id: The ID of the work item to check

            Returns:
                JSON with work status, progress, task statuses, and latest job logs
            """
            import json

            from cachibot.models.work import TaskStatus
            from cachibot.storage.work_repository import (
                TaskRepository,
                WorkJobRepository,
                WorkRepository,
            )

            try:
                work_repo = WorkRepository()
                task_repo = TaskRepository()
                job_repo = WorkJobRepository()

                work = await work_repo.get(work_id)
                if not work:
                    return json.dumps({"error": f"Work {work_id} not found"}, indent=2)

                tasks = await task_repo.get_by_work(work_id)
                completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)

                task_info = [
                    {
                        "id": t.id,
                        "title": t.title,
                        "status": t.status.value,
                        "order": t.order,
                        "error": t.error,
                    }
                    for t in tasks
                ]

                # Get latest job logs
                jobs = await job_repo.get_by_work(work_id)
                latest_logs = []
                if jobs:
                    latest_job = jobs[0]
                    latest_logs = latest_job.logs[-5:] if latest_job.logs else []

                return json.dumps(
                    {
                        "id": work.id,
                        "title": work.title,
                        "status": work.status.value,
                        "priority": work.priority.value,
                        "progress": work.progress,
                        "tasks_total": len(tasks),
                        "tasks_completed": completed,
                        "tasks": task_info,
                        "latest_logs": latest_logs,
                        "error": work.error,
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error checking job status: {e}"

        @skill(
            name="job_cancel",
            description="Cancel a running background job.",
            category="work",
            tags=["job", "cancel"],
            is_async=True,
            side_effects=True,
            display_name="Cancel Job",
            icon="x-circle",
            risk_level=RiskLevel.SAFE,
        )
        async def job_cancel(work_id: str) -> str:
            """Cancel a running work item and its jobs.

            Args:
                work_id: The ID of the work item to cancel

            Returns:
                Confirmation message
            """
            import json

            from cachibot.storage.work_repository import WorkRepository

            try:
                work_repo = WorkRepository()
                work = await work_repo.get(work_id)
                if not work:
                    return json.dumps({"error": f"Work {work_id} not found"}, indent=2)

                # Use the job runner to cancel (handles stopping running jobs)
                try:
                    from cachibot.services.job_runner import get_job_runner

                    runner = get_job_runner()
                    await runner.cancel_work(work_id)
                except (ImportError, RuntimeError):
                    # Runner not available, just update status directly
                    from cachibot.models.work import WorkStatus

                    await work_repo.update_status(work_id, WorkStatus.CANCELLED)

                return json.dumps(
                    {
                        "id": work.id,
                        "title": work.title,
                        "status": "cancelled",
                        "message": "Job cancelled successfully.",
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error cancelling job: {e}"

        @skill(
            name="job_list",
            description="List background jobs for this bot.",
            category="work",
            tags=["job", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Jobs",
            icon="list",
            risk_level=RiskLevel.SAFE,
        )
        async def job_list(status: str = "all", limit: int = 10) -> str:
            """List background jobs (work items) for this bot.

            Args:
                status: Filter by status (all, pending, in_progress, completed, failed, cancelled)
                limit: Maximum number of items to return

            Returns:
                JSON list of jobs with their status and progress
            """
            import json

            from cachibot.models.work import WorkStatus
            from cachibot.storage.work_repository import TaskRepository, WorkRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                work_repo = WorkRepository()
                task_repo = TaskRepository()
                status_filter = None if status == "all" else WorkStatus(status)
                items = await work_repo.get_by_bot(bot_id, status=status_filter, limit=limit)

                result = []
                for w in items:
                    tasks = await task_repo.get_by_work(w.id)
                    from cachibot.models.work import TaskStatus

                    completed = sum(1 for t in tasks if t.status == TaskStatus.COMPLETED)
                    result.append(
                        {
                            "id": w.id,
                            "title": w.title,
                            "status": w.status.value,
                            "priority": w.priority.value,
                            "progress": w.progress,
                            "tasks_total": len(tasks),
                            "tasks_completed": completed,
                            "created_at": w.created_at.isoformat(),
                            "error": w.error,
                        }
                    )

                if not result:
                    return "No jobs found"
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing jobs: {e}"

        return {
            "job_create": job_create.__skill__,
            "job_status": job_status.__skill__,
            "job_cancel": job_cancel.__skill__,
            "job_list": job_list.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

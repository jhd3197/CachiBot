"""
Job Runner Service

Background async loop that polls for pending Work items, resolves ready tasks,
creates Job execution records, runs them through CachibotAgent, and broadcasts
progress via WebSocket.
"""

import asyncio
import copy
import logging
import uuid

from cachibot.config import Config
from cachibot.models.work import (
    Job,
    JobStatus,
    TaskStatus,
    Work,
    WorkStatus,
)
from cachibot.storage.work_repository import (
    TaskRepository,
    WorkJobRepository,
    WorkRepository,
)

logger = logging.getLogger(__name__)

# How often the runner checks for pending work (seconds)
_POLL_INTERVAL = 10

# Maximum concurrent job executions
_MAX_CONCURRENT_JOBS = 5


class JobRunnerService:
    """Background service that executes Work tasks as Jobs via CachibotAgent."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False

        # Repositories
        self._work_repo = WorkRepository()
        self._task_repo = TaskRepository()
        self._job_repo = WorkJobRepository()

        # Track running asyncio.Tasks keyed by job_id for cancellation
        self._running_jobs: dict[str, asyncio.Task] = {}

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Start the job runner background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Job runner service started (poll every %ds)", _POLL_INTERVAL)

    async def stop(self) -> None:
        """Stop the job runner background loop and cancel all running jobs."""
        self._running = False
        # Cancel all running jobs
        for job_id, task in list(self._running_jobs.items()):
            task.cancel()
            logger.info("Cancelled running job %s during shutdown", job_id)
        self._running_jobs.clear()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Job runner service stopped")

    # ------------------------------------------------------------------
    # Main Loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._process_pending_work()
            except Exception:
                logger.exception("Error in job runner loop")

            # Clean up finished job handles
            finished = [jid for jid, t in self._running_jobs.items() if t.done()]
            for jid in finished:
                self._running_jobs.pop(jid, None)

            await asyncio.sleep(_POLL_INTERVAL)

    async def _process_pending_work(self) -> None:
        """Find all active work and dispatch ready tasks."""
        from cachibot.storage.repository import BotRepository

        bot_repo = BotRepository()

        # Get all bots, then collect active work across all of them
        all_bots = await bot_repo.get_all_bots()
        for bot in all_bots:
            active_work = await self._work_repo.get_active(bot.id)
            for work in active_work:
                try:
                    await self._process_work(work)
                except Exception:
                    logger.exception("Error processing work %s", work.id)

    async def _process_work(self, work: Work) -> None:
        """Process a single work item: find ready tasks and dispatch them."""
        ready_tasks = await self._task_repo.get_ready_tasks(work.id)
        if not ready_tasks:
            return

        for task in ready_tasks:
            # Enforce concurrency limit
            if len(self._running_jobs) >= _MAX_CONCURRENT_JOBS:
                logger.debug(
                    "Concurrency limit reached (%d), deferring task %s",
                    _MAX_CONCURRENT_JOBS,
                    task.id,
                )
                return

            # Create a Job record
            job = Job(
                id=str(uuid.uuid4()),
                bot_id=task.bot_id,
                task_id=task.id,
                work_id=work.id,
                chat_id=task.chat_id,
                status=JobStatus.PENDING,
                attempt=task.retry_count + 1,
            )
            await self._job_repo.save(job)

            # Launch execution
            exec_task = asyncio.create_task(
                self._execute_job(job, task, work),
            )
            self._running_jobs[job.id] = exec_task

    # ------------------------------------------------------------------
    # Job Execution
    # ------------------------------------------------------------------

    async def _execute_job(self, job: Job, task, work: Work) -> None:
        """Execute a single job through CachibotAgent."""
        try:
            # Mark job as RUNNING
            await self._job_repo.update_status(job.id, JobStatus.RUNNING)
            await self._job_repo.append_log(job.id, "info", "Job started")

            # Mark task as IN_PROGRESS
            await self._task_repo.update_status(task.id, TaskStatus.IN_PROGRESS)

            # Mark work as IN_PROGRESS if still pending
            if work.status == WorkStatus.PENDING:
                await self._work_repo.update_status(work.id, WorkStatus.IN_PROGRESS)

            # Broadcast status
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job.id,
                status="running",
                progress=work.progress,
            )

            # Create agent and run
            result_text = await self._run_agent_for_task(job, task)

            # Job completed successfully
            await self._job_repo.update_status(job.id, JobStatus.COMPLETED, result=result_text)
            await self._job_repo.append_log(job.id, "info", "Job completed")
            await self._task_repo.update_status(task.id, TaskStatus.COMPLETED, result=result_text)

            # Update work progress
            await self._update_work_progress(work.id)

            # Broadcast success
            updated_work = await self._work_repo.get(work.id)
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job.id,
                status="completed",
                progress=updated_work.progress if updated_work else 1.0,
            )

        except asyncio.CancelledError:
            # Job was cancelled externally
            await self._job_repo.update_status(job.id, JobStatus.CANCELLED, error="Cancelled")
            await self._job_repo.append_log(job.id, "warn", "Job cancelled")
            await self._task_repo.update_status(
                task.id, TaskStatus.PENDING, error="Cancelled, will retry"
            )
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job.id,
                status="cancelled",
                progress=work.progress,
            )

        except asyncio.TimeoutError:
            timeout = task.timeout_seconds or "unknown"
            error_msg = f"Timeout after {timeout} seconds"
            await self._job_repo.update_status(job.id, JobStatus.FAILED, error=error_msg)
            await self._job_repo.append_log(job.id, "error", error_msg)
            await self._handle_task_failure(task, work, job.id, error_msg)

        except Exception as exc:
            error_msg = str(exc)
            await self._job_repo.update_status(job.id, JobStatus.FAILED, error=error_msg)
            await self._job_repo.append_log(job.id, "error", f"Job failed: {error_msg}")
            await self._handle_task_failure(task, work, job.id, error_msg)

        finally:
            self._running_jobs.pop(job.id, None)

    async def _run_agent_for_task(self, job: Job, task) -> str:
        """Create a CachibotAgent and run the task action through it."""
        from cachibot.agent import CachibotAgent
        from cachibot.storage.repository import BotRepository

        bot_repo = BotRepository()
        bot = await bot_repo.get_bot(task.bot_id)

        if not bot:
            raise RuntimeError(f"Bot {task.bot_id} not found")

        config = Config.load()

        # Apply bot model override
        if bot.models and bot.models.get("default"):
            config = copy.deepcopy(config)
            config.agent.model = bot.models["default"]
        elif bot.model:
            config = copy.deepcopy(config)
            config.agent.model = bot.model

        agent = CachibotAgent(
            config=config,
            system_prompt_override=bot.system_prompt,
            capabilities=bot.capabilities,
            bot_id=bot.id,
            chat_id=task.chat_id,
            bot_models=bot.models,
        )

        # Build the user message from task action
        action = task.action or task.title
        if task.description:
            action = f"{action}\n\nDetails: {task.description}"

        # Wrap in timeout if configured
        if task.timeout_seconds:
            result = await asyncio.wait_for(agent.run(action), timeout=task.timeout_seconds)
        else:
            result = await agent.run(action)

        return result.output_text or ""

    # ------------------------------------------------------------------
    # Failure Handling
    # ------------------------------------------------------------------

    async def _handle_task_failure(
        self,
        task,
        work: Work,
        job_id: str,
        error_msg: str,
    ) -> None:
        """Handle a failed task: retry or mark as permanently failed."""
        new_count = await self._task_repo.increment_retry(task.id)

        if new_count < task.max_retries:
            # Leave as PENDING for next poll to pick up
            await self._task_repo.update_status(task.id, TaskStatus.PENDING, error=error_msg)
            logger.info(
                "Task %s failed (attempt %d/%d), will retry",
                task.id,
                new_count,
                task.max_retries,
            )
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job_id,
                status="retrying",
                progress=work.progress,
                error=error_msg,
            )
        else:
            # Max retries exceeded — mark task and work as failed
            await self._task_repo.update_status(task.id, TaskStatus.FAILED, error=error_msg)
            await self._work_repo.update_status(
                work.id, WorkStatus.FAILED, error=f"Task '{task.title}' failed: {error_msg}"
            )
            logger.error(
                "Task %s permanently failed after %d attempts, work %s marked FAILED",
                task.id,
                new_count,
                work.id,
            )
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job_id,
                status="failed",
                progress=work.progress,
                error=error_msg,
            )

    # ------------------------------------------------------------------
    # Progress Tracking
    # ------------------------------------------------------------------

    async def _update_work_progress(self, work_id: str) -> None:
        """Recalculate and update work progress based on completed tasks."""
        all_tasks = await self._task_repo.get_by_work(work_id)
        if not all_tasks:
            return

        completed = sum(1 for t in all_tasks if t.status == TaskStatus.COMPLETED)
        total = len(all_tasks)
        progress = completed / total

        await self._work_repo.update_progress(work_id, progress)

        # If all tasks are done, mark work as completed
        if completed == total:
            await self._work_repo.update_status(work_id, WorkStatus.COMPLETED)
            logger.info("Work %s completed (all %d tasks done)", work_id, total)

    # ------------------------------------------------------------------
    # Cancellation
    # ------------------------------------------------------------------

    async def cancel_job(self, job_id: str) -> bool:
        """Cancel a running job by its ID."""
        if task := self._running_jobs.get(job_id):
            task.cancel()
            self._running_jobs.pop(job_id, None)
            logger.info("Cancelled job %s", job_id)
            return True
        return False

    async def cancel_work(self, work_id: str) -> int:
        """Cancel all running jobs for a work item. Returns count cancelled."""
        cancelled = 0
        # Find all running jobs for this work
        jobs = await self._job_repo.get_by_work(work_id)
        for job in jobs:
            if job.status == JobStatus.RUNNING and job.id in self._running_jobs:
                self._running_jobs[job.id].cancel()
                self._running_jobs.pop(job.id, None)
                cancelled += 1

        # Mark work as cancelled
        if cancelled > 0:
            await self._work_repo.update_status(
                work_id, WorkStatus.CANCELLED, error="Cancelled by user"
            )
            await self._broadcast_update(
                work_id=work_id,
                status="cancelled",
            )

        return cancelled

    # ------------------------------------------------------------------
    # WebSocket Broadcasting
    # ------------------------------------------------------------------

    async def _broadcast_update(
        self,
        work_id: str,
        task_id: str | None = None,
        job_id: str | None = None,
        status: str = "",
        progress: float = 0.0,
        error: str | None = None,
        logs: list[dict] | None = None,
    ) -> None:
        """Broadcast a JOB_UPDATE message to all connected WebSocket clients."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.job_update(
                work_id=work_id,
                task_id=task_id,
                job_id=job_id,
                status=status,
                progress=progress,
                error=error,
                logs=logs,
            )
            await ws.broadcast(msg)
        except Exception:
            logger.debug("Could not broadcast job update to WebSocket")


# Singleton
_job_runner: JobRunnerService | None = None


def get_job_runner() -> JobRunnerService:
    """Get the singleton job runner service."""
    global _job_runner
    if _job_runner is None:
        _job_runner = JobRunnerService()
    return _job_runner

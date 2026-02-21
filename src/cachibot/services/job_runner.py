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
from typing import Any

from prompture.exceptions import BudgetExceededError

from cachibot.config import Config
from cachibot.models.work import (
    Job,
    JobStatus,
    TaskStatus,
    Work,
    WorkStatus,
)
from cachibot.storage.automations_repository import (
    ExecutionLogRepository,
    TimelineEventRepository,
)
from cachibot.storage.work_repository import (
    FunctionRepository,
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
        self._task: asyncio.Task[None] | None = None
        self._running = False

        # Repositories
        self._work_repo = WorkRepository()
        self._task_repo = TaskRepository()
        self._job_repo = WorkJobRepository()
        self._function_repo = FunctionRepository()
        self._exec_log_repo = ExecutionLogRepository()
        self._timeline_repo = TimelineEventRepository()

        # Track running asyncio.Tasks keyed by job_id for cancellation
        self._running_jobs: dict[str, asyncio.Task[None]] = {}

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

    async def _execute_job(self, job: Job, task: Any, work: Work) -> None:
        """Execute a single job through CachibotAgent or ScriptSandbox."""
        from cachibot.models.automations import ExecutionLog, TimelineEvent, TriggerType

        # Create execution log entry
        exec_log_id = str(uuid.uuid4())
        exec_log = ExecutionLog(
            id=exec_log_id,
            execution_type="work",
            source_type="function" if work.function_id else "manual",
            source_id=work.function_id or work.id,
            source_name=work.title,
            bot_id=task.bot_id,
            chat_id=task.chat_id,
            trigger=TriggerType.CRON if work.schedule_id else TriggerType.MANUAL,
            work_id=work.id,
            work_job_id=job.id,
        )
        try:
            await self._exec_log_repo.save(exec_log)
        except Exception:
            logger.debug("Could not create execution log entry")

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
            await self._broadcast_execution_start(exec_log)

            # Determine execution type
            function = None
            if work.function_id:
                function = await self._function_repo.get(work.function_id)

            if (
                function
                and getattr(function, "execution_type", "agent") == "script"
                and getattr(function, "script_id", None)
            ):
                result_text, usage_data = await self._run_script_for_task(job, task, work, function)
            else:
                result_text, usage_data = await self._run_agent_for_task(job, task)

            # Job completed successfully
            await self._job_repo.update_status(job.id, JobStatus.COMPLETED, result=result_text)
            await self._job_repo.append_log(job.id, "info", "Job completed")
            await self._task_repo.update_status(task.id, TaskStatus.COMPLETED, result=result_text)

            # Complete execution log with usage data
            try:
                await self._exec_log_repo.complete(
                    exec_log_id,
                    status="success",
                    output=result_text,
                    credits=usage_data.get("cost", 0.0),
                    tokens=usage_data.get("total_tokens", 0),
                    prompt_tokens=usage_data.get("prompt_tokens", 0),
                    completion_tokens=usage_data.get("completion_tokens", 0),
                    llm_calls=usage_data.get("call_count", 0),
                )
                # Create timeline event
                await self._timeline_repo.save(
                    TimelineEvent(
                        id=str(uuid.uuid4()),
                        bot_id=task.bot_id,
                        source_type="function" if work.function_id else "work",
                        source_id=work.function_id or work.id,
                        event_type="execution",
                        title=f"Executed: {work.title}",
                        description="Completed successfully",
                        execution_log_id=exec_log_id,
                    )
                )
            except Exception:
                logger.debug("Could not complete execution log")

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
            await self._broadcast_execution_end(exec_log_id, "success", usage_data)

        except asyncio.CancelledError:
            # Job was cancelled externally
            await self._job_repo.update_status(job.id, JobStatus.CANCELLED, error="Cancelled")
            await self._job_repo.append_log(job.id, "warn", "Job cancelled")
            await self._task_repo.update_status(
                task.id, TaskStatus.PENDING, error="Cancelled, will retry"
            )
            try:
                await self._exec_log_repo.complete(exec_log_id, status="cancelled")
            except Exception:
                pass
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job.id,
                status="cancelled",
                progress=work.progress,
            )
            await self._broadcast_execution_end(exec_log_id, "cancelled")

        except asyncio.TimeoutError:
            timeout = task.timeout_seconds or "unknown"
            error_msg = f"Timeout after {timeout} seconds"
            await self._job_repo.update_status(job.id, JobStatus.FAILED, error=error_msg)
            await self._job_repo.append_log(job.id, "error", error_msg)
            try:
                await self._exec_log_repo.complete(exec_log_id, status="timeout", error=error_msg)
            except Exception:
                pass
            await self._handle_task_failure(task, work, job.id, error_msg)
            await self._broadcast_execution_end(exec_log_id, "timeout", error=error_msg)

        except BudgetExceededError as exc:
            error_msg = f"Budget limit reached: {exc}"
            await self._job_repo.update_status(job.id, JobStatus.FAILED, error=error_msg)
            await self._job_repo.append_log(job.id, "error", error_msg)
            try:
                await self._exec_log_repo.complete(
                    exec_log_id, status="error", error=error_msg
                )
                await self._timeline_repo.save(
                    TimelineEvent(
                        id=str(uuid.uuid4()),
                        bot_id=task.bot_id,
                        source_type="function" if work.function_id else "work",
                        source_id=work.function_id or work.id,
                        event_type="execution",
                        title=f"Budget exceeded: {work.title}",
                        description=error_msg,
                        execution_log_id=exec_log_id,
                    )
                )
            except Exception:
                pass
            # No retry — budget exceeded would fail again immediately
            await self._task_repo.update_status(task.id, TaskStatus.FAILED, error=error_msg)
            await self._work_repo.update_status(
                work.id, WorkStatus.FAILED, error=error_msg
            )
            await self._broadcast_update(
                work_id=work.id,
                task_id=task.id,
                job_id=job.id,
                status="failed",
                progress=work.progress,
                error=error_msg,
            )
            await self._broadcast_execution_end(exec_log_id, "error", error=error_msg)

        except Exception as exc:
            error_msg = str(exc)
            await self._job_repo.update_status(job.id, JobStatus.FAILED, error=error_msg)
            await self._job_repo.append_log(job.id, "error", f"Job failed: {error_msg}")
            try:
                await self._exec_log_repo.complete(exec_log_id, status="error", error=error_msg)
                await self._timeline_repo.save(
                    TimelineEvent(
                        id=str(uuid.uuid4()),
                        bot_id=task.bot_id,
                        source_type="function" if work.function_id else "work",
                        source_id=work.function_id or work.id,
                        event_type="execution",
                        title=f"Failed: {work.title}",
                        description=error_msg,
                        execution_log_id=exec_log_id,
                    )
                )
            except Exception:
                pass
            await self._handle_task_failure(task, work, job.id, error_msg)
            await self._broadcast_execution_end(exec_log_id, "error", error=error_msg)

        finally:
            self._running_jobs.pop(job.id, None)

    async def _run_agent_for_task(self, job: Job, task: Any) -> tuple[str, dict[str, Any]]:
        """Create a CachibotAgent and run the task action through it.

        Returns:
            Tuple of (result_text, usage_data dict).
        """
        from cachibot.agent import CachibotAgent, load_disabled_capabilities
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

        # Resolve per-bot environment (API keys, temperature, etc.)
        driver = None
        provider_environment = None
        try:
            from cachibot.api.websocket import _resolve_bot_env

            resolved_env, resolved_driver = await _resolve_bot_env(
                bot.id, effective_model=config.agent.model
            )
            if resolved_env:
                provider_environment = resolved_env
            if resolved_driver:
                driver = resolved_driver
        except Exception:
            logger.debug("Could not resolve per-bot environment for bot %s", task.bot_id)

        disabled_caps = await load_disabled_capabilities()
        agent = CachibotAgent(
            config=config,
            system_prompt_override=bot.system_prompt,
            capabilities=bot.capabilities,
            bot_id=bot.id,
            chat_id=task.chat_id,
            bot_models=bot.models,
            driver=driver,
            provider_environment=provider_environment,
            disabled_capabilities=disabled_caps,
        )

        # Load custom instructions from DB
        from cachibot.agent import load_dynamic_instructions

        await load_dynamic_instructions(agent)

        # Build the user message from task action
        action = task.action or task.title
        if task.description:
            action = f"{action}\n\nDetails: {task.description}"

        # Wrap in timeout if configured
        if task.timeout_seconds:
            result = await asyncio.wait_for(agent.run(action), timeout=task.timeout_seconds)
        else:
            result = await agent.run(action)

        # Extract usage data from the agent result
        usage_data: dict[str, Any] = {}
        if result.run_usage:
            usage = result.run_usage
            usage_data = {
                "total_tokens": getattr(usage, "total_tokens", 0),
                "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                "completion_tokens": getattr(usage, "completion_tokens", 0),
                "cost": getattr(usage, "total_cost", 0.0),
                "call_count": getattr(usage, "call_count", 0),
            }

        return result.output_text or "", usage_data

    async def _run_script_for_task(
        self, job: Job, task: Any, work: Work, function: Any
    ) -> tuple[str, dict[str, Any]]:
        """Execute a script in the sandbox.

        Returns:
            Tuple of (result_text, usage_data dict).
        """
        from cachibot.services.script_sandbox import ScriptSandbox
        from cachibot.storage.automations_repository import ScriptRepository

        script_repo = ScriptRepository()
        script = await script_repo.get(function.script_id)

        if not script or script.status.value != "active":
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

        # Update script run stats
        await script_repo.increment_run_count(script.id, success=result.success)

        return result.output or "", {}

    # ------------------------------------------------------------------
    # Failure Handling
    # ------------------------------------------------------------------

    async def _handle_task_failure(
        self,
        task: Any,
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

    async def _broadcast_execution_start(self, exec_log: Any) -> None:
        """Broadcast an EXECUTION_START message."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.execution_start(
                execution_log_id=exec_log.id,
                bot_id=exec_log.bot_id,
                source_name=exec_log.source_name,
                execution_type=exec_log.execution_type,
                trigger=exec_log.trigger.value
                if hasattr(exec_log.trigger, "value")
                else str(exec_log.trigger),
            )
            await ws.broadcast(msg)
        except Exception:
            logger.debug("Could not broadcast execution start")

    async def _broadcast_execution_end(
        self,
        exec_log_id: str,
        status: str,
        usage_data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        """Broadcast an EXECUTION_END message."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.execution_end(
                execution_log_id=exec_log_id,
                status=status,
                credits_consumed=usage_data.get("cost", 0.0) if usage_data else 0.0,
                error=error,
            )
            await ws.broadcast(msg)
        except Exception:
            logger.debug("Could not broadcast execution end")

    async def _broadcast_update(
        self,
        work_id: str,
        task_id: str | None = None,
        job_id: str | None = None,
        status: str = "",
        progress: float = 0.0,
        error: str | None = None,
        logs: list[dict[str, Any]] | None = None,
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

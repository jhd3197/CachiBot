"""
Scheduler Service

Background async loop that polls for due schedules and todo reminders,
then delivers messages via platform connections and/or WebSocket.
"""

import asyncio
import logging
from datetime import datetime, timedelta

from cachibot.models.work import ScheduleType, TodoStatus
from cachibot.storage.work_repository import ScheduleRepository, TodoRepository

logger = logging.getLogger(__name__)

# How often the scheduler checks for due items (seconds)
_POLL_INTERVAL = 30


class SchedulerService:
    """Background service that fires due schedules and reminders."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._schedule_repo = ScheduleRepository()
        self._todo_repo = TodoRepository()

    async def start(self) -> None:
        """Start the scheduler background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Scheduler service started (poll every %ds)", _POLL_INTERVAL)

    async def stop(self) -> None:
        """Stop the scheduler background loop."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Scheduler service stopped")

    async def _run_loop(self) -> None:
        """Main polling loop."""
        while self._running:
            try:
                await self._check_due_schedules()
            except Exception:
                logger.exception("Error checking due schedules")

            try:
                await self._check_due_reminders()
            except Exception:
                logger.exception("Error checking due reminders")

            await asyncio.sleep(_POLL_INTERVAL)

    # ------------------------------------------------------------------
    # Schedules
    # ------------------------------------------------------------------

    async def _check_due_schedules(self) -> None:
        """Find and fire all due schedules."""
        due = await self._schedule_repo.get_due_schedules()
        for schedule in due:
            try:
                await self._fire_schedule(schedule)
            except Exception:
                logger.exception("Error firing schedule %s", schedule.id)

    async def _fire_schedule(self, schedule) -> None:
        """Execute a single due schedule."""
        params = schedule.function_params or {}
        message = params.get("message") or schedule.description or schedule.name
        chat_id = params.get("chat_id")

        logger.info(
            "Firing schedule %s (%s) for bot %s",
            schedule.id,
            schedule.name,
            schedule.bot_id,
        )

        await self._deliver_message(schedule.bot_id, message, chat_id)

        # Record the run
        await self._schedule_repo.record_run(schedule.id)

        # Calculate and set next_run_at (or disable for one-time)
        if schedule.schedule_type == ScheduleType.ONCE:
            await self._schedule_repo.toggle_enabled(schedule.id, False)
            await self._schedule_repo.update_next_run(schedule.id, None)

        elif schedule.schedule_type == ScheduleType.INTERVAL:
            if schedule.interval_seconds:
                next_run = datetime.utcnow() + timedelta(seconds=schedule.interval_seconds)
                await self._schedule_repo.update_next_run(schedule.id, next_run)

        elif schedule.schedule_type == ScheduleType.CRON:
            if schedule.cron_expression:
                try:
                    from croniter import croniter

                    cron = croniter(schedule.cron_expression, datetime.utcnow())
                    next_run = cron.get_next(datetime)
                    await self._schedule_repo.update_next_run(schedule.id, next_run)
                except Exception:
                    logger.exception(
                        "Invalid cron expression for schedule %s: %s",
                        schedule.id,
                        schedule.cron_expression,
                    )
                    await self._schedule_repo.toggle_enabled(schedule.id, False)

    # ------------------------------------------------------------------
    # Todo Reminders
    # ------------------------------------------------------------------

    async def _check_due_reminders(self) -> None:
        """Find and fire all due todo reminders."""
        due = await self._todo_repo.get_due_reminders()
        for todo in due:
            try:
                message = f"Reminder: {todo.title}"
                if todo.notes:
                    message += f"\n{todo.notes}"

                await self._deliver_message(todo.bot_id, message, todo.chat_id)
                await self._todo_repo.update_status(todo.id, TodoStatus.DONE)

                logger.info("Fired reminder for todo %s (%s)", todo.id, todo.title)
            except Exception:
                logger.exception("Error firing reminder for todo %s", todo.id)

    # ------------------------------------------------------------------
    # Message Delivery
    # ------------------------------------------------------------------

    async def _deliver_message(
        self,
        bot_id: str,
        message: str,
        chat_id: str | None = None,
    ) -> None:
        """Deliver a scheduled message via platform and/or WebSocket.

        Strategy:
        1. If chat_id is known, look up the chat to find its platform info
           and send directly to that platform chat.
        2. Always broadcast to WebSocket so dashboard users see it.
        """
        # Try platform delivery if we have a chat context
        if chat_id:
            await self._deliver_via_platform(bot_id, chat_id, message)

        # Always broadcast to WebSocket for the dashboard
        await self._broadcast_to_websocket(bot_id, chat_id, message)

    async def _deliver_via_platform(
        self,
        bot_id: str,
        chat_id: str,
        message: str,
    ) -> None:
        """Send message to the platform chat associated with the given chat_id."""
        from cachibot.services.platform_manager import get_platform_manager
        from cachibot.storage.repository import ChatRepository

        try:
            chat_repo = ChatRepository()
            chat = await chat_repo.get_chat(chat_id)
            if chat and chat.platform and chat.platform_chat_id:
                manager = get_platform_manager()
                success = await manager.send_to_bot_connection(
                    bot_id, chat.platform, chat.platform_chat_id, message
                )
                if success:
                    logger.info(
                        "Delivered scheduled message to %s chat %s",
                        chat.platform,
                        chat.platform_chat_id,
                    )
                else:
                    logger.warning(
                        "Failed to deliver to %s (connection may be down)",
                        chat.platform,
                    )
        except Exception:
            logger.exception("Error delivering via platform for chat %s", chat_id)

    async def _broadcast_to_websocket(
        self,
        bot_id: str,
        chat_id: str | None,
        message: str,
    ) -> None:
        """Broadcast a scheduled message notification to WebSocket clients."""
        try:
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            ws = get_ws_manager()
            msg = WSMessage.scheduled_notification(
                bot_id=bot_id,
                chat_id=chat_id,
                content=message,
            )
            await ws.broadcast(msg)
        except Exception:
            # WSMessage.scheduled_notification may not exist yet,
            # or WS manager may not be initialized. That's fine.
            logger.debug("Could not broadcast scheduled message to WebSocket")


# Singleton
_scheduler: SchedulerService | None = None


def get_scheduler_service() -> SchedulerService:
    """Get the singleton scheduler service."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SchedulerService()
    return _scheduler

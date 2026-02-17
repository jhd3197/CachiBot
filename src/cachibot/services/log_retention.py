"""
Log Retention Service

Daily background task that aggregates old execution logs into daily summaries
and deletes expired log lines and records based on tier limits.
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone

from cachibot.services.tier_limits import get_tier_limits
from cachibot.storage.automations_repository import (
    ExecutionDailySummaryRepository,
    ExecutionLogLineRepository,
    ExecutionLogRepository,
)

logger = logging.getLogger(__name__)

# Run retention check every 6 hours
_RETENTION_INTERVAL = 6 * 3600


class LogRetentionService:
    """Background service that cleans up old execution logs."""

    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._running = False
        self._exec_log_repo = ExecutionLogRepository()
        self._log_line_repo = ExecutionLogLineRepository()
        self._summary_repo = ExecutionDailySummaryRepository()

    async def start(self) -> None:
        """Start the retention service background loop."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("Log retention service started (check every %dh)", _RETENTION_INTERVAL // 3600)

    async def stop(self) -> None:
        """Stop the retention service."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Log retention service stopped")

    async def _run_loop(self) -> None:
        """Main loop — runs retention check periodically."""
        # Wait a bit on startup to not compete with other init tasks
        await asyncio.sleep(60)

        while self._running:
            try:
                await self._run_retention()
            except Exception:
                logger.exception("Error in log retention")

            await asyncio.sleep(_RETENTION_INTERVAL)

    async def _run_retention(self) -> None:
        """Execute one retention cycle."""
        from sqlalchemy import select

        from cachibot.storage import db
        from cachibot.storage.models.automations import ExecutionLog as ExecutionLogORM

        tier_limits = get_tier_limits()  # Default tier for self-hosted
        cutoff = datetime.now(timezone.utc) - timedelta(days=tier_limits.log_retention_days)

        logger.info(
            "Running log retention: removing logs older than %s (%d days)",
            cutoff.isoformat(),
            tier_limits.log_retention_days,
        )

        async with db.ensure_initialized()() as session:
            # Find expired logs (not running, older than cutoff)
            result = await session.execute(
                select(ExecutionLogORM)
                .where(
                    ExecutionLogORM.started_at < cutoff,
                    ExecutionLogORM.status != "running",
                    ExecutionLogORM.retained.is_(True),
                )
                .limit(500)
            )
            expired_logs = result.scalars().all()

        if not expired_logs:
            logger.debug("No expired logs to clean up")
            return

        # Aggregate and delete
        aggregated = 0
        deleted = 0

        for log in expired_logs:
            try:
                # Aggregate into daily summary
                await self._aggregate_log(log)
                aggregated += 1

                # Delete log lines first, then mark as not retained
                await self._log_line_repo.delete_by_log(log.id)

                async with db.ensure_initialized()() as session:
                    from sqlalchemy import update as sa_update

                    await session.execute(
                        sa_update(ExecutionLogORM)
                        .where(ExecutionLogORM.id == log.id)
                        .values(retained=False, output=None, error=None)
                    )
                    await session.commit()
                deleted += 1

            except Exception:
                logger.debug("Error processing expired log %s", log.id)

        logger.info(
            "Log retention complete: aggregated %d, cleaned %d logs",
            aggregated,
            deleted,
        )

    async def _aggregate_log(self, log) -> None:
        """Aggregate a single log into the daily summary."""
        from cachibot.models.automations import ExecutionDailySummary

        summary_date = log.started_at.date()

        # Try to find existing summary for this source/date
        await self._summary_repo.get_by_bot_date(
            bot_id=log.bot_id,
            from_date=datetime.combine(summary_date, datetime.min.time()),
            to_date=datetime.combine(summary_date, datetime.max.time()),
            limit=1,
        )

        # For simplicity, create a new summary record per log
        # (in production, you'd upsert/merge into an existing one)
        summary = ExecutionDailySummary(
            id=str(uuid.uuid4()),
            bot_id=log.bot_id,
            user_id=log.user_id if hasattr(log, "user_id") else None,
            source_type=log.source_type,
            source_id=log.source_id or "",
            execution_type=log.execution_type,
            summary_date=summary_date,
            total_runs=1,
            success_count=1 if log.status == "success" else 0,
            error_count=1 if log.status == "error" else 0,
            timeout_count=1 if log.status == "timeout" else 0,
            cancelled_count=1 if log.status == "cancelled" else 0,
            total_duration_ms=log.duration_ms or 0,
            avg_duration_ms=log.duration_ms or 0,
            total_credits=log.credits_consumed or 0.0,
            total_tokens=log.tokens_used or 0,
            error_types={log.error[:100]: 1} if log.error else {},
        )
        await self._summary_repo.save(summary)


# Singleton
_retention_service: LogRetentionService | None = None


def get_log_retention_service() -> LogRetentionService:
    """Get the singleton log retention service."""
    global _retention_service
    if _retention_service is None:
        _retention_service = LogRetentionService()
    return _retention_service

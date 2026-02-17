"""
Repository Classes for Unified Automations System

Provides async CRUD operations for scripts, script versions, execution logs,
log lines, timeline events, and daily summaries.
"""

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update

from cachibot.models.automations import (
    AuthorType,
    ExecutionStatus,
    LogLevel,
    ScriptStatus,
    TriggerType,
)
from cachibot.models.automations import (
    ExecutionDailySummary as ExecutionDailySummaryModel,
)
from cachibot.models.automations import (
    ExecutionLog as ExecutionLogModel,
)
from cachibot.models.automations import (
    ExecutionLogLine as ExecutionLogLineModel,
)
from cachibot.models.automations import (
    Script as ScriptModel,
)
from cachibot.models.automations import (
    ScriptVersion as ScriptVersionModel,
)
from cachibot.models.automations import (
    TimelineEvent as TimelineEventModel,
)
from cachibot.storage import db
from cachibot.storage.models.automations import (
    ExecutionDailySummary as ExecutionDailySummaryORM,
)
from cachibot.storage.models.automations import (
    ExecutionLog as ExecutionLogORM,
)
from cachibot.storage.models.automations import (
    ExecutionLogLine as ExecutionLogLineORM,
)
from cachibot.storage.models.automations import (
    Script as ScriptORM,
)
from cachibot.storage.models.automations import (
    ScriptVersion as ScriptVersionORM,
)
from cachibot.storage.models.automations import (
    TimelineEvent as TimelineEventORM,
)


class ScriptRepository:
    """Repository for bot scripts (versioned Python code)."""

    async def save(self, script: ScriptModel) -> None:
        """Save a new script."""
        async with db.ensure_initialized()() as session:
            obj = ScriptORM(
                id=script.id,
                bot_id=script.bot_id,
                name=script.name,
                description=script.description,
                source_code=script.source_code,
                language=script.language,
                status=script.status.value
                if isinstance(script.status, ScriptStatus)
                else script.status,
                current_version=script.current_version,
                tags=script.tags,
                created_at=script.created_at,
                updated_at=script.updated_at,
                created_by=script.created_by,
                timeout_seconds=script.timeout_seconds,
                max_memory_mb=script.max_memory_mb,
                allowed_imports=script.allowed_imports,
                run_count=script.run_count,
                last_run_at=script.last_run_at,
                success_rate=script.success_rate,
            )
            session.add(obj)
            await session.commit()

    async def update(self, script: ScriptModel) -> None:
        """Update an existing script."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(ScriptORM)
                .where(ScriptORM.id == script.id)
                .values(
                    name=script.name,
                    description=script.description,
                    source_code=script.source_code,
                    language=script.language,
                    status=script.status.value
                    if isinstance(script.status, ScriptStatus)
                    else script.status,
                    current_version=script.current_version,
                    tags=script.tags,
                    updated_at=datetime.now(timezone.utc),
                    timeout_seconds=script.timeout_seconds,
                    max_memory_mb=script.max_memory_mb,
                    allowed_imports=script.allowed_imports,
                    run_count=script.run_count,
                    last_run_at=script.last_run_at,
                    success_rate=script.success_rate,
                )
            )
            await session.commit()

    async def get(self, script_id: str) -> ScriptModel | None:
        """Get a script by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(ScriptORM).where(ScriptORM.id == script_id))
            row = result.scalar_one_or_none()
        return self._row_to_script(row) if row else None

    async def get_by_bot(
        self, bot_id: str, status: ScriptStatus | None = None, limit: int = 50
    ) -> list[ScriptModel]:
        """Get all scripts for a bot."""
        stmt = select(ScriptORM).where(ScriptORM.bot_id == bot_id)
        if status:
            stmt = stmt.where(ScriptORM.status == status.value)
        stmt = stmt.order_by(ScriptORM.updated_at.desc()).limit(limit)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_script(row) for row in rows]

    async def delete(self, script_id: str) -> bool:
        """Delete a script by ID (cascades to versions)."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(ScriptORM).where(ScriptORM.id == script_id))
            await session.commit()
            return result.rowcount > 0

    async def update_status(self, script_id: str, status: ScriptStatus) -> None:
        """Update script status."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(ScriptORM)
                .where(ScriptORM.id == script_id)
                .values(status=status.value, updated_at=now)
            )
            await session.commit()

    async def increment_run_count(self, script_id: str, success: bool) -> None:
        """Increment run count and update success rate."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ScriptORM.run_count, ScriptORM.success_rate).where(ScriptORM.id == script_id)
            )
            row = result.one_or_none()
            if row:
                old_count, old_rate = row[0], row[1]
                new_count = old_count + 1
                old_successes = old_count * old_rate
                new_successes = old_successes + (1 if success else 0)
                new_rate = new_successes / new_count

                await session.execute(
                    update(ScriptORM)
                    .where(ScriptORM.id == script_id)
                    .values(
                        run_count=new_count,
                        success_rate=new_rate,
                        last_run_at=now,
                        updated_at=now,
                    )
                )
                await session.commit()

    def _row_to_script(self, row: ScriptORM) -> ScriptModel:
        """Convert database row to Script pydantic model."""
        return ScriptModel(
            id=row.id,
            bot_id=row.bot_id,
            name=row.name,
            description=row.description,
            source_code=row.source_code,
            language=row.language,
            status=ScriptStatus(row.status),
            current_version=row.current_version,
            tags=row.tags if row.tags else [],
            created_at=row.created_at,
            updated_at=row.updated_at,
            created_by=row.created_by,
            timeout_seconds=row.timeout_seconds,
            max_memory_mb=row.max_memory_mb,
            allowed_imports=row.allowed_imports if row.allowed_imports else [],
            run_count=row.run_count,
            last_run_at=row.last_run_at,
            success_rate=row.success_rate,
        )


class ScriptVersionRepository:
    """Repository for script versions (git-like history)."""

    async def save(self, version: ScriptVersionModel) -> None:
        """Save a new script version."""
        async with db.ensure_initialized()() as session:
            obj = ScriptVersionORM(
                id=version.id,
                script_id=version.script_id,
                version_number=version.version_number,
                source_code=version.source_code,
                diff_from_previous=version.diff_from_previous,
                author_type=version.author_type.value
                if isinstance(version.author_type, AuthorType)
                else version.author_type,
                author_id=version.author_id,
                commit_message=version.commit_message,
                approved=version.approved,
                approved_by=version.approved_by,
                approved_at=version.approved_at,
                created_at=version.created_at,
            )
            session.add(obj)
            await session.commit()

    async def get(self, version_id: str) -> ScriptVersionModel | None:
        """Get a version by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ScriptVersionORM).where(ScriptVersionORM.id == version_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_version(row) if row else None

    async def get_by_script(self, script_id: str) -> list[ScriptVersionModel]:
        """Get all versions for a script."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ScriptVersionORM)
                .where(ScriptVersionORM.script_id == script_id)
                .order_by(ScriptVersionORM.version_number.desc())
            )
            rows = result.scalars().all()
        return [self._row_to_version(row) for row in rows]

    async def get_version(self, script_id: str, version_number: int) -> ScriptVersionModel | None:
        """Get a specific version of a script."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ScriptVersionORM).where(
                    ScriptVersionORM.script_id == script_id,
                    ScriptVersionORM.version_number == version_number,
                )
            )
            row = result.scalar_one_or_none()
        return self._row_to_version(row) if row else None

    async def approve(
        self,
        script_id: str,
        version_number: int,
        approved_by: str,
    ) -> None:
        """Approve a script version."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(ScriptVersionORM)
                .where(
                    ScriptVersionORM.script_id == script_id,
                    ScriptVersionORM.version_number == version_number,
                )
                .values(approved=True, approved_by=approved_by, approved_at=now)
            )
            await session.commit()

    def _row_to_version(self, row: ScriptVersionORM) -> ScriptVersionModel:
        """Convert database row to ScriptVersion pydantic model."""
        return ScriptVersionModel(
            id=row.id,
            script_id=row.script_id,
            version_number=row.version_number,
            source_code=row.source_code,
            diff_from_previous=row.diff_from_previous,
            author_type=AuthorType(row.author_type),
            author_id=row.author_id,
            commit_message=row.commit_message,
            approved=row.approved,
            approved_by=row.approved_by,
            approved_at=row.approved_at,
            created_at=row.created_at,
        )


class ExecutionLogRepository:
    """Repository for execution logs (unified tracking)."""

    async def save(self, log: ExecutionLogModel) -> None:
        """Save a new execution log."""
        async with db.ensure_initialized()() as session:
            obj = ExecutionLogORM(
                id=log.id,
                execution_type=log.execution_type,
                source_type=log.source_type,
                source_id=log.source_id,
                source_name=log.source_name,
                bot_id=log.bot_id,
                user_id=log.user_id,
                chat_id=log.chat_id,
                trigger=log.trigger.value if isinstance(log.trigger, TriggerType) else log.trigger,
                started_at=log.started_at,
                finished_at=log.finished_at,
                duration_ms=log.duration_ms,
                status=log.status.value if isinstance(log.status, ExecutionStatus) else log.status,
                output=log.output,
                error=log.error,
                exit_code=log.exit_code,
                credits_consumed=log.credits_consumed,
                tokens_used=log.tokens_used,
                prompt_tokens=log.prompt_tokens,
                completion_tokens=log.completion_tokens,
                llm_calls=log.llm_calls,
                work_id=log.work_id,
                work_job_id=log.work_job_id,
                metadata_json=log.metadata_json,
                retained=log.retained,
            )
            session.add(obj)
            await session.commit()

    async def complete(
        self,
        log_id: str,
        status: str,
        output: str | None = None,
        error: str | None = None,
        credits: float = 0.0,
        tokens: int = 0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        llm_calls: int = 0,
        exit_code: int | None = None,
    ) -> None:
        """Complete an execution log with final status and metrics."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            # Get started_at to compute duration
            result = await session.execute(
                select(ExecutionLogORM.started_at).where(ExecutionLogORM.id == log_id)
            )
            started_at = result.scalar_one_or_none()
            duration_ms = None
            if started_at:
                duration_ms = int((now - started_at).total_seconds() * 1000)

            await session.execute(
                update(ExecutionLogORM)
                .where(ExecutionLogORM.id == log_id)
                .values(
                    status=status,
                    finished_at=now,
                    duration_ms=duration_ms,
                    output=output,
                    error=error,
                    exit_code=exit_code,
                    credits_consumed=credits,
                    tokens_used=tokens,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    llm_calls=llm_calls,
                )
            )
            await session.commit()

    async def append_line(
        self,
        log_id: str,
        level: str,
        content: str,
        data: dict | None = None,
    ) -> None:
        """Append a log line to an execution."""
        async with db.ensure_initialized()() as session:
            # Get next sequence number
            result = await session.execute(
                select(func.coalesce(func.max(ExecutionLogLineORM.seq), 0)).where(
                    ExecutionLogLineORM.execution_log_id == log_id
                )
            )
            next_seq = result.scalar() + 1

            obj = ExecutionLogLineORM(
                id=str(uuid.uuid4()),
                execution_log_id=log_id,
                seq=next_seq,
                timestamp=datetime.now(timezone.utc),
                level=level,
                content=content,
                data=data,
            )
            session.add(obj)
            await session.commit()

    async def get(self, log_id: str) -> ExecutionLogModel | None:
        """Get an execution log by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ExecutionLogORM).where(ExecutionLogORM.id == log_id)
            )
            row = result.scalar_one_or_none()
        return self._row_to_log(row) if row else None

    async def get_by_bot(
        self,
        bot_id: str,
        execution_type: str | None = None,
        status: str | None = None,
        trigger: str | None = None,
        source_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionLogModel]:
        """Get execution logs for a bot with filtering."""
        stmt = select(ExecutionLogORM).where(
            ExecutionLogORM.bot_id == bot_id,
            ExecutionLogORM.retained.is_(True),
        )
        if execution_type:
            stmt = stmt.where(ExecutionLogORM.execution_type == execution_type)
        if status:
            stmt = stmt.where(ExecutionLogORM.status == status)
        if trigger:
            stmt = stmt.where(ExecutionLogORM.trigger == trigger)
        if source_id:
            stmt = stmt.where(ExecutionLogORM.source_id == source_id)
        if from_date:
            stmt = stmt.where(ExecutionLogORM.started_at >= from_date)
        if to_date:
            stmt = stmt.where(ExecutionLogORM.started_at <= to_date)

        stmt = stmt.order_by(ExecutionLogORM.started_at.desc()).limit(limit).offset(offset)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_log(row) for row in rows]

    async def get_running(self, bot_id: str | None = None) -> list[ExecutionLogModel]:
        """Get currently running executions."""
        stmt = select(ExecutionLogORM).where(ExecutionLogORM.status == "running")
        if bot_id:
            stmt = stmt.where(ExecutionLogORM.bot_id == bot_id)
        stmt = stmt.order_by(ExecutionLogORM.started_at.asc())

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_log(row) for row in rows]

    async def get_global(
        self,
        execution_type: str | None = None,
        status: str | None = None,
        bot_id: str | None = None,
        trigger: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ExecutionLogModel]:
        """Get execution logs across all bots (admin)."""
        stmt = select(ExecutionLogORM).where(ExecutionLogORM.retained.is_(True))
        if execution_type:
            stmt = stmt.where(ExecutionLogORM.execution_type == execution_type)
        if status:
            stmt = stmt.where(ExecutionLogORM.status == status)
        if bot_id:
            stmt = stmt.where(ExecutionLogORM.bot_id == bot_id)
        if trigger:
            stmt = stmt.where(ExecutionLogORM.trigger == trigger)
        if from_date:
            stmt = stmt.where(ExecutionLogORM.started_at >= from_date)
        if to_date:
            stmt = stmt.where(ExecutionLogORM.started_at <= to_date)

        stmt = stmt.order_by(ExecutionLogORM.started_at.desc()).limit(limit).offset(offset)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_log(row) for row in rows]

    async def get_stats(self, bot_id: str | None = None, period: str = "24h") -> dict:
        """Get execution stats for a period."""
        now = datetime.now(timezone.utc)
        if period == "24h":
            since = now - timedelta(hours=24)
        elif period == "7d":
            since = now - timedelta(days=7)
        elif period == "30d":
            since = now - timedelta(days=30)
        else:
            since = now - timedelta(hours=24)

        stmt = select(
            func.count().label("total"),
            func.count().filter(ExecutionLogORM.status == "success").label("success"),
            func.count().filter(ExecutionLogORM.status == "error").label("errors"),
            func.count().filter(ExecutionLogORM.status == "timeout").label("timeouts"),
            func.count().filter(ExecutionLogORM.status == "cancelled").label("cancelled"),
            func.coalesce(func.sum(ExecutionLogORM.credits_consumed), 0.0).label("total_credits"),
            func.coalesce(func.sum(ExecutionLogORM.tokens_used), 0).label("total_tokens"),
            func.coalesce(func.avg(ExecutionLogORM.duration_ms), 0).label("avg_duration_ms"),
        ).where(ExecutionLogORM.started_at >= since)

        if bot_id:
            stmt = stmt.where(ExecutionLogORM.bot_id == bot_id)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            row = result.one()

        return {
            "period": period,
            "total": row.total,
            "success": row.success,
            "errors": row.errors,
            "timeouts": row.timeouts,
            "cancelled": row.cancelled,
            "total_credits": float(row.total_credits),
            "total_tokens": int(row.total_tokens),
            "avg_duration_ms": int(row.avg_duration_ms),
        }

    async def get_error_spotlight(self, days: int = 7) -> list[dict]:
        """Get error analysis grouped by error type."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    ExecutionLogORM.error,
                    ExecutionLogORM.source_name,
                    ExecutionLogORM.bot_id,
                    func.count().label("count"),
                    func.max(ExecutionLogORM.started_at).label("last_seen"),
                )
                .where(
                    ExecutionLogORM.status == "error",
                    ExecutionLogORM.started_at >= since,
                    ExecutionLogORM.error.isnot(None),
                )
                .group_by(
                    ExecutionLogORM.error,
                    ExecutionLogORM.source_name,
                    ExecutionLogORM.bot_id,
                )
                .order_by(func.count().desc())
                .limit(20)
            )
            rows = result.all()

        return [
            {
                "error": row.error,
                "source_name": row.source_name,
                "bot_id": row.bot_id,
                "count": row.count,
                "last_seen": row.last_seen.isoformat() if row.last_seen else None,
            }
            for row in rows
        ]

    async def get_cost_analysis(self, days: int = 30, limit: int = 20) -> list[dict]:
        """Get cost analysis ranked by credits consumed."""
        since = datetime.now(timezone.utc) - timedelta(days=days)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    ExecutionLogORM.source_name,
                    ExecutionLogORM.source_id,
                    ExecutionLogORM.bot_id,
                    ExecutionLogORM.execution_type,
                    func.sum(ExecutionLogORM.credits_consumed).label("total_credits"),
                    func.sum(ExecutionLogORM.tokens_used).label("total_tokens"),
                    func.count().label("run_count"),
                    func.avg(ExecutionLogORM.duration_ms).label("avg_duration_ms"),
                )
                .where(ExecutionLogORM.started_at >= since)
                .group_by(
                    ExecutionLogORM.source_name,
                    ExecutionLogORM.source_id,
                    ExecutionLogORM.bot_id,
                    ExecutionLogORM.execution_type,
                )
                .order_by(func.sum(ExecutionLogORM.credits_consumed).desc())
                .limit(limit)
            )
            rows = result.all()

        return [
            {
                "source_name": row.source_name,
                "source_id": row.source_id,
                "bot_id": row.bot_id,
                "execution_type": row.execution_type,
                "total_credits": float(row.total_credits or 0),
                "total_tokens": int(row.total_tokens or 0),
                "run_count": row.run_count,
                "avg_duration_ms": int(row.avg_duration_ms or 0),
            }
            for row in rows
        ]

    async def cancel(self, log_id: str) -> bool:
        """Mark a running execution as cancelled."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(ExecutionLogORM)
                .where(
                    ExecutionLogORM.id == log_id,
                    ExecutionLogORM.status == "running",
                )
                .values(status="cancelled", finished_at=now)
            )
            await session.commit()
            return result.rowcount > 0

    async def export_csv(
        self,
        bot_id: str | None = None,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
    ) -> str:
        """Export execution logs as CSV string."""
        stmt = select(ExecutionLogORM).where(ExecutionLogORM.retained.is_(True))
        if bot_id:
            stmt = stmt.where(ExecutionLogORM.bot_id == bot_id)
        if from_date:
            stmt = stmt.where(ExecutionLogORM.started_at >= from_date)
        if to_date:
            stmt = stmt.where(ExecutionLogORM.started_at <= to_date)
        stmt = stmt.order_by(ExecutionLogORM.started_at.desc()).limit(10000)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "id",
                "execution_type",
                "source_type",
                "source_name",
                "bot_id",
                "trigger",
                "started_at",
                "finished_at",
                "duration_ms",
                "status",
                "credits_consumed",
                "tokens_used",
                "error",
            ]
        )
        for row in rows:
            writer.writerow(
                [
                    row.id,
                    row.execution_type,
                    row.source_type,
                    row.source_name,
                    row.bot_id,
                    row.trigger,
                    row.started_at,
                    row.finished_at,
                    row.duration_ms,
                    row.status,
                    row.credits_consumed,
                    row.tokens_used,
                    row.error,
                ]
            )
        return output.getvalue()

    def _row_to_log(self, row: ExecutionLogORM) -> ExecutionLogModel:
        """Convert database row to ExecutionLog pydantic model."""
        return ExecutionLogModel(
            id=row.id,
            execution_type=row.execution_type,
            source_type=row.source_type,
            source_id=row.source_id,
            source_name=row.source_name,
            bot_id=row.bot_id,
            user_id=row.user_id,
            chat_id=row.chat_id,
            trigger=TriggerType(row.trigger)
            if row.trigger in TriggerType.__members__.values()
            else TriggerType.MANUAL,
            started_at=row.started_at,
            finished_at=row.finished_at,
            duration_ms=row.duration_ms,
            status=ExecutionStatus(row.status)
            if row.status in {e.value for e in ExecutionStatus}
            else ExecutionStatus.RUNNING,
            output=row.output,
            error=row.error,
            exit_code=row.exit_code,
            credits_consumed=row.credits_consumed,
            tokens_used=row.tokens_used,
            prompt_tokens=row.prompt_tokens,
            completion_tokens=row.completion_tokens,
            llm_calls=row.llm_calls,
            work_id=row.work_id,
            work_job_id=row.work_job_id,
            metadata_json=row.metadata_json if row.metadata_json else {},
            retained=row.retained,
        )


class ExecutionLogLineRepository:
    """Repository for execution log lines."""

    async def append(
        self,
        log_id: str,
        level: str,
        content: str,
        data: dict | None = None,
    ) -> None:
        """Append a log line."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(func.coalesce(func.max(ExecutionLogLineORM.seq), 0)).where(
                    ExecutionLogLineORM.execution_log_id == log_id
                )
            )
            next_seq = result.scalar() + 1

            obj = ExecutionLogLineORM(
                id=str(uuid.uuid4()),
                execution_log_id=log_id,
                seq=next_seq,
                timestamp=datetime.now(timezone.utc),
                level=level,
                content=content,
                data=data,
            )
            session.add(obj)
            await session.commit()

    async def get_lines(
        self, log_id: str, limit: int = 100, offset: int = 0
    ) -> list[ExecutionLogLineModel]:
        """Get paginated log lines for an execution."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ExecutionLogLineORM)
                .where(ExecutionLogLineORM.execution_log_id == log_id)
                .order_by(ExecutionLogLineORM.seq.asc())
                .limit(limit)
                .offset(offset)
            )
            rows = result.scalars().all()

        return [
            ExecutionLogLineModel(
                id=row.id,
                execution_log_id=row.execution_log_id,
                seq=row.seq,
                timestamp=row.timestamp,
                level=LogLevel(row.level)
                if row.level in {e.value for e in LogLevel}
                else LogLevel.INFO,
                content=row.content,
                data=row.data,
            )
            for row in rows
        ]

    async def delete_by_log(self, log_id: str) -> int:
        """Delete all lines for an execution log. Returns count deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(ExecutionLogLineORM).where(ExecutionLogLineORM.execution_log_id == log_id)
            )
            await session.commit()
            return result.rowcount


class TimelineEventRepository:
    """Repository for timeline events."""

    async def save(self, event: TimelineEventModel) -> None:
        """Save a new timeline event."""
        async with db.ensure_initialized()() as session:
            obj = TimelineEventORM(
                id=event.id,
                bot_id=event.bot_id,
                source_type=event.source_type,
                source_id=event.source_id,
                event_type=event.event_type,
                event_at=event.event_at,
                actor_type=event.actor_type,
                actor_id=event.actor_id,
                actor_name=event.actor_name,
                title=event.title,
                description=event.description,
                diff=event.diff,
                execution_log_id=event.execution_log_id,
                version_number=event.version_number,
                commit_message=event.commit_message,
                metadata_json=event.metadata_json,
            )
            session.add(obj)
            await session.commit()

    async def get_timeline(
        self,
        source_type: str,
        source_id: str,
        event_types: list[str] | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[TimelineEventModel]:
        """Get timeline events for a source entity."""
        stmt = select(TimelineEventORM).where(
            TimelineEventORM.source_type == source_type,
            TimelineEventORM.source_id == source_id,
        )
        if event_types:
            stmt = stmt.where(TimelineEventORM.event_type.in_(event_types))
        stmt = stmt.order_by(TimelineEventORM.event_at.desc()).limit(limit).offset(offset)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._row_to_event(row) for row in rows]

    async def get_by_bot(
        self, bot_id: str, limit: int = 50, offset: int = 0
    ) -> list[TimelineEventModel]:
        """Get all timeline events for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(TimelineEventORM)
                .where(TimelineEventORM.bot_id == bot_id)
                .order_by(TimelineEventORM.event_at.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = result.scalars().all()
        return [self._row_to_event(row) for row in rows]

    def _row_to_event(self, row: TimelineEventORM) -> TimelineEventModel:
        """Convert database row to TimelineEvent pydantic model."""
        return TimelineEventModel(
            id=row.id,
            bot_id=row.bot_id,
            source_type=row.source_type,
            source_id=row.source_id,
            event_type=row.event_type,
            event_at=row.event_at,
            actor_type=row.actor_type,
            actor_id=row.actor_id,
            actor_name=row.actor_name,
            title=row.title,
            description=row.description,
            diff=row.diff,
            execution_log_id=row.execution_log_id,
            version_number=row.version_number,
            commit_message=row.commit_message,
            metadata_json=row.metadata_json if row.metadata_json else {},
        )


class ExecutionDailySummaryRepository:
    """Repository for execution daily summaries."""

    async def save(self, summary: ExecutionDailySummaryModel) -> None:
        """Save a new daily summary."""
        async with db.ensure_initialized()() as session:
            obj = ExecutionDailySummaryORM(
                id=summary.id,
                bot_id=summary.bot_id,
                user_id=summary.user_id,
                source_type=summary.source_type,
                source_id=summary.source_id,
                execution_type=summary.execution_type,
                summary_date=summary.summary_date,
                total_runs=summary.total_runs,
                success_count=summary.success_count,
                error_count=summary.error_count,
                timeout_count=summary.timeout_count,
                cancelled_count=summary.cancelled_count,
                total_duration_ms=summary.total_duration_ms,
                avg_duration_ms=summary.avg_duration_ms,
                total_credits=summary.total_credits,
                total_tokens=summary.total_tokens,
                error_types=summary.error_types,
                created_at=summary.created_at,
            )
            session.add(obj)
            await session.commit()

    async def get_by_bot_date(
        self,
        bot_id: str,
        from_date: datetime | None = None,
        to_date: datetime | None = None,
        limit: int = 90,
    ) -> list[ExecutionDailySummaryModel]:
        """Get summaries for a bot within a date range."""
        stmt = select(ExecutionDailySummaryORM).where(ExecutionDailySummaryORM.bot_id == bot_id)
        if from_date:
            stmt = stmt.where(ExecutionDailySummaryORM.summary_date >= from_date.date())
        if to_date:
            stmt = stmt.where(ExecutionDailySummaryORM.summary_date <= to_date.date())
        stmt = stmt.order_by(ExecutionDailySummaryORM.summary_date.desc()).limit(limit)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [
            ExecutionDailySummaryModel(
                id=row.id,
                bot_id=row.bot_id,
                user_id=row.user_id,
                source_type=row.source_type,
                source_id=row.source_id,
                execution_type=row.execution_type,
                summary_date=row.summary_date,
                total_runs=row.total_runs,
                success_count=row.success_count,
                error_count=row.error_count,
                timeout_count=row.timeout_count,
                cancelled_count=row.cancelled_count,
                total_duration_ms=row.total_duration_ms,
                avg_duration_ms=row.avg_duration_ms,
                total_credits=row.total_credits,
                total_tokens=row.total_tokens,
                error_types=row.error_types if row.error_types else {},
                created_at=row.created_at,
            )
            for row in rows
        ]

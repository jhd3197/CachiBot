"""
Execution Log API Routes

Per-bot endpoints for viewing execution history, logs, and stats.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.automations import ExecutionLog, ExecutionLogLine
from cachibot.models.group import BotAccessLevel
from cachibot.storage.automations_repository import (
    ExecutionLogLineRepository,
    ExecutionLogRepository,
)

router = APIRouter(prefix="/api/bots/{bot_id}", tags=["executions"])

exec_log_repo = ExecutionLogRepository()
log_line_repo = ExecutionLogLineRepository()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class ExecutionLogResponse(BaseModel):
    """Response model for an execution log."""

    id: str
    executionType: str
    sourceType: str
    sourceId: str | None
    sourceName: str
    botId: str
    userId: str | None
    chatId: str | None
    trigger: str
    startedAt: str
    finishedAt: str | None
    durationMs: int | None
    status: str
    output: str | None
    error: str | None
    exitCode: int | None
    creditsConsumed: float
    tokensUsed: int
    promptTokens: int
    completionTokens: int
    llmCalls: int
    workId: str | None
    workJobId: str | None

    @classmethod
    def from_log(cls, log: ExecutionLog) -> "ExecutionLogResponse":
        return cls(
            id=log.id,
            executionType=log.execution_type,
            sourceType=log.source_type,
            sourceId=log.source_id,
            sourceName=log.source_name,
            botId=log.bot_id,
            userId=log.user_id,
            chatId=log.chat_id,
            trigger=log.trigger.value if hasattr(log.trigger, "value") else str(log.trigger),
            startedAt=log.started_at.isoformat(),
            finishedAt=log.finished_at.isoformat() if log.finished_at else None,
            durationMs=log.duration_ms,
            status=log.status.value if hasattr(log.status, "value") else str(log.status),
            output=log.output,
            error=log.error,
            exitCode=log.exit_code,
            creditsConsumed=log.credits_consumed,
            tokensUsed=log.tokens_used,
            promptTokens=log.prompt_tokens,
            completionTokens=log.completion_tokens,
            llmCalls=log.llm_calls,
            workId=log.work_id,
            workJobId=log.work_job_id,
        )


class LogLineResponse(BaseModel):
    """Response model for a log line."""

    id: str
    seq: int
    timestamp: str
    level: str
    content: str
    data: dict | None

    @classmethod
    def from_line(cls, line: ExecutionLogLine) -> "LogLineResponse":
        return cls(
            id=line.id,
            seq=line.seq,
            timestamp=line.timestamp.isoformat(),
            level=line.level.value if hasattr(line.level, "value") else str(line.level),
            content=line.content,
            data=line.data,
        )


# =============================================================================
# EXECUTION LOG ENDPOINTS
# =============================================================================


@router.get("/executions")
async def list_executions(
    bot_id: str,
    type: str | None = None,
    status: str | None = None,
    trigger: str | None = None,
    source_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user: User = Depends(require_bot_access),
) -> list[ExecutionLogResponse]:
    """List execution logs for a bot (paginated, filterable)."""
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    logs = await exec_log_repo.get_by_bot(
        bot_id=bot_id,
        execution_type=type,
        status=status,
        trigger=trigger,
        source_id=source_id,
        from_date=from_dt,
        to_date=to_dt,
        limit=limit,
        offset=offset,
    )
    return [ExecutionLogResponse.from_log(log) for log in logs]


@router.get("/executions/running")
async def get_running_executions(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[ExecutionLogResponse]:
    """Get currently running executions for a bot."""
    logs = await exec_log_repo.get_running(bot_id=bot_id)
    return [ExecutionLogResponse.from_log(log) for log in logs]


@router.get("/executions/stats")
async def get_execution_stats(
    bot_id: str,
    period: str = "24h",
    user: User = Depends(require_bot_access),
) -> dict:
    """Get execution stats for a bot (24h, 7d, 30d)."""
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=422, detail="period must be 24h, 7d, or 30d")
    raw = await exec_log_repo.get_stats(bot_id=bot_id, period=period)
    return {
        "totalRuns": raw.get("total", 0),
        "successCount": raw.get("success", 0),
        "errorCount": raw.get("errors", 0),
        "avgDurationMs": raw.get("avg_duration_ms", 0),
        "totalCredits": raw.get("total_credits", 0),
        "totalTokens": raw.get("total_tokens", 0),
    }


@router.get("/executions/{exec_id}")
async def get_execution(
    bot_id: str,
    exec_id: str,
    user: User = Depends(require_bot_access),
) -> ExecutionLogResponse:
    """Get execution log detail."""
    log = await exec_log_repo.get(exec_id)
    if not log or log.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Execution log not found")
    return ExecutionLogResponse.from_log(log)


@router.get("/executions/{exec_id}/output")
async def get_execution_output(
    bot_id: str,
    exec_id: str,
    user: User = Depends(require_bot_access),
) -> dict:
    """Get full output of an execution."""
    log = await exec_log_repo.get(exec_id)
    if not log or log.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Execution log not found")
    return {
        "id": log.id,
        "output": log.output,
        "error": log.error,
        "status": log.status.value if hasattr(log.status, "value") else str(log.status),
    }


@router.get("/executions/{exec_id}/lines")
async def get_execution_lines(
    bot_id: str,
    exec_id: str,
    limit: int = Query(default=100, le=1000),
    offset: int = 0,
    user: User = Depends(require_bot_access),
) -> list[LogLineResponse]:
    """Get paginated log lines for an execution."""
    log = await exec_log_repo.get(exec_id)
    if not log or log.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Execution log not found")

    lines = await log_line_repo.get_lines(exec_id, limit=limit, offset=offset)
    return [LogLineResponse.from_line(line) for line in lines]


@router.post("/executions/{exec_id}/cancel")
async def cancel_execution(
    bot_id: str,
    exec_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> dict:
    """Cancel a running execution."""
    log = await exec_log_repo.get(exec_id)
    if not log or log.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Execution log not found")

    cancelled = await exec_log_repo.cancel(exec_id)
    if not cancelled:
        raise HTTPException(status_code=422, detail="Execution is not running")

    # Also cancel the associated work job if linked
    if log.work_job_id:
        try:
            from cachibot.services.job_runner import get_job_runner

            runner = get_job_runner()
            await runner.cancel_job(log.work_job_id)
        except Exception:
            pass

    return {"cancelled": True}

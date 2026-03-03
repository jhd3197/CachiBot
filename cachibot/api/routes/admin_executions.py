"""
Admin Execution Log API Routes

Global execution log endpoints for admin users.
"""

import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from cachibot.api.auth import get_admin_user
from cachibot.api.helpers import require_found
from cachibot.api.routes.executions import ExecutionLogResponse
from cachibot.models.auth import User
from cachibot.storage.automations_repository import ExecutionLogRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin-executions"])

exec_log_repo = ExecutionLogRepository()


# =============================================================================
# ADMIN EXECUTION LOG ENDPOINTS
# =============================================================================


@router.get("/executions")
async def admin_list_executions(
    type: str | None = None,
    status: str | None = None,
    bot_id: str | None = None,
    trigger: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    limit: int = Query(default=50, le=200),
    offset: int = 0,
    user: User = Depends(get_admin_user),
) -> list[ExecutionLogResponse]:
    """Global execution log across all bots (admin only)."""
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    logs = await exec_log_repo.get_global(
        execution_type=type,
        status=status,
        bot_id=bot_id,
        trigger=trigger,
        from_date=from_dt,
        to_date=to_dt,
        limit=limit,
        offset=offset,
    )
    return [ExecutionLogResponse.from_log(log) for log in logs]


@router.get("/executions/errors")
async def admin_error_spotlight(
    days: int = 7,
    user: User = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """Error spotlight: errors grouped by type (admin only)."""
    rows = await exec_log_repo.get_error_spotlight(days=days)
    return [
        {
            "errorType": r.get("error", "Unknown"),
            "count": r.get("count", 0),
            "lastSeen": r.get("last_seen"),
            "botIds": [r["bot_id"]] if r.get("bot_id") else [],
        }
        for r in rows
    ]


@router.get("/executions/costs")
async def admin_cost_analysis(
    days: int = 30,
    limit: int = 20,
    user: User = Depends(get_admin_user),
) -> list[dict[str, Any]]:
    """Cost analysis: ranked by credits consumed (admin only)."""
    rows = await exec_log_repo.get_cost_analysis(days=days, limit=limit)
    return [
        {
            "botId": r.get("bot_id", ""),
            "botName": r.get("source_name", r.get("bot_id", "")),
            "totalCredits": r.get("total_credits", 0),
            "totalTokens": r.get("total_tokens", 0),
            "executionCount": r.get("run_count", 0),
        }
        for r in rows
    ]


@router.get("/executions/stats")
async def admin_global_stats(
    period: str = "24h",
    user: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Global execution stats (admin only)."""
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=422, detail="period must be 24h, 7d, or 30d")
    raw = await exec_log_repo.get_stats(period=period)
    return {
        "totalRuns": raw.get("total", 0),
        "successCount": raw.get("success", 0),
        "errorCount": raw.get("errors", 0),
        "avgDurationMs": raw.get("avg_duration_ms", 0),
        "totalCredits": raw.get("total_credits", 0),
        "totalTokens": raw.get("total_tokens", 0),
    }


@router.get("/executions/running")
async def admin_running_executions(
    user: User = Depends(get_admin_user),
) -> list[ExecutionLogResponse]:
    """All currently running executions across all bots (admin only)."""
    logs = await exec_log_repo.get_running()
    return [ExecutionLogResponse.from_log(log) for log in logs]


@router.post("/executions/{exec_id}/cancel")
async def admin_cancel_execution(
    exec_id: str,
    user: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Admin kill switch for a running execution."""
    log = require_found(await exec_log_repo.get(exec_id), "Execution log")

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
            logger.warning(
                "Failed to cancel work job %s for execution %s",
                log.work_job_id,
                exec_id,
                exc_info=True,
            )

    return {"cancelled": True}


@router.get("/executions/export")
async def admin_export_csv(
    bot_id: str | None = None,
    from_date: str | None = None,
    to_date: str | None = None,
    user: User = Depends(get_admin_user),
) -> PlainTextResponse:
    """Export execution logs as CSV (admin only)."""
    from_dt = datetime.fromisoformat(from_date) if from_date else None
    to_dt = datetime.fromisoformat(to_date) if to_date else None

    csv_data = await exec_log_repo.export_csv(bot_id=bot_id, from_date=from_dt, to_date=to_dt)
    return PlainTextResponse(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=execution_logs.csv"},
    )


@router.post("/executions/cancel-all")
async def admin_cancel_all(
    user: User = Depends(get_admin_user),
) -> dict[str, Any]:
    """Emergency: cancel ALL running executions (admin only)."""
    running = await exec_log_repo.get_running()
    cancelled_count = 0

    for log in running:
        try:
            success = await exec_log_repo.cancel(log.id)
            if success:
                cancelled_count += 1
                # Also cancel the associated work job
                if log.work_job_id:
                    try:
                        from cachibot.services.job_runner import get_job_runner

                        runner = get_job_runner()
                        await runner.cancel_job(log.work_job_id)
                    except Exception:
                        logger.warning(
                            "Failed to cancel work job %s for execution %s",
                            log.work_job_id,
                            log.id,
                            exc_info=True,
                        )
        except Exception:
            logger.warning(
                "Failed to cancel execution %s during cancel-all",
                log.id,
                exc_info=True,
            )

    return {"cancelledCount": cancelled_count}

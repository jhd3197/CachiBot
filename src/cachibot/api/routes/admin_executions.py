"""
Admin Execution Log API Routes

Global execution log endpoints for admin users.
"""

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse

from cachibot.api.auth import get_admin_user
from cachibot.api.routes.executions import ExecutionLogResponse
from cachibot.models.auth import User
from cachibot.storage.automations_repository import ExecutionLogRepository

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
) -> list[dict]:
    """Error spotlight: errors grouped by type (admin only)."""
    return await exec_log_repo.get_error_spotlight(days=days)


@router.get("/executions/costs")
async def admin_cost_analysis(
    days: int = 30,
    limit: int = 20,
    user: User = Depends(get_admin_user),
) -> list[dict]:
    """Cost analysis: ranked by credits consumed (admin only)."""
    return await exec_log_repo.get_cost_analysis(days=days, limit=limit)


@router.get("/executions/stats")
async def admin_global_stats(
    period: str = "24h",
    user: User = Depends(get_admin_user),
) -> dict:
    """Global execution stats (admin only)."""
    if period not in ("24h", "7d", "30d"):
        raise HTTPException(status_code=422, detail="period must be 24h, 7d, or 30d")
    return await exec_log_repo.get_stats(period=period)


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
) -> dict:
    """Admin kill switch for a running execution."""
    log = await exec_log_repo.get(exec_id)
    if not log:
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
) -> dict:
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
                        pass
        except Exception:
            pass

    return {"cancelledCount": cancelled_count}

"""Update check and apply endpoints."""

from fastapi import APIRouter, Depends, Request

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.update import (
    UpdateCheckResponse,
    UpdateDiagnosticsResponse,
    UpdatePerformRequest,
    UpdatePerformResponse,
    UpdateRestartResponse,
)
from cachibot.services.update_service import (
    _is_venv,
    _python_info,
    check_for_updates,
    detect_corruption,
    perform_update,
    restart_server,
    verify_installation,
)

router = APIRouter()


@router.get("/update/check", response_model=UpdateCheckResponse)
async def check_update(
    force: bool = False,
    user: User = Depends(get_current_user),
) -> UpdateCheckResponse:
    """Check for available updates."""
    return await check_for_updates(force=force)


@router.post("/update/apply", response_model=UpdatePerformResponse)
async def apply_update(
    body: UpdatePerformRequest,
    user: User = Depends(get_current_user),
) -> UpdatePerformResponse:
    """Download and install an update via pip."""
    return await perform_update(
        target_version=body.target_version,
        include_prerelease=body.include_prerelease,
    )


@router.post("/update/restart", response_model=UpdateRestartResponse)
async def restart(
    request: Request,
    user: User = Depends(get_current_user),
) -> UpdateRestartResponse:
    """Restart the server after an update."""
    # Derive host/port from the current request
    host = request.headers.get("host", "127.0.0.1:6392")
    if ":" in host:
        server_host, port_str = host.rsplit(":", 1)
        try:
            server_port = int(port_str)
        except ValueError:
            server_host, server_port = "127.0.0.1", 6392
    else:
        server_host, server_port = host, 6392

    # Strip IPv6 brackets if present
    server_host = server_host.strip("[]")

    await restart_server(server_host, server_port)
    return UpdateRestartResponse(
        restarting=True,
        message=f"Server restarting on {server_host}:{server_port}...",
    )


@router.get("/update/diagnostics", response_model=UpdateDiagnosticsResponse)
async def diagnostics(
    user: User = Depends(get_current_user),
) -> UpdateDiagnosticsResponse:
    """Run installation diagnostics: corruption check, verify, environment info."""
    report = detect_corruption()
    ok, verify_detail = verify_installation()
    py_info = _python_info()

    return UpdateDiagnosticsResponse(
        is_corrupted=report.is_corrupted,
        corrupted_artifacts=report.corrupted_dirs + report.corrupted_dists,
        corruption_details=report.details,
        install_verified=ok,
        verify_detail=verify_detail,
        python_version=py_info["version"],
        python_executable=py_info["executable"],
        platform=py_info["platform"],
        is_venv=_is_venv(),
    )

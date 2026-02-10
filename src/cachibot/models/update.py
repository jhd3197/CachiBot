"""Update system models."""

from pydantic import BaseModel


class UpdateCheckResponse(BaseModel):
    """Response from update check."""

    current_version: str
    latest_stable: str | None = None
    latest_prerelease: str | None = None
    update_available: bool = False
    prerelease_available: bool = False
    release_notes: str | None = None
    release_url: str | None = None
    published_at: str | None = None
    is_docker: bool = False


class UpdatePerformRequest(BaseModel):
    """Request to perform an update."""

    target_version: str | None = None
    include_prerelease: bool = False


class UpdatePerformResponse(BaseModel):
    """Response from performing an update."""

    success: bool
    old_version: str
    new_version: str
    message: str
    restart_required: bool = False
    pip_output: str = ""


class UpdateRestartResponse(BaseModel):
    """Response from restart request."""

    restarting: bool
    message: str

"""Bot computer API routes.

``GET /api/bots/{bot_id}/computer`` reports the computer's state for the UI;
``POST .../wake|sleep|stop`` drive it (wake returns immediately — the work
happens in the background and streams ``computer_update`` WS events).
``GET /api/computer/status`` exposes the Docker probe so the UI can hide
every computer surface when Docker is absent.

C2 adds the live surface: the preview and per-window frames (proxied image
bytes with ETag/304 — a preview never wakes the computer), the windows list
with the activity line, watch heartbeats (watching keeps it awake), take
over / hand back / person input under the driver's lease, and the needs-you
answer. All of it is proxied through CachiBot with its own bot-access rules;
the Vela port and controller token are never exposed.

Access: viewers can watch (status, preview, views, frames, heartbeats);
operators and above can control (wake/sleep/stop, take over, hand back,
input, needs-you answers).
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from cachibot.api.auth import get_current_user, require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.computer import (
    BotComputerStatus,
    ComputerInputRequest,
    ComputerNeedsYouRespond,
    ComputerViewsResponse,
    ComputerWatchResponse,
    DockerProbeResult,
)
from cachibot.models.group import BotAccessLevel
from cachibot.services.computer.service import (
    ComputerRequestError,
    PreviewResult,
    get_computer_service,
)

router = APIRouter(tags=["computer"])


def _http_error(exc: ComputerRequestError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


def _frame_response(result: PreviewResult) -> Response:
    """Image bytes with the caching contract: no-store, named by ETag."""
    headers = {"Cache-Control": "no-store"}
    if result.etag:
        headers["ETag"] = result.etag
    if result.status == 304:
        return Response(status_code=304, headers=headers)
    return Response(content=result.body, media_type=result.media_type, headers=headers)


@router.get("/api/bots/{bot_id}/computer")
async def get_computer(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotComputerStatus:
    """Current state of the bot's computer (viewer+)."""
    return BotComputerStatus(**await get_computer_service().get_status(bot_id))


@router.post("/api/bots/{bot_id}/computer/wake")
async def wake_computer(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Turn the computer on in the background; returns the state right now."""
    return BotComputerStatus(**await get_computer_service().wake(bot_id))


@router.post("/api/bots/{bot_id}/computer/sleep")
async def sleep_computer(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Stop the container but keep the volumes (operator+)."""
    return BotComputerStatus(**await get_computer_service().sleep(bot_id))


@router.post("/api/bots/{bot_id}/computer/stop")
async def stop_computer(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Stop the computer and mark it off; volumes are kept (operator+)."""
    return BotComputerStatus(**await get_computer_service().stop_computer(bot_id))


@router.get("/api/computer/status")
async def computer_status(user: User = Depends(get_current_user)) -> DockerProbeResult:
    """Docker probe summary (any signed-in user) — the UI hides everything
    computer-related when this says unavailable."""
    return DockerProbeResult(**await get_computer_service().get_docker_status())


# ---------------------------------------------------------------------------
# C2: live preview, windows, watchers, take-over, input, needs-you
# ---------------------------------------------------------------------------


@router.get("/api/bots/{bot_id}/computer/preview")
async def get_computer_preview(
    bot_id: str,
    request: Request,
    user: User = Depends(require_bot_access),
) -> Response:
    """The live preview image (viewer+): the full-desktop frame when the
    container's Vela offers it, otherwise the focused/top window's frame.
    ETag/If-None-Match → 304; never wakes the computer (409 while asleep)."""
    try:
        result = await get_computer_service().get_preview(
            bot_id, user.id, etag=request.headers.get("if-none-match")
        )
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return _frame_response(result)


@router.get("/api/bots/{bot_id}/computer/views")
async def get_computer_views(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> ComputerViewsResponse:
    """The open windows (app + title) and the activity line (viewer+)."""
    try:
        payload = await get_computer_service().get_views(bot_id, user.id)
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return ComputerViewsResponse(**payload)


@router.get("/api/bots/{bot_id}/computer/views/{view_id}/frame")
async def get_computer_view_frame(
    bot_id: str,
    view_id: str,
    request: Request,
    user: User = Depends(require_bot_access),
) -> Response:
    """One window's frame, proxied (viewer+). ETag/If-None-Match → 304."""
    try:
        result = await get_computer_service().get_view_frame(
            bot_id, user.id, view_id, etag=request.headers.get("if-none-match")
        )
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return _frame_response(result)


@router.post("/api/bots/{bot_id}/computer/watch")
async def watch_computer(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> ComputerWatchResponse:
    """A watch heartbeat (viewer+): the caller counts as watching for ~30 s,
    which keeps the computer awake; the heartbeat is forwarded to Vela."""
    try:
        payload = await get_computer_service().note_watching(bot_id, user.id)
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return ComputerWatchResponse(**payload)


@router.post("/api/bots/{bot_id}/computer/takeover")
async def takeover_computer(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Take over the computer (operator+): the bot's driving pauses and the
    caller holds the control lease until hand back or lease expiry."""
    try:
        payload = await get_computer_service().takeover(bot_id, user.id, user.username)
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return BotComputerStatus(**payload)


@router.post("/api/bots/{bot_id}/computer/handback")
async def handback_computer(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Hand the computer back (operator+): releases the control lease. The
    paused run carries on when somebody says so, never on its own."""
    try:
        payload = await get_computer_service().handback(bot_id, user.id)
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return BotComputerStatus(**payload)


@router.post("/api/bots/{bot_id}/computer/input")
async def send_computer_input(
    bot_id: str,
    data: ComputerInputRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> dict[str, bool]:
    """Send one piece of person input (operator+), only while the caller
    holds the take-over: click (left/right/middle), scroll, type, key."""
    try:
        return await get_computer_service().send_input(bot_id, user.id, data)
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc


@router.post("/api/bots/{bot_id}/computer/needs-you/respond")
async def respond_computer_needs_you(
    bot_id: str,
    data: ComputerNeedsYouRespond,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> BotComputerStatus:
    """Answer a needs-you (operator+): take over, or skip — the documented
    closest refusal (an approval is denied; a needs-person pause stops the
    run, as Vela has no "skip this step")."""
    try:
        payload = await get_computer_service().respond_needs_you(
            bot_id, user.id, user.username, data.action
        )
    except ComputerRequestError as exc:
        raise _http_error(exc) from exc
    return BotComputerStatus(**payload)

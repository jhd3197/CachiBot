"""Faro Agent Bridge API routes.

``GET /api/integrations/faro/status`` reports the global bridge detection
(any signed-in user) so the UI can hide every Faro surface when the bridge
is absent. ``GET /api/bots/{bot_id}/faro`` reports the bot's connection,
the live bridge status and the approvals Faro is waiting on (viewer+).
``POST .../faro/connect|disconnect`` toggle the per-bot opt-in: connecting
needs the same level as other privileged bot settings (editor+), and a
running bridge; disconnecting is always allowed. ``POST
.../faro/approvals/{request_id}/deny`` is the only approval answer here —
approving only ever happens in Faro's own UI (operator+).

None of these responses ever carry the bridge token, the endpoint URL or
the bridge pid; the token never leaves the discovery file.
"""

from fastapi import APIRouter, Depends, HTTPException

from cachibot.api.auth import get_current_user, require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.faro import BotFaroStatus, FaroBridgeStatus, FaroDenyApprovalResponse
from cachibot.models.group import BotAccessLevel
from cachibot.services.faro.service import FaroRequestError, get_faro_service

router = APIRouter(tags=["faro"])


def _http_error(exc: FaroRequestError) -> HTTPException:
    return HTTPException(status_code=exc.status_code, detail=exc.detail)


@router.get("/api/integrations/faro/status")
async def faro_status(user: User = Depends(get_current_user)) -> FaroBridgeStatus:
    """Bridge detection summary (any signed-in user) — no secrets."""
    return await get_faro_service().get_status()


@router.get("/api/bots/{bot_id}/faro")
async def get_bot_faro(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotFaroStatus:
    """The bot's Faro connection: the flag, the live bridge status and the
    approvals Faro is waiting on (viewer+)."""
    return BotFaroStatus(**await get_faro_service().get_bot_status(bot_id))


@router.post("/api/bots/{bot_id}/faro/connect")
async def connect_bot_faro(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> BotFaroStatus:
    """Connect this bot to Faro (editor+): the bot's faro tools appear while
    the bridge is running. Requires a running bridge."""
    try:
        payload = await get_faro_service().connect(bot_id)
    except FaroRequestError as exc:
        raise _http_error(exc) from exc
    return BotFaroStatus(**payload)


@router.post("/api/bots/{bot_id}/faro/disconnect")
async def disconnect_bot_faro(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> BotFaroStatus:
    """Disconnect this bot from Faro (always allowed for anyone with bot
    access): the bot's faro tools disappear."""
    return BotFaroStatus(**await get_faro_service().disconnect(bot_id))


@router.post("/api/bots/{bot_id}/faro/approvals/{request_id}/deny")
async def deny_bot_faro_approval(
    bot_id: str,
    request_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> FaroDenyApprovalResponse:
    """Deny one pending approval in Faro (operator+).

    There is deliberately no approve route: approving only ever happens in
    Faro's own window.
    """
    try:
        await get_faro_service().deny_approval(bot_id, request_id)
    except FaroRequestError as exc:
        raise _http_error(exc) from exc
    return FaroDenyApprovalResponse(denied=True)

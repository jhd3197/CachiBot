"""Bot computer API routes.

``GET /api/bots/{bot_id}/computer`` reports the computer's state for the UI;
``POST .../wake|sleep|stop`` drive it (wake returns immediately — the work
happens in the background and streams ``computer_update`` WS events).
``GET /api/computer/status`` exposes the Docker probe so the UI can hide
every computer surface when Docker is absent.

Access: viewers can read; wake/sleep/stop need operator-or-higher. The
controller token and host port are never exposed.
"""

from fastapi import APIRouter, Depends

from cachibot.api.auth import get_current_user, require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.computer import BotComputerStatus, DockerProbeResult
from cachibot.models.group import BotAccessLevel
from cachibot.services.computer.service import get_computer_service

router = APIRouter(tags=["computer"])


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

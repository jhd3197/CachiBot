"""
Side Tasks API Routes

Endpoints for starting, listing and stopping side tasks (child chats of a
parent chat that work in parallel and report back).

Access: viewers can list/read; operators (and above) can start/stop.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.models.side_task import (
    SideTask,
    SideTaskKind,
    SideTaskStartedBy,
)
from cachibot.services.side_task_service import (
    SideTaskStartError,
    get_side_task_service,
)
from cachibot.storage.side_task_repository import SideTaskRepository

router = APIRouter(prefix="/api/bots/{bot_id}", tags=["side-tasks"])

side_task_repo = SideTaskRepository()


class SideTaskResponse(BaseModel):
    """Response model for a side task (camelCase like other routes)."""

    id: str
    botId: str
    parentChatId: str
    chatId: str
    title: str
    prompt: str
    kind: str
    groupId: str | None
    status: str
    needsYouReason: str | None
    startedBy: str
    worktreePath: str | None
    branch: str | None
    baseCommit: str | None
    mergedCommit: str | None
    mergedFiles: list[dict[str, object]]
    conflictFiles: list[str]
    error: str | None
    workId: str | None
    createdAt: str
    startedAt: str | None
    finishedAt: str | None
    updatedAt: str

    @classmethod
    def from_side_task(cls, st: SideTask) -> "SideTaskResponse":
        return cls(**st.model_dump(mode="json", by_alias=True))


class StartSideTaskRequest(BaseModel):
    """Request body for starting a side task."""

    prompt: str = Field(min_length=1, description="What the side task should do")
    title: str | None = Field(
        default=None, description="Short name (derived from the prompt if omitted)"
    )
    kind: SideTaskKind = Field(default=SideTaskKind.SIDE)
    startedBy: SideTaskStartedBy = Field(default=SideTaskStartedBy.USER)
    groupId: str | None = Field(default=None, description="Helper group id (E3)")


@router.get("/side-tasks")
async def list_side_tasks(
    bot_id: str,
    parent_chat_id: str | None = None,
    user: User = Depends(require_bot_access),
) -> list[SideTaskResponse]:
    """List side tasks for a bot, optionally filtered by parent chat."""
    side_tasks = await side_task_repo.get_by_bot(bot_id, parent_chat_id=parent_chat_id)
    return [SideTaskResponse.from_side_task(st) for st in side_tasks]


@router.get("/side-tasks/{side_task_id}")
async def get_side_task(
    bot_id: str,
    side_task_id: str,
    user: User = Depends(require_bot_access),
) -> SideTaskResponse:
    """Get a single side task."""
    side_task = await side_task_repo.get(side_task_id)
    if side_task is None or side_task.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")
    return SideTaskResponse.from_side_task(side_task)


@router.post("/chats/{chat_id}/side-tasks", status_code=201)
async def start_side_task(
    bot_id: str,
    chat_id: str,
    request: StartSideTaskRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> SideTaskResponse:
    """Start a side task on a parent chat (queues it if no slot is free)."""
    service = get_side_task_service()
    try:
        side_task = await service.start(
            parent_chat_id=chat_id,
            bot_id=bot_id,
            prompt=request.prompt,
            title=request.title,
            started_by=request.startedBy,
            kind=request.kind,
            group_id=request.groupId,
        )
    except SideTaskStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return SideTaskResponse.from_side_task(side_task)


class StopSideTaskResponse(BaseModel):
    """Response model for stopping a side task."""

    id: str
    status: str


@router.post("/side-tasks/{side_task_id}/stop")
async def stop_side_task(
    bot_id: str,
    side_task_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> StopSideTaskResponse:
    """Stop a side task (running or waiting)."""
    existing = await side_task_repo.get(side_task_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")

    service = get_side_task_service()
    stopped = await service.stop(side_task_id)
    if stopped is None:
        raise HTTPException(status_code=404, detail="Side task not found")
    return StopSideTaskResponse(id=stopped.id, status=stopped.status.value)


@router.post("/side-tasks/{side_task_id}/retry-merge", status_code=200)
async def retry_merge_side_task(
    bot_id: str,
    side_task_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> SideTaskResponse:
    """Retry merging back a side task that waits on a merge conflict.

    For after the user fixed things in either tree: pending changes in the
    worktree are committed and the merge is attempted again. Stays
    ``needs_you`` (with the updated conflict paths) when it conflicts again.
    """
    existing = await side_task_repo.get(side_task_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")

    service = get_side_task_service()
    try:
        side_task = await service.retry_merge(side_task_id)
    except SideTaskStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if side_task is None:
        raise HTTPException(status_code=404, detail="Side task not found")
    return SideTaskResponse.from_side_task(side_task)


@router.post("/side-tasks/{side_task_id}/discard", status_code=200)
async def discard_side_task(
    bot_id: str,
    side_task_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> SideTaskResponse:
    """Discard a stopped, failed or needs_you side task for good.

    Removes its worktree and force-deletes its branch (the only place a
    side branch is force-deleted) and marks it stopped.
    """
    existing = await side_task_repo.get(side_task_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")

    service = get_side_task_service()
    try:
        side_task = await service.discard(side_task_id)
    except SideTaskStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if side_task is None:
        raise HTTPException(status_code=404, detail="Side task not found")
    return SideTaskResponse.from_side_task(side_task)

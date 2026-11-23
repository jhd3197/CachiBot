"""
Side Tasks API Routes

Endpoints for starting, listing and stopping side tasks (child chats of a
parent chat that work in parallel and report back).

Access: viewers can list/read (incl. the diff); operators (and above) can
start/stop/reply, retry a merge and discard.
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
    SideTaskReplyError,
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
    groupTitle: str | None
    status: str
    needsYouReason: str | None
    startedBy: str
    worktreePath: str | None
    branch: str | None
    baseCommit: str | None
    mergedCommit: str | None
    mergedFiles: list[dict[str, object]]
    conflictFiles: list[str]
    sourceMessageId: str | None
    replyMessageId: str | None
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
    groupTitle: str | None = Field(default=None, description="Helper group title (E3)")
    sourceMessageId: str | None = Field(
        default=None,
        description=(
            "Parent-chat message this side task answers (validated to belong to "
            "the chat; the latest user message in the chat is used when omitted)"
        ),
    )


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


class SideTaskGroupSummaryResponse(BaseModel):
    """Aggregate view of one helper group (bot-started helpers)."""

    groupId: str
    title: str | None
    total: int
    done: int
    failed: int
    running: int
    waiting: int
    needsYou: int
    items: list[SideTaskResponse]


@router.get("/side-task-groups/{group_id}")
async def get_side_task_group(
    bot_id: str,
    group_id: str,
    user: User = Depends(require_bot_access),
) -> SideTaskGroupSummaryResponse:
    """Get one helper group with per-status counts and its helpers.

    Counts are computed from the real records: ``done`` covers done and
    merged helpers, ``waiting`` is waiting_for_slot and ``needsYou`` is
    needs_you. Stopped helpers are only listed in ``items``.
    """
    summary = await get_side_task_service().group_summary(group_id)
    if summary is None or summary.items[0].bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task group not found")
    return SideTaskGroupSummaryResponse(
        groupId=summary.group_id,
        title=summary.title,
        total=summary.total,
        done=summary.done,
        failed=summary.failed,
        running=summary.running,
        waiting=summary.waiting,
        needsYou=summary.needs_you,
        items=[SideTaskResponse.from_side_task(st) for st in summary.items],
    )


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
            group_title=request.groupTitle,
            source_message_id=request.sourceMessageId,
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


class ReplySideTaskRequest(BaseModel):
    """Request body for replying inside a side task's own chat."""

    content: str = Field(min_length=1, description="The reply message")


@router.post("/side-tasks/{side_task_id}/messages", status_code=200)
async def reply_to_side_task(
    bot_id: str,
    side_task_id: str,
    request: ReplySideTaskRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> SideTaskResponse:
    """Reply inside a side task's chat and continue its turn.

    The reply is persisted into the side chat and the side task runs again
    in its own worktree, then merges back only the new changes. Allowed once
    the side task is settled (done / merged / failed / stopped /
    needs_you without merge conflict); 409 while it works or waits on a
    merge conflict.
    """
    existing = await side_task_repo.get(side_task_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")

    service = get_side_task_service()
    try:
        side_task = await service.reply(side_task_id, request.content)
    except SideTaskReplyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except SideTaskStartError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if side_task is None:
        raise HTTPException(status_code=404, detail="Side task not found")
    return SideTaskResponse.from_side_task(side_task)


class SideTaskDiffFileResponse(BaseModel):
    """One changed file in a side-task diff."""

    path: str
    status: str  # added | modified | deleted
    additions: int | None  # None when the file is binary
    deletions: int | None
    binary: bool = False


class SideTaskDiffResponse(BaseModel):
    """Unified diff + per-file stats for "View changes"."""

    sideTaskId: str
    status: str
    base: str | None
    head: str | None
    truncated: bool
    files: list[SideTaskDiffFileResponse]
    diff: str


@router.get("/side-tasks/{side_task_id}/diff")
async def get_side_task_diff(
    bot_id: str,
    side_task_id: str,
    user: User = Depends(require_bot_access),
) -> SideTaskDiffResponse:
    """The changes a side task is about to bring back (or already brought back).

    Unmerged: the worktree against its base commit, including uncommitted
    changes. Merged: the merged commit range (only what the latest bring-in
    added). The diff text is capped (``truncated`` flags a cut); binary
    files are listed without line stats. Viewers allowed — the diff is
    read-only.
    """
    existing = await side_task_repo.get(side_task_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Side task not found")

    result = await get_side_task_service().diff(side_task_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Side task not found")
    return SideTaskDiffResponse(
        sideTaskId=side_task_id,
        status=existing.status.value,
        base=result.base,
        head=result.head,
        truncated=result.truncated,
        files=[
            SideTaskDiffFileResponse(
                path=f.path,
                status=f.status,
                additions=f.additions,
                deletions=f.deletions,
                binary=f.binary,
            )
            for f in result.files
        ],
        diff=result.diff,
    )

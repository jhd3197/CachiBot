"""Side task models: a child chat of a parent chat that works in parallel."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(name: str) -> str:
    """Convert snake_case field names to camelCase for API/WS payloads."""
    parts = name.split("_")
    return parts[0] + "".join(p.title() for p in parts[1:])


class SideTaskKind(str, Enum):
    """Who a side task is for: user-started, or a bot-started helper."""

    SIDE = "side"
    HELPER = "helper"


class SideTaskStatus(str, Enum):
    """Lifecycle of a side task.

    E2 adds the merge step on finish: done -> merged, or needs_you on
    merge conflict.
    """

    WAITING_FOR_SLOT = "waiting_for_slot"
    RUNNING = "running"
    NEEDS_YOU = "needs_you"
    DONE = "done"
    MERGED = "merged"
    FAILED = "failed"
    STOPPED = "stopped"


class SideTaskStartedBy(str, Enum):
    """Who started the side task."""

    USER = "user"
    BOT = "bot"


ACTIVE_STATUSES = (
    SideTaskStatus.WAITING_FOR_SLOT,
    SideTaskStatus.RUNNING,
    SideTaskStatus.NEEDS_YOU,
)

TERMINAL_STATUSES = (
    SideTaskStatus.DONE,
    SideTaskStatus.MERGED,
    SideTaskStatus.FAILED,
    SideTaskStatus.STOPPED,
)


class SideTask(BaseModel):
    """A side task: child chat of a parent chat, run by the same bot.

    Workspace fields (worktree_path, branch, base_commit) and merge result
    fields (merged_commit, merged_files, conflict_files) are filled in by
    E2; the columns exist from E1 so E2 only writes values.
    """

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    id: str = Field(description="Unique side task ID")
    bot_id: str = Field(description="Bot that runs the side task")
    parent_chat_id: str = Field(description="Main task chat this belongs to")
    chat_id: str = Field(description="The side task's own chat")

    # Identity
    title: str = Field(description="Short name shown on the card and sidebar")
    prompt: str = Field(description="What the side task should do")
    kind: SideTaskKind = Field(default=SideTaskKind.SIDE)
    group_id: str | None = Field(
        default=None, description="Helper group id (bot-started helpers, E3)"
    )

    # Status
    status: SideTaskStatus = Field(default=SideTaskStatus.WAITING_FOR_SLOT)
    needs_you_reason: str | None = Field(default=None)
    started_by: SideTaskStartedBy = Field(default=SideTaskStartedBy.USER)

    # Workspace (E2: git worktree on a side/<slug> branch)
    worktree_path: str | None = Field(default=None)
    branch: str | None = Field(default=None)
    base_commit: str | None = Field(default=None)

    # Merge result (E2)
    merged_commit: str | None = Field(default=None)
    merged_files: list[dict[str, Any]] = Field(default_factory=list)
    conflict_files: list[str] = Field(default_factory=list)

    # Results
    error: str | None = Field(default=None)

    # Link to the Work row (Runs / job runner integration)
    work_id: str | None = Field(default=None)

    # Timing
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: datetime | None = Field(default=None)
    finished_at: datetime | None = Field(default=None)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SideTaskList(BaseModel):
    """List of side tasks."""

    items: list[SideTask] = Field(default_factory=list)
    total: int = Field(default=0)

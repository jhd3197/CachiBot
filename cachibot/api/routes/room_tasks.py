"""Room Tasks API Routes -- shared kanban board per room."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query

from cachibot.api.auth import get_current_user
from cachibot.api.helpers import require_found, require_member, require_room_ownership
from cachibot.models.auth import User
from cachibot.models.room_task import (
    CreateRoomTaskRequest,
    ReorderRoomTaskRequest,
    RoomTask,
    RoomTaskEvent,
    RoomTaskEventAction,
    RoomTaskEventResponse,
    RoomTaskResponse,
    UpdateRoomTaskRequest,
)
from cachibot.storage.room_repository import RoomMemberRepository, RoomRepository
from cachibot.storage.room_task_event_repository import RoomTaskEventRepository
from cachibot.storage.room_task_repository import RoomTaskRepository

router = APIRouter(prefix="/api/rooms", tags=["room-tasks"])

room_repo = RoomRepository()
member_repo = RoomMemberRepository()
task_repo = RoomTaskRepository()
event_repo = RoomTaskEventRepository()

# Field -> action mapping for update events
_FIELD_ACTION_MAP: dict[str, RoomTaskEventAction] = {
    "status": RoomTaskEventAction.STATUS_CHANGED,
    "priority": RoomTaskEventAction.PRIORITY_CHANGED,
    "assigned_to_bot_id": RoomTaskEventAction.ASSIGNED,
    "assigned_to_user_id": RoomTaskEventAction.ASSIGNED,
}


def _make_event(
    *,
    task_id: str,
    room_id: str,
    action: RoomTaskEventAction,
    user_id: str,
    field: str | None = None,
    old_value: str | None = None,
    new_value: str | None = None,
) -> RoomTaskEvent:
    """Factory for creating task events."""
    return RoomTaskEvent(
        id=str(uuid.uuid4()),
        task_id=task_id,
        room_id=room_id,
        action=action,
        field=field,
        old_value=old_value,
        new_value=new_value,
        actor_user_id=user_id,
        created_at=datetime.now(timezone.utc),
    )


def _stringify(val: Any) -> str | None:
    """Convert a value to string for event storage."""
    if val is None:
        return None
    if hasattr(val, "value"):
        return str(val.value)
    if isinstance(val, datetime):
        return val.isoformat()
    if isinstance(val, list):
        return ", ".join(str(v) for v in val)
    return str(val)


async def _check_room_member(room_id: str, user: User) -> None:
    """Verify room exists and user is a member."""
    require_found(await room_repo.get_room(room_id), "Room")
    require_member(await member_repo.is_member(room_id, user.id))


@router.get("/{room_id}/tasks")
async def list_room_tasks(
    room_id: str,
    status: str | None = None,
    user: User = Depends(get_current_user),
) -> list[RoomTaskResponse]:
    """Get all tasks for a room."""
    await _check_room_member(room_id, user)
    tasks = await task_repo.get_by_room(room_id, status=status)
    return [RoomTaskResponse.from_entity(t) for t in tasks]


@router.post("/{room_id}/tasks", status_code=201)
async def create_room_task(
    room_id: str,
    data: CreateRoomTaskRequest,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Create a new task in the room."""
    await _check_room_member(room_id, user)

    now = datetime.now(timezone.utc)
    max_pos = await task_repo.get_max_position(room_id, data.status.value)

    due_at = None
    if data.due_at:
        due_at = datetime.fromisoformat(data.due_at)

    task = RoomTask(
        id=str(uuid.uuid4()),
        room_id=room_id,
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        position=max_pos + 1.0,
        assigned_to_bot_id=data.assigned_to_bot_id,
        assigned_to_user_id=data.assigned_to_user_id,
        created_by_user_id=user.id,
        tags=data.tags,
        due_at=due_at,
        created_at=now,
        updated_at=now,
    )
    await task_repo.create(task)

    event = _make_event(
        task_id=task.id,
        room_id=room_id,
        action=RoomTaskEventAction.CREATED,
        user_id=user.id,
    )
    await event_repo.create(event)

    return RoomTaskResponse.from_entity(task)


@router.get("/{room_id}/tasks/{task_id}")
async def get_room_task(
    room_id: str,
    task_id: str,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Get a single task."""
    await _check_room_member(room_id, user)
    task = require_room_ownership(await task_repo.get(task_id), room_id, "Task")
    return RoomTaskResponse.from_entity(task)


@router.get("/{room_id}/tasks/{task_id}/events")
async def get_room_task_events(
    room_id: str,
    task_id: str,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
) -> list[RoomTaskEventResponse]:
    """Get activity history for a task."""
    await _check_room_member(room_id, user)

    require_room_ownership(await task_repo.get(task_id), room_id, "Task")

    events = await event_repo.get_by_task(task_id, limit=limit, offset=offset)
    return [RoomTaskEventResponse.from_entity(e) for e in events]


@router.patch("/{room_id}/tasks/{task_id}")
async def update_room_task(
    room_id: str,
    task_id: str,
    data: UpdateRoomTaskRequest,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Update a task."""
    await _check_room_member(room_id, user)

    existing = require_room_ownership(await task_repo.get(task_id), room_id, "Task")

    kwargs: dict[str, Any] = {}
    if data.title is not None:
        kwargs["title"] = data.title
    if data.description is not None:
        kwargs["description"] = data.description
    if data.status is not None:
        kwargs["status"] = data.status
    if data.priority is not None:
        kwargs["priority"] = data.priority
    if data.assigned_to_bot_id is not None:
        kwargs["assigned_to_bot_id"] = data.assigned_to_bot_id
    if data.assigned_to_user_id is not None:
        kwargs["assigned_to_user_id"] = data.assigned_to_user_id
    if data.tags is not None:
        kwargs["tags"] = data.tags
    if data.due_at is not None:
        kwargs["due_at"] = datetime.fromisoformat(data.due_at)

    # Build granular events by diffing each changed field
    events: list[RoomTaskEvent] = []
    for field_name, new_val in kwargs.items():
        old_val = getattr(existing, field_name, None)
        old_str = _stringify(old_val)
        new_str = _stringify(new_val)
        if old_str == new_str:
            continue
        action = _FIELD_ACTION_MAP.get(field_name, RoomTaskEventAction.UPDATED)
        events.append(
            _make_event(
                task_id=task_id,
                room_id=room_id,
                action=action,
                user_id=user.id,
                field=field_name,
                old_value=old_str,
                new_value=new_str,
            )
        )

    updated = require_found(await task_repo.update(task_id, **kwargs), "Task")

    if events:
        await event_repo.create_many(events)

    return RoomTaskResponse.from_entity(updated)


@router.patch("/{room_id}/tasks/{task_id}/reorder")
async def reorder_room_task(
    room_id: str,
    task_id: str,
    data: ReorderRoomTaskRequest,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Move a task to a new status column and position."""
    await _check_room_member(room_id, user)

    existing = require_room_ownership(await task_repo.get(task_id), room_id, "Task")

    old_status = _stringify(existing.status)
    new_status = _stringify(data.status)

    updated = require_found(
        await task_repo.reorder(task_id, data.status.value, data.position),
        "Task",
    )

    if old_status != new_status:
        event = _make_event(
            task_id=task_id,
            room_id=room_id,
            action=RoomTaskEventAction.STATUS_CHANGED,
            user_id=user.id,
            field="status",
            old_value=old_status,
            new_value=new_status,
        )
        await event_repo.create(event)

    return RoomTaskResponse.from_entity(updated)


@router.delete("/{room_id}/tasks/{task_id}", status_code=204)
async def delete_room_task(
    room_id: str,
    task_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete a task."""
    await _check_room_member(room_id, user)

    require_room_ownership(await task_repo.get(task_id), room_id, "Task")

    # Emit deleted event before deletion (will be cascaded away with the task)
    event = _make_event(
        task_id=task_id,
        room_id=room_id,
        action=RoomTaskEventAction.DELETED,
        user_id=user.id,
    )
    await event_repo.create(event)

    await task_repo.delete(task_id)

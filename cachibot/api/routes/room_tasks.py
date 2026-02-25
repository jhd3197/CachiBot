"""Room Tasks API Routes -- shared kanban board per room."""

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.room_task import (
    CreateRoomTaskRequest,
    ReorderRoomTaskRequest,
    RoomTask,
    RoomTaskResponse,
    UpdateRoomTaskRequest,
)
from cachibot.storage.room_repository import RoomMemberRepository, RoomRepository
from cachibot.storage.room_task_repository import RoomTaskRepository

router = APIRouter(prefix="/api/rooms", tags=["room-tasks"])

room_repo = RoomRepository()
member_repo = RoomMemberRepository()
task_repo = RoomTaskRepository()


async def _check_room_member(room_id: str, user: User) -> None:
    """Verify room exists and user is a member."""
    room = await room_repo.get_room(room_id)
    if room is None:
        raise HTTPException(status_code=404, detail="Room not found")
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")


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
    return RoomTaskResponse.from_entity(task)


@router.get("/{room_id}/tasks/{task_id}")
async def get_room_task(
    room_id: str,
    task_id: str,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Get a single task."""
    await _check_room_member(room_id, user)
    task = await task_repo.get(task_id)
    if task is None or task.room_id != room_id:
        raise HTTPException(status_code=404, detail="Task not found")
    return RoomTaskResponse.from_entity(task)


@router.patch("/{room_id}/tasks/{task_id}")
async def update_room_task(
    room_id: str,
    task_id: str,
    data: UpdateRoomTaskRequest,
    user: User = Depends(get_current_user),
) -> RoomTaskResponse:
    """Update a task."""
    await _check_room_member(room_id, user)

    existing = await task_repo.get(task_id)
    if existing is None or existing.room_id != room_id:
        raise HTTPException(status_code=404, detail="Task not found")

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

    updated = await task_repo.update(task_id, **kwargs)
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
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

    existing = await task_repo.get(task_id)
    if existing is None or existing.room_id != room_id:
        raise HTTPException(status_code=404, detail="Task not found")

    updated = await task_repo.reorder(task_id, data.status.value, data.position)
    if updated is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return RoomTaskResponse.from_entity(updated)


@router.delete("/{room_id}/tasks/{task_id}", status_code=204)
async def delete_room_task(
    room_id: str,
    task_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete a task."""
    await _check_room_member(room_id, user)

    existing = await task_repo.get(task_id)
    if existing is None or existing.room_id != room_id:
        raise HTTPException(status_code=404, detail="Task not found")

    await task_repo.delete(task_id)

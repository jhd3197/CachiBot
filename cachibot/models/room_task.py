"""Pydantic models for room tasks (shared kanban board)."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RoomTaskStatus(str, Enum):
    """Status of a room task."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    BLOCKED = "blocked"


class RoomTaskPriority(str, Enum):
    """Priority of a room task."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class RoomTask(BaseModel):
    """A task on a room's shared kanban board."""

    id: str
    room_id: str
    title: str
    description: str | None = None
    status: RoomTaskStatus = RoomTaskStatus.TODO
    priority: RoomTaskPriority = RoomTaskPriority.NORMAL
    position: float = 0.0
    assigned_to_bot_id: str | None = None
    assigned_to_user_id: str | None = None
    created_by_user_id: str | None = None
    created_by_bot_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class CreateRoomTaskRequest(BaseModel):
    """Request to create a room task."""

    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    status: RoomTaskStatus = RoomTaskStatus.TODO
    priority: RoomTaskPriority = RoomTaskPriority.NORMAL
    assigned_to_bot_id: str | None = None
    assigned_to_user_id: str | None = None
    tags: list[str] = Field(default_factory=list)
    due_at: str | None = None


class UpdateRoomTaskRequest(BaseModel):
    """Request to update a room task."""

    title: str | None = None
    description: str | None = None
    status: RoomTaskStatus | None = None
    priority: RoomTaskPriority | None = None
    assigned_to_bot_id: str | None = None
    assigned_to_user_id: str | None = None
    tags: list[str] | None = None
    due_at: str | None = None


class ReorderRoomTaskRequest(BaseModel):
    """Request to reorder a room task."""

    status: RoomTaskStatus
    position: float


class RoomTaskEventAction(str, Enum):
    """Type of activity event on a room task."""

    CREATED = "created"
    UPDATED = "updated"
    STATUS_CHANGED = "status_changed"
    PRIORITY_CHANGED = "priority_changed"
    ASSIGNED = "assigned"
    DELETED = "deleted"


class RoomTaskEvent(BaseModel):
    """A single activity event on a room task."""

    id: str
    task_id: str
    room_id: str
    action: RoomTaskEventAction
    field: str | None = None
    old_value: str | None = None
    new_value: str | None = None
    actor_user_id: str | None = None
    actor_bot_id: str | None = None
    created_at: datetime


class RoomTaskEventResponse(BaseModel):
    """Response model for a room task event."""

    id: str
    taskId: str
    roomId: str
    action: str
    field: str | None
    oldValue: str | None
    newValue: str | None
    actorUserId: str | None
    actorBotId: str | None
    createdAt: str

    @classmethod
    def from_entity(cls, event: RoomTaskEvent) -> "RoomTaskEventResponse":
        return cls(
            id=event.id,
            taskId=event.task_id,
            roomId=event.room_id,
            action=event.action.value
            if isinstance(event.action, RoomTaskEventAction)
            else event.action,
            field=event.field,
            oldValue=event.old_value,
            newValue=event.new_value,
            actorUserId=event.actor_user_id,
            actorBotId=event.actor_bot_id,
            createdAt=event.created_at.isoformat(),
        )


class RoomTaskResponse(BaseModel):
    """Response model for a room task."""

    id: str
    roomId: str
    title: str
    description: str | None
    status: str
    priority: str
    position: float
    assignedToBotId: str | None
    assignedToUserId: str | None
    createdByUserId: str | None
    createdByBotId: str | None
    tags: list[str]
    dueAt: str | None
    createdAt: str
    updatedAt: str

    @classmethod
    def from_entity(cls, task: RoomTask) -> "RoomTaskResponse":
        return cls(
            id=task.id,
            roomId=task.room_id,
            title=task.title,
            description=task.description,
            status=task.status.value if isinstance(task.status, RoomTaskStatus) else task.status,
            priority=task.priority.value
            if isinstance(task.priority, RoomTaskPriority)
            else task.priority,
            position=task.position,
            assignedToBotId=task.assigned_to_bot_id,
            assignedToUserId=task.assigned_to_user_id,
            createdByUserId=task.created_by_user_id,
            createdByBotId=task.created_by_bot_id,
            tags=task.tags,
            dueAt=task.due_at.isoformat() if task.due_at else None,
            createdAt=task.created_at.isoformat(),
            updatedAt=task.updated_at.isoformat(),
        )

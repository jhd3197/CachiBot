from __future__ import annotations

from typing import Any, TypeVar

from fastapi import HTTPException

T = TypeVar("T")


def require_found(value: T | None, label: str = "Resource") -> T:
    """Raise 404 if *value* is ``None`` or ``False``.

    Use for both "get-or-404" and "delete-or-404" patterns::

        bot = require_found(await repo.get_bot(bot_id), "Bot")
        require_found(await repo.delete_bot(bot_id), "Bot")
    """
    if value is None or value is False:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return value


def require_bot_ownership(record: Any, bot_id: str, label: str = "Resource") -> Any:
    """Raise 404 if record is None or doesn't belong to the given bot."""
    if not record or record.bot_id != bot_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def require_room_ownership(record: Any, room_id: str, label: str = "Resource") -> Any:
    """Raise 404 if record is None or doesn't belong to the given room.

    Mirrors :func:`require_bot_ownership` but checks ``room_id``.
    """
    if not record or record.room_id != room_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record


def require_member(is_member: bool, label: str = "room") -> None:
    """Raise 403 if the caller is not a member of *label*."""
    if not is_member:
        raise HTTPException(status_code=403, detail=f"Not a {label} member")


def require_role(
    actual_role: str | None,
    required_role: str,
    action: str = "perform this action",
) -> None:
    """Raise 403 unless *actual_role* matches *required_role*.

    Example::

        role = await member_repo.get_member_role(room_id, user.id)
        require_role(role, RoomMemberRole.CREATOR, "update room settings")
    """
    if actual_role != required_role:
        raise HTTPException(
            status_code=403,
            detail=f"Only the {required_role} can {action}",
        )

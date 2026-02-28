from __future__ import annotations

from typing import TypeVar, overload

from fastapi import HTTPException

T = TypeVar("T")


@overload
def require_found(value: T | None, label: str = "Resource") -> T: ...


@overload
def require_found(value: bool, label: str = "Resource") -> bool: ...


def require_found(value: T | None | bool, label: str = "Resource") -> T | bool:
    """Raise 404 if *value* is ``None`` or falsy.

    Use for both "get-or-404" and "delete-or-404" patterns::

        bot = require_found(await repo.get_bot(bot_id), "Bot")
        require_found(await repo.delete_bot(bot_id), "Bot")
    """
    if value is None or value is False:
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return value


def require_bot_ownership(record: T | None, bot_id: str, label: str = "Resource") -> T:
    """Raise 404 if record is None or doesn't belong to the given bot."""
    if not record or record.bot_id != bot_id:  # type: ignore[union-attr]
        raise HTTPException(status_code=404, detail=f"{label} not found")
    return record

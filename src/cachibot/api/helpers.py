from __future__ import annotations

from typing import Any

from fastapi import HTTPException


def require_bot_ownership(record: Any, bot_id: str, label: str = "Resource") -> None:
    """Raise 404 if record is None or doesn't belong to the given bot."""
    if not record or record.bot_id != bot_id:
        raise HTTPException(status_code=404, detail=f"{label} not found")

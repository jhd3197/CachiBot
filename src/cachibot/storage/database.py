"""
Database Setup and Connection Management — Backward Compatibility Wrapper

Delegates to the new PostgreSQL-based db.py module.
Kept for backward compatibility during the migration period.

Legacy code that imports from here (init_db, close_db, get_db) will
continue to work, but callers should migrate to using
`cachibot.storage.db` and the repository pattern with AsyncSession.
"""

from __future__ import annotations

import warnings

from cachibot.storage import db
from cachibot.storage.db import close_db, init_db

__all__ = ["init_db", "close_db", "get_db"]


async def get_db():
    """Legacy compatibility shim.

    Returns an async session for callers that still use `get_db()`.

    .. deprecated::
        Use ``async with db.async_session_maker() as session:`` directly,
        or inject via ``get_session()`` from ``cachibot.storage.db``.
    """
    warnings.warn(
        "get_db() is deprecated. Use db.async_session_maker() context manager "
        "or cachibot.storage.db.get_session() instead.",
        DeprecationWarning,
        stacklevel=2,
    )
    return db.async_session_maker()

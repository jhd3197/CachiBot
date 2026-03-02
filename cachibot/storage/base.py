"""
Base Repository — generic CRUD helpers for all CachiBot repositories.

Eliminates the repeated ``async with db.ensure_initialized()() as session``
boilerplate and the identical get-by-id / delete-by-id / list-all patterns
that every repository duplicates.

Subclasses set ``_model`` to their SQLAlchemy ORM class and implement
``_row_to_entity`` to convert a row into a Pydantic domain object.
"""

from __future__ import annotations

from abc import abstractmethod
from contextlib import asynccontextmanager
from typing import Any, Generic, TypeVar

from sqlalchemy import Delete, Select, Update, delete, select

from cachibot.storage import db

ModelT = TypeVar("ModelT")
EntityT = TypeVar("EntityT")


class BaseRepository(Generic[ModelT, EntityT]):
    """Async repository base with common CRUD helpers.

    Class attributes that subclasses should set:

        _model:  The SQLAlchemy ORM model class (e.g. ``BotModel``).

    Subclasses **must** implement:

        _row_to_entity(row) -> EntityT
    """

    _model: type[ModelT]

    # ------------------------------------------------------------------
    # Session helper
    # ------------------------------------------------------------------

    @staticmethod
    @asynccontextmanager
    async def _session() -> Any:
        """Yield an ``AsyncSession`` from the shared session maker."""
        async with db.ensure_initialized()() as session:
            yield session

    # ------------------------------------------------------------------
    # Abstract converter
    # ------------------------------------------------------------------

    @abstractmethod
    def _row_to_entity(self, row: ModelT) -> EntityT:
        """Convert a SQLAlchemy row into a domain entity."""
        ...

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    async def _fetch_one(self, stmt: Select[Any]) -> EntityT | None:
        """Execute *stmt*, return the first scalar converted via ``_row_to_entity``, or ``None``."""
        async with self._session() as session:
            result = await session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._row_to_entity(row)

    async def _fetch_all(self, stmt: Select[Any]) -> list[EntityT]:
        """Execute *stmt*, return all scalars converted via ``_row_to_entity``."""
        async with self._session() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
        return [self._row_to_entity(row) for row in rows]

    async def _scalar(self, stmt: Select[Any]) -> Any:
        """Execute *stmt* and return the raw scalar result (for counts, etc.)."""
        async with self._session() as session:
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    # ------------------------------------------------------------------
    # Write helpers
    # ------------------------------------------------------------------

    async def _add(self, obj: ModelT) -> None:
        """Add a single ORM object and commit."""
        async with self._session() as session:
            session.add(obj)
            await session.commit()

    async def _update(self, stmt: Update) -> int:
        """Execute an UPDATE statement and commit. Returns affected row count."""
        async with self._session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount)

    async def _delete(self, stmt: Delete) -> int:
        """Execute a DELETE statement and commit. Returns affected row count."""
        async with self._session() as session:
            result = await session.execute(stmt)
            await session.commit()
            return int(result.rowcount)

    # ------------------------------------------------------------------
    # Common CRUD (use _model)
    # ------------------------------------------------------------------

    async def get_by_id(self, entity_id: str) -> EntityT | None:
        """Fetch a single row by its ``id`` column."""
        return await self._fetch_one(
            select(self._model).where(self._model.id == entity_id)  # type: ignore[attr-defined]
        )

    async def delete_by_id(self, entity_id: str) -> bool:
        """Delete a single row by ``id``. Returns ``True`` if a row was removed."""
        count = await self._delete(
            delete(self._model).where(self._model.id == entity_id)  # type: ignore[attr-defined]
        )
        return count > 0

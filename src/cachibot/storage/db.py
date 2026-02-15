"""
PostgreSQL Database Setup and Connection Management

Uses SQLAlchemy 2.0 async with asyncpg for PostgreSQL operations.
Replaces the legacy SQLite database.py (kept for migration period).
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all CachiBot models."""

    pass


# Module-level engine and session maker — initialized lazily via init_db()
engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None


def _create_engine_from_config() -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create engine and session maker from CachiBot config.

    Reads DatabaseConfig from Config (which respects DATABASE_URL env var,
    TOML config files, and defaults). Falls back to env var directly if
    Config is not loadable.
    """
    try:
        from cachibot.config import Config

        config = Config.load()
        db_config = config.database
        url = db_config.get_url()
        pool_size = db_config.pool_size
        max_overflow = db_config.max_overflow
        pool_recycle = db_config.pool_recycle
        echo = db_config.echo
    except Exception:
        import os

        url = os.getenv("CACHIBOT_DATABASE_URL") or os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://localhost:5432/cachibot",
        )
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+asyncpg" not in url:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        pool_size = 10
        max_overflow = 20
        pool_recycle = 3600
        echo = False

    eng = create_async_engine(
        url,
        echo=echo,
        future=True,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
        pool_pre_ping=True,
    )

    session_maker = async_sessionmaker(
        eng,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    return eng, session_maker


def _ensure_initialized() -> async_sessionmaker[AsyncSession]:
    """Ensure engine and session maker are initialized. Returns session maker."""
    global engine, async_session_maker
    if async_session_maker is None:
        engine, async_session_maker = _create_engine_from_config()
    return async_session_maker


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session.

    Usage as a FastAPI dependency or async context manager:
        async for session in get_session():
            ...
    """
    session_maker = _ensure_initialized()
    async with session_maker() as session:
        yield session


async def init_db() -> None:
    """Initialize the database connection and create tables if needed.

    In production, tables are managed by Alembic migrations.
    This function ensures the engine is ready and connectivity is verified.
    """
    global engine, async_session_maker
    engine, async_session_maker = _create_engine_from_config()

    # Import all models so Base.metadata is fully populated
    import cachibot.storage.models  # noqa: F401

    # Verify connectivity
    async with engine.begin():
        pass


async def close_db() -> None:
    """Dispose of the database engine and close all connections."""
    global engine, async_session_maker
    if engine:
        await engine.dispose()
    engine = None
    async_session_maker = None

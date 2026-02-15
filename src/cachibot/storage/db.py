"""
Smart Database Setup — auto-detects and configures the right database.

- No DATABASE_URL set -> auto-creates SQLite at ~/.cachibot/cachibot.db (zero config)
- DATABASE_URL set -> use it (PostgreSQL, SQLite, whatever SQLAlchemy supports)
- Logs clearly which database is being used
- Auto-creates ~/.cachibot directory
- Enables WAL mode for SQLite
- Connection pooling for PostgreSQL
- Helpful error messages for connection failures
"""

from __future__ import annotations

import logging
import os
from collections.abc import AsyncGenerator
from pathlib import Path

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger("cachibot.database")


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base for all CachiBot models."""

    pass


# Module-level engine and session maker — initialized lazily via init_db()
engine: AsyncEngine | None = None
async_session_maker: async_sessionmaker[AsyncSession] | None = None

# Database dialect: "sqlite" or "postgresql" (set during init_db)
db_type: str = "sqlite"


def resolve_database_url() -> str:
    """Determine the database URL from config, env vars, or default.

    Resolution order (highest priority first):
        1. CACHIBOT_DATABASE_URL env var
        2. DATABASE_URL env var
        3. Config TOML database.url (if non-empty)
        4. Default: sqlite+aiosqlite at ~/.cachibot/cachibot.db
    """
    # 1. Check env vars
    url = os.getenv("CACHIBOT_DATABASE_URL") or os.getenv("DATABASE_URL") or ""

    # 2. Check TOML config if no env var
    if not url:
        try:
            from cachibot.config import Config

            config = Config.load()
            url = config.database.url
        except Exception:
            pass

    # 3. Default to SQLite
    if not url:
        db_dir = Path.home() / ".cachibot"
        db_path = db_dir / "cachibot.db"
        url = f"sqlite+aiosqlite:///{db_path}"

    # Normalize PostgreSQL URLs for asyncpg
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and "+asyncpg" not in url:
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)

    return url


def _detect_db_type(url: str) -> str:
    """Detect database type from URL string."""
    if url.startswith("sqlite"):
        return "sqlite"
    if url.startswith("postgres"):
        return "postgresql"
    # Fallback: try to parse the dialect
    return url.split("://")[0].split("+")[0] if "://" in url else "sqlite"


def _create_engine_from_url(
    url: str,
    echo: bool = False,
    pool_size: int = 10,
    max_overflow: int = 20,
    pool_recycle: int = 3600,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create engine and session maker configured for the detected dialect.

    SQLite: uses aiosqlite with StaticPool, enables WAL journal mode.
    PostgreSQL: uses asyncpg with connection pooling and pre-ping.
    """
    detected = _detect_db_type(url)

    if detected == "sqlite":
        from sqlalchemy.pool import StaticPool

        eng = create_async_engine(
            url,
            echo=echo,
            future=True,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )

        # Enable WAL mode for better concurrent read performance
        @event.listens_for(eng.sync_engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, connection_record):  # type: ignore[no-untyped-def]
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    else:
        # PostgreSQL (or other server-based DB)
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
    global engine, async_session_maker, db_type
    if async_session_maker is None:
        url = resolve_database_url()
        db_type = _detect_db_type(url)

        try:
            from cachibot.config import Config

            config = Config.load()
            db_config = config.database
            echo = db_config.echo
            pool_size = db_config.pool_size
            max_overflow = db_config.max_overflow
            pool_recycle = db_config.pool_recycle
        except Exception:
            echo = False
            pool_size = 10
            max_overflow = 20
            pool_recycle = 3600

        engine, async_session_maker = _create_engine_from_url(
            url,
            echo=echo,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_recycle=pool_recycle,
        )
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

    - Creates ~/.cachibot/ directory for SQLite if needed
    - Creates engine with dialect-appropriate settings
    - Verifies connectivity
    - Auto-creates all tables for fresh installs (via Base.metadata.create_all)
    - Logs which database backend is being used
    """
    global engine, async_session_maker, db_type

    url = resolve_database_url()
    db_type = _detect_db_type(url)

    # Load config for pool settings
    try:
        from cachibot.config import Config

        config = Config.load()
        db_config = config.database
        echo = db_config.echo
        pool_size = db_config.pool_size
        max_overflow = db_config.max_overflow
        pool_recycle = db_config.pool_recycle
    except Exception:
        echo = False
        pool_size = 10
        max_overflow = 20
        pool_recycle = 3600

    # For SQLite, ensure the parent directory exists
    if db_type == "sqlite":
        # Extract path from URL: sqlite+aiosqlite:///path/to/db
        db_path_str = url.split("///", 1)[-1] if "///" in url else ""
        if db_path_str:
            db_dir = Path(db_path_str).parent
            db_dir.mkdir(parents=True, exist_ok=True)
            logger.info("Using SQLite at %s", db_path_str)
        else:
            logger.info("Using SQLite (in-memory)")
    else:
        # Log PostgreSQL connection (mask password)
        safe_url = url
        if "@" in safe_url:
            # Mask the password portion
            pre_at = safe_url.split("@")[0]
            post_at = safe_url.split("@", 1)[1]
            if ":" in pre_at.split("//")[-1]:
                user = pre_at.split("//")[-1].split(":")[0]
                scheme = pre_at.split("//")[0]
                safe_url = f"{scheme}//{user}:***@{post_at}"
        logger.info("Using PostgreSQL at %s", safe_url)

    engine, async_session_maker = _create_engine_from_url(
        url,
        echo=echo,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_recycle=pool_recycle,
    )

    # Import all models so Base.metadata is fully populated
    import cachibot.storage.models  # noqa: F401

    # Verify connectivity and create tables
    try:
        async with engine.begin() as conn:
            # For PostgreSQL, try to enable pgvector if available
            if db_type == "postgresql":
                try:
                    await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
                except Exception:
                    logger.warning(
                        "pgvector extension not available. Vector search features will be limited."
                    )

            # Create all tables that don't exist yet
            await conn.run_sync(Base.metadata.create_all)

    except Exception as e:
        if db_type == "postgresql":
            logger.error(
                "Failed to connect to PostgreSQL: %s. "
                "Check your DATABASE_URL or remove it to use SQLite (default).",
                e,
            )
        else:
            logger.error("Failed to initialize SQLite database: %s", e)
        raise


async def close_db() -> None:
    """Dispose of the database engine and close all connections."""
    global engine, async_session_maker
    if engine:
        await engine.dispose()
    engine = None
    async_session_maker = None

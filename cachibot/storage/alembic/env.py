"""
Alembic environment configuration for CachiBot.

Supports both async PostgreSQL (asyncpg) and async SQLite (aiosqlite) migrations.
Reads DATABASE_URL from environment variables, falling back to the smart db module.
"""

from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

# Import Base and ALL models so metadata is fully populated
from cachibot.storage.db import Base
from cachibot.storage.models import (  # noqa: F401
    Bot,
    BotConnection,
    BotContact,
    BotDocument,
    BotInstruction,
    BotMessage,
    BotNote,
    BotOwnership,
    BotSkill,
    Chat,
    DocChunk,
    Function,
    Job,
    Message,
    Room,
    RoomBot,
    RoomMember,
    RoomMessage,
    Schedule,
    Skill,
    Task,
    Todo,
    User,
    Work,
    WorkJob,
)

# Alembic Config object (provides access to .ini values)
config = context.config

# Interpret the config file for Python logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata for autogenerate support
target_metadata = Base.metadata


def _get_url() -> str:
    """Resolve the database URL from environment or the smart db module."""
    url = os.getenv("CACHIBOT_DATABASE_URL") or os.getenv("DATABASE_URL")
    if url:
        # Auto-convert postgres:// to the right async driver
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://") and "+" not in url.split("://")[0]:
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Fall back to the smart resolver (which defaults to SQLite)
    try:
        from cachibot.storage.db import resolve_database_url

        return resolve_database_url()
    except Exception:
        pass

    return config.get_main_option("sqlalchemy.url", "sqlite+aiosqlite:///cachibot.db")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    Generates SQL scripts without connecting to the database.
    """
    url = _get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=url.startswith("sqlite"),  # SQLite needs batch mode for ALTER
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Run migrations using a synchronous connection."""
    url = _get_url()
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=url.startswith("sqlite"),  # SQLite needs batch mode for ALTER
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using an async engine.

    Uses NullPool to avoid connection pool issues during migrations.
    """
    url = _get_url()
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

"""Shared test fixtures for CachiBot test suite."""

import os

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.storage.db import Base

# Default test database URL — uses the docker-compose PostgreSQL on port 5433.
# Override with TEST_DATABASE_URL env var for CI or custom setups.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot_test",
)


@pytest.fixture
async def pg_db():
    """Set up a test PostgreSQL database with all tables.

    Creates fresh tables before the test and drops them after.
    Patches cachibot.storage.db module-level engine/session so that
    all repositories use the test database automatically.

    Requires:
        - PostgreSQL with pgvector running (docker compose up -d db)
        - Test database created::

            docker exec cachibot-db psql -U cachibot -d postgres \
                -c "CREATE DATABASE cachibot_test OWNER cachibot;"
            docker exec cachibot-db psql -U cachibot -d cachibot_test \
                -c "CREATE EXTENSION IF NOT EXISTS vector;"
    """
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    session_maker = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Import all ORM models so Base.metadata is fully populated
    import cachibot.storage.models  # noqa: F401

    # Create pgvector extension (idempotent) and all tables
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Patch module-level variables so repositories use the test database
    original_engine = db_mod.engine
    original_session_maker = db_mod.async_session_maker
    db_mod.engine = engine
    db_mod.async_session_maker = session_maker

    yield session_maker

    # Teardown: drop all tables and restore originals
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    db_mod.engine = original_engine
    db_mod.async_session_maker = original_session_maker

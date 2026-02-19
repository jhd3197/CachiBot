"""Shared test fixtures for CachiBot test suite."""

import os
import uuid
from datetime import datetime, timezone

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.config import AuthConfig
from cachibot.models.auth import UserInDB, UserRole
from cachibot.services.auth_service import AuthService
from cachibot.storage.db import Base
from cachibot.storage.user_repository import UserRepository

# Default test database URL — uses the docker-compose PostgreSQL on port 5433.
# Override with TEST_DATABASE_URL env var for CI or custom setups.
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot_test",
)

# Fixed JWT secret for deterministic test tokens
TEST_JWT_SECRET = "test-secret-for-unit-tests-only-do-not-use-in-production"


@pytest.fixture
async def pg_db(request):
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

    # Test connectivity — skip if Postgres is not reachable
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        await engine.dispose()
        pytest.skip("PostgreSQL not available")

    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

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


# ---------------------------------------------------------------------------
# Auth service fixture — deterministic JWT secret for testing
# ---------------------------------------------------------------------------


@pytest.fixture
def auth_service():
    """Create a test AuthService with a fixed JWT secret.

    Patches the global singleton so all code paths (routes, dependencies)
    use the same test instance.
    """
    import cachibot.services.auth_service as auth_mod

    svc = AuthService(AuthConfig(jwt_secret=TEST_JWT_SECRET))
    original = auth_mod._auth_service
    auth_mod._auth_service = svc
    yield svc
    auth_mod._auth_service = original


# ---------------------------------------------------------------------------
# API test client
# ---------------------------------------------------------------------------


@pytest.fixture
async def api_client(pg_db, auth_service):
    """Async HTTP client wired to the FastAPI app (no lifespan).

    The app is created fresh and routes use the test-patched DB engine
    (via pg_db) and test auth service (via auth_service). The lifespan
    is intentionally skipped to avoid starting schedulers / platform
    managers during tests.
    """
    from fastapi import FastAPI

    from cachibot.api.routes import auth, chat, custom_instructions

    app = FastAPI()
    app.include_router(auth.router, prefix="/api", tags=["auth"])
    app.include_router(chat.router, prefix="/api", tags=["chat"])
    app.include_router(custom_instructions.router, tags=["custom-instructions"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------


async def create_test_user(
    auth_service: AuthService,
    *,
    email: str = "test@example.com",
    username: str = "testuser",
    password: str = "testpassword123",
    role: UserRole = UserRole.USER,
) -> tuple[UserInDB, str]:
    """Create a user in the test DB and return (user, raw_password).

    Returns the UserInDB and the plaintext password for login tests.
    """
    repo = UserRepository()
    now = datetime.now(timezone.utc)

    user = UserInDB(
        id=str(uuid.uuid4()),
        email=email.lower(),
        username=username.lower(),
        password_hash=auth_service.hash_password(password),
        role=role,
        is_active=True,
        created_at=now,
        created_by=None,
        last_login=None,
    )
    await repo.create_user(user)
    return user, password


@pytest.fixture
async def admin_user_with_token(api_client, auth_service):
    """Create an admin user and return (User, access_token)."""
    user, _ = await create_test_user(
        auth_service,
        email="admin@test.com",
        username="admin",
        password="adminpass123",
        role=UserRole.ADMIN,
    )
    token = auth_service.create_access_token(user.id, user.role.value)
    return user, token


@pytest.fixture
async def regular_user_with_token(api_client, auth_service):
    """Create a regular user and return (User, access_token)."""
    user, _ = await create_test_user(
        auth_service,
        email="user@test.com",
        username="regularuser",
        password="userpass1234",
        role=UserRole.USER,
    )
    token = auth_service.create_access_token(user.id, user.role.value)
    return user, token

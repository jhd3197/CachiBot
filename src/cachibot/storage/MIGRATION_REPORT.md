# SQLite to PostgreSQL Migration Report

**Date**: 2026-02-14
**Migration Team**: ORM Modeler, Infrastructure, Query Migrator, Vector Search Migrator
**Reviewer**: Integration Tester

---

## 1. Summary of What Was Migrated

CachiBot's data layer was fully migrated from **SQLite (aiosqlite)** to **PostgreSQL (asyncpg)** using SQLAlchemy 2.0 ORM. The migration covers:

- **25 ORM models** defined across 12 model files under `storage/models/`
- **13 repository classes** across 4 repository files, all rewritten from raw SQL to SQLAlchemy ORM queries
- **Vector search** migrated from in-memory numpy cosine similarity + binary BLOB storage to **pgvector** with HNSW indexing
- **Alembic** migration framework added for schema management
- **Docker Compose** updated with `pgvector/pgvector:pg16` image
- **Configuration** updated with `DatabaseConfig` dataclass and environment variable support

---

## 2. All Files Changed

### New Files (created for migration)

| File | Purpose |
|------|---------|
| `src/cachibot/storage/db.py` | New PostgreSQL engine, Base, session factory, init/close lifecycle |
| `src/cachibot/storage/models/__init__.py` | Exports all 25 ORM models + Base |
| `src/cachibot/storage/models/base.py` | `TimestampMixin`, `BotScopedMixin` |
| `src/cachibot/storage/models/bot.py` | `Bot`, `BotOwnership` ORM models |
| `src/cachibot/storage/models/chat.py` | `Chat` ORM model |
| `src/cachibot/storage/models/connection.py` | `BotConnection` ORM model |
| `src/cachibot/storage/models/contact.py` | `BotContact` ORM model |
| `src/cachibot/storage/models/job.py` | `Job` ORM model |
| `src/cachibot/storage/models/knowledge.py` | `BotInstruction`, `BotDocument`, `DocChunk` (with pgvector `Vector(384)`) |
| `src/cachibot/storage/models/message.py` | `Message`, `BotMessage` ORM models |
| `src/cachibot/storage/models/room.py` | `Room`, `RoomMember`, `RoomBot`, `RoomMessage` ORM models |
| `src/cachibot/storage/models/skill.py` | `Skill`, `BotSkill` ORM models |
| `src/cachibot/storage/models/user.py` | `User` ORM model |
| `src/cachibot/storage/models/work.py` | `Function`, `Schedule`, `Work`, `Task`, `WorkJob`, `Todo` ORM models |
| `src/cachibot/storage/alembic/env.py` | Alembic environment with async asyncpg support |
| `src/cachibot/storage/alembic/versions/001_initial_schema.py` | Initial migration creating all 25 tables + pgvector extension |
| `alembic.ini` | Alembic configuration pointing to `src/cachibot/storage/alembic` |
| `docker-compose.yml` | PostgreSQL + pgvector container, backend, frontend services |
| `.env.example` | `DATABASE_URL` template |
| `scripts/init_pgvector.sql` | PostgreSQL initialization script for pgvector |
| `scripts/migrate_sqlite_to_postgres.py` | Data migration script from SQLite to PostgreSQL |

### Modified Files

| File | What Changed |
|------|-------------|
| `src/cachibot/storage/__init__.py` | Updated exports to import from `db.py` and all 4 repository modules |
| `src/cachibot/storage/database.py` | Converted to backward-compatibility wrapper delegating to `db.py` |
| `src/cachibot/storage/repository.py` | Rewritten: raw aiosqlite SQL replaced with SQLAlchemy ORM queries (9 repositories) |
| `src/cachibot/storage/work_repository.py` | Rewritten: raw aiosqlite SQL replaced with SQLAlchemy ORM queries (6 repositories) |
| `src/cachibot/storage/room_repository.py` | Rewritten: raw aiosqlite SQL replaced with SQLAlchemy ORM queries (4 repositories) |
| `src/cachibot/storage/user_repository.py` | Rewritten: raw aiosqlite SQL replaced with SQLAlchemy ORM queries (2 repositories) |
| `src/cachibot/services/vector_store.py` | Migrated from in-memory cosine similarity to pgvector `cosine_distance()` |
| `src/cachibot/config.py` | Added `DatabaseConfig` dataclass with pool settings |
| `pyproject.toml` | Added `sqlalchemy[asyncio]`, `asyncpg`, `alembic`, `pgvector`; removed `aiosqlite`, `sqlite-vec` |

---

## 3. Issues Found

### CRITICAL

#### C1. `RoomMessageRepository.get_messages()` -- `before` parameter type mismatch

**File**: `src/cachibot/storage/room_repository.py`, line ~299
**Problem**: The `before` parameter is typed as `str | None`, but is compared against `RoomMessageModel.timestamp` which is a `DateTime(timezone=True)` column. The comparison `RoomMessageModel.timestamp < before` will cause a runtime type error or incorrect comparison when a string is passed.

```python
async def get_messages(
    self,
    room_id: str,
    limit: int = 50,
    before: str | None = None,   # <-- str, but compared to DateTime column
) -> list[RoomMessage]:
    ...
    if before:
        stmt = stmt.where(RoomMessageModel.timestamp < before)  # Type mismatch
```

**Fix required**: Change `before` to `datetime | None` and ensure callers pass a datetime object, or parse the string to datetime before comparison.

---

#### C2. `db.py` ignores `Config.database` settings

**File**: `src/cachibot/storage/db.py`, lines 49-57
**File**: `src/cachibot/config.py`, lines 145-166
**Problem**: The database engine in `db.py` is created at **module import time** by reading environment variables directly via `_get_database_url()`. The `DatabaseConfig` class in `config.py` has `pool_size`, `max_overflow`, `pool_recycle`, and `echo` settings that are **never consumed** by `db.py`. The engine hardcodes `pool_size=10, max_overflow=20, pool_recycle=3600, echo=False`.

```python
# db.py -- hardcoded values, ignores Config.database
engine = create_async_engine(
    _get_database_url(),
    echo=False,
    future=True,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    pool_pre_ping=True,
)
```

```python
# config.py -- these settings are never read by db.py
@dataclass
class DatabaseConfig:
    url: str = "postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot"
    pool_size: int = 10
    max_overflow: int = 20
    pool_recycle: int = 3600
    echo: bool = False
```

The `cachibot.example.toml` documents `[database]` section with these settings, giving users the impression they can configure pool behavior via TOML -- but these settings are silently ignored.

**Fix required**: Either (a) have `db.py` read from `Config.database` before creating the engine (requires deferred engine initialization), or (b) remove `DatabaseConfig` pool settings from `config.py` and `cachibot.example.toml` to avoid confusion.

---

#### C3. Test files reference removed SQLite globals and removed VectorStore methods

**File**: `tests/test_kb_pipeline.py`, lines 9, 22-29
**File**: `tests/test_scheduler.py`, lines 10, 21-28
**Problem**: Both test files still use the old SQLite test setup pattern:

```python
import cachibot.storage.database as db_mod
# ...
db_mod.DB_PATH = test_db    # DOES NOT EXIST in new db.py/database.py
db_mod._db = None            # DOES NOT EXIST in new db.py/database.py
await db_mod.init_db()
```

The attributes `DB_PATH` and `_db` were removed during the migration. These tests will crash with `AttributeError` at setup time.

Additionally, `test_kb_pipeline.py` tests reference methods that no longer exist in `VectorStore`:

| Test Class | Method Called | Status |
|-----------|-------------|--------|
| `TestVectorStoreSerialization` | `VectorStore.deserialize_embedding()` | **REMOVED** -- pgvector handles deserialization natively |
| `TestVectorStoreSerialization` | `VectorStore.serialize_embedding()` returning `bytes` | **CHANGED** -- now returns `list[float]` instead of `bytes` |
| `TestCosineSimilarity` | `VectorStore.cosine_similarity()` | **REMOVED** -- pgvector handles similarity server-side |
| `TestVectorStoreSearch` | `VectorStore._repo.get_all_embeddings_by_bot()` | **REMOVED** -- search now uses pgvector SQL, not in-memory |

All tests in classes `TestVectorStoreSerialization`, `TestCosineSimilarity`, and `TestVectorStoreSearch` need to be rewritten.

---

### WARNING

#### W1. `datetime.utcnow()` produces naive datetimes vs timezone-aware DB columns

**Files**: `repository.py` (10 occurrences), `work_repository.py` (12 occurrences), `room_repository.py` (1 occurrence), `user_repository.py` (1 occurrence)
**Total**: 24 occurrences across 4 repository files

**Problem**: All repository files use `datetime.utcnow()` which returns a **naive** datetime (no tzinfo). However, all ORM models use `DateTime(timezone=True)` columns via the `TimestampMixin`. PostgreSQL will accept naive datetimes and treat them as UTC by default, but:

1. `datetime.utcnow()` is deprecated since Python 3.12 (see PEP 587)
2. Naive datetimes mixed with timezone-aware datetimes from PostgreSQL can cause comparison issues
3. SQLAlchemy may warn about timezone-naive vs timezone-aware comparisons

**Recommendation**: Replace all `datetime.utcnow()` with `datetime.now(timezone.utc)` for consistency with timezone-aware columns.

---

#### W2. `server.py` imports from deprecated backward-compatibility wrapper

**File**: `src/cachibot/api/server.py`, line 51
**Problem**: The server imports `init_db` and `close_db` from the deprecated wrapper:

```python
from cachibot.storage.database import close_db, init_db
```

This works correctly (the wrapper delegates to `db.py`) but introduces an unnecessary indirection layer and will trigger the deprecation path for `get_db()` if any code accidentally uses it.

**Recommendation**: Change to direct import:

```python
from cachibot.storage.db import close_db, init_db
```

---

#### W3. `work_repository.py` uses `.isoformat()` for JSONB log entry

**File**: `src/cachibot/storage/work_repository.py`, line 860
**Problem**: One line uses `datetime.utcnow().isoformat()` when constructing a timestamp string inside a JSONB log entry:

```python
"timestamp": datetime.utcnow().isoformat(),
```

This is not a database column write (it's a string inside a JSONB dict), so it is functionally correct. However, the naive datetime and the `.isoformat()` format (no `+00:00` suffix) may differ from other timestamps returned by PostgreSQL (which will include timezone info).

**Recommendation**: Use `datetime.now(timezone.utc).isoformat()` for consistency with other timestamps.

---

#### W4. `skills/cachibot-api-route/SKILL.md` references SQLite

**File**: `skills/cachibot-api-route/SKILL.md`, line 18
**Problem**: The skill documentation still says:

```
- **Storage**: Repository pattern with async SQLite (aiosqlite)
```

This is outdated and should reference PostgreSQL + SQLAlchemy ORM.

---

### INFO

#### I1. `aiosqlite` references in docstrings are acceptable

The string "aiosqlite" appears in the docstrings of 4 repository files as historical context:

- `repository.py:5` -- "Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0."
- `work_repository.py:5` -- same
- `room_repository.py:5` -- same
- `user_repository.py:5` -- same

These are documentation-only and do not affect runtime behavior. The migration script `scripts/migrate_sqlite_to_postgres.py` correctly imports `aiosqlite` since its purpose is to migrate from SQLite.

---

#### I2. No residual `json.dumps` / `json.loads` in storage layer

Verified: Zero occurrences of `json.dumps` or `json.loads` in `src/cachibot/storage/`. All JSON serialization is handled by SQLAlchemy's `JSONB` column type.

---

#### I3. No residual `datetime.fromisoformat` in storage layer

Verified: Zero occurrences. All datetime values are handled natively by PostgreSQL `DateTime(timezone=True)` columns.

---

#### I4. No residual `get_db()` callers

Verified: Zero imports of `from cachibot.storage.database import get_db` exist in the codebase. All code has been migrated to the `async_session_maker()` pattern.

---

#### I5. `pyproject.toml` dependencies are correct

Verified: `pyproject.toml` includes all required PostgreSQL dependencies and contains no SQLite dependencies:

```toml
"sqlalchemy[asyncio]>=2.0.0",
"asyncpg>=0.29.0",
"alembic>=1.13.0",
"pgvector>=0.3.0",
```

No `aiosqlite` or `sqlite-vec` entries present.

---

#### I6. All 25 ORM models are exported and registered

Verified: `storage/models/__init__.py` exports all 25 models plus `Base`. The Alembic `env.py` imports all 25 models to ensure `Base.metadata` is fully populated. The `001_initial_schema.py` migration creates all 25 tables.

---

#### I7. `serialize_embedding()` return type changed (breaking for tests, compatible for callers)

`VectorStore.serialize_embedding()` now returns `list[float]` instead of `bytes`. The `DocumentProcessor` calls this method and passes the result to `DocChunk.embedding`, which expects `list[float] | None` -- so the production code is compatible. Only the test assertions expecting `bytes` are broken (covered in C3).

---

#### I8. `BotResponse.from_bot()` uses `.isoformat()` for JSON serialization to frontend

**File**: `src/cachibot/models/bot.py`
**Status**: Correct usage. This is API response serialization, not a database write. The only difference is that timezone-aware datetimes from PostgreSQL will produce `+00:00` suffix in the output (e.g., `2026-02-14T10:30:00+00:00` vs the old `2026-02-14T10:30:00`). Frontend callers should handle both formats.

---

## 4. Remaining Work

### Must Fix Before Merge

1. **Fix `RoomMessageRepository.get_messages()` `before` parameter** (C1) -- change type from `str` to `datetime` or add parsing
2. **Fix `db.py` to read from `Config.database`** (C2) -- either wire up the config or remove dead config settings
3. **Rewrite broken tests** (C3):
   - `tests/test_kb_pipeline.py`: Remove SQLite fixture, rewrite `TestVectorStoreSerialization` (serialize returns `list[float]` not `bytes`), remove `TestCosineSimilarity` and `TestVectorStoreSearch` (methods removed), add new pgvector-based search tests
   - `tests/test_scheduler.py`: Remove SQLite fixture, add PostgreSQL test fixtures (testcontainers or mock-based)

### Should Fix

4. **Replace `datetime.utcnow()` with `datetime.now(timezone.utc)`** (W1) -- 24 occurrences across 4 files
5. **Update `server.py` import** (W2) -- change from `storage.database` to `storage.db`
6. **Update `skills/cachibot-api-route/SKILL.md`** (W4) -- update "async SQLite (aiosqlite)" reference to PostgreSQL

### Nice to Have

7. Add integration tests that verify repository operations against a real PostgreSQL instance (via testcontainers or similar)
8. Add a `conftest.py` with a PostgreSQL test fixture that all test files can share
9. Consider adding a `pytest-asyncio` mode configuration for consistent async test execution

---

## 5. Migration Checklist (for running the migration)

### Prerequisites

- [ ] PostgreSQL 16+ with pgvector extension installed
- [ ] Docker and Docker Compose installed (for local dev)
- [ ] Python environment with updated dependencies (`pip install -e ".[dev]"`)

### Steps

1. **Start PostgreSQL**
   ```bash
   docker compose up -d db
   ```
   Wait for healthcheck to pass.

2. **Set environment variable**
   ```bash
   export DATABASE_URL=postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot
   ```
   Or copy `.env.example` to `.env`.

3. **Run Alembic migration**
   ```bash
   alembic upgrade head
   ```
   This creates all 25 tables and the pgvector extension.

4. **Migrate existing data (if upgrading from SQLite)**
   ```bash
   python scripts/migrate_sqlite_to_postgres.py --sqlite-path <path_to_old_db>
   ```

5. **Start the application**
   ```bash
   cachibot server
   ```

6. **Verify connectivity**
   ```bash
   curl http://localhost:6392/api/health
   ```

### Rollback

If the migration needs to be rolled back:
```bash
alembic downgrade base
```
The SQLite `database.py` wrapper still exists and the old database file (if preserved) can be used by reverting the code changes.

---

## 6. Architecture Diagram (Post-Migration)

```
                    FastAPI Server (server.py)
                           |
                     init_db() / close_db()
                           |
               +--- storage/db.py ---+
               |  create_async_engine |
               |  async_session_maker |
               |  Base (DeclarativeBase)|
               +-----------+---------+
                           |
            +--------------+--------------+
            |              |              |
     repository.py   room_repository.py  work_repository.py
     user_repository.py
            |              |              |
            +---------- ORM Models ------+
            |  storage/models/*.py (25)  |
            +----------------------------+
                           |
              PostgreSQL + pgvector (asyncpg)
```

---

*Report generated 2026-02-14 by Integration Tester.*

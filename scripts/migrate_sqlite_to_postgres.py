#!/usr/bin/env python3
"""
SQLite to PostgreSQL Migration Script for CachiBot

Migrates all data from the legacy SQLite database (~/.cachibot/cachibot.db)
to a PostgreSQL database. Handles type conversions, FK ordering, and
embedding format changes for pgvector.

Usage:
    python scripts/migrate_sqlite_to_postgres.py
    python scripts/migrate_sqlite_to_postgres.py \
        --sqlite-path ~/.cachibot/cachibot.db \
        --postgres-url "postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot"

Features:
    - Idempotent: uses ON CONFLICT (UPSERT) so it can be run multiple times
    - Progress reporting: shows table name, row count, time elapsed
    - FK-ordered: migrates parent tables before children
    - Validates: row count comparison and sample data checks after migration
"""

import argparse
import asyncio
import logging
import struct
import sys
import time
from pathlib import Path

import aiosqlite
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================================
# Table definitions in FK-safe migration order
# ============================================================================
# Each entry: (table_name, list_of_columns, primary_key_columns)
#
# Order rationale:
#   1. No-FK tables (users, messages, bots, skills, rooms)
#   2. Tables referencing only tier-1 tables
#   3. Tables referencing tier-2 tables, etc.
# ============================================================================

MIGRATION_ORDER: list[tuple[str, list[str], list[str]]] = [
    # === Tier 1: No foreign key dependencies ===
    (
        "users",
        [
            "id", "email", "username", "password_hash", "role",
            "is_active", "created_at", "created_by", "last_login",
        ],
        ["id"],
    ),
    (
        "messages",
        ["id", "role", "content", "timestamp", "metadata"],
        ["id"],
    ),
    (
        "bots",
        [
            "id", "name", "description", "icon", "color", "model",
            "system_prompt", "capabilities", "models", "created_at", "updated_at",
        ],
        ["id"],
    ),
    (
        "skills",
        [
            "id", "name", "description", "version", "author", "tags",
            "requires_tools", "instructions", "source", "filepath",
            "created_at", "updated_at",
        ],
        ["id"],
    ),

    # === Tier 2: Reference only tier-1 tables ===
    (
        "rooms",
        [
            "id", "title", "description", "creator_id", "max_bots",
            "settings", "created_at", "updated_at",
        ],
        ["id"],
    ),
    (
        "bot_ownership",
        ["id", "bot_id", "user_id", "created_at"],
        ["id"],
    ),
    (
        "bot_messages",
        [
            "id", "bot_id", "chat_id", "role", "content",
            "timestamp", "metadata", "reply_to_id",
        ],
        ["id"],
    ),
    (
        "bot_instructions",
        ["id", "bot_id", "content", "updated_at"],
        ["id"],
    ),
    (
        "bot_documents",
        [
            "id", "bot_id", "filename", "file_type", "file_hash",
            "file_size", "chunk_count", "status", "uploaded_at", "processed_at",
        ],
        ["id"],
    ),
    (
        "bot_contacts",
        ["id", "bot_id", "name", "details", "created_at", "updated_at"],
        ["id"],
    ),
    (
        "bot_connections",
        [
            "id", "bot_id", "platform", "name", "status", "config_encrypted",
            "message_count", "last_activity", "error", "created_at", "updated_at",
        ],
        ["id"],
    ),
    (
        "chats",
        [
            "id", "bot_id", "title", "platform", "platform_chat_id",
            "pinned", "archived", "created_at", "updated_at",
        ],
        ["id"],
    ),
    (
        "bot_skills",
        ["bot_id", "skill_id", "enabled", "activated_at"],
        ["bot_id", "skill_id"],
    ),
    (
        "functions",
        [
            "id", "bot_id", "name", "description", "version", "steps",
            "parameters", "tags", "created_at", "updated_at",
            "run_count", "last_run_at", "success_rate",
        ],
        ["id"],
    ),
    (
        "bot_notes",
        [
            "id", "bot_id", "title", "content", "tags", "source",
            "created_at", "updated_at",
        ],
        ["id"],
    ),

    # === Tier 3: Reference tier-2 tables ===
    (
        "room_members",
        ["room_id", "user_id", "role", "joined_at"],
        ["room_id", "user_id"],
    ),
    (
        "room_bots",
        ["room_id", "bot_id", "added_at"],
        ["room_id", "bot_id"],
    ),
    (
        "doc_chunks",
        [
            "id", "document_id", "bot_id", "chunk_index",
            "content", "embedding",
        ],
        ["id"],
    ),
    (
        "schedules",
        [
            "id", "bot_id", "name", "description", "function_id",
            "function_params", "schedule_type", "cron_expression",
            "interval_seconds", "run_at", "event_trigger", "timezone",
            "enabled", "max_concurrent", "catch_up", "created_at",
            "updated_at", "next_run_at", "last_run_at", "run_count",
        ],
        ["id"],
    ),
    (
        "room_messages",
        [
            "id", "room_id", "sender_type", "sender_id", "sender_name",
            "content", "metadata", "timestamp",
        ],
        ["id"],
    ),
    (
        "jobs",
        [
            "id", "status", "message_id", "created_at", "started_at",
            "completed_at", "result", "error", "progress",
        ],
        ["id"],
    ),

    # === Tier 4: Reference tier-3 tables ===
    (
        "work",
        [
            "id", "bot_id", "chat_id", "title", "description", "goal",
            "function_id", "schedule_id", "parent_work_id", "status",
            "priority", "progress", "created_at", "started_at",
            "completed_at", "due_at", "result", "error", "context", "tags",
        ],
        ["id"],
    ),

    # === Tier 5: Reference tier-4 tables ===
    (
        "tasks",
        [
            "id", "bot_id", "work_id", "chat_id", "title", "description",
            "action", "task_order", "depends_on", "status", "priority",
            "retry_count", "max_retries", "timeout_seconds", "created_at",
            "started_at", "completed_at", "result", "error",
        ],
        ["id"],
    ),
    (
        "todos",
        [
            "id", "bot_id", "chat_id", "title", "notes", "status",
            "priority", "created_at", "completed_at", "remind_at",
            "converted_to_work_id", "converted_to_task_id", "tags",
        ],
        ["id"],
    ),

    # === Tier 6: Reference tier-5 tables ===
    (
        "work_jobs",
        [
            "id", "bot_id", "task_id", "work_id", "chat_id", "status",
            "attempt", "progress", "created_at", "started_at",
            "completed_at", "result", "error", "logs",
        ],
        ["id"],
    ),
]

# Columns that store INTEGER booleans in SQLite (0/1 -> Python bool)
BOOLEAN_COLUMNS = {
    "users": {"is_active"},
    "chats": {"pinned", "archived"},
    "bot_skills": {"enabled"},
    "schedules": {"enabled", "catch_up"},
}

# Columns that contain BLOB embeddings (float32 arrays -> list[float])
BLOB_EMBEDDING_COLUMNS = {
    "doc_chunks": {"embedding"},
}


def convert_blob_to_vector_literal(blob: bytes | None) -> str | None:
    """Convert a SQLite BLOB (float32 array) to a pgvector-compatible string literal.

    SQLite stores embeddings as packed float32 arrays. pgvector accepts
    string literals like '[0.1, 0.2, 0.3]' for vector columns.
    """
    if blob is None:
        return None
    num_floats = len(blob) // 4
    floats = struct.unpack(f"<{num_floats}f", blob)
    return "[" + ",".join(f"{f:.8f}" for f in floats) + "]"


def convert_value(table: str, column: str, value):
    """Convert a SQLite value to its PostgreSQL-compatible Python equivalent."""
    if value is None:
        return None

    # Boolean conversion
    if column in BOOLEAN_COLUMNS.get(table, set()):
        return bool(value)

    # Embedding blob conversion
    if column in BLOB_EMBEDDING_COLUMNS.get(table, set()):
        return convert_blob_to_vector_literal(value)

    return value


async def get_sqlite_table_columns(
    sqlite_db: aiosqlite.Connection,
    table_name: str,
) -> list[str]:
    """Get the actual column names present in a SQLite table."""
    async with sqlite_db.execute(f"PRAGMA table_info({table_name})") as cursor:
        rows = await cursor.fetchall()
    return [row[1] for row in rows]


async def get_sqlite_row_count(
    sqlite_db: aiosqlite.Connection,
    table_name: str,
) -> int:
    """Get the row count for a SQLite table."""
    async with sqlite_db.execute(f"SELECT COUNT(*) FROM {table_name}") as cursor:
        row = await cursor.fetchone()
    return row[0] if row else 0


async def get_postgres_row_count(
    session: AsyncSession,
    table_name: str,
) -> int:
    """Get the row count for a PostgreSQL table."""
    result = await session.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    row = result.fetchone()
    return row[0] if row else 0


def build_upsert_sql(
    table_name: str,
    columns: list[str],
    pk_columns: list[str],
) -> str:
    """Build a PostgreSQL UPSERT (INSERT ... ON CONFLICT ... DO UPDATE) statement."""
    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    pk_list = ", ".join(pk_columns)

    # For DO UPDATE, set all non-PK columns
    non_pk = [c for c in columns if c not in pk_columns]

    if non_pk:
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
        return (
            f"INSERT INTO {table_name} ({col_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_set}"
        )
    else:
        # All columns are PKs (unlikely but handle it)
        return (
            f"INSERT INTO {table_name} ({col_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({pk_list}) DO NOTHING"
        )


async def migrate_table(
    sqlite_db: aiosqlite.Connection,
    pg_session: AsyncSession,
    table_name: str,
    expected_columns: list[str],
    pk_columns: list[str],
) -> tuple[int, float]:
    """Migrate a single table from SQLite to PostgreSQL.

    Returns (row_count, elapsed_seconds).
    """
    start = time.monotonic()

    # Get actual columns in the SQLite table
    actual_columns = await get_sqlite_table_columns(sqlite_db, table_name)
    if not actual_columns:
        logger.warning("  Table '%s' not found in SQLite, skipping.", table_name)
        return 0, time.monotonic() - start

    # Use intersection of expected and actual columns (handles migration columns)
    columns = [c for c in expected_columns if c in actual_columns]
    if not columns:
        logger.warning("  No matching columns for '%s', skipping.", table_name)
        return 0, time.monotonic() - start

    # Ensure PK columns are all present
    for pk in pk_columns:
        if pk not in columns:
            logger.error(
                "  PK column '%s' missing from table '%s', skipping.", pk, table_name
            )
            return 0, time.monotonic() - start

    # Read all rows from SQLite
    col_select = ", ".join(columns)
    async with sqlite_db.execute(
        f"SELECT {col_select} FROM {table_name}"
    ) as cursor:
        rows = await cursor.fetchall()

    if not rows:
        logger.info("  %s: 0 rows (empty table)", table_name)
        return 0, time.monotonic() - start

    # Build upsert SQL
    upsert_sql = build_upsert_sql(table_name, columns, pk_columns)

    # Convert and insert in batches
    batch_size = 500
    total = len(rows)

    for batch_start in range(0, total, batch_size):
        batch_end = min(batch_start + batch_size, total)
        batch_rows = rows[batch_start:batch_end]

        param_dicts = []
        for row in batch_rows:
            params = {}
            for i, col in enumerate(columns):
                params[col] = convert_value(table_name, col, row[i])
            param_dicts.append(params)

        await pg_session.execute(text(upsert_sql), param_dicts)

    await pg_session.commit()

    elapsed = time.monotonic() - start
    logger.info(
        "  %s: %d rows migrated (%.2fs)", table_name, total, elapsed
    )
    return total, elapsed


async def create_postgres_tables(pg_session: AsyncSession) -> None:
    """Create all tables in PostgreSQL if they don't exist.

    This mirrors the SQLite schema from database.py but uses PostgreSQL types:
    - TEXT PRIMARY KEY stays as TEXT
    - INTEGER booleans become BOOLEAN
    - BLOB embeddings become vector(384) via pgvector
    - TEXT timestamps stay as TEXT (keeping ISO format for compatibility)
    - TEXT JSON stays as TEXT (can be migrated to JSONB later)
    """
    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT NOT NULL,
            created_by TEXT,
            last_login TEXT
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            color TEXT,
            model TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            capabilities TEXT DEFAULT '{}',
            models TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            version TEXT DEFAULT '1.0.0',
            author TEXT,
            tags TEXT DEFAULT '[]',
            requires_tools TEXT DEFAULT '[]',
            instructions TEXT NOT NULL,
            source TEXT DEFAULT 'local',
            filepath TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            creator_id TEXT NOT NULL,
            max_bots INTEGER NOT NULL DEFAULT 4,
            settings TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_ownership (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_messages (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            reply_to_id TEXT
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_instructions (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_documents (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            filename TEXT NOT NULL,
            file_type TEXT NOT NULL,
            file_hash TEXT NOT NULL,
            file_size INTEGER NOT NULL,
            chunk_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'processing',
            uploaded_at TEXT NOT NULL,
            processed_at TEXT
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_contacts (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_connections (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            platform TEXT NOT NULL,
            name TEXT NOT NULL,
            status TEXT DEFAULT 'disconnected',
            config_encrypted TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            last_activity TEXT,
            error TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            platform TEXT,
            platform_chat_id TEXT,
            pinned BOOLEAN DEFAULT FALSE,
            archived BOOLEAN DEFAULT FALSE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_skills (
            bot_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            activated_at TEXT NOT NULL,
            PRIMARY KEY (bot_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS functions (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            version TEXT DEFAULT '1.0.0',
            steps TEXT NOT NULL DEFAULT '[]',
            parameters TEXT NOT NULL DEFAULT '[]',
            tags TEXT DEFAULT '[]',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            run_count INTEGER DEFAULT 0,
            last_run_at TEXT,
            success_rate REAL DEFAULT 0.0
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS bot_notes (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT 'user',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS room_members (
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TEXT NOT NULL,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS room_bots (
            room_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (room_id, bot_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )
    """))

    # doc_chunks: embedding stored as TEXT for now (pgvector vector type
    # will be added via ALTER COLUMN in a future Alembic migration once
    # the embedding dimension is confirmed). During migration the embedding
    # is stored as a text literal like '[0.1,0.2,...]'.
    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS doc_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            FOREIGN KEY (document_id) REFERENCES bot_documents(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            function_id TEXT,
            function_params TEXT DEFAULT '{}',
            schedule_type TEXT NOT NULL DEFAULT 'cron',
            cron_expression TEXT,
            interval_seconds INTEGER,
            run_at TEXT,
            event_trigger TEXT,
            timezone TEXT DEFAULT 'UTC',
            enabled BOOLEAN DEFAULT TRUE,
            max_concurrent INTEGER DEFAULT 1,
            catch_up BOOLEAN DEFAULT FALSE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            next_run_at TEXT,
            last_run_at TEXT,
            run_count INTEGER DEFAULT 0,
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE SET NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS room_messages (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'pending',
            message_id TEXT,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            progress REAL DEFAULT 0.0,
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS work (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            goal TEXT,
            function_id TEXT,
            schedule_id TEXT,
            parent_work_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT DEFAULT 'normal',
            progress REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            due_at TEXT,
            result TEXT,
            error TEXT,
            context TEXT DEFAULT '{}',
            tags TEXT DEFAULT '[]',
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE SET NULL,
            FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE SET NULL,
            FOREIGN KEY (parent_work_id) REFERENCES work(id) ON DELETE SET NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            work_id TEXT NOT NULL,
            chat_id TEXT,
            title TEXT NOT NULL,
            description TEXT,
            action TEXT,
            task_order INTEGER DEFAULT 0,
            depends_on TEXT DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT DEFAULT 'normal',
            retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3,
            timeout_seconds INTEGER,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            FOREIGN KEY (work_id) REFERENCES work(id) ON DELETE CASCADE
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT,
            title TEXT NOT NULL,
            notes TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT DEFAULT 'normal',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            remind_at TEXT,
            converted_to_work_id TEXT,
            converted_to_task_id TEXT,
            tags TEXT DEFAULT '[]',
            FOREIGN KEY (converted_to_work_id) REFERENCES work(id) ON DELETE SET NULL,
            FOREIGN KEY (converted_to_task_id) REFERENCES tasks(id) ON DELETE SET NULL
        )
    """))

    await pg_session.execute(text("""
        CREATE TABLE IF NOT EXISTS work_jobs (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            task_id TEXT NOT NULL,
            work_id TEXT NOT NULL,
            chat_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER DEFAULT 1,
            progress REAL DEFAULT 0.0,
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            result TEXT,
            error TEXT,
            logs TEXT DEFAULT '[]',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (work_id) REFERENCES work(id) ON DELETE CASCADE
        )
    """))

    # Create indexes (matching SQLite schema)
    index_statements = [
        "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_jobs_message ON jobs(message_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_messages_bot_chat ON bot_messages(bot_id, chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_messages_timestamp ON bot_messages(timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_bot_documents_bot ON bot_documents(bot_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_documents_hash"
        " ON bot_documents(bot_id, file_hash)",
        "CREATE INDEX IF NOT EXISTS idx_doc_chunks_document ON doc_chunks(document_id)",
        "CREATE INDEX IF NOT EXISTS idx_doc_chunks_bot ON doc_chunks(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_contacts_bot ON bot_contacts(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_connections_bot ON bot_connections(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_connections_status ON bot_connections(status)",
        "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
        "CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)",
        "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
        "CREATE INDEX IF NOT EXISTS idx_bot_ownership_user ON bot_ownership(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_ownership_bot ON bot_ownership(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_chats_bot ON chats(bot_id)",
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_platform"
        " ON chats(bot_id, platform, platform_chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source)",
        "CREATE INDEX IF NOT EXISTS idx_bot_skills_bot ON bot_skills(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_skills_skill ON bot_skills(skill_id)",
        "CREATE INDEX IF NOT EXISTS idx_functions_bot ON functions(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(bot_id, name)",
        "CREATE INDEX IF NOT EXISTS idx_schedules_bot ON schedules(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled)",
        "CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules(next_run_at)",
        "CREATE INDEX IF NOT EXISTS idx_work_bot ON work(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_status ON work(status)",
        "CREATE INDEX IF NOT EXISTS idx_work_schedule ON work(schedule_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_parent ON work(parent_work_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_chat ON work(bot_id, chat_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_bot ON tasks(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_work ON tasks(work_id)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)",
        "CREATE INDEX IF NOT EXISTS idx_tasks_order ON tasks(work_id, task_order)",
        "CREATE INDEX IF NOT EXISTS idx_work_jobs_bot ON work_jobs(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_jobs_task ON work_jobs(task_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_jobs_work ON work_jobs(work_id)",
        "CREATE INDEX IF NOT EXISTS idx_work_jobs_status ON work_jobs(status)",
        "CREATE INDEX IF NOT EXISTS idx_bot_notes_bot ON bot_notes(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_bot_notes_tags ON bot_notes(tags)",
        "CREATE INDEX IF NOT EXISTS idx_rooms_creator ON rooms(creator_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_members_user ON room_members(user_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_members_room ON room_members(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_bots_room ON room_bots(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_bots_bot ON room_bots(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_messages_room ON room_messages(room_id)",
        "CREATE INDEX IF NOT EXISTS idx_room_messages_room_timestamp"
        " ON room_messages(room_id, timestamp)",
        "CREATE INDEX IF NOT EXISTS idx_room_messages_sender"
        " ON room_messages(sender_type, sender_id)",
        "CREATE INDEX IF NOT EXISTS idx_todos_bot ON todos(bot_id)",
        "CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status)",
        "CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at)",
    ]

    for stmt in index_statements:
        try:
            await pg_session.execute(text(stmt))
        except Exception as e:
            # Index may already exist with different definition
            logger.debug("Index creation note: %s", e)

    await pg_session.commit()


async def validate_migration(
    sqlite_db: aiosqlite.Connection,
    pg_session: AsyncSession,
) -> bool:
    """Validate the migration by comparing row counts and spot-checking data.

    Returns True if all validations pass.
    """
    logger.info("")
    logger.info("=" * 60)
    logger.info("VALIDATION")
    logger.info("=" * 60)

    all_ok = True

    for table_name, columns, pk_columns in MIGRATION_ORDER:
        # Check if table exists in SQLite
        actual_columns = await get_sqlite_table_columns(sqlite_db, table_name)
        if not actual_columns:
            continue

        sqlite_count = await get_sqlite_row_count(sqlite_db, table_name)

        try:
            pg_count = await get_postgres_row_count(pg_session, table_name)
        except Exception:
            logger.error("  %s: PostgreSQL table not found!", table_name)
            all_ok = False
            continue

        status = "OK" if sqlite_count == pg_count else "MISMATCH"
        if status == "MISMATCH":
            all_ok = False

        logger.info(
            "  %s: SQLite=%d, PostgreSQL=%d [%s]",
            table_name,
            sqlite_count,
            pg_count,
            status,
        )

    # Spot-check: sample first 5 rows from key tables
    key_tables = ["users", "bots", "chats", "bot_messages", "work"]
    logger.info("")
    logger.info("Spot-check (first 5 rows from key tables):")

    for table_name in key_tables:
        actual_columns = await get_sqlite_table_columns(sqlite_db, table_name)
        if not actual_columns:
            continue

        try:
            result = await pg_session.execute(
                text(f"SELECT id FROM {table_name} ORDER BY id LIMIT 5")
            )
            pg_ids = [row[0] for row in result.fetchall()]
        except Exception:
            logger.warning("  %s: could not query PostgreSQL", table_name)
            continue

        async with sqlite_db.execute(
            f"SELECT id FROM {table_name} ORDER BY id LIMIT 5"
        ) as cursor:
            sqlite_rows = await cursor.fetchall()
        sqlite_ids = [row[0] for row in sqlite_rows]

        match = pg_ids == sqlite_ids
        logger.info(
            "  %s: %d sample IDs, match=%s",
            table_name,
            len(pg_ids),
            match,
        )
        if not match:
            all_ok = False
            logger.warning("    SQLite IDs:  %s", sqlite_ids[:5])
            logger.warning("    Postgres IDs: %s", pg_ids[:5])

    return all_ok


def fix_postgres_url(url: str) -> str:
    """Ensure the URL uses the postgresql+asyncpg:// scheme."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


async def main(sqlite_path: str, postgres_url: str) -> None:
    """Run the full migration pipeline."""
    sqlite_file = Path(sqlite_path).expanduser()
    if not sqlite_file.exists():
        logger.error("SQLite database not found: %s", sqlite_file)
        sys.exit(1)

    postgres_url = fix_postgres_url(postgres_url)
    logger.info("SQLite source: %s", sqlite_file)
    logger.info("PostgreSQL target: %s", postgres_url.split("@")[-1])  # Hide credentials
    logger.info("")

    # Connect to SQLite
    sqlite_db = await aiosqlite.connect(str(sqlite_file))
    sqlite_db.row_factory = aiosqlite.Row

    # Connect to PostgreSQL
    engine = create_async_engine(
        postgres_url,
        echo=False,
        pool_size=5,
        max_overflow=10,
    )
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    overall_start = time.monotonic()

    try:
        async with async_session() as pg_session:
            # Step 1: Create tables in PostgreSQL
            logger.info("Creating PostgreSQL tables...")
            await create_postgres_tables(pg_session)
            logger.info("Tables created successfully.")
            logger.info("")

            # Step 2: Migrate each table
            logger.info("=" * 60)
            logger.info("MIGRATING DATA")
            logger.info("=" * 60)

            total_rows = 0
            table_results = []

            for table_name, columns, pk_columns in MIGRATION_ORDER:
                try:
                    count, elapsed = await migrate_table(
                        sqlite_db, pg_session, table_name, columns, pk_columns
                    )
                    total_rows += count
                    table_results.append((table_name, count, elapsed, None))
                except Exception as e:
                    logger.error("  %s: FAILED - %s", table_name, e)
                    table_results.append((table_name, 0, 0.0, str(e)))
                    # Rollback and continue with next table
                    await pg_session.rollback()

            overall_elapsed = time.monotonic() - overall_start

            # Step 3: Summary
            logger.info("")
            logger.info("=" * 60)
            logger.info("MIGRATION SUMMARY")
            logger.info("=" * 60)
            logger.info("Total tables: %d", len(MIGRATION_ORDER))
            logger.info("Total rows migrated: %d", total_rows)
            logger.info("Total time: %.2fs", overall_elapsed)

            failed = [t for t in table_results if t[3] is not None]
            if failed:
                logger.warning("")
                logger.warning("Failed tables (%d):", len(failed))
                for name, _, _, error in failed:
                    logger.warning("  - %s: %s", name, error)

            # Step 4: Validate
            logger.info("")
            valid = await validate_migration(sqlite_db, pg_session)
            if valid:
                logger.info("")
                logger.info("Migration completed successfully! All validations passed.")
            else:
                logger.warning("")
                logger.warning(
                    "Migration completed with warnings. Review the validation output above."
                )

    finally:
        await sqlite_db.close()
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Migrate CachiBot data from SQLite to PostgreSQL",
    )
    parser.add_argument(
        "--sqlite-path",
        default=str(Path.home() / ".cachibot" / "cachibot.db"),
        help="Path to the SQLite database file (default: ~/.cachibot/cachibot.db)",
    )
    parser.add_argument(
        "--postgres-url",
        default="postgresql+asyncpg://cachibot:cachibot@localhost:5433/cachibot",
        help="PostgreSQL connection URL (default: local dev database)",
    )
    args = parser.parse_args()

    asyncio.run(main(args.sqlite_path, args.postgres_url))

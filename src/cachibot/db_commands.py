"""
Database CLI Commands for CachiBot

Provides commands for PostgreSQL setup, data migration from SQLite,
and database status inspection.
"""

import asyncio
import os
import re
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table
from rich.theme import Theme
from rich.tree import Tree

# Use the same theme as the main CLI
CACHIBOT_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "thinking": "dim italic",
        "tool": "magenta",
        "user": "bold blue",
        "assistant": "bold green",
        "cost": "dim cyan",
    }
)

console = Console(theme=CACHIBOT_THEME)

# --- Typer sub-apps ---

db_app = typer.Typer(help="Database management commands.")
setup_db_app = typer.Typer(help="Database setup wizards.")

# Default paths
SQLITE_PATH = Path.home() / ".cachibot" / "cachibot.db"
ENV_FILE = Path.cwd() / ".env"

# Default Docker container settings
DOCKER_CONTAINER = "cachibot-db"
DOCKER_IMAGE = "pgvector/pgvector:pg16"
DOCKER_PORT = 5433
DOCKER_DB = "cachibot"
DOCKER_USER = "cachibot"
DOCKER_PASSWORD = "cachibot"
DEFAULT_PG_URL = (
    f"postgresql+asyncpg://{DOCKER_USER}:{DOCKER_PASSWORD}@localhost:{DOCKER_PORT}/{DOCKER_DB}"
)


# ============================================================================
# Helpers
# ============================================================================


def _fix_postgres_url(url: str) -> str:
    """Ensure the URL uses the postgresql+asyncpg:// scheme."""
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    if url.startswith("postgresql://") and "+asyncpg" not in url:
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url


def _mask_url(url: str) -> str:
    """Mask password in a database URL for display."""
    return re.sub(r"://([^:]+):([^@]+)@", r"://\1:****@", url)


def _get_database_url() -> str | None:
    """Get DATABASE_URL from environment or .env file."""
    url = os.getenv("DATABASE_URL")
    if url:
        return url

    # Try loading from .env file in cwd
    env_path = Path.cwd() / ".env"
    if env_path.exists():
        try:
            content = env_path.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("DATABASE_URL=") and not line.startswith("#"):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
        except Exception:
            pass

    return None


def _write_env_url(url: str) -> None:
    """Write or update DATABASE_URL in the .env file."""
    env_path = Path.cwd() / ".env"
    new_line = f"DATABASE_URL={url}"

    if env_path.exists():
        content = env_path.read_text(encoding="utf-8")
        lines = content.splitlines()
        updated = False
        for i, line in enumerate(lines):
            stripped = line.strip()
            if stripped.startswith("DATABASE_URL=") or stripped.startswith("# DATABASE_URL="):
                lines[i] = new_line
                updated = True
                break
        if not updated:
            lines.append(new_line)
        env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    else:
        env_path.write_text(new_line + "\n", encoding="utf-8")


async def _test_postgres_connection(url: str) -> tuple[bool, str]:
    """Test a PostgreSQL connection. Returns (success, message)."""
    url = _fix_postgres_url(url)
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        engine = create_async_engine(url, echo=False, pool_pre_ping=True)
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT version()"))
            version = result.scalar()
        await engine.dispose()
        return True, str(version)
    except Exception as e:
        return False, str(e)


async def _create_postgres_tables_raw(url: str) -> None:
    """Create all CachiBot tables in PostgreSQL using raw SQL.

    This is a self-contained implementation that does not depend on
    the migration script, making it suitable for the CLI.
    """
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    url = _fix_postgres_url(url)
    engine = create_async_engine(url, echo=False, pool_pre_ping=True)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Table DDL statements (matching the migration script)
    table_ddl = [
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT NOT NULL,
            created_by TEXT,
            last_login TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS bots (
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
        )""",
        """CREATE TABLE IF NOT EXISTS skills (
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
        )""",
        """CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            description TEXT,
            creator_id TEXT NOT NULL,
            max_bots INTEGER NOT NULL DEFAULT 4,
            settings TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS bot_ownership (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS bot_messages (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            reply_to_id TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS bot_instructions (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_documents (
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
        )""",
        """CREATE TABLE IF NOT EXISTS bot_contacts (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_connections (
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
        )""",
        """CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            platform TEXT,
            platform_chat_id TEXT,
            pinned BOOLEAN DEFAULT FALSE,
            archived BOOLEAN DEFAULT FALSE,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_skills (
            bot_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE,
            activated_at TEXT NOT NULL,
            PRIMARY KEY (bot_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS functions (
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
        )""",
        """CREATE TABLE IF NOT EXISTS bot_notes (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT 'user',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS room_members (
            room_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member',
            joined_at TEXT NOT NULL,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS room_bots (
            room_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (room_id, bot_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS doc_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding TEXT,
            FOREIGN KEY (document_id) REFERENCES bot_documents(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS schedules (
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
        )""",
        """CREATE TABLE IF NOT EXISTS room_messages (
            id TEXT PRIMARY KEY,
            room_id TEXT NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL,
            content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}',
            timestamp TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS jobs (
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
        )""",
        """CREATE TABLE IF NOT EXISTS work (
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
        )""",
        """CREATE TABLE IF NOT EXISTS tasks (
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
        )""",
        """CREATE TABLE IF NOT EXISTS todos (
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
        )""",
        """CREATE TABLE IF NOT EXISTS work_jobs (
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
        )""",
    ]

    # Index creation statements
    index_ddl = [
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

    try:
        async with async_session() as session:
            for ddl in table_ddl:
                await session.execute(text(ddl))
            for idx in index_ddl:
                try:
                    await session.execute(text(idx))
                except Exception:
                    pass  # Index may already exist
            await session.commit()
    finally:
        await engine.dispose()


def _has_docker() -> bool:
    """Check if Docker is available."""
    return shutil.which("docker") is not None


def _has_psql() -> bool:
    """Check if psql or pg_isready is available."""
    return shutil.which("psql") is not None or shutil.which("pg_isready") is not None


def _docker_container_exists(name: str) -> bool:
    """Check if a Docker container with the given name exists."""
    try:
        result = subprocess.run(
            ["docker", "inspect", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except Exception:
        return False


def _docker_container_running(name: str) -> bool:
    """Check if a Docker container is running."""
    try:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", name],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and "true" in result.stdout.strip().lower()
    except Exception:
        return False


def _start_docker_container(name: str) -> bool:
    """Start an existing Docker container."""
    try:
        result = subprocess.run(
            ["docker", "start", name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except Exception:
        return False


def _create_docker_container() -> tuple[bool, str]:
    """Create and start a new PostgreSQL Docker container.

    Returns (success, message).
    """
    cmd = [
        "docker",
        "run",
        "-d",
        "--name",
        DOCKER_CONTAINER,
        "-e",
        f"POSTGRES_DB={DOCKER_DB}",
        "-e",
        f"POSTGRES_USER={DOCKER_USER}",
        "-e",
        f"POSTGRES_PASSWORD={DOCKER_PASSWORD}",
        "-p",
        f"{DOCKER_PORT}:5432",
        "--restart",
        "unless-stopped",
        DOCKER_IMAGE,
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode == 0:
            return True, result.stdout.strip()[:12]  # container ID
        return False, result.stderr.strip()
    except Exception as e:
        return False, str(e)


def _wait_for_postgres_ready(container: str, timeout: int = 30) -> bool:
    """Wait for PostgreSQL to be ready inside a Docker container."""
    start = time.monotonic()
    while time.monotonic() - start < timeout:
        try:
            result = subprocess.run(
                [
                    "docker",
                    "exec",
                    container,
                    "pg_isready",
                    "-U",
                    DOCKER_USER,
                    "-d",
                    DOCKER_DB,
                ],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return True
        except Exception:
            pass
        time.sleep(1)
    return False


def _format_size(size_bytes: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024  # type: ignore[assignment]
    return f"{size_bytes:.1f} TB"


# ============================================================================
# Migration logic (adapted from scripts/migrate_sqlite_to_postgres.py)
# ============================================================================

# Table migration order and column definitions
# (matching scripts/migrate_sqlite_to_postgres.py)
MIGRATION_ORDER: list[tuple[str, list[str], list[str]]] = [
    # Tier 1
    (
        "users",
        [
            "id",
            "email",
            "username",
            "password_hash",
            "role",
            "is_active",
            "created_at",
            "created_by",
            "last_login",
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
            "id",
            "name",
            "description",
            "icon",
            "color",
            "model",
            "system_prompt",
            "capabilities",
            "models",
            "created_at",
            "updated_at",
        ],
        ["id"],
    ),
    (
        "skills",
        [
            "id",
            "name",
            "description",
            "version",
            "author",
            "tags",
            "requires_tools",
            "instructions",
            "source",
            "filepath",
            "created_at",
            "updated_at",
        ],
        ["id"],
    ),
    # Tier 2
    (
        "rooms",
        [
            "id",
            "title",
            "description",
            "creator_id",
            "max_bots",
            "settings",
            "created_at",
            "updated_at",
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
        ["id", "bot_id", "chat_id", "role", "content", "timestamp", "metadata", "reply_to_id"],
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
            "id",
            "bot_id",
            "filename",
            "file_type",
            "file_hash",
            "file_size",
            "chunk_count",
            "status",
            "uploaded_at",
            "processed_at",
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
            "id",
            "bot_id",
            "platform",
            "name",
            "status",
            "config_encrypted",
            "message_count",
            "last_activity",
            "error",
            "created_at",
            "updated_at",
        ],
        ["id"],
    ),
    (
        "chats",
        [
            "id",
            "bot_id",
            "title",
            "platform",
            "platform_chat_id",
            "pinned",
            "archived",
            "created_at",
            "updated_at",
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
            "id",
            "bot_id",
            "name",
            "description",
            "version",
            "steps",
            "parameters",
            "tags",
            "created_at",
            "updated_at",
            "run_count",
            "last_run_at",
            "success_rate",
        ],
        ["id"],
    ),
    (
        "bot_notes",
        ["id", "bot_id", "title", "content", "tags", "source", "created_at", "updated_at"],
        ["id"],
    ),
    # Tier 3
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
        ["id", "document_id", "bot_id", "chunk_index", "content", "embedding"],
        ["id"],
    ),
    (
        "schedules",
        [
            "id",
            "bot_id",
            "name",
            "description",
            "function_id",
            "function_params",
            "schedule_type",
            "cron_expression",
            "interval_seconds",
            "run_at",
            "event_trigger",
            "timezone",
            "enabled",
            "max_concurrent",
            "catch_up",
            "created_at",
            "updated_at",
            "next_run_at",
            "last_run_at",
            "run_count",
        ],
        ["id"],
    ),
    (
        "room_messages",
        [
            "id",
            "room_id",
            "sender_type",
            "sender_id",
            "sender_name",
            "content",
            "metadata",
            "timestamp",
        ],
        ["id"],
    ),
    (
        "jobs",
        [
            "id",
            "status",
            "message_id",
            "created_at",
            "started_at",
            "completed_at",
            "result",
            "error",
            "progress",
        ],
        ["id"],
    ),
    # Tier 4
    (
        "work",
        [
            "id",
            "bot_id",
            "chat_id",
            "title",
            "description",
            "goal",
            "function_id",
            "schedule_id",
            "parent_work_id",
            "status",
            "priority",
            "progress",
            "created_at",
            "started_at",
            "completed_at",
            "due_at",
            "result",
            "error",
            "context",
            "tags",
        ],
        ["id"],
    ),
    # Tier 5
    (
        "tasks",
        [
            "id",
            "bot_id",
            "work_id",
            "chat_id",
            "title",
            "description",
            "action",
            "task_order",
            "depends_on",
            "status",
            "priority",
            "retry_count",
            "max_retries",
            "timeout_seconds",
            "created_at",
            "started_at",
            "completed_at",
            "result",
            "error",
        ],
        ["id"],
    ),
    (
        "todos",
        [
            "id",
            "bot_id",
            "chat_id",
            "title",
            "notes",
            "status",
            "priority",
            "created_at",
            "completed_at",
            "remind_at",
            "converted_to_work_id",
            "converted_to_task_id",
            "tags",
        ],
        ["id"],
    ),
    # Tier 6
    (
        "work_jobs",
        [
            "id",
            "bot_id",
            "task_id",
            "work_id",
            "chat_id",
            "status",
            "attempt",
            "progress",
            "created_at",
            "started_at",
            "completed_at",
            "result",
            "error",
            "logs",
        ],
        ["id"],
    ),
]

BOOLEAN_COLUMNS = {
    "users": {"is_active"},
    "chats": {"pinned", "archived"},
    "bot_skills": {"enabled"},
    "schedules": {"enabled", "catch_up"},
}

BLOB_EMBEDDING_COLUMNS = {
    "doc_chunks": {"embedding"},
}

# Key tables for status display
KEY_TABLES = ["users", "bots", "chats", "messages", "bot_messages", "bot_documents"]


def _convert_blob_to_vector(blob: bytes | None) -> str | None:
    """Convert SQLite BLOB (float32 array) to pgvector string literal."""
    import struct as _struct

    if blob is None:
        return None
    num_floats = len(blob) // 4
    floats = _struct.unpack(f"<{num_floats}f", blob)
    return "[" + ",".join(f"{f:.8f}" for f in floats) + "]"


def _convert_value(table: str, column: str, value: object) -> object:
    """Convert a SQLite value to its PostgreSQL-compatible equivalent."""
    if value is None:
        return None
    if column in BOOLEAN_COLUMNS.get(table, set()):
        return bool(value)
    if column in BLOB_EMBEDDING_COLUMNS.get(table, set()):
        return _convert_blob_to_vector(value)  # type: ignore[arg-type]
    return value


def _build_upsert_sql(table_name: str, columns: list[str], pk_columns: list[str]) -> str:
    """Build a PostgreSQL UPSERT statement."""
    col_list = ", ".join(columns)
    placeholders = ", ".join(f":{c}" for c in columns)
    pk_list = ", ".join(pk_columns)
    non_pk = [c for c in columns if c not in pk_columns]

    if non_pk:
        update_set = ", ".join(f"{c} = EXCLUDED.{c}" for c in non_pk)
        return (
            f"INSERT INTO {table_name} ({col_list}) "
            f"VALUES ({placeholders}) "
            f"ON CONFLICT ({pk_list}) DO UPDATE SET {update_set}"
        )
    return (
        f"INSERT INTO {table_name} ({col_list}) "
        f"VALUES ({placeholders}) "
        f"ON CONFLICT ({pk_list}) DO NOTHING"
    )


# ============================================================================
# Command: cachibot setup-db postgres
# ============================================================================


@setup_db_app.command("postgres")
def setup_postgres() -> None:
    """Guided PostgreSQL setup for CachiBot."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]PostgreSQL Setup Wizard[/]\n\n"
            "This will help you set up PostgreSQL for CachiBot.\n"
            "SQLite is the default -- PostgreSQL is optional but recommended for production.",
            border_style="cyan",
        )
    )
    console.print()

    database_url: str | None = None

    # --- Option 1: Docker ---
    if _has_docker():
        console.print("[info]Docker detected![/]")

        # Check if container already exists
        if _docker_container_exists(DOCKER_CONTAINER):
            if _docker_container_running(DOCKER_CONTAINER):
                console.print(f"[success]Container '{DOCKER_CONTAINER}' is already running.[/]")
                database_url = DEFAULT_PG_URL
            else:
                console.print(f"[warning]Container '{DOCKER_CONTAINER}' exists but is stopped.[/]")
                if Confirm.ask("  Start the existing container?", default=True):
                    with console.status("[info]Starting container...[/]"):
                        if _start_docker_container(DOCKER_CONTAINER):
                            console.print(f"[success]Container '{DOCKER_CONTAINER}' started.[/]")
                            # Wait for ready
                            if _wait_for_postgres_ready(DOCKER_CONTAINER):
                                console.print("[success]PostgreSQL is ready.[/]")
                                database_url = DEFAULT_PG_URL
                            else:
                                console.print("[error]PostgreSQL did not become ready in time.[/]")
                                raise typer.Exit(1)
                        else:
                            console.print("[error]Failed to start the container.[/]")
                            raise typer.Exit(1)
        else:
            if Confirm.ask(
                "  Would you like to auto-create a PostgreSQL container?",
                default=True,
            ):
                console.print()
                console.print("[dim]Creating container with:[/]")
                console.print(f"  [dim]Image:[/]     {DOCKER_IMAGE}")
                console.print(f"  [dim]Port:[/]      {DOCKER_PORT} -> 5432")
                console.print(f"  [dim]Database:[/]  {DOCKER_DB}")
                console.print(f"  [dim]User:[/]      {DOCKER_USER}")
                console.print()

                with console.status("[info]Pulling image and creating container...[/]"):
                    success, msg = _create_docker_container()

                if not success:
                    console.print(f"[error]Failed to create container: {msg}[/]")
                    raise typer.Exit(1)

                console.print(f"[success]Container created (ID: {msg}).[/]")

                with console.status("[info]Waiting for PostgreSQL to be ready...[/]"):
                    if _wait_for_postgres_ready(DOCKER_CONTAINER, timeout=60):
                        console.print("[success]PostgreSQL is ready![/]")
                        database_url = DEFAULT_PG_URL
                    else:
                        console.print(
                            "[error]PostgreSQL did not become ready within 60 seconds.[/]"
                        )
                        console.print("[dim]Try checking: docker logs cachibot-db[/]")
                        raise typer.Exit(1)

    # --- Option 2: Local PostgreSQL ---
    if database_url is None and _has_psql():
        console.print("[info]Local PostgreSQL installation detected.[/]")
        if Confirm.ask(
            "  Use local PostgreSQL?",
            default=True,
        ):
            host = Prompt.ask("  Host", default="localhost")
            port = Prompt.ask("  Port", default="5432")
            db_name = Prompt.ask("  Database", default="cachibot")
            user = Prompt.ask("  User", default="cachibot")
            password = Prompt.ask("  Password", password=True, default="cachibot")
            database_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db_name}"

    # --- Option 3: Cloud provider ---
    if database_url is None:
        console.print()
        console.print(
            Panel(
                "[bold]Cloud PostgreSQL Providers[/]\n\n"
                "[cyan]Supabase[/] (free tier)\n"
                "  1. Go to [link=https://supabase.com]supabase.com[/link] -> New Project\n"
                "  2. Settings -> Database -> Connection string (URI)\n"
                "  3. Format: postgresql+asyncpg://postgres.[ref]:[password]"
                "@aws-0-[region].pooler.supabase.com:5432/postgres\n\n"
                "[cyan]Neon[/] (free tier)\n"
                "  1. Go to [link=https://neon.tech]neon.tech[/link] -> New Project\n"
                "  2. Connection Details -> Connection string\n"
                "  3. Format: postgresql+asyncpg://[user]:[password]"
                "@[endpoint].neon.tech/neondb?sslmode=require\n\n"
                "[cyan]Railway[/]\n"
                "  1. Go to [link=https://railway.app]railway.app[/link] -> New Project\n"
                "  2. Add PostgreSQL -> Copy connection URL\n\n"
                "[dim]Tip: Make sure the URL starts with postgresql+asyncpg://\n"
                "If it starts with postgres:// or postgresql://,"
                " we will convert it automatically.[/]",
                title="Cloud Setup Instructions",
                border_style="cyan",
            )
        )
        console.print()

        url_input = Prompt.ask(
            "  Paste your DATABASE_URL (or 'skip' to exit)",
        )
        if url_input.strip().lower() == "skip":
            console.print("[dim]Setup cancelled.[/]")
            raise typer.Exit()
        database_url = url_input.strip()

    if database_url is None:
        console.print("[error]No database URL configured. Setup cancelled.[/]")
        raise typer.Exit(1)

    # --- Normalize the URL ---
    database_url = _fix_postgres_url(database_url)

    # --- Test the connection ---
    console.print()
    with console.status("[info]Testing connection...[/]"):
        success, msg = asyncio.run(_test_postgres_connection(database_url))

    if not success:
        console.print("[error]Connection failed![/]")
        console.print()
        console.print(
            Panel(
                f"[bold red]Error:[/] {msg}\n\n"
                "[bold]Troubleshooting:[/]\n"
                "  - Is PostgreSQL running? Check with: docker ps / pg_isready\n"
                "  - Is the host/port correct? Try connecting with psql\n"
                "  - Is the database/user created? Check credentials\n"
                "  - For cloud: is your IP whitelisted?\n"
                "  - For SSL: add ?sslmode=require to the URL",
                title="Connection Failed",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    console.print("[success]Connected successfully![/]")
    console.print(f"  [dim]{msg}[/]")

    # --- Write to .env ---
    console.print()
    _write_env_url(database_url)
    console.print("[success]DATABASE_URL saved to .env[/]")
    console.print(f"  [dim]{_mask_url(database_url)}[/]")

    # --- Create tables ---
    console.print()
    with console.status("[info]Creating database tables...[/]"):
        try:
            asyncio.run(_create_postgres_tables_raw(database_url))
            console.print("[success]Database tables created successfully.[/]")
        except Exception as e:
            console.print(f"[error]Failed to create tables: {e}[/]")
            console.print("[dim]You can try again later or check the database manually.[/]")

    # --- Check for existing SQLite data ---
    sqlite_path = Path.home() / ".cachibot" / "cachibot.db"
    if sqlite_path.exists():
        size = sqlite_path.stat().st_size
        console.print()
        console.print(
            Panel(
                f"[warning]Found existing SQLite data[/]\n\n"
                f"  Path: {sqlite_path}\n"
                f"  Size: {_format_size(size)}\n\n"
                "Run [bold]cachibot db migrate[/] to transfer your data to PostgreSQL.",
                title="Existing Data",
                border_style="yellow",
            )
        )

    # --- Final summary ---
    console.print()
    console.print(
        Panel(
            "[bold green]PostgreSQL setup complete![/]\n\n"
            "CachiBot will use PostgreSQL when DATABASE_URL is set.\n\n"
            "Useful commands:\n"
            "  [bold]cachibot db status[/]   - Check database status\n"
            "  [bold]cachibot db migrate[/]  - Migrate data from SQLite\n"
            "  [bold]cachibot server[/]      - Start the server",
            title="Setup Complete",
            border_style="green",
        )
    )


# ============================================================================
# Command: cachibot db migrate
# ============================================================================


@db_app.command("migrate")
def migrate_data() -> None:
    """Migrate data from SQLite to PostgreSQL."""
    console.print()
    console.print(
        Panel(
            "[bold cyan]SQLite to PostgreSQL Migration[/]\n\n"
            "This will copy all data from your SQLite database to PostgreSQL.\n"
            "The migration is idempotent (safe to run multiple times).",
            border_style="cyan",
        )
    )
    console.print()

    # Step 1: Verify SQLite file exists
    sqlite_path = Path.home() / ".cachibot" / "cachibot.db"
    if not sqlite_path.exists():
        console.print(
            Panel(
                "[warning]No SQLite database found.[/]\n\n"
                f"  Expected: {sqlite_path}\n\n"
                "Nothing to migrate. If you are starting fresh, "
                "PostgreSQL tables were already created during setup.",
                border_style="yellow",
            )
        )
        raise typer.Exit()

    sqlite_size = sqlite_path.stat().st_size
    console.print(f"  [info]SQLite database:[/] {sqlite_path} ({_format_size(sqlite_size)})")

    # Step 2: Verify DATABASE_URL
    database_url = _get_database_url()
    if not database_url:
        console.print()
        console.print(
            Panel(
                "[error]DATABASE_URL is not set.[/]\n\n"
                "Set DATABASE_URL to your PostgreSQL database first.\n"
                "Run [bold]cachibot setup-db postgres[/] for guided setup.",
                border_style="red",
            )
        )
        raise typer.Exit(1)

    database_url = _fix_postgres_url(database_url)
    console.print(f"  [info]PostgreSQL target:[/] {_mask_url(database_url)}")

    # Step 3: Test PostgreSQL connectivity
    console.print()
    with console.status("[info]Testing PostgreSQL connection...[/]"):
        success, msg = asyncio.run(_test_postgres_connection(database_url))

    if not success:
        console.print(f"[error]Cannot connect to PostgreSQL: {msg}[/]")
        console.print("[dim]Check your DATABASE_URL and ensure PostgreSQL is running.[/]")
        raise typer.Exit(1)

    console.print("  [success]PostgreSQL connected.[/]")

    # Step 4: Show what will be migrated
    console.print()
    console.print("[info]Scanning SQLite database...[/]")

    table_info = asyncio.run(_scan_sqlite(sqlite_path))
    total_tables = len(table_info)
    total_rows = sum(count for _, count in table_info)

    table = Table(title="Tables to Migrate", show_lines=False)
    table.add_column("Table", style="cyan")
    table.add_column("Rows", style="green", justify="right")

    for tname, count in table_info:
        table.add_row(tname, f"{count:,}")

    table.add_section()
    table.add_row("[bold]Total[/]", f"[bold]{total_rows:,}[/]")

    console.print(table)

    if total_rows == 0:
        console.print()
        console.print("[warning]No data to migrate. All tables are empty.[/]")
        raise typer.Exit()

    # Step 5: Confirmation
    console.print()
    if not Confirm.ask(
        "  [bold]Copy all data from SQLite to PostgreSQL?[/]",
        default=False,
    ):
        console.print("[dim]Migration cancelled.[/]")
        raise typer.Exit()

    # Step 6: Run the migration
    console.print()
    results = asyncio.run(_run_migration(sqlite_path, database_url, table_info))

    # Step 7: Print summary
    migrated_count = sum(r[1] for r in results if r[2] is None)
    failed_tables = [r for r in results if r[2] is not None]
    total_time = sum(r[3] for r in results)

    console.print()
    tree = Tree("[bold]Migration Complete[/]")
    tree.add(f"Tables: {total_tables}")
    tree.add(f"Rows: {migrated_count:,}")
    tree.add(f"Time: {total_time:.1f}s")

    if failed_tables:
        fail_branch = tree.add(f"[error]Failed: {len(failed_tables)}[/]")
        for name, _, error, _ in failed_tables:
            fail_branch.add(f"[error]{name}: {error}[/]")
        tree.add("[warning]Status: Completed with errors[/]")
    else:
        tree.add("[success]Status: All validations passed[/]")

    console.print(tree)
    console.print()
    console.print(f"  [dim]Your SQLite database has been preserved at {sqlite_path} (backup)[/]")
    console.print("  [dim]CachiBot will now use PostgreSQL.[/]")


async def _scan_sqlite(sqlite_path: Path) -> list[tuple[str, int]]:
    """Scan SQLite database and return (table_name, row_count) for each table."""
    import aiosqlite

    results: list[tuple[str, int]] = []

    async with aiosqlite.connect(str(sqlite_path)) as db:
        for table_name, columns, pk_columns in MIGRATION_ORDER:
            # Check if table exists
            async with db.execute(f"PRAGMA table_info({table_name})") as cursor:
                cols = await cursor.fetchall()
            if not cols:
                continue

            # Get row count
            async with db.execute(f"SELECT COUNT(*) FROM {table_name}") as cursor:
                row = await cursor.fetchone()
            count = row[0] if row else 0
            results.append((table_name, count))

    return results


async def _run_migration(
    sqlite_path: Path,
    postgres_url: str,
    table_info: list[tuple[str, int]],
) -> list[tuple[str, int, str | None, float]]:
    """Run the actual migration with progress display.

    Returns list of (table_name, rows_migrated, error_or_none, elapsed).
    """
    import aiosqlite
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    engine = create_async_engine(postgres_url, echo=False, pool_size=5, max_overflow=10)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    results: list[tuple[str, int, str | None, float]] = []

    try:
        async with aiosqlite.connect(str(sqlite_path)) as sqlite_db:
            # Create tables first
            async with async_session() as session:
                await _create_tables_in_session(session)

            # Now table_info has the ordered list; build a lookup for progress
            table_names_in_order = [t[0] for t in table_info]

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("{task.completed}/{task.total} rows"),
                TimeElapsedColumn(),
                console=console,
            ) as progress:
                for table_name, expected_columns, pk_columns in MIGRATION_ORDER:
                    if table_name not in table_names_in_order:
                        continue

                    row_count = next((c for n, c in table_info if n == table_name), 0)

                    task_id = progress.add_task(
                        f"[cyan]{table_name}[/]",
                        total=row_count,
                    )

                    start = time.monotonic()
                    try:
                        migrated = await _migrate_single_table(
                            sqlite_db,
                            async_session,
                            table_name,
                            expected_columns,
                            pk_columns,
                            progress,
                            task_id,
                        )
                        elapsed = time.monotonic() - start
                        progress.update(task_id, completed=migrated)
                        results.append((table_name, migrated, None, elapsed))
                    except Exception as e:
                        elapsed = time.monotonic() - start
                        progress.update(
                            task_id,
                            description=f"[error]{table_name} (FAILED)[/]",
                        )
                        results.append((table_name, 0, str(e), elapsed))
    finally:
        await engine.dispose()

    return results


async def _create_tables_in_session(session: Any) -> None:
    """Create all tables using the session (reuses _create_postgres_tables_raw logic)."""
    from sqlalchemy import text

    table_ddl = [
        """CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY, email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user', is_active BOOLEAN DEFAULT TRUE,
            created_at TEXT NOT NULL, created_by TEXT, last_login TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY, role TEXT NOT NULL, content TEXT NOT NULL,
            timestamp TEXT NOT NULL, metadata TEXT DEFAULT '{}'
        )""",
        """CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            icon TEXT, color TEXT, model TEXT NOT NULL,
            system_prompt TEXT NOT NULL, capabilities TEXT DEFAULT '{}',
            models TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY, name TEXT NOT NULL, description TEXT,
            version TEXT DEFAULT '1.0.0', author TEXT,
            tags TEXT DEFAULT '[]', requires_tools TEXT DEFAULT '[]',
            instructions TEXT NOT NULL, source TEXT DEFAULT 'local',
            filepath TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS rooms (
            id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
            creator_id TEXT NOT NULL, max_bots INTEGER NOT NULL DEFAULT 4,
            settings TEXT DEFAULT '{}', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            FOREIGN KEY (creator_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS bot_ownership (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL, created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS bot_messages (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, chat_id TEXT NOT NULL,
            role TEXT NOT NULL, content TEXT NOT NULL, timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}', reply_to_id TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS bot_instructions (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_documents (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL,
            filename TEXT NOT NULL, file_type TEXT NOT NULL,
            file_hash TEXT NOT NULL, file_size INTEGER NOT NULL,
            chunk_count INTEGER DEFAULT 0, status TEXT DEFAULT 'processing',
            uploaded_at TEXT NOT NULL, processed_at TEXT
        )""",
        """CREATE TABLE IF NOT EXISTS bot_contacts (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, name TEXT NOT NULL,
            details TEXT, created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_connections (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, platform TEXT NOT NULL,
            name TEXT NOT NULL, status TEXT DEFAULT 'disconnected',
            config_encrypted TEXT NOT NULL, message_count INTEGER DEFAULT 0,
            last_activity TEXT, error TEXT,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, title TEXT NOT NULL,
            platform TEXT, platform_chat_id TEXT,
            pinned BOOLEAN DEFAULT FALSE, archived BOOLEAN DEFAULT FALSE,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS bot_skills (
            bot_id TEXT NOT NULL, skill_id TEXT NOT NULL,
            enabled BOOLEAN DEFAULT TRUE, activated_at TEXT NOT NULL,
            PRIMARY KEY (bot_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS functions (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, name TEXT NOT NULL,
            description TEXT, version TEXT DEFAULT '1.0.0',
            steps TEXT NOT NULL DEFAULT '[]', parameters TEXT NOT NULL DEFAULT '[]',
            tags TEXT DEFAULT '[]', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, run_count INTEGER DEFAULT 0,
            last_run_at TEXT, success_rate REAL DEFAULT 0.0
        )""",
        """CREATE TABLE IF NOT EXISTS bot_notes (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, title TEXT NOT NULL,
            content TEXT NOT NULL, tags TEXT DEFAULT '[]',
            source TEXT DEFAULT 'user', created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )""",
        """CREATE TABLE IF NOT EXISTS room_members (
            room_id TEXT NOT NULL, user_id TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'member', joined_at TEXT NOT NULL,
            PRIMARY KEY (room_id, user_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS room_bots (
            room_id TEXT NOT NULL, bot_id TEXT NOT NULL,
            added_at TEXT NOT NULL,
            PRIMARY KEY (room_id, bot_id),
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS doc_chunks (
            id TEXT PRIMARY KEY, document_id TEXT NOT NULL,
            bot_id TEXT NOT NULL, chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL, embedding TEXT,
            FOREIGN KEY (document_id) REFERENCES bot_documents(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS schedules (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, name TEXT NOT NULL,
            description TEXT, function_id TEXT,
            function_params TEXT DEFAULT '{}',
            schedule_type TEXT NOT NULL DEFAULT 'cron',
            cron_expression TEXT, interval_seconds INTEGER,
            run_at TEXT, event_trigger TEXT, timezone TEXT DEFAULT 'UTC',
            enabled BOOLEAN DEFAULT TRUE, max_concurrent INTEGER DEFAULT 1,
            catch_up BOOLEAN DEFAULT FALSE, created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL, next_run_at TEXT, last_run_at TEXT,
            run_count INTEGER DEFAULT 0,
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS room_messages (
            id TEXT PRIMARY KEY, room_id TEXT NOT NULL,
            sender_type TEXT NOT NULL, sender_id TEXT NOT NULL,
            sender_name TEXT NOT NULL, content TEXT NOT NULL,
            metadata TEXT DEFAULT '{}', timestamp TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'pending',
            message_id TEXT, created_at TEXT NOT NULL,
            started_at TEXT, completed_at TEXT, result TEXT,
            error TEXT, progress REAL DEFAULT 0.0,
            FOREIGN KEY (message_id) REFERENCES messages(id)
        )""",
        """CREATE TABLE IF NOT EXISTS work (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, chat_id TEXT,
            title TEXT NOT NULL, description TEXT, goal TEXT,
            function_id TEXT, schedule_id TEXT, parent_work_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT DEFAULT 'normal', progress REAL DEFAULT 0.0,
            created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            due_at TEXT, result TEXT, error TEXT,
            context TEXT DEFAULT '{}', tags TEXT DEFAULT '[]',
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE SET NULL,
            FOREIGN KEY (schedule_id) REFERENCES schedules(id) ON DELETE SET NULL,
            FOREIGN KEY (parent_work_id) REFERENCES work(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS tasks (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL,
            work_id TEXT NOT NULL, chat_id TEXT, title TEXT NOT NULL,
            description TEXT, action TEXT, task_order INTEGER DEFAULT 0,
            depends_on TEXT DEFAULT '[]', status TEXT NOT NULL DEFAULT 'pending',
            priority TEXT DEFAULT 'normal', retry_count INTEGER DEFAULT 0,
            max_retries INTEGER DEFAULT 3, timeout_seconds INTEGER,
            created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            result TEXT, error TEXT,
            FOREIGN KEY (work_id) REFERENCES work(id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS todos (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL, chat_id TEXT,
            title TEXT NOT NULL, notes TEXT,
            status TEXT NOT NULL DEFAULT 'open',
            priority TEXT DEFAULT 'normal', created_at TEXT NOT NULL,
            completed_at TEXT, remind_at TEXT,
            converted_to_work_id TEXT, converted_to_task_id TEXT,
            tags TEXT DEFAULT '[]',
            FOREIGN KEY (converted_to_work_id) REFERENCES work(id) ON DELETE SET NULL,
            FOREIGN KEY (converted_to_task_id) REFERENCES tasks(id) ON DELETE SET NULL
        )""",
        """CREATE TABLE IF NOT EXISTS work_jobs (
            id TEXT PRIMARY KEY, bot_id TEXT NOT NULL,
            task_id TEXT NOT NULL, work_id TEXT NOT NULL, chat_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            attempt INTEGER DEFAULT 1, progress REAL DEFAULT 0.0,
            created_at TEXT NOT NULL, started_at TEXT, completed_at TEXT,
            result TEXT, error TEXT, logs TEXT DEFAULT '[]',
            FOREIGN KEY (task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY (work_id) REFERENCES work(id) ON DELETE CASCADE
        )""",
    ]

    for ddl in table_ddl:
        await session.execute(text(ddl))
    await session.commit()


async def _migrate_single_table(
    sqlite_db: Any,
    async_session_factory: Any,
    table_name: str,
    expected_columns: list[str],
    pk_columns: list[str],
    progress: Any,
    task_id: Any,
) -> int:
    """Migrate a single table from SQLite to PostgreSQL with progress updates."""
    from sqlalchemy import text

    # Get actual columns in SQLite
    async with sqlite_db.execute(f"PRAGMA table_info({table_name})") as cursor:
        col_rows = await cursor.fetchall()
    actual_columns = [row[1] for row in col_rows]

    if not actual_columns:
        return 0

    columns = [c for c in expected_columns if c in actual_columns]
    if not columns:
        return 0

    for pk in pk_columns:
        if pk not in columns:
            return 0

    # Read all rows
    col_select = ", ".join(columns)
    async with sqlite_db.execute(f"SELECT {col_select} FROM {table_name}") as cursor:
        rows = await cursor.fetchall()

    if not rows:
        return 0

    # Build upsert
    upsert_sql = _build_upsert_sql(table_name, columns, pk_columns)

    # Insert in batches
    batch_size = 500
    total = len(rows)
    migrated = 0

    async with async_session_factory() as pg_session:
        for batch_start in range(0, total, batch_size):
            batch_end = min(batch_start + batch_size, total)
            batch_rows = rows[batch_start:batch_end]

            param_dicts = []
            for row in batch_rows:
                params = {}
                for i, col in enumerate(columns):
                    params[col] = _convert_value(table_name, col, row[i])
                param_dicts.append(params)

            await pg_session.execute(text(upsert_sql), param_dicts)
            migrated += len(batch_rows)
            progress.update(task_id, completed=migrated)

        await pg_session.commit()

    return migrated


# ============================================================================
# Command: cachibot db status
# ============================================================================


@db_app.command("status")
def db_status() -> None:
    """Show current database status and statistics."""
    console.print()

    database_url = _get_database_url()
    sqlite_path = Path.home() / ".cachibot" / "cachibot.db"

    # Determine which database to inspect
    if database_url:
        _show_postgres_status(database_url)
    elif sqlite_path.exists():
        _show_sqlite_status(sqlite_path)
    else:
        console.print(
            Panel(
                "[warning]No database configured.[/]\n\n"
                "  - SQLite will be auto-created at ~/.cachibot/cachibot.db on first use\n"
                "  - For PostgreSQL, run [bold]cachibot setup-db postgres[/]",
                title="Database Status",
                border_style="yellow",
            )
        )

    # Also show SQLite if both exist
    if database_url and sqlite_path.exists():
        console.print()
        console.print(f"  [dim]Legacy SQLite database also exists at {sqlite_path}[/]")
        console.print(f"  [dim]Size: {_format_size(sqlite_path.stat().st_size)}[/]")


def _show_sqlite_status(sqlite_path: Path) -> None:
    """Display SQLite database status."""
    size = sqlite_path.stat().st_size

    tree = Tree("[bold cyan]Database Status[/]")
    tree.add("[info]Type:[/] SQLite")
    tree.add(f"[info]Location:[/] {sqlite_path}")
    tree.add(f"[info]Size:[/] {_format_size(size)}")

    # Get table stats
    try:
        stats = asyncio.run(_get_sqlite_stats(sqlite_path))
        tree.add(f"[info]Tables:[/] {stats['table_count']}")

        if stats["key_stats"]:
            stats_branch = tree.add("[info]Key Statistics:[/]")
            for tname, count in stats["key_stats"]:
                stats_branch.add(f"{tname}: {count:,}")

        tree.add("[success]Status: Connected[/]")
    except Exception as e:
        tree.add(f"[error]Status: Error - {e}[/]")

    console.print(tree)


def _show_postgres_status(database_url: str) -> None:
    """Display PostgreSQL database status."""
    database_url = _fix_postgres_url(database_url)

    # Parse host info from URL
    host_info = "unknown"
    db_name = "unknown"
    try:
        # Extract host:port and database from URL
        # postgresql+asyncpg://user:pass@host:port/dbname
        after_at = database_url.split("@")[-1]
        parts = after_at.split("/", 1)
        host_info = parts[0]
        db_name = parts[1].split("?")[0] if len(parts) > 1 else "unknown"
    except Exception:
        pass

    tree = Tree("[bold cyan]Database Status[/]")
    tree.add("[info]Type:[/] PostgreSQL")
    tree.add(f"[info]Host:[/] {host_info}")
    tree.add(f"[info]Database:[/] {db_name}")

    try:
        stats = asyncio.run(_get_postgres_stats(database_url))

        if stats.get("size"):
            tree.add(f"[info]Size:[/] {stats['size']}")
        tree.add(f"[info]Tables:[/] {stats.get('table_count', '?')}")

        if stats.get("pool_info"):
            tree.add(f"[info]Pool:[/] {stats['pool_info']}")

        if stats.get("key_stats"):
            stats_branch = tree.add("[info]Key Statistics:[/]")
            for tname, count in stats["key_stats"]:
                stats_branch.add(f"{tname}: {count:,}")

        tree.add("[success]Status: Connected[/]")
    except Exception as e:
        error_msg = str(e)
        if len(error_msg) > 100:
            error_msg = error_msg[:97] + "..."
        tree.add("[error]Status: Connection failed[/]")
        tree.add(f"[error]{error_msg}[/]")

    console.print(tree)


async def _get_sqlite_stats(sqlite_path: Path) -> dict[str, Any]:
    """Get statistics from a SQLite database."""
    import aiosqlite

    stats: dict[str, Any] = {"table_count": 0, "key_stats": []}

    async with aiosqlite.connect(str(sqlite_path)) as db:
        # Count tables
        table_count = 0
        key_stats = []

        for table_name, _, _ in MIGRATION_ORDER:
            async with db.execute(f"PRAGMA table_info({table_name})") as cursor:
                cols = await cursor.fetchall()
            if not cols:
                continue
            table_count += 1

            if table_name in KEY_TABLES:
                async with db.execute(f"SELECT COUNT(*) FROM {table_name}") as cursor:
                    row = await cursor.fetchone()
                count = row[0] if row else 0
                key_stats.append((table_name, count))

        stats["table_count"] = table_count
        stats["key_stats"] = key_stats

    return stats


async def _get_postgres_stats(database_url: str) -> dict[str, Any]:
    """Get statistics from a PostgreSQL database."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    stats: dict[str, Any] = {
        "table_count": 0,
        "size": None,
        "pool_info": None,
        "key_stats": [],
    }

    try:
        async with engine.begin() as conn:
            # Database size
            result = await conn.execute(
                text("SELECT pg_size_pretty(pg_database_size(current_database()))")
            )
            row = result.fetchone()
            if row:
                stats["size"] = row[0]

            # Table count
            result = await conn.execute(
                text(
                    "SELECT COUNT(*) FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
                )
            )
            row = result.fetchone()
            if row:
                stats["table_count"] = row[0]

            # Key table stats
            for tname in KEY_TABLES:
                try:
                    result = await conn.execute(text(f"SELECT COUNT(*) FROM {tname}"))
                    row = result.fetchone()
                    if row:
                        stats["key_stats"].append((tname, row[0]))
                except Exception:
                    pass  # Table might not exist yet

            # Pool info
            pool = engine.pool
            stats["pool_info"] = (
                f"{pool.checkedin()}/{pool.size()} "  # type: ignore[attr-defined]
                f"(available/pool_size)"
            )
    finally:
        await engine.dispose()

    return stats

"""
Database Setup and Connection Management

Uses aiosqlite for async SQLite operations.
"""

from pathlib import Path

import aiosqlite

# Database path (user data directory)
DB_PATH = Path.home() / ".cachibot" / "cachibot.db"

# Global connection
_db: aiosqlite.Connection | None = None


async def init_db() -> None:
    """Initialize the database and create tables."""
    global _db

    # Ensure directory exists
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Connect to database
    _db = await aiosqlite.connect(DB_PATH)
    _db.row_factory = aiosqlite.Row

    # Create tables
    await _db.executescript(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        );

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
        );

        CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
        CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
        CREATE INDEX IF NOT EXISTS idx_jobs_message ON jobs(message_id);

        -- Bot-scoped conversation history
        CREATE TABLE IF NOT EXISTS bot_messages (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            chat_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            metadata TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_bot_messages_bot_chat ON bot_messages(bot_id, chat_id);
        CREATE INDEX IF NOT EXISTS idx_bot_messages_timestamp ON bot_messages(timestamp);

        -- Custom instructions per bot (one per bot)
        CREATE TABLE IF NOT EXISTS bot_instructions (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            content TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Document metadata per bot
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
        );
        CREATE INDEX IF NOT EXISTS idx_bot_documents_bot ON bot_documents(bot_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_documents_hash ON bot_documents(bot_id, file_hash);

        -- Document chunks with embeddings (for vector search)
        -- Note: sqlite-vec virtual table created separately after extension loads
        CREATE TABLE IF NOT EXISTS doc_chunks (
            id TEXT PRIMARY KEY,
            document_id TEXT NOT NULL,
            bot_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            content TEXT NOT NULL,
            embedding BLOB,
            FOREIGN KEY (document_id) REFERENCES bot_documents(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_document ON doc_chunks(document_id);
        CREATE INDEX IF NOT EXISTS idx_doc_chunks_bot ON doc_chunks(bot_id);

        -- Bot contacts (for contacts capability)
        CREATE TABLE IF NOT EXISTS bot_contacts (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            name TEXT NOT NULL,
            details TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bot_contacts_bot ON bot_contacts(bot_id);

        -- Bot connections (for platform integrations: Telegram, Discord)
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
        );
        CREATE INDEX IF NOT EXISTS idx_bot_connections_bot ON bot_connections(bot_id);
        CREATE INDEX IF NOT EXISTS idx_bot_connections_status ON bot_connections(status);

        -- Users table (authentication)
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT NOT NULL UNIQUE,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            is_active INTEGER DEFAULT 1,
            created_at TEXT NOT NULL,
            created_by TEXT,
            last_login TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);

        -- Bot ownership tracking (user-scoped bots)
        CREATE TABLE IF NOT EXISTS bot_ownership (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL UNIQUE,
            user_id TEXT NOT NULL,
            created_at TEXT NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_bot_ownership_user ON bot_ownership(user_id);
        CREATE INDEX IF NOT EXISTS idx_bot_ownership_bot ON bot_ownership(bot_id);

        -- Bot configuration (synced from frontend)
        CREATE TABLE IF NOT EXISTS bots (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            icon TEXT,
            color TEXT,
            model TEXT NOT NULL,
            system_prompt TEXT NOT NULL,
            capabilities TEXT DEFAULT '{}',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        -- Chats (for platform conversations like Telegram/Discord)
        CREATE TABLE IF NOT EXISTS chats (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            platform TEXT,
            platform_chat_id TEXT,
            pinned INTEGER DEFAULT 0,
            archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_chats_bot ON chats(bot_id);
        CREATE UNIQUE INDEX IF NOT EXISTS idx_chats_platform ON chats(bot_id, platform, platform_chat_id);

        -- Skills (reusable behavior modules)
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
        );
        CREATE INDEX IF NOT EXISTS idx_skills_source ON skills(source);

        -- Bot skill activations (which skills are enabled for each bot)
        CREATE TABLE IF NOT EXISTS bot_skills (
            bot_id TEXT NOT NULL,
            skill_id TEXT NOT NULL,
            enabled INTEGER DEFAULT 1,
            activated_at TEXT NOT NULL,
            PRIMARY KEY (bot_id, skill_id),
            FOREIGN KEY (skill_id) REFERENCES skills(id) ON DELETE CASCADE
        );
        CREATE INDEX IF NOT EXISTS idx_bot_skills_bot ON bot_skills(bot_id);
        CREATE INDEX IF NOT EXISTS idx_bot_skills_skill ON bot_skills(skill_id);

        -- =============================================================================
        -- WORK MANAGEMENT SYSTEM
        -- =============================================================================

        -- Functions (Reusable Templates/Procedures)
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
        );
        CREATE INDEX IF NOT EXISTS idx_functions_bot ON functions(bot_id);
        CREATE INDEX IF NOT EXISTS idx_functions_name ON functions(bot_id, name);

        -- Schedules (Cron/Timer triggers)
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
            enabled INTEGER DEFAULT 1,
            max_concurrent INTEGER DEFAULT 1,
            catch_up INTEGER DEFAULT 0,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            next_run_at TEXT,
            last_run_at TEXT,
            run_count INTEGER DEFAULT 0,
            FOREIGN KEY (function_id) REFERENCES functions(id) ON DELETE SET NULL
        );
        CREATE INDEX IF NOT EXISTS idx_schedules_bot ON schedules(bot_id);
        CREATE INDEX IF NOT EXISTS idx_schedules_enabled ON schedules(enabled);
        CREATE INDEX IF NOT EXISTS idx_schedules_next_run ON schedules(next_run_at);

        -- Work (High-level objectives)
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
        );
        CREATE INDEX IF NOT EXISTS idx_work_bot ON work(bot_id);
        CREATE INDEX IF NOT EXISTS idx_work_status ON work(status);
        CREATE INDEX IF NOT EXISTS idx_work_schedule ON work(schedule_id);
        CREATE INDEX IF NOT EXISTS idx_work_parent ON work(parent_work_id);
        CREATE INDEX IF NOT EXISTS idx_work_chat ON work(bot_id, chat_id);

        -- Tasks (Steps within Work)
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
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_bot ON tasks(bot_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_work ON tasks(work_id);
        CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
        CREATE INDEX IF NOT EXISTS idx_tasks_order ON tasks(work_id, task_order);

        -- Work Jobs (Execution attempts - new version linked to work system)
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
        );
        CREATE INDEX IF NOT EXISTS idx_work_jobs_bot ON work_jobs(bot_id);
        CREATE INDEX IF NOT EXISTS idx_work_jobs_task ON work_jobs(task_id);
        CREATE INDEX IF NOT EXISTS idx_work_jobs_work ON work_jobs(work_id);
        CREATE INDEX IF NOT EXISTS idx_work_jobs_status ON work_jobs(status);

        -- Bot Notes (persistent memory for bots)
        CREATE TABLE IF NOT EXISTS bot_notes (
            id TEXT PRIMARY KEY,
            bot_id TEXT NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            tags TEXT DEFAULT '[]',
            source TEXT DEFAULT 'user',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_bot_notes_bot ON bot_notes(bot_id);
        CREATE INDEX IF NOT EXISTS idx_bot_notes_tags ON bot_notes(tags);

        -- Todos (Reminders/Notes)
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
        );
        CREATE INDEX IF NOT EXISTS idx_todos_bot ON todos(bot_id);
        CREATE INDEX IF NOT EXISTS idx_todos_status ON todos(status);
        CREATE INDEX IF NOT EXISTS idx_todos_remind ON todos(remind_at);
        """
    )

    await _db.commit()

    # ==========================================================================
    # MIGRATIONS - Add new columns to existing tables
    # ==========================================================================
    # These use "ALTER TABLE ... ADD COLUMN" which SQLite ignores if column exists
    # (via catching the "duplicate column name" error)

    migrations = [
        # Add archived column to chats table
        "ALTER TABLE chats ADD COLUMN archived INTEGER DEFAULT 0",
    ]

    for migration in migrations:
        try:
            await _db.execute(migration)
            await _db.commit()
        except Exception:
            # Column already exists or other expected error
            pass


async def close_db() -> None:
    """Close the database connection."""
    global _db
    if _db:
        await _db.close()
        _db = None


async def get_db() -> aiosqlite.Connection:
    """Get the database connection, initializing if needed."""
    global _db
    if _db is None:
        await init_db()
    return _db

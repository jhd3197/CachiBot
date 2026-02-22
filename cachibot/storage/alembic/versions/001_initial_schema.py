"""Initial schema - all 25 CachiBotV2 tables migrated to PostgreSQL.

Revision ID: 001
Revises: None
Create Date: 2026-02-14

Covers all tables from the SQLite database.py:
- messages, jobs, bot_messages
- bot_instructions, bot_documents, doc_chunks
- bot_contacts, bot_connections
- users (unified with website), bot_ownership
- bots, chats
- skills, bot_skills
- functions, schedules, work, tasks, work_jobs
- bot_notes, todos
- rooms, room_members, room_bots, room_messages
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Enable pgvector extension for embedding similarity search
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # =========================================================================
    # 1. messages
    # =========================================================================
    op.create_table(
        "messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_messages_timestamp", "messages", ["timestamp"])
    op.create_index(
        "idx_messages_metadata",
        "messages",
        ["metadata"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 2. jobs
    # =========================================================================
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("message_id", sa.String(), sa.ForeignKey("messages.id"), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.create_index("idx_jobs_status", "jobs", ["status"])
    op.create_index("idx_jobs_message", "jobs", ["message_id"])
    op.create_index("idx_jobs_result", "jobs", ["result"], postgresql_using="gin")

    # =========================================================================
    # 3. bot_messages
    # =========================================================================
    op.create_table(
        "bot_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column("reply_to_id", sa.String(), nullable=True),
    )
    op.create_index("idx_bot_messages_bot_chat", "bot_messages", ["bot_id", "chat_id"])
    op.create_index("idx_bot_messages_timestamp", "bot_messages", ["timestamp"])
    op.create_index(
        "idx_bot_messages_metadata",
        "bot_messages",
        ["metadata"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 4. bot_instructions
    # =========================================================================
    op.create_table(
        "bot_instructions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), unique=True, nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # =========================================================================
    # 5. bot_documents
    # =========================================================================
    op.create_table(
        "bot_documents",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("filename", sa.String(), nullable=False),
        sa.Column("file_type", sa.String(), nullable=False),
        sa.Column("file_hash", sa.String(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("chunk_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(), nullable=False, server_default="processing"),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_bot_documents_bot", "bot_documents", ["bot_id"])
    op.create_index(
        "idx_bot_documents_hash",
        "bot_documents",
        ["bot_id", "file_hash"],
        unique=True,
    )

    # =========================================================================
    # 6. doc_chunks (with pgvector)
    # =========================================================================
    op.create_table(
        "doc_chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "document_id",
            sa.String(),
            sa.ForeignKey("bot_documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
    )
    # Add the vector column via raw SQL (pgvector type)
    op.execute("ALTER TABLE doc_chunks ADD COLUMN embedding vector(384)")
    op.create_index("idx_doc_chunks_document", "doc_chunks", ["document_id"])
    op.create_index("idx_doc_chunks_bot", "doc_chunks", ["bot_id"])
    # HNSW index for cosine similarity search on embeddings
    op.execute(
        "CREATE INDEX idx_doc_chunks_embedding ON doc_chunks "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )

    # =========================================================================
    # 7. bot_contacts
    # =========================================================================
    op.create_table(
        "bot_contacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_bot_contacts_bot", "bot_contacts", ["bot_id"])

    # =========================================================================
    # 8. bot_connections
    # =========================================================================
    op.create_table(
        "bot_connections",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column(
            "status",
            sa.String(),
            nullable=False,
            server_default="disconnected",
        ),
        sa.Column("config_encrypted", JSONB(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_activity", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_bot_connections_bot", "bot_connections", ["bot_id"])
    op.create_index("idx_bot_connections_status", "bot_connections", ["status"])
    op.create_index(
        "idx_bot_connections_config_encrypted",
        "bot_connections",
        ["config_encrypted"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 9. users (UNIFIED — platform + website columns)
    # =========================================================================
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("email", sa.String(), unique=True, nullable=False),
        sa.Column("username", sa.String(), unique=True, nullable=False),
        sa.Column("password_hash", sa.String(), nullable=False),
        # Authorization
        sa.Column("role", sa.String(), nullable=False, server_default="user"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_admin", sa.Boolean(), nullable=False, server_default="false"),
        # Tier
        sa.Column("tier", sa.String(), nullable=False, server_default="free"),
        # Email verification
        sa.Column("verification_token", sa.String(), nullable=True),
        sa.Column(
            "verification_token_expires",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column("verification_token_hint", sa.String(16), nullable=True),
        # Password reset
        sa.Column("reset_token", sa.String(), nullable=True),
        sa.Column("reset_token_expires", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reset_token_hint", sa.String(16), nullable=True),
        # Password change tracking
        sa.Column("password_changed_at", sa.DateTime(timezone=True), nullable=True),
        # Billing
        sa.Column("credit_balance", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "low_balance_alerted",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        # Platform-specific
        sa.Column("created_by", sa.String(), nullable=True),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        # Timestamps
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("idx_users_email", "users", ["email"])
    op.create_index("idx_users_username", "users", ["username"])
    op.create_index("idx_users_role", "users", ["role"])
    op.create_index(
        "idx_users_verification_token_hint",
        "users",
        ["verification_token_hint"],
    )
    op.create_index("idx_users_reset_token_hint", "users", ["reset_token_hint"])

    # =========================================================================
    # 10. bot_ownership
    # =========================================================================
    op.create_table(
        "bot_ownership",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), unique=True, nullable=False),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_bot_ownership_user", "bot_ownership", ["user_id"])
    op.create_index("idx_bot_ownership_bot", "bot_ownership", ["bot_id"])

    # =========================================================================
    # 11. bots
    # =========================================================================
    op.create_table(
        "bots",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("color", sa.String(), nullable=True),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("capabilities", JSONB(), nullable=False, server_default="{}"),
        sa.Column("models", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "idx_bots_capabilities",
        "bots",
        ["capabilities"],
        postgresql_using="gin",
    )
    op.create_index("idx_bots_models", "bots", ["models"], postgresql_using="gin")

    # =========================================================================
    # 12. chats
    # =========================================================================
    op.create_table(
        "chats",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("platform", sa.String(), nullable=True),
        sa.Column("platform_chat_id", sa.String(), nullable=True),
        sa.Column("pinned", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("archived", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_chats_bot", "chats", ["bot_id"])
    op.create_index(
        "idx_chats_platform",
        "chats",
        ["bot_id", "platform", "platform_chat_id"],
        unique=True,
    )

    # =========================================================================
    # 13. skills
    # =========================================================================
    op.create_table(
        "skills",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(), nullable=False, server_default="1.0.0"),
        sa.Column("author", sa.String(), nullable=True),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("requires_tools", JSONB(), nullable=False, server_default="[]"),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="local"),
        sa.Column("filepath", sa.String(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_skills_source", "skills", ["source"])
    op.create_index("idx_skills_tags", "skills", ["tags"], postgresql_using="gin")
    op.create_index(
        "idx_skills_requires_tools",
        "skills",
        ["requires_tools"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 14. bot_skills (composite PK)
    # =========================================================================
    op.create_table(
        "bot_skills",
        sa.Column("bot_id", sa.String(), primary_key=True),
        sa.Column(
            "skill_id",
            sa.String(),
            sa.ForeignKey("skills.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "activated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_bot_skills_bot", "bot_skills", ["bot_id"])
    op.create_index("idx_bot_skills_skill", "bot_skills", ["skill_id"])

    # =========================================================================
    # 15. functions
    # =========================================================================
    op.create_table(
        "functions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version", sa.String(), nullable=False, server_default="1.0.0"),
        sa.Column("steps", JSONB(), nullable=False, server_default="[]"),
        sa.Column("parameters", JSONB(), nullable=False, server_default="[]"),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("success_rate", sa.Float(), nullable=False, server_default="0.0"),
    )
    op.create_index("idx_functions_bot", "functions", ["bot_id"])
    op.create_index("idx_functions_name", "functions", ["bot_id", "name"])
    op.create_index("idx_functions_steps", "functions", ["steps"], postgresql_using="gin")
    op.create_index(
        "idx_functions_parameters",
        "functions",
        ["parameters"],
        postgresql_using="gin",
    )
    op.create_index("idx_functions_tags", "functions", ["tags"], postgresql_using="gin")

    # =========================================================================
    # 16. schedules
    # =========================================================================
    op.create_table(
        "schedules",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "function_id",
            sa.String(),
            sa.ForeignKey("functions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("function_params", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "schedule_type",
            sa.String(),
            nullable=False,
            server_default="cron",
        ),
        sa.Column("cron_expression", sa.String(), nullable=True),
        sa.Column("interval_seconds", sa.Integer(), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("event_trigger", sa.String(), nullable=True),
        sa.Column("timezone", sa.String(), nullable=False, server_default="UTC"),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "max_concurrent",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
        sa.Column("catch_up", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("run_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("idx_schedules_bot", "schedules", ["bot_id"])
    op.create_index("idx_schedules_enabled", "schedules", ["enabled"])
    op.create_index("idx_schedules_next_run", "schedules", ["next_run_at"])
    op.create_index(
        "idx_schedules_function_params",
        "schedules",
        ["function_params"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 17. work
    # =========================================================================
    op.create_table(
        "work",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("goal", sa.Text(), nullable=True),
        sa.Column(
            "function_id",
            sa.String(),
            sa.ForeignKey("functions.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "schedule_id",
            sa.String(),
            sa.ForeignKey("schedules.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "parent_work_id",
            sa.String(),
            sa.ForeignKey("work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("context", JSONB(), nullable=False, server_default="{}"),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("idx_work_bot", "work", ["bot_id"])
    op.create_index("idx_work_status", "work", ["status"])
    op.create_index("idx_work_schedule", "work", ["schedule_id"])
    op.create_index("idx_work_parent", "work", ["parent_work_id"])
    op.create_index("idx_work_chat", "work", ["bot_id", "chat_id"])
    op.create_index("idx_work_result", "work", ["result"], postgresql_using="gin")
    op.create_index("idx_work_context", "work", ["context"], postgresql_using="gin")
    op.create_index("idx_work_tags", "work", ["tags"], postgresql_using="gin")

    # =========================================================================
    # 18. tasks
    # =========================================================================
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column(
            "work_id",
            sa.String(),
            sa.ForeignKey("work.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=True),
        sa.Column("task_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("depends_on", JSONB(), nullable=False, server_default="[]"),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_retries", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("timeout_seconds", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
    )
    op.create_index("idx_tasks_bot", "tasks", ["bot_id"])
    op.create_index("idx_tasks_work", "tasks", ["work_id"])
    op.create_index("idx_tasks_status", "tasks", ["status"])
    op.create_index("idx_tasks_order", "tasks", ["work_id", "task_order"])
    op.create_index(
        "idx_tasks_depends_on",
        "tasks",
        ["depends_on"],
        postgresql_using="gin",
    )
    op.create_index("idx_tasks_result", "tasks", ["result"], postgresql_using="gin")

    # =========================================================================
    # 19. work_jobs
    # =========================================================================
    op.create_table(
        "work_jobs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column(
            "task_id",
            sa.String(),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "work_id",
            sa.String(),
            sa.ForeignKey("work.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("progress", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("result", JSONB(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("logs", JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("idx_work_jobs_bot", "work_jobs", ["bot_id"])
    op.create_index("idx_work_jobs_task", "work_jobs", ["task_id"])
    op.create_index("idx_work_jobs_work", "work_jobs", ["work_id"])
    op.create_index("idx_work_jobs_status", "work_jobs", ["status"])
    op.create_index(
        "idx_work_jobs_result",
        "work_jobs",
        ["result"],
        postgresql_using="gin",
    )
    op.create_index("idx_work_jobs_logs", "work_jobs", ["logs"], postgresql_using="gin")

    # =========================================================================
    # 20. bot_notes
    # =========================================================================
    op.create_table(
        "bot_notes",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
        sa.Column("source", sa.String(), nullable=False, server_default="user"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_bot_notes_bot", "bot_notes", ["bot_id"])
    op.create_index("idx_bot_notes_tags", "bot_notes", ["tags"], postgresql_using="gin")

    # =========================================================================
    # 21. rooms
    # =========================================================================
    op.create_table(
        "rooms",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "creator_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("max_bots", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("settings", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_rooms_creator", "rooms", ["creator_id"])
    op.create_index("idx_rooms_settings", "rooms", ["settings"], postgresql_using="gin")

    # =========================================================================
    # 22. room_members (composite PK)
    # =========================================================================
    op.create_table(
        "room_members",
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_room_members_user", "room_members", ["user_id"])
    op.create_index("idx_room_members_room", "room_members", ["room_id"])

    # =========================================================================
    # 23. room_bots (composite PK)
    # =========================================================================
    op.create_table(
        "room_bots",
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("bot_id", sa.String(), primary_key=True),
        sa.Column(
            "added_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_room_bots_room", "room_bots", ["room_id"])
    op.create_index("idx_room_bots_bot", "room_bots", ["bot_id"])

    # =========================================================================
    # 24. room_messages
    # =========================================================================
    op.create_table(
        "room_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sender_type", sa.String(), nullable=False),
        sa.Column("sender_id", sa.String(), nullable=False),
        sa.Column("sender_name", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata", JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_room_messages_room", "room_messages", ["room_id"])
    op.create_index(
        "idx_room_messages_room_timestamp",
        "room_messages",
        ["room_id", "timestamp"],
    )
    op.create_index(
        "idx_room_messages_sender",
        "room_messages",
        ["sender_type", "sender_id"],
    )
    op.create_index(
        "idx_room_messages_metadata",
        "room_messages",
        ["metadata"],
        postgresql_using="gin",
    )

    # =========================================================================
    # 25. todos
    # =========================================================================
    op.create_table(
        "todos",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=False),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="open"),
        sa.Column("priority", sa.String(), nullable=False, server_default="normal"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remind_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "converted_to_work_id",
            sa.String(),
            sa.ForeignKey("work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "converted_to_task_id",
            sa.String(),
            sa.ForeignKey("tasks.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("tags", JSONB(), nullable=False, server_default="[]"),
    )
    op.create_index("idx_todos_bot", "todos", ["bot_id"])
    op.create_index("idx_todos_status", "todos", ["status"])
    op.create_index("idx_todos_remind", "todos", ["remind_at"])
    op.create_index("idx_todos_tags", "todos", ["tags"], postgresql_using="gin")


def downgrade() -> None:
    # Drop tables in reverse dependency order
    op.drop_table("todos")
    op.drop_table("room_messages")
    op.drop_table("room_bots")
    op.drop_table("room_members")
    op.drop_table("rooms")
    op.drop_table("bot_notes")
    op.drop_table("work_jobs")
    op.drop_table("tasks")
    op.drop_table("work")
    op.drop_table("schedules")
    op.drop_table("functions")
    op.drop_table("bot_skills")
    op.drop_table("skills")
    op.drop_table("chats")
    op.drop_table("bots")
    op.drop_table("bot_ownership")
    op.drop_table("users")
    op.drop_table("bot_connections")
    op.drop_table("bot_contacts")
    op.drop_table("doc_chunks")
    op.drop_table("bot_documents")
    op.drop_table("bot_instructions")
    op.drop_table("bot_messages")
    op.drop_table("jobs")
    op.drop_table("messages")

    # Drop pgvector extension
    op.execute("DROP EXTENSION IF EXISTS vector")

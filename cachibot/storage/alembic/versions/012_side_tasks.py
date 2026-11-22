"""Add side tasks table and chats.parent_chat_id.

Revision ID: 012
Revises: 011
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "012"
down_revision: str | None = "011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "side_tasks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_chat_id",
            sa.String(),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "chat_id",
            sa.String(),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("prompt", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False, server_default="side"),
        sa.Column("group_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False, server_default="waiting_for_slot"),
        sa.Column("needs_you_reason", sa.Text(), nullable=True),
        sa.Column("started_by", sa.String(), nullable=False, server_default="user"),
        sa.Column("worktree_path", sa.String(), nullable=True),
        sa.Column("branch", sa.String(), nullable=True),
        sa.Column("base_commit", sa.String(), nullable=True),
        sa.Column("merged_commit", sa.String(), nullable=True),
        sa.Column("merged_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("conflict_files", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "work_id",
            sa.String(),
            sa.ForeignKey("work.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_side_tasks_bot", "side_tasks", ["bot_id"])
    op.create_index("idx_side_tasks_parent", "side_tasks", ["parent_chat_id"])
    op.create_index("idx_side_tasks_chat", "side_tasks", ["chat_id"])
    op.create_index("idx_side_tasks_status", "side_tasks", ["status"])
    op.create_index("idx_side_tasks_group", "side_tasks", ["group_id"])

    op.add_column(
        "chats",
        sa.Column(
            "parent_chat_id",
            sa.String(),
            sa.ForeignKey("chats.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("idx_chats_parent", "chats", ["parent_chat_id"])


def downgrade() -> None:
    op.drop_index("idx_chats_parent", table_name="chats")
    op.drop_column("chats", "parent_chat_id")
    op.drop_table("side_tasks")

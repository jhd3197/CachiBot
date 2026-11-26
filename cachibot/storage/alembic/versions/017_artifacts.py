"""Add artifacts table (server-side artifact store).

Revision ID: 017
Revises: 016
Create Date: 2026-11-26
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "017"
down_revision: str | None = "016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Server-side artifact store: one row per artifact, owned by a bot and
    # optionally tied to a chat/message. `version` bumps on every saved edit
    # so clients can tell stale local copies from the stored source.
    op.create_table(
        "artifacts",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chat_id", sa.String(), nullable=True),
        sa.Column("message_id", sa.String(), nullable=True),
        sa.Column("type", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=True),
        sa.Column("plugin", sa.String(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default="{}"),
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
    op.create_index("idx_artifacts_bot", "artifacts", ["bot_id"])
    op.create_index("idx_artifacts_bot_chat", "artifacts", ["bot_id", "chat_id"])


def downgrade() -> None:
    op.drop_index("idx_artifacts_bot_chat", table_name="artifacts")
    op.drop_index("idx_artifacts_bot", table_name="artifacts")
    op.drop_table("artifacts")

"""Add source_message_id and reply_message_id to side_tasks (E5 replies).

Revision ID: 015
Revises: 014
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "015"
down_revision: str | None = "014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Parent-chat message the side task was started from (nullable: chats
    # that predate replies, or a parent chat with no user message, have none).
    op.add_column(
        "side_tasks",
        sa.Column("source_message_id", sa.String(), nullable=True),
    )
    # The one reply message in the parent chat (created on the first
    # qualifying transition, updated in place after — never duplicated).
    op.add_column(
        "side_tasks",
        sa.Column("reply_message_id", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("side_tasks", "reply_message_id")
    op.drop_column("side_tasks", "source_message_id")

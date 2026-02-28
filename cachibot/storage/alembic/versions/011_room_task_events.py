"""Add room task events table for activity history.

Revision ID: 011
Revises: 010
Create Date: 2026-02-25
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "011"
down_revision: str | None = "010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "room_task_events",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "task_id",
            sa.String(),
            sa.ForeignKey("room_tasks.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("field", sa.String(), nullable=True),
        sa.Column("old_value", sa.Text(), nullable=True),
        sa.Column("new_value", sa.Text(), nullable=True),
        sa.Column(
            "actor_user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "actor_bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_room_task_events_task", "room_task_events", ["task_id"])
    op.create_index(
        "idx_room_task_events_task_created",
        "room_task_events",
        ["task_id", "created_at"],
    )
    op.create_index("idx_room_task_events_room", "room_task_events", ["room_id"])


def downgrade() -> None:
    op.drop_table("room_task_events")

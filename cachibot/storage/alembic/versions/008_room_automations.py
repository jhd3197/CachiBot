"""Add room automations table.

Revision ID: 008
Revises: 007
Create Date: 2026-02-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "008"
down_revision: str | None = "007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "room_automations",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("trigger_type", sa.String(), nullable=False),
        sa.Column("trigger_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("action_config", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_by", sa.String(), nullable=False),
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default="0"),
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
    op.create_index("idx_automations_room", "room_automations", ["room_id"])
    op.create_index(
        "idx_automations_trigger",
        "room_automations",
        ["trigger_type"],
    )


def downgrade() -> None:
    op.drop_table("room_automations")

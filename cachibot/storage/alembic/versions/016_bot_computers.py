"""Add bot_computers table (per-bot Vela computer).

Revision ID: 016
Revises: 015
Create Date: 2026-11-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: str | None = "015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # One row per bot; bot_id is the primary key. State is one of
    # unavailable | off | building | starting | awake | asleep | needs_you.
    op.create_table(
        "bot_computers",
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("state", sa.String(), nullable=False, server_default="off"),
        sa.Column("container_name", sa.String(), nullable=True),
        sa.Column("host_port", sa.Integer(), nullable=True),
        sa.Column("image_tag", sa.String(), nullable=False),
        sa.Column("vela_version", sa.String(), nullable=False),
        sa.Column("last_active_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
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


def downgrade() -> None:
    op.drop_table("bot_computers")

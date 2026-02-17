"""Platform-wide tool visibility configuration — single-row table.

Revision ID: 004
Revises: 003
Create Date: 2026-02-17

Adds the platform_tool_config table for globally disabling capabilities
and skills across the entire platform.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "004"
down_revision: str | None = "003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "platform_tool_config",
        sa.Column("id", sa.String(), primary_key=True, server_default="default"),
        sa.Column("disabled_capabilities", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("disabled_skills", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_table("platform_tool_config")

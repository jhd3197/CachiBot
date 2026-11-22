"""Add group_title to side_tasks (E3 helper groups).

Revision ID: 014
Revises: 013
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "014"
down_revision: str | None = "013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "side_tasks",
        sa.Column("group_title", sa.String(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("side_tasks", "group_title")

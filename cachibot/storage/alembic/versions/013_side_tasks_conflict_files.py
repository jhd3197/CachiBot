"""Add conflict_files to side_tasks (E2 merge conflicts).

Revision ID: 013
Revises: 012
Create Date: 2026-11-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "013"
down_revision: str | None = "012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "side_tasks",
        sa.Column("conflict_files", sa.JSON(), nullable=False, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("side_tasks", "conflict_files")

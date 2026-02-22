"""Add role column to room_bots table.

Revision ID: 006
Revises: 005
Create Date: 2026-02-20
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "006"
down_revision: str | None = "005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "room_bots", sa.Column("role", sa.String(), nullable=False, server_default="default")
    )


def downgrade() -> None:
    op.drop_column("room_bots", "role")

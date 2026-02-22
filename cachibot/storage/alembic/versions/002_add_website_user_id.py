"""Add website_user_id column to users table.

Revision ID: 002
Revises: 001
Create Date: 2026-02-14

Links V2 platform users to CachiBot website INT user IDs
for the auth bridge (cloud deploy mode).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "002"
down_revision: str | None = "001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("website_user_id", sa.Integer(), nullable=True),
    )
    op.create_index(
        "idx_users_website_user_id",
        "users",
        ["website_user_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_users_website_user_id", table_name="users")
    op.drop_column("users", "website_user_id")

"""Groups, group members, and bot-group access tables.

Revision ID: 005
Revises: 004
Create Date: 2026-02-17

Adds the groups, group_members, and bot_group_access tables for
role-based bot sharing via user groups.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "005"
down_revision: str | None = "004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Groups table
    op.create_table(
        "groups",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False, unique=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_by",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
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
    op.create_index("idx_groups_created_by", "groups", ["created_by"])

    # Group members table (composite PK)
    op.create_table(
        "group_members",
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("role", sa.String(), nullable=False, server_default="member"),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_group_members_user", "group_members", ["user_id"])
    op.create_index("idx_group_members_group", "group_members", ["group_id"])

    # Bot-group access table
    op.create_table(
        "bot_group_access",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "group_id",
            sa.String(),
            sa.ForeignKey("groups.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("access_level", sa.String(), nullable=False, server_default="viewer"),
        sa.Column(
            "granted_by",
            sa.String(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("bot_id", "group_id", name="uq_bot_group_access"),
    )
    op.create_index("idx_bot_group_access_bot", "bot_group_access", ["bot_id"])
    op.create_index("idx_bot_group_access_group", "bot_group_access", ["group_id"])


def downgrade() -> None:
    op.drop_table("bot_group_access")
    op.drop_table("group_members")
    op.drop_table("groups")

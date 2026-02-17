"""Per-bot environment variable system — 4 new tables.

Revision ID: 003
Revises: 002
Create Date: 2026-02-16

Adds tables for per-bot environment variable overrides, platform-level
defaults, per-bot skill configuration, and an audit trail:
- bot_environments: per-bot encrypted env var overrides
- platform_environments: per-platform encrypted env var defaults
- bot_skill_configs: per-bot skill configuration (JSON)
- env_audit_log: audit trail for all env var operations
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "003"
down_revision: str | None = "002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # =========================================================================
    # 1. bot_environments — per-bot env var overrides (Layer 3)
    # =========================================================================
    op.create_table(
        "bot_environments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
        sa.Column("source", sa.String(), nullable=False, server_default="user"),
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
        sa.Column(
            "created_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("bot_id", "key", name="uq_bot_env_bot_key"),
    )
    op.create_index("idx_bot_env_bot", "bot_environments", ["bot_id"])

    # =========================================================================
    # 2. platform_environments — per-platform defaults (Layer 2)
    # =========================================================================
    op.create_table(
        "platform_environments",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("platform", sa.String(), nullable=False),
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value_encrypted", sa.Text(), nullable=False),
        sa.Column("nonce", sa.Text(), nullable=False),
        sa.Column("salt", sa.Text(), nullable=False),
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
        sa.Column(
            "created_by",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("platform", "key", name="uq_platform_env_platform_key"),
    )
    op.create_index("idx_platform_env_platform", "platform_environments", ["platform"])

    # =========================================================================
    # 3. bot_skill_configs — per-bot skill configuration (Layer 4)
    # =========================================================================
    op.create_table(
        "bot_skill_configs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "bot_id",
            sa.String(),
            sa.ForeignKey("bots.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("skill_name", sa.String(), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
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
        sa.UniqueConstraint("bot_id", "skill_name", name="uq_bot_skill_config_bot_skill"),
    )
    op.create_index("idx_bot_skill_config_bot", "bot_skill_configs", ["bot_id"])

    # =========================================================================
    # 4. env_audit_log — audit trail for env var operations
    # =========================================================================
    op.create_table(
        "env_audit_log",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("bot_id", sa.String(), nullable=True),
        sa.Column(
            "user_id",
            sa.String(),
            sa.ForeignKey("users.id"),
            nullable=True,
        ),
        sa.Column("action", sa.String(), nullable=False),
        sa.Column("key_name", sa.String(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ip_address", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False, server_default="{}"),
    )
    op.create_index("idx_env_audit_bot", "env_audit_log", ["bot_id"])
    op.create_index("idx_env_audit_time", "env_audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_table("env_audit_log")
    op.drop_table("bot_skill_configs")
    op.drop_table("platform_environments")
    op.drop_table("bot_environments")

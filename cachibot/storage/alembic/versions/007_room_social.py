"""Add room social features: reactions, pinned messages, bookmarks.

Revision ID: 007
Revises: 006
Create Date: 2026-02-22
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "007"
down_revision: str | None = "006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reactions on room messages
    op.create_table(
        "room_message_reactions",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(),
            sa.ForeignKey("room_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("emoji", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("room_id", "message_id", "user_id", "emoji", name="uq_reaction"),
    )
    op.create_index("idx_reactions_message", "room_message_reactions", ["message_id"])
    op.create_index("idx_reactions_room", "room_message_reactions", ["room_id"])

    # Pinned messages
    op.create_table(
        "room_pinned_messages",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(),
            sa.ForeignKey("room_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("pinned_by", sa.String(), nullable=False),
        sa.Column(
            "pinned_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("room_id", "message_id", name="uq_pin"),
    )
    op.create_index("idx_pins_room", "room_pinned_messages", ["room_id"])

    # Bookmarks (personal, user-scoped)
    op.create_table(
        "room_bookmarks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "room_id",
            sa.String(),
            sa.ForeignKey("rooms.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "message_id",
            sa.String(),
            sa.ForeignKey("room_messages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "message_id", name="uq_bookmark"),
    )
    op.create_index("idx_bookmarks_user", "room_bookmarks", ["user_id"])
    op.create_index("idx_bookmarks_room", "room_bookmarks", ["room_id"])


def downgrade() -> None:
    op.drop_table("room_bookmarks")
    op.drop_table("room_pinned_messages")
    op.drop_table("room_message_reactions")

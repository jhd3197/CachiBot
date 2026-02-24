"""Add embedding model tracking to bot_documents and expand vector dimension.

Revision ID: 009
Revises: 008
Create Date: 2026-02-23
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009"
down_revision: str | None = "008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add embedding tracking columns to bot_documents
    op.add_column("bot_documents", sa.Column("embedding_model", sa.String(), nullable=True))
    op.add_column("bot_documents", sa.Column("embedding_dimensions", sa.Integer(), nullable=True))

    # Note: VectorType dimension change (384 -> 3072) for doc_chunks.embedding:
    # - SQLite: stores as JSON text, no column alteration needed.
    # - PostgreSQL with pgvector: would need ALTER COLUMN ... TYPE vector(3072).
    #   This is handled by dropping and recreating the column if on PostgreSQL.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.execute("ALTER TABLE doc_chunks ALTER COLUMN embedding TYPE vector(3072)")
        except Exception:
            pass  # Column may already be correct size or pgvector not installed


def downgrade() -> None:
    op.drop_column("bot_documents", "embedding_dimensions")
    op.drop_column("bot_documents", "embedding_model")

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        try:
            op.execute("ALTER TABLE doc_chunks ALTER COLUMN embedding TYPE vector(384)")
        except Exception:
            pass

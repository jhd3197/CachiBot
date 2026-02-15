"""
Knowledge base models: BotInstruction, BotDocument, DocChunk, BotNote.

Uses cross-dialect types so models work on both SQLite and PostgreSQL.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

import sqlalchemy as sa
from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

__all__ = ["BotInstruction", "BotDocument", "DocChunk", "BotNote", "VectorType"]


class VectorType(sa.types.TypeDecorator):
    """Vector type that uses pgvector on PostgreSQL and Text on SQLite.

    On PostgreSQL: delegates to pgvector's Vector(dim) for native similarity search.
    On SQLite: stores embeddings as JSON-encoded text (list of floats).
    """

    impl = sa.Text
    cache_ok = True

    def __init__(self, dim: int = 384):
        super().__init__()
        self.dim = dim

    def load_dialect_impl(self, dialect):  # type: ignore[no-untyped-def]
        if dialect.name == "postgresql":
            try:
                from pgvector.sqlalchemy import Vector

                return dialect.type_descriptor(Vector(self.dim))
            except ImportError:
                # pgvector not installed, fall back to Text
                return dialect.type_descriptor(sa.Text())
        return dialect.type_descriptor(sa.Text())

    def process_bind_param(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if dialect.name != "postgresql":
            # SQLite: serialize to JSON string
            if isinstance(value, (list, tuple)):
                return json.dumps(list(value))
            return value
        # PostgreSQL: pgvector handles list[float] natively
        return value

    def process_result_value(self, value, dialect):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if dialect.name != "postgresql" and isinstance(value, str):
            return json.loads(value)
        return value


class BotInstruction(Base):
    """Custom instructions for a bot (one per bot)."""

    __tablename__ = "bot_instructions"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class BotDocument(Base):
    """Uploaded document metadata for a bot's knowledge base."""

    __tablename__ = "bot_documents"
    __table_args__ = (
        Index("idx_bot_documents_bot", "bot_id"),
        Index("idx_bot_documents_hash", "bot_id", "file_hash", unique=True),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    file_type: Mapped[str] = mapped_column(String, nullable=False)
    file_hash: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    chunk_count: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default="0"
    )
    status: Mapped[str] = mapped_column(
        String, nullable=False, server_default="processing"
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    chunks: Mapped[list[DocChunk]] = relationship(
        "DocChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocChunk(Base):
    """Document chunk with vector embedding for RAG search.

    Uses VectorType which delegates to pgvector on PostgreSQL
    and stores as JSON text on SQLite. The embedding column stores a
    384-dimensional vector (matching BAAI/bge-small-en-v1.5).
    """

    __tablename__ = "doc_chunks"
    # HNSW index on embedding is PostgreSQL-only (pgvector).
    # It is created conditionally via DDL in init_db when on PostgreSQL.
    __table_args__ = (
        Index("idx_doc_chunks_document", "document_id"),
        Index("idx_doc_chunks_bot", "bot_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    document_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("bot_documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(VectorType(384), nullable=True)

    # Relationships
    document: Mapped[BotDocument] = relationship(
        "BotDocument", back_populates="chunks"
    )


class BotNote(Base):
    """Persistent memory notes for a bot."""

    __tablename__ = "bot_notes"
    __table_args__ = (
        Index("idx_bot_notes_bot", "bot_id"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(String, nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tags: Mapped[list] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )
    source: Mapped[str] = mapped_column(
        String, nullable=False, server_default="user"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

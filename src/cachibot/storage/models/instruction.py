"""
Custom Instruction models: InstructionRecord and InstructionVersion.

Stores bot-created instructions with versioned prompt templates,
enabling bots to create and manage their own LLM-powered tools.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from cachibot.storage.db import Base

__all__ = [
    "InstructionRecord",
    "InstructionVersion",
]


class InstructionRecord(Base):
    """A custom instruction owned by a bot."""

    __tablename__ = "custom_instructions"
    __table_args__ = (
        Index("idx_instructions_bot", "bot_id"),
        Index("idx_instructions_bot_name", "bot_id", "name"),
        Index("idx_instructions_category", "category"),
        UniqueConstraint("bot_id", "name", name="uq_instruction_bot_name"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    bot_id: Mapped[str] = mapped_column(
        String, ForeignKey("bots.id", ondelete="CASCADE"), nullable=False
    )

    # Identity
    name: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Prompt configuration
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str] = mapped_column(
        String, nullable=False, server_default="text"
    )  # text, json, list, markdown

    # Model hints
    model_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Template variables (JSON list of variable names)
    input_variables: Mapped[list] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )

    # Few-shot examples (JSON list of {input, output} dicts)
    few_shot_examples: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    # Authorship
    created_by: Mapped[str | None] = mapped_column(String, nullable=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default="1")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    # Organisation
    category: Mapped[str] = mapped_column(String, nullable=False, server_default="custom")
    tags: Mapped[list] = mapped_column(sa.JSON, nullable=False, server_default="[]")

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    versions: Mapped[list[InstructionVersion]] = relationship(
        "InstructionVersion",
        back_populates="instruction",
        cascade="all, delete-orphan",
        order_by="InstructionVersion.version",
    )


class InstructionVersion(Base):
    """Version history for a custom instruction."""

    __tablename__ = "custom_instruction_versions"
    __table_args__ = (
        Index("idx_instr_versions_instruction", "instruction_id"),
        UniqueConstraint(
            "instruction_id", "version", name="uq_instruction_version"
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True)
    instruction_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("custom_instructions.id", ondelete="CASCADE"),
        nullable=False,
    )

    # Version identity
    version: Mapped[int] = mapped_column(Integer, nullable=False)

    # Snapshot of prompt config at this version
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    system_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_format: Mapped[str] = mapped_column(String, nullable=False)
    model_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    temperature: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_variables: Mapped[list] = mapped_column(
        sa.JSON, nullable=False, server_default="[]"
    )
    few_shot_examples: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    # Authorship
    author: Mapped[str] = mapped_column(String, nullable=False)
    commit_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    instruction: Mapped[InstructionRecord] = relationship(
        "InstructionRecord", back_populates="versions"
    )

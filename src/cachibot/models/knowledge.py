"""
Pydantic models for Knowledge Base data.

Includes models for bot-scoped messages, custom instructions, documents, and chunks.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class DocumentStatus(str, Enum):
    """Document processing status."""

    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"


class BotMessage(BaseModel):
    """A message in a bot's conversation history."""

    id: str
    bot_id: str
    chat_id: str
    role: str  # 'user' | 'assistant' | 'system'
    content: str
    timestamp: datetime
    metadata: dict = Field(default_factory=dict)


class BotInstruction(BaseModel):
    """Custom instructions for a bot."""

    id: str
    bot_id: str
    content: str
    updated_at: datetime


class Document(BaseModel):
    """Uploaded document metadata."""

    id: str
    bot_id: str
    filename: str
    file_type: str  # 'pdf' | 'txt' | 'md'
    file_hash: str
    file_size: int
    chunk_count: int = 0
    status: DocumentStatus = DocumentStatus.PROCESSING
    uploaded_at: datetime
    processed_at: datetime | None = None


class DocChunk(BaseModel):
    """A chunk of document text with its embedding."""

    id: str
    document_id: str
    bot_id: str
    chunk_index: int
    content: str
    embedding: bytes | None = None  # Serialized float32 array


class DocumentCreate(BaseModel):
    """Input for creating a document record."""

    bot_id: str
    filename: str
    file_type: str
    file_hash: str
    file_size: int


class InstructionUpdate(BaseModel):
    """Input for updating bot instructions."""

    content: str = Field(max_length=10000)

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


# =============================================================================
# NOTES
# =============================================================================


class NoteSource(str, Enum):
    """Source of a note."""

    USER = "user"
    BOT = "bot"


class BotNote(BaseModel):
    """A note in a bot's knowledge base."""

    id: str
    bot_id: str
    title: str
    content: str
    tags: list[str] = Field(default_factory=list)
    source: NoteSource = NoteSource.USER
    created_at: datetime
    updated_at: datetime


class NoteCreate(BaseModel):
    """Input for creating a note."""

    title: str = Field(max_length=200)
    content: str = Field(max_length=50000)
    tags: list[str] = Field(default_factory=list, max_length=20)


class NoteUpdate(BaseModel):
    """Input for updating a note."""

    title: str | None = Field(default=None, max_length=200)
    content: str | None = Field(default=None, max_length=50000)
    tags: list[str] | None = Field(default=None, max_length=20)


class NoteResponse(BaseModel):
    """Response model for note operations."""

    id: str
    bot_id: str
    title: str
    content: str
    tags: list[str]
    source: str
    created_at: str
    updated_at: str


class KnowledgeStats(BaseModel):
    """Overview stats for a bot's knowledge base."""

    total_documents: int = 0
    documents_ready: int = 0
    documents_processing: int = 0
    documents_failed: int = 0
    total_chunks: int = 0
    total_notes: int = 0
    has_instructions: bool = False


class SearchRequest(BaseModel):
    """Input for knowledge base search."""

    query: str = Field(max_length=500)
    include_notes: bool = True
    include_documents: bool = True
    limit: int = Field(default=10, ge=1, le=50)


class SearchResultResponse(BaseModel):
    """A single search result."""

    type: str  # 'document' | 'note'
    id: str
    title: str
    content: str
    score: float | None = None
    source: str | None = None  # document filename or note source


class ChunkResponse(BaseModel):
    """Response for a document chunk (without embedding)."""

    id: str
    document_id: str
    chunk_index: int
    content: str

"""Chat-related Pydantic models."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    """Message role in conversation."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatMessage(BaseModel):
    """A single chat message."""

    id: str = Field(description="Unique message ID")
    role: MessageRole = Field(description="Message role")
    content: str = Field(description="Message content")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChatRequest(BaseModel):
    """Request to send a chat message."""

    message: str = Field(description="User message content", min_length=1)
    workspace: str | None = Field(default=None, description="Workspace path override")


class ChatResponse(BaseModel):
    """Response from chat endpoint."""

    message_id: str = Field(description="ID of the created message")
    status: str = Field(default="processing", description="Current status")


class ChatHistory(BaseModel):
    """Chat history response."""

    messages: list[ChatMessage] = Field(default_factory=list)
    total: int = Field(default=0)

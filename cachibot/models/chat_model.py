"""
Pydantic models for Chat data.

Chats created from platform conversations (Telegram, Discord).
"""

from datetime import datetime

from pydantic import BaseModel


class Chat(BaseModel):
    """A chat/conversation, potentially from a platform."""

    id: str
    bot_id: str
    title: str
    platform: str | None = None  # 'telegram', 'discord', or None for web chats
    platform_chat_id: str | None = None  # The platform's chat ID
    pinned: bool = False
    archived: bool = False  # Archived chats are hidden and won't be re-synced
    created_at: datetime
    updated_at: datetime


class ChatCreate(BaseModel):
    """Request body for creating a chat."""

    title: str
    platform: str | None = None
    platform_chat_id: str | None = None


class ChatResponse(BaseModel):
    """Response model for a chat."""

    id: str
    botId: str
    title: str
    platform: str | None
    platformChatId: str | None
    pinned: bool
    archived: bool
    createdAt: str
    updatedAt: str

    @classmethod
    def from_chat(cls, chat: Chat) -> "ChatResponse":
        return cls(
            id=chat.id,
            botId=chat.bot_id,
            title=chat.title,
            platform=chat.platform,
            platformChatId=chat.platform_chat_id,
            pinned=chat.pinned,
            archived=chat.archived,
            createdAt=chat.created_at.isoformat(),
            updatedAt=chat.updated_at.isoformat(),
        )

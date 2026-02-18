"""
Chats API Routes

Endpoints for managing bot chats, including platform conversations.
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.chat_model import ChatResponse
from cachibot.models.group import BotAccessLevel
from cachibot.models.knowledge import BotMessage
from cachibot.storage.repository import ChatRepository, KnowledgeRepository

router = APIRouter(prefix="/api/bots/{bot_id}/chats", tags=["chats"])

# Repository instances
chat_repo = ChatRepository()
knowledge_repo = KnowledgeRepository()


class MessageResponse(BaseModel):
    """Response model for a message."""

    id: str
    chatId: str
    role: str
    content: str
    timestamp: str
    metadata: dict
    replyToId: str | None = None

    @classmethod
    def from_message(cls, msg: BotMessage) -> "MessageResponse":
        return cls(
            id=msg.id,
            chatId=msg.chat_id,
            role=msg.role,
            content=msg.content,
            timestamp=msg.timestamp.isoformat(),
            metadata=msg.metadata,
            replyToId=msg.reply_to_id,
        )


@router.get("")
async def list_chats(
    bot_id: str,
    include_archived: bool = False,
    user: User = Depends(require_bot_access),
) -> list[ChatResponse]:
    """Get all chats for a bot (including platform chats). Excludes archived by default."""
    chats = await chat_repo.get_chats_by_bot(bot_id, include_archived=include_archived)
    return [ChatResponse.from_chat(c) for c in chats]


class ClearDataResponse(BaseModel):
    """Response for clear data operation."""

    chats_deleted: int
    messages_deleted: int


class ArchiveResponse(BaseModel):
    """Response for archive operation."""

    archived: bool
    chat_id: str


# Use POST /_clear with underscore to clearly distinguish from /{chat_id} pattern
@router.post("/_clear", status_code=200)
async def clear_all_chats(
    bot_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ClearDataResponse:
    """Delete all chats and messages for a bot (platform data cleanup)."""
    # Delete all messages first (they reference chats)
    messages_deleted = await knowledge_repo.delete_all_messages_for_bot(bot_id)

    # Delete all chats
    chats_deleted = await chat_repo.delete_all_chats_for_bot(bot_id)

    return ClearDataResponse(
        chats_deleted=chats_deleted,
        messages_deleted=messages_deleted,
    )


@router.get("/{chat_id}")
async def get_chat(
    bot_id: str,
    chat_id: str,
    user: User = Depends(require_bot_access),
) -> ChatResponse:
    """Get a specific chat."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return ChatResponse.from_chat(chat)


@router.get("/{chat_id}/messages")
async def get_chat_messages(
    bot_id: str,
    chat_id: str,
    limit: int = 50,
    user: User = Depends(require_bot_access),
) -> list[MessageResponse]:
    """Get messages for a chat."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages = await knowledge_repo.get_bot_messages(bot_id, chat_id, limit)
    return [MessageResponse.from_message(m) for m in messages]


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(
    bot_id: str,
    chat_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> None:
    """Delete a chat permanently (including messages)."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    # Delete messages for this chat first
    await knowledge_repo.delete_messages_for_chat(bot_id, chat_id)
    # Then delete the chat
    await chat_repo.delete_chat(chat_id)


@router.post("/{chat_id}/_clear-messages", status_code=200)
async def clear_chat_messages(
    bot_id: str,
    chat_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ClearDataResponse:
    """Clear all messages for a chat but keep the chat itself."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    messages_deleted = await knowledge_repo.delete_messages_for_chat(bot_id, chat_id)
    return ClearDataResponse(chats_deleted=0, messages_deleted=messages_deleted)


@router.post("/{chat_id}/_archive", status_code=200)
async def archive_chat(
    bot_id: str,
    chat_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ArchiveResponse:
    """Archive a chat. Archived chats are hidden and won't receive new messages."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    await chat_repo.archive_chat(chat_id, archived=True)
    return ArchiveResponse(archived=True, chat_id=chat_id)


@router.post("/{chat_id}/_unarchive", status_code=200)
async def unarchive_chat(
    bot_id: str,
    chat_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> ArchiveResponse:
    """Unarchive a chat. It will appear in listings and receive messages again."""
    chat = await chat_repo.get_chat(chat_id)
    if chat is None or chat.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Chat not found")

    await chat_repo.archive_chat(chat_id, archived=False)
    return ArchiveResponse(archived=False, chat_id=chat_id)

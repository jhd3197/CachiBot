"""Chat endpoints."""

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from cachibot.api.auth import get_current_user
from cachibot.models.auth import User
from cachibot.models.chat import (
    ChatHistory,
    ChatMessage,
    ChatRequest,
    ChatResponse,
    MessageRole,
)
from cachibot.storage.repository import MessageRepository

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def send_message(
    request: Request,
    chat_request: ChatRequest,
    user: User = Depends(get_current_user),
) -> ChatResponse:
    """
    Send a chat message (non-streaming).

    For real-time streaming, use the WebSocket endpoint instead.
    This endpoint queues the message and returns immediately.
    """
    message_id = str(uuid.uuid4())

    # Store message in database
    repo = MessageRepository()
    await repo.save_message(
        ChatMessage(
            id=message_id,
            role=MessageRole.USER,
            content=chat_request.message,
            timestamp=datetime.now(),
        )
    )

    return ChatResponse(
        message_id=message_id,
        status="processing",
    )


@router.get("/chat/history", response_model=ChatHistory)
async def get_history(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
) -> ChatHistory:
    """Get chat history."""
    repo = MessageRepository()
    messages = await repo.get_messages(limit=limit, offset=offset)
    total = await repo.get_message_count()

    return ChatHistory(messages=messages, total=total)


@router.delete("/chat/history", status_code=204)
async def clear_history(user: User = Depends(get_current_user)) -> None:
    """Clear all chat history."""
    repo = MessageRepository()
    await repo.clear_messages()
    return None

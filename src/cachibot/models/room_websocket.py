"""Room-specific WebSocket message models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RoomWSMessageType(str, Enum):
    """WebSocket message types for room communication."""

    # Client -> Server
    ROOM_CHAT = "room_chat"
    ROOM_TYPING = "room_typing"
    ROOM_CANCEL = "room_cancel"

    # Server -> Client
    ROOM_MESSAGE = "room_message"
    ROOM_BOT_THINKING = "room_bot_thinking"
    ROOM_BOT_TOOL_START = "room_bot_tool_start"
    ROOM_BOT_TOOL_END = "room_bot_tool_end"
    ROOM_BOT_INSTRUCTION_DELTA = "room_bot_instruction_delta"
    ROOM_BOT_DONE = "room_bot_done"
    ROOM_TYPING_INDICATOR = "room_typing_indicator"
    ROOM_PRESENCE = "room_presence"
    ROOM_ERROR = "room_error"
    ROOM_USAGE = "room_usage"
    ROOM_CHAIN_STEP = "room_chain_step"
    ROOM_ROUTE_DECISION = "room_route_decision"


class RoomWSMessage(BaseModel):
    """Generic room WebSocket message wrapper."""

    type: RoomWSMessageType = Field(description="Message type")
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def room_message(
        cls,
        room_id: str,
        sender_type: str,
        sender_id: str,
        sender_name: str,
        content: str,
        message_id: str | None = None,
    ) -> "RoomWSMessage":
        """Create a room message."""
        return cls(
            type=RoomWSMessageType.ROOM_MESSAGE,
            payload={
                "roomId": room_id,
                "senderType": sender_type,
                "senderId": sender_id,
                "senderName": sender_name,
                "content": content,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_thinking(cls, room_id: str, bot_id: str, bot_name: str) -> "RoomWSMessage":
        """Create a bot thinking indicator."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_THINKING,
            payload={"roomId": room_id, "botId": bot_id, "botName": bot_name},
        )

    @classmethod
    def bot_tool_start(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        tool_name: str,
        args: dict[str, Any],
        message_id: str = "",
    ) -> "RoomWSMessage":
        """Create a bot tool start message."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_TOOL_START,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "toolName": tool_name,
                "args": args,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_tool_end(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        result: Any,
        success: bool = True,
        message_id: str = "",
    ) -> "RoomWSMessage":
        """Create a bot tool end message."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_TOOL_END,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "result": result,
                "success": success,
                "messageId": message_id,
            },
        )

    @classmethod
    def bot_instruction_delta(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        tool_id: str,
        text: str,
    ) -> "RoomWSMessage":
        """Incremental text from a bot's instruction LLM execution."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_INSTRUCTION_DELTA,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "toolId": tool_id,
                "text": text,
            },
        )

    @classmethod
    def bot_done(cls, room_id: str, bot_id: str, bot_name: str) -> "RoomWSMessage":
        """Create a bot done message."""
        return cls(
            type=RoomWSMessageType.ROOM_BOT_DONE,
            payload={"roomId": room_id, "botId": bot_id, "botName": bot_name},
        )

    @classmethod
    def typing_indicator(
        cls, room_id: str, user_id: str, username: str, is_typing: bool
    ) -> "RoomWSMessage":
        """Create a typing indicator."""
        return cls(
            type=RoomWSMessageType.ROOM_TYPING_INDICATOR,
            payload={
                "roomId": room_id,
                "userId": user_id,
                "username": username,
                "isTyping": is_typing,
            },
        )

    @classmethod
    def presence(cls, room_id: str, user_id: str, username: str, status: str) -> "RoomWSMessage":
        """Create a presence update (online/offline)."""
        return cls(
            type=RoomWSMessageType.ROOM_PRESENCE,
            payload={
                "roomId": room_id,
                "userId": user_id,
                "username": username,
                "status": status,
            },
        )

    @classmethod
    def error(cls, room_id: str, message: str, bot_id: str | None = None) -> "RoomWSMessage":
        """Create a room error message."""
        payload: dict[str, Any] = {"roomId": room_id, "message": message}
        if bot_id:
            payload["botId"] = bot_id
        return cls(type=RoomWSMessageType.ROOM_ERROR, payload=payload)

    @classmethod
    def usage(
        cls,
        room_id: str,
        bot_id: str,
        message_id: str = "",
        tokens: int = 0,
        cost: float = 0.0,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        elapsed_ms: float = 0.0,
        tokens_per_second: float = 0.0,
        model: str = "",
    ) -> "RoomWSMessage":
        """Create a usage stats message."""
        return cls(
            type=RoomWSMessageType.ROOM_USAGE,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "messageId": message_id,
                "totalTokens": tokens,
                "totalCost": cost,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "elapsedMs": elapsed_ms,
                "tokensPerSecond": tokens_per_second,
                "model": model,
            },
        )

    @classmethod
    def chain_step(
        cls,
        room_id: str,
        step: int,
        total_steps: int,
        bot_id: str,
        bot_name: str,
    ) -> "RoomWSMessage":
        """Create a chain step progress indicator."""
        return cls(
            type=RoomWSMessageType.ROOM_CHAIN_STEP,
            payload={
                "roomId": room_id,
                "step": step,
                "totalSteps": total_steps,
                "botId": bot_id,
                "botName": bot_name,
            },
        )

    @classmethod
    def route_decision(
        cls,
        room_id: str,
        bot_id: str,
        bot_name: str,
        reason: str,
    ) -> "RoomWSMessage":
        """Create a route decision message."""
        return cls(
            type=RoomWSMessageType.ROOM_ROUTE_DECISION,
            payload={
                "roomId": room_id,
                "botId": bot_id,
                "botName": bot_name,
                "reason": reason,
            },
        )

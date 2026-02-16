"""WebSocket message models."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class WSMessageType(str, Enum):
    """WebSocket message types."""

    # Client -> Server
    CHAT = "chat"
    CANCEL = "cancel"
    APPROVAL = "approval"

    # Server -> Client
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    MESSAGE = "message"
    PLATFORM_MESSAGE = "platform_message"  # For Telegram/Discord message sync
    SCHEDULED_NOTIFICATION = "scheduled_notification"  # Fired by the scheduler
    CONNECTION_STATUS = "connection_status"  # Platform connection state changes
    DOCUMENT_STATUS = "document_status"  # Document processing progress
    JOB_UPDATE = "job_update"  # Job/work execution progress
    APPROVAL_NEEDED = "approval_needed"
    USAGE = "usage"
    ERROR = "error"
    DONE = "done"


class ThinkingPayload(BaseModel):
    """Payload for thinking events."""

    content: str = Field(description="Thinking/reasoning content")


class ToolStartPayload(BaseModel):
    """Payload for tool execution start."""

    id: str = Field(description="Tool call ID")
    tool: str = Field(description="Tool name")
    args: dict[str, Any] = Field(description="Tool arguments")


class ToolEndPayload(BaseModel):
    """Payload for tool execution end."""

    id: str = Field(description="Tool call ID")
    result: Any = Field(description="Tool result")
    success: bool = Field(default=True)


class MessagePayload(BaseModel):
    """Payload for chat messages."""

    role: str = Field(description="Message role (user/assistant)")
    content: str = Field(description="Message content")
    message_id: str | None = Field(default=None)


class ApprovalPayload(BaseModel):
    """Payload for approval requests."""

    id: str = Field(description="Approval request ID")
    tool: str = Field(description="Tool requiring approval")
    action: str = Field(description="Action description")
    details: dict[str, Any] = Field(description="Additional details (e.g., code)")


class UsagePayload(BaseModel):
    """Payload for usage/cost information."""

    total_tokens: int = Field(default=0)
    prompt_tokens: int = Field(default=0)
    completion_tokens: int = Field(default=0)
    total_cost: float = Field(default=0.0)
    iterations: int = Field(default=0)
    elapsed_ms: float = Field(default=0.0)
    tokens_per_second: float = Field(default=0.0)
    call_count: int = Field(default=0)
    errors: int = Field(default=0)
    per_model: dict = Field(default_factory=dict)
    latency_stats: dict = Field(default_factory=dict)


class ErrorPayload(BaseModel):
    """Payload for error messages."""

    message: str = Field(description="Error message")
    code: str | None = Field(default=None, description="Error code")


class WSMessage(BaseModel):
    """Generic WebSocket message wrapper."""

    type: WSMessageType = Field(description="Message type")
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def thinking(cls, content: str) -> "WSMessage":
        """Create a thinking message."""
        return cls(type=WSMessageType.THINKING, payload={"content": content})

    @classmethod
    def tool_start(cls, id: str, tool: str, args: dict) -> "WSMessage":
        """Create a tool start message."""
        return cls(
            type=WSMessageType.TOOL_START,
            payload={"id": id, "tool": tool, "args": args},
        )

    @classmethod
    def tool_end(cls, id: str, result: Any, success: bool = True) -> "WSMessage":
        """Create a tool end message."""
        return cls(
            type=WSMessageType.TOOL_END,
            payload={"id": id, "result": result, "success": success},
        )

    @classmethod
    def message(
        cls,
        role: str,
        content: str,
        message_id: str | None = None,
        reply_to_id: str | None = None,
    ) -> "WSMessage":
        """Create a chat message."""
        payload: dict[str, Any] = {"role": role, "content": content, "messageId": message_id}
        if reply_to_id:
            payload["replyToId"] = reply_to_id
        return cls(type=WSMessageType.MESSAGE, payload=payload)

    @classmethod
    def approval_needed(cls, id: str, tool: str, action: str, details: dict) -> "WSMessage":
        """Create an approval request message."""
        return cls(
            type=WSMessageType.APPROVAL_NEEDED,
            payload={"id": id, "tool": tool, "action": action, "details": details},
        )

    @classmethod
    def usage(
        cls,
        tokens: int,
        cost: float,
        iterations: int,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        elapsed_ms: float = 0.0,
        tokens_per_second: float = 0.0,
        call_count: int = 0,
        errors: int = 0,
        per_model: dict | None = None,
        latency_stats: dict | None = None,
    ) -> "WSMessage":
        """Create a usage message."""
        return cls(
            type=WSMessageType.USAGE,
            payload={
                "totalTokens": tokens,
                "promptTokens": prompt_tokens,
                "completionTokens": completion_tokens,
                "totalCost": cost,
                "iterations": iterations,
                "elapsedMs": elapsed_ms,
                "tokensPerSecond": tokens_per_second,
                "callCount": call_count,
                "errors": errors,
                "perModel": per_model or {},
                "latencyStats": latency_stats or {},
            },
        )

    @classmethod
    def error(cls, message: str, code: str | None = None) -> "WSMessage":
        """Create an error message."""
        return cls(type=WSMessageType.ERROR, payload={"message": message, "code": code})

    @classmethod
    def done(cls, reply_to_id: str | None = None) -> "WSMessage":
        """Create a done message."""
        payload: dict[str, Any] = {}
        if reply_to_id:
            payload["replyToId"] = reply_to_id
        return cls(type=WSMessageType.DONE, payload=payload)

    @classmethod
    def platform_message(
        cls,
        bot_id: str,
        chat_id: str,
        role: str,
        content: str,
        message_id: str,
        platform: str,
        metadata: dict | None = None,
    ) -> "WSMessage":
        """Create a platform message notification (for Telegram/Discord sync)."""
        payload = {
            "botId": bot_id,
            "chatId": chat_id,
            "role": role,
            "content": content,
            "messageId": message_id,
            "platform": platform,
        }
        if metadata:
            payload["metadata"] = metadata
        return cls(type=WSMessageType.PLATFORM_MESSAGE, payload=payload)

    @classmethod
    def connection_status(
        cls,
        connection_id: str,
        bot_id: str,
        status: str,
        platform: str,
        error: str | None = None,
    ) -> "WSMessage":
        """Create a connection status change notification."""
        payload: dict[str, Any] = {
            "connectionId": connection_id,
            "botId": bot_id,
            "status": status,
            "platform": platform,
        }
        if error:
            payload["error"] = error
        return cls(type=WSMessageType.CONNECTION_STATUS, payload=payload)

    @classmethod
    def document_status(
        cls,
        bot_id: str,
        document_id: str,
        status: str,
        chunk_count: int | None = None,
        filename: str | None = None,
    ) -> "WSMessage":
        """Create a document processing status event."""
        payload: dict[str, Any] = {
            "botId": bot_id,
            "documentId": document_id,
            "status": status,
        }
        if chunk_count is not None:
            payload["chunkCount"] = chunk_count
        if filename:
            payload["filename"] = filename
        return cls(type=WSMessageType.DOCUMENT_STATUS, payload=payload)

    @classmethod
    def scheduled_notification(
        cls,
        bot_id: str,
        chat_id: str | None,
        content: str,
    ) -> "WSMessage":
        """Create a scheduled notification (fired by the scheduler service)."""
        payload: dict[str, Any] = {
            "botId": bot_id,
            "content": content,
        }
        if chat_id:
            payload["chatId"] = chat_id
        return cls(type=WSMessageType.SCHEDULED_NOTIFICATION, payload=payload)

    @classmethod
    def job_update(
        cls,
        work_id: str,
        task_id: str | None = None,
        job_id: str | None = None,
        status: str = "",
        progress: float = 0.0,
        error: str | None = None,
        logs: list[dict] | None = None,
    ) -> "WSMessage":
        """Create a job/work execution progress update."""
        payload: dict[str, Any] = {
            "workId": work_id,
            "status": status,
            "progress": progress,
        }
        if task_id:
            payload["taskId"] = task_id
        if job_id:
            payload["jobId"] = job_id
        if error:
            payload["error"] = error
        if logs:
            payload["logs"] = logs
        return cls(type=WSMessageType.JOB_UPDATE, payload=payload)

"""
Base Platform Adapter

Abstract base class for platform integrations.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any, ClassVar

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import PlatformResponse
from cachibot.utils.markdown import strip_markdown

# Type for message handler callback
MessageHandler = Callable[[str, str, str, dict[str, Any]], Awaitable[PlatformResponse]]
# Args: connection_id, chat_id, user_message, metadata
# Returns: PlatformResponse with text and optional media

# Type for status change callback
StatusChangeHandler = Callable[[str, str], Awaitable[None]]
# Args: connection_id, new_status ("connected", "error", "disconnected")


@dataclass
class AdapterHealth:
    """Health status for a platform adapter."""

    healthy: bool
    latency_ms: float | None = None
    details: dict[str, Any] = field(default_factory=dict)


class BasePlatformAdapter(ABC):
    """Abstract base class for platform adapters."""

    platform: ConnectionPlatform

    # Class-level metadata — subclasses should override these
    platform_name: ClassVar[str] = ""
    display_name: ClassVar[str] = ""
    required_config: ClassVar[list[str]] = []
    optional_config: ClassVar[dict[str, str]] = {}

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
        on_status_change: StatusChangeHandler | None = None,
    ):
        """Initialize the adapter.

        Args:
            connection: The connection configuration.
            on_message: Callback when a message is received.
            on_status_change: Callback when the connection status changes.
        """
        self.connection = connection
        self.on_message = on_message
        self.on_status_change = on_status_change
        self._running = False

    @property
    def connection_id(self) -> str:
        """Get the connection ID."""
        return self.connection.id

    @property
    def bot_id(self) -> str:
        """Get the bot ID."""
        return self.connection.bot_id

    async def wait_until_ready(self, timeout: float = 30.0) -> None:
        """Wait until the adapter is fully ready.

        Default implementation returns immediately if _running is True.
        Subclasses can override for platform-specific readiness checks.

        Args:
            timeout: Maximum seconds to wait.

        Raises:
            asyncio.TimeoutError: If the adapter doesn't become ready in time.
        """
        if self._running:
            return

    @abstractmethod
    async def connect(self) -> None:
        """
        Start the platform connection.

        Should initialize the client and start listening for messages.
        """
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Stop the platform connection.

        Should clean up resources and stop listening.
        """
        pass

    @abstractmethod
    async def send_message(self, chat_id: str, message: str) -> bool:
        """
        Send a message to a chat.

        Args:
            chat_id: The chat/channel ID to send to
            message: The message content

        Returns:
            True if sent successfully, False otherwise
        """
        pass

    @property
    def is_running(self) -> bool:
        """Check if the adapter is running."""
        return self._running

    @property
    def should_strip_markdown(self) -> bool:
        """Check if markdown should be stripped for this connection."""
        return self.connection.config.get("strip_markdown", "false").lower() == "true"

    def format_outgoing_message(self, message: str) -> str:
        """
        Format a message for sending to the platform.

        Strips markdown if the connection has strip_markdown enabled.

        Args:
            message: The original message content

        Returns:
            Formatted message ready for the platform
        """
        if self.should_strip_markdown:
            return strip_markdown(message)
        return message

    @property
    def max_message_length(self) -> int:
        """Maximum message length for this platform. Subclasses should override."""
        return 4096

    def chunk_message(self, text: str) -> list[str]:
        """Split text into chunks that fit within the platform's message length limit.

        Splits on paragraph boundaries first, then sentence boundaries, then hard-wraps.

        Args:
            text: The text to split.

        Returns:
            List of text chunks, each within max_message_length.
        """
        limit = self.max_message_length
        if len(text) <= limit:
            return [text]

        chunks: list[str] = []
        remaining = text

        while remaining:
            if len(remaining) <= limit:
                chunks.append(remaining)
                break

            # Try to split on a double newline (paragraph boundary)
            split_pos = remaining.rfind("\n\n", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 2 :]
                continue

            # Try to split on a single newline
            split_pos = remaining.rfind("\n", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 1 :]
                continue

            # Try to split on a sentence boundary (". ")
            split_pos = remaining.rfind(". ", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[: split_pos + 1])
                remaining = remaining[split_pos + 2 :]
                continue

            # Try to split on a space
            split_pos = remaining.rfind(" ", 0, limit)
            if split_pos > 0:
                chunks.append(remaining[:split_pos])
                remaining = remaining[split_pos + 1 :]
                continue

            # Hard wrap as last resort
            chunks.append(remaining[:limit])
            remaining = remaining[limit:]

        return chunks

    async def send_response(self, chat_id: str, response: PlatformResponse) -> bool:
        """Send a PlatformResponse (text + media) to a chat.

        Default implementation sends text via send_message with chunking.
        Subclasses can override for platform-specific media handling.

        Args:
            chat_id: The chat/channel ID to send to.
            response: The response with text and optional media.

        Returns:
            True if all parts sent successfully.
        """
        success = True

        if response.text:
            formatted = self.format_outgoing_message(response.text)
            for chunk in self.chunk_message(formatted):
                if not await self.send_message(chat_id, chunk):
                    success = False

        return success

    async def health_check(self) -> AdapterHealth:
        """Check the health of this adapter.

        Default implementation returns health based on _running state.
        Subclasses can override for platform-specific health checks.
        """
        return AdapterHealth(healthy=self._running, details={"running": self._running})

    async def send_typing(self, chat_id: str) -> None:
        """Send a typing indicator to a chat. Default is a no-op.

        Subclasses can override to send platform-specific typing indicators.

        Args:
            chat_id: The chat/channel ID.
        """
        pass

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate platform-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        for key in cls.required_config:
            if key not in config or not config[key]:
                display = cls.display_name or cls.platform_name or "Platform"
                errors.append(f"{display} {key} is required")
        return errors

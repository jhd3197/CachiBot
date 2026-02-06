"""
Base Platform Adapter

Abstract base class for platform integrations.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.utils.markdown import strip_markdown

# Type for message handler callback
MessageHandler = Callable[[str, str, str, dict], Awaitable[str]]
# Args: connection_id, chat_id, user_message, metadata
# Returns: bot response


class BasePlatformAdapter(ABC):
    """Abstract base class for platform adapters."""

    platform: ConnectionPlatform

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
    ):
        """
        Initialize the adapter.

        Args:
            connection: The connection configuration
            on_message: Callback when a message is received
        """
        self.connection = connection
        self.on_message = on_message
        self._running = False

    @property
    def connection_id(self) -> str:
        """Get the connection ID."""
        return self.connection.id

    @property
    def bot_id(self) -> str:
        """Get the bot ID."""
        return self.connection.bot_id

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

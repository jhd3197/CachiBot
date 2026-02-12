"""
Platform Manager Service

Manages platform adapter lifecycle and message routing.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cachibot.models.connection import BotConnection, ConnectionPlatform, ConnectionStatus
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler
from cachibot.services.adapters.discord import DiscordAdapter
from cachibot.services.adapters.telegram import TelegramAdapter
from cachibot.services.command_processor import get_command_processor
from cachibot.storage.repository import ConnectionRepository

logger = logging.getLogger(__name__)


# Type for bot message processor
BotMessageProcessor = Callable[[str, str, str, dict], Awaitable[str]]
# Args: bot_id, chat_id, message, metadata
# Returns: bot response


class PlatformManager:
    """
    Manages platform adapters for all bot connections.

    This is a singleton that orchestrates adapter lifecycle
    and routes messages to the appropriate bots.
    """

    def __init__(self):
        self._adapters: dict[str, BasePlatformAdapter] = {}
        self._repo = ConnectionRepository()
        self._message_processor: BotMessageProcessor | None = None
        self._lock = asyncio.Lock()

    def set_message_processor(self, processor: BotMessageProcessor) -> None:
        """Set the callback for processing incoming messages."""
        self._message_processor = processor

    async def _handle_message(
        self,
        connection_id: str,
        chat_id: str,
        message: str,
        metadata: dict,
    ) -> str:
        """Handle an incoming message from any platform."""
        # Get connection to find bot_id
        connection = await self._repo.get_connection(connection_id)
        if not connection:
            return "Connection not found."

        # Extract user_id from metadata (platform-specific)
        user_id = metadata.get("user_id") or metadata.get("username") or chat_id

        # Check if this is a command or continuing a flow
        processor = get_command_processor()
        platform = metadata.get("platform", "unknown")

        if processor.is_command(message) or processor.has_active_flow(user_id, chat_id):
            try:
                result = await processor.process(
                    text=message,
                    platform=platform,
                    user_id=user_id,
                    chat_id=chat_id,
                    metadata=metadata,
                )
                return result.response
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                return "Sorry, I encountered an error processing that command."

        # Normal message processing
        if not self._message_processor:
            return "Bot is not configured to respond."

        # Increment message count
        await self._repo.increment_message_count(connection_id)

        # Process the message through the bot
        try:
            response = await self._message_processor(
                connection.bot_id,
                chat_id,
                message,
                metadata,
            )
            return response
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "Sorry, I encountered an error."

    def _create_adapter(self, connection: BotConnection) -> BasePlatformAdapter:
        """Create an adapter for the given connection."""
        handler: MessageHandler = self._handle_message

        if connection.platform == ConnectionPlatform.telegram:
            return TelegramAdapter(connection, on_message=handler)
        elif connection.platform == ConnectionPlatform.discord:
            return DiscordAdapter(connection, on_message=handler)
        else:
            raise ValueError(f"Unknown platform: {connection.platform}")

    async def connect(self, connection_id: str) -> None:
        """
        Start a platform connection.

        Args:
            connection_id: The connection ID to start
        """
        async with self._lock:
            # Check if already connected
            if connection_id in self._adapters:
                if self._adapters[connection_id].is_running:
                    return
                # Clean up old adapter
                del self._adapters[connection_id]

            # Get connection from database
            connection = await self._repo.get_connection(connection_id)
            if not connection:
                raise ValueError(f"Connection not found: {connection_id}")

            # Update status to connecting
            await self._repo.update_connection_status(connection_id, ConnectionStatus.connecting)

            try:
                # Create and start adapter
                adapter = self._create_adapter(connection)
                await adapter.connect()

                # Store adapter
                self._adapters[connection_id] = adapter

                # Update status to connected
                await self._repo.update_connection_status(connection_id, ConnectionStatus.connected)

                logger.info(f"Connected {connection.platform.value} adapter: {connection_id}")

            except Exception as e:
                # Update status to error
                await self._repo.update_connection_status(
                    connection_id, ConnectionStatus.error, str(e)
                )
                raise

    async def disconnect(self, connection_id: str) -> None:
        """
        Stop a platform connection.

        Args:
            connection_id: The connection ID to stop
        """
        async with self._lock:
            adapter = self._adapters.get(connection_id)
            if adapter:
                await adapter.disconnect()
                del self._adapters[connection_id]

            # Update status to disconnected
            await self._repo.update_connection_status(connection_id, ConnectionStatus.disconnected)

            logger.info(f"Disconnected adapter: {connection_id}")

    async def send_message(
        self,
        connection_id: str,
        chat_id: str,
        message: str,
    ) -> bool:
        """
        Send a message through a connection.

        Args:
            connection_id: The connection to send through
            chat_id: The chat/channel ID to send to
            message: The message content

        Returns:
            True if sent successfully
        """
        adapter = self._adapters.get(connection_id)
        if not adapter or not adapter.is_running:
            return False

        return await adapter.send_message(chat_id, message)

    async def send_to_bot_connection(
        self,
        bot_id: str,
        platform: ConnectionPlatform,
        chat_id: str,
        message: str,
    ) -> bool:
        """
        Send a message to a bot's connected platform.

        Args:
            bot_id: The bot ID
            platform: The platform to send to
            chat_id: The chat/channel ID
            message: The message content

        Returns:
            True if sent successfully
        """
        # Find connection for this bot and platform
        connections = await self._repo.get_connections_by_bot(bot_id)
        for conn in connections:
            if conn.platform == platform and conn.status == ConnectionStatus.connected:
                return await self.send_message(conn.id, chat_id, message)
        return False

    async def reconnect_all(self) -> None:
        """Reconnect all connections that should be connected."""
        connections = await self._repo.get_all_connected()
        for conn in connections:
            try:
                await self.connect(conn.id)
            except Exception as e:
                logger.error(f"Failed to reconnect {conn.id}: {e}")

    async def disconnect_all(self) -> None:
        """Disconnect all active connections."""
        async with self._lock:
            for connection_id, adapter in list(self._adapters.items()):
                try:
                    await adapter.disconnect()
                except Exception as e:
                    logger.error(f"Error disconnecting {connection_id}: {e}")

            self._adapters.clear()

    def get_adapter(self, connection_id: str) -> BasePlatformAdapter | None:
        """Get an adapter by connection ID."""
        return self._adapters.get(connection_id)

    def is_connected(self, connection_id: str) -> bool:
        """Check if a connection is active."""
        adapter = self._adapters.get(connection_id)
        return adapter is not None and adapter.is_running


# Singleton instance
_platform_manager: PlatformManager | None = None


def get_platform_manager() -> PlatformManager:
    """Get the singleton platform manager instance."""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager

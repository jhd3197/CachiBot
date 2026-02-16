"""
Platform Manager Service

Manages platform adapter lifecycle and message routing.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable

from cachibot.models.connection import BotConnection, ConnectionPlatform, ConnectionStatus
from cachibot.models.platform import PlatformResponse
from cachibot.models.websocket import WSMessage
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler
from cachibot.services.adapters.registry import AdapterRegistry
from cachibot.services.command_processor import get_command_processor
from cachibot.storage.repository import ConnectionRepository

logger = logging.getLogger(__name__)


# Type for bot message processor
BotMessageProcessor = Callable[[str, str, str, dict], Awaitable[PlatformResponse]]
# Args: bot_id, chat_id, message, metadata
# Returns: PlatformResponse with text and optional media


class PlatformManager:
    """Manages platform adapters for all bot connections.

    This is a singleton that orchestrates adapter lifecycle
    and routes messages to the appropriate bots.
    """

    def __init__(self):
        self._adapters: dict[str, BasePlatformAdapter] = {}
        self._repo = ConnectionRepository()
        self._message_processor: BotMessageProcessor | None = None
        self._locks: dict[str, asyncio.Lock] = {}
        self._locks_lock = asyncio.Lock()
        self._health_task: asyncio.Task | None = None

    def set_message_processor(self, processor: BotMessageProcessor) -> None:
        """Set the callback for processing incoming messages."""
        self._message_processor = processor

    async def _get_lock(self, connection_id: str) -> asyncio.Lock:
        """Get or create a per-connection lock."""
        async with self._locks_lock:
            if connection_id not in self._locks:
                self._locks[connection_id] = asyncio.Lock()
            return self._locks[connection_id]

    def _broadcast_status(self, connection_id: str, status: str, error: str | None = None) -> None:
        """Broadcast a connection status change to WebSocket clients."""
        try:
            from cachibot.api.websocket import get_ws_manager

            adapter = self._adapters.get(connection_id)
            connection = None
            if adapter:
                connection = adapter.connection

            ws_manager = get_ws_manager()
            msg = WSMessage.connection_status(
                connection_id=connection_id,
                bot_id=connection.bot_id if connection else "",
                status=status,
                platform=connection.platform.value if connection else "",
                error=error,
            )
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws_manager.broadcast(msg))
            except RuntimeError:
                pass
        except Exception as e:
            logger.warning(f"Failed to broadcast connection status: {e}")

    async def _handle_status_change(self, connection_id: str, status: str) -> None:
        """Handle adapter status changes (from reconnection logic)."""
        try:
            status_enum = ConnectionStatus(status)
            await self._repo.update_connection_status(connection_id, status_enum)
            self._broadcast_status(connection_id, status)
            logger.info(f"Connection {connection_id} status changed to {status}")
        except Exception as e:
            logger.error(f"Error handling status change for {connection_id}: {e}")

    async def _handle_message(
        self,
        connection_id: str,
        chat_id: str,
        message: str,
        metadata: dict,
    ) -> PlatformResponse:
        """Handle an incoming message from any platform."""
        # Get connection to find bot_id
        connection = await self._repo.get_connection(connection_id)
        if not connection:
            return PlatformResponse(text="Connection not found.")

        # Add connection_id to metadata for downstream use
        metadata["connection_id"] = connection_id

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
                return PlatformResponse(text=result.response)
            except Exception as e:
                logger.error(f"Error processing command: {e}")
                return PlatformResponse(
                    text="Sorry, I encountered an error processing that command."
                )

        # Normal message processing
        if not self._message_processor:
            return PlatformResponse(text="Bot is not configured to respond.")

        # Increment message count
        await self._repo.increment_message_count(connection_id)

        # Process the message through the bot
        try:
            return await self._message_processor(
                connection.bot_id,
                chat_id,
                message,
                metadata,
            )
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return PlatformResponse(text="Sorry, I encountered an error.")

    def _create_adapter(self, connection: BotConnection) -> BasePlatformAdapter:
        """Create an adapter for the given connection via the registry."""
        handler: MessageHandler = self._handle_message
        return AdapterRegistry.create(
            connection, on_message=handler, on_status_change=self._handle_status_change
        )

    async def connect(self, connection_id: str) -> None:
        """Start a platform connection.

        Args:
            connection_id: The connection ID to start.
        """
        lock = await self._get_lock(connection_id)
        async with lock:
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
            self._broadcast_status(connection_id, "connecting")

            try:
                # Create and start adapter
                adapter = self._create_adapter(connection)
                await adapter.connect()

                # Wait for the adapter to be fully ready (e.g. Discord on_ready)
                try:
                    await adapter.wait_until_ready(30.0)
                except asyncio.TimeoutError:
                    await adapter.disconnect()
                    await self._repo.update_connection_status(
                        connection_id,
                        ConnectionStatus.error,
                        "Timed out waiting for platform to become ready",
                    )
                    raise RuntimeError("Adapter did not become ready within 30 seconds")

                # Store adapter
                self._adapters[connection_id] = adapter

                # Update status to connected
                await self._repo.update_connection_status(connection_id, ConnectionStatus.connected)
                self._broadcast_status(connection_id, "connected")

                # Mark for auto-reconnect on next server restart
                await self._repo.set_auto_connect(connection_id, True)

                logger.info(f"Connected {connection.platform.value} adapter: {connection_id}")

            except Exception as e:
                # Update status to error
                await self._repo.update_connection_status(
                    connection_id, ConnectionStatus.error, str(e)
                )
                self._broadcast_status(connection_id, "error", str(e))
                raise

    async def disconnect(self, connection_id: str) -> None:
        """Stop a platform connection.

        Args:
            connection_id: The connection ID to stop.
        """
        lock = await self._get_lock(connection_id)
        async with lock:
            adapter = self._adapters.get(connection_id)
            if adapter:
                try:
                    await asyncio.wait_for(adapter.disconnect(), timeout=15.0)
                except asyncio.TimeoutError:
                    logger.warning(f"Adapter disconnect timed out for {connection_id}")
                del self._adapters[connection_id]

            # Update status to disconnected
            await self._repo.update_connection_status(connection_id, ConnectionStatus.disconnected)
            self._broadcast_status(connection_id, "disconnected")

            # Clear auto-reconnect (user-initiated disconnect)
            await self._repo.set_auto_connect(connection_id, False)

            logger.info(f"Disconnected adapter: {connection_id}")

        # Clean up the lock
        async with self._locks_lock:
            self._locks.pop(connection_id, None)

    async def send_message(
        self,
        connection_id: str,
        chat_id: str,
        message: str,
    ) -> bool:
        """Send a message through a connection.

        Args:
            connection_id: The connection to send through.
            chat_id: The chat/channel ID to send to.
            message: The message content.

        Returns:
            True if sent successfully.
        """
        adapter = self._adapters.get(connection_id)
        if not adapter or not adapter.is_running:
            return False

        return await adapter.send_message(chat_id, message)

    async def send_to_bot_connection(
        self,
        bot_id: str,
        platform: ConnectionPlatform | str,
        chat_id: str,
        message: str,
    ) -> bool:
        """Send a message to a bot's connected platform.

        Args:
            bot_id: The bot ID.
            platform: The platform to send to (ConnectionPlatform enum or string name).
            chat_id: The chat/channel ID.
            message: The message content.

        Returns:
            True if sent successfully.
        """
        # Normalize platform to string for comparison
        platform_value = platform.value if isinstance(platform, ConnectionPlatform) else platform

        # Find connection for this bot and platform
        connections = await self._repo.get_connections_by_bot(bot_id)
        for conn in connections:
            if conn.platform.value == platform_value and conn.status == ConnectionStatus.connected:
                return await self.send_message(conn.id, chat_id, message)
        return False

    async def reset_all_statuses(self) -> None:
        """Reset all connection statuses to disconnected.

        Called on server startup -- after a restart no adapters are actually
        running, so the DB should reflect that instead of showing stale
        'connected' status.
        """
        count = await self._repo.bulk_reset_connected()
        if count:
            logger.info(f"Reset {count} stale connection(s) to disconnected.")

    async def auto_reconnect_all(self) -> None:
        """Reconnect all connections marked for auto-connect.

        Called on server startup after reset_all_statuses().
        """
        connections = await self._repo.get_auto_connect_connections()
        if not connections:
            return

        logger.info(f"Auto-reconnecting {len(connections)} connection(s)...")
        for conn in connections:
            try:
                await self.connect(conn.id)
            except Exception as e:
                logger.error(f"Auto-reconnect failed for {conn.id}: {e}")

    async def disconnect_all(self) -> None:
        """Disconnect all active connections."""
        adapters = list(self._adapters.items())

        async def _disconnect_one(cid: str, adapter: BasePlatformAdapter) -> None:
            try:
                await adapter.disconnect()
            except Exception as e:
                logger.error(f"Error disconnecting {cid}: {e}")

        await asyncio.gather(*[_disconnect_one(cid, a) for cid, a in adapters])
        self._adapters.clear()
        self._locks.clear()

    def get_adapter(self, connection_id: str) -> BasePlatformAdapter | None:
        """Get an adapter by connection ID."""
        return self._adapters.get(connection_id)

    def is_connected(self, connection_id: str) -> bool:
        """Check if a connection is active."""
        adapter = self._adapters.get(connection_id)
        return adapter is not None and adapter.is_running

    # ===== Health Monitoring =====

    async def start_health_monitor(self, interval: float = 60.0) -> None:
        """Start periodic health checks for active adapters."""
        self._health_task = asyncio.create_task(self._health_loop(interval))

    async def _health_loop(self, interval: float) -> None:
        """Periodically check adapter health."""
        failures: dict[str, int] = {}  # connection_id -> consecutive failure count
        while True:
            try:
                await asyncio.sleep(interval)
                for connection_id, adapter in list(self._adapters.items()):
                    try:
                        health = await adapter.health_check()
                        if health.healthy:
                            failures.pop(connection_id, None)
                        else:
                            failures[connection_id] = failures.get(connection_id, 0) + 1
                            if failures[connection_id] >= 3:
                                logger.warning(
                                    f"Connection {connection_id} failed "
                                    f"{failures[connection_id]} consecutive "
                                    f"health checks, marking as error"
                                )
                                await self._repo.update_connection_status(
                                    connection_id,
                                    ConnectionStatus.error,
                                    "Health check failed",
                                )
                                self._broadcast_status(
                                    connection_id, "error", "Health check failed"
                                )
                                failures.pop(connection_id, None)
                    except Exception as e:
                        logger.debug(f"Health check error for {connection_id}: {e}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def stop_health_monitor(self) -> None:
        """Stop the health monitor."""
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
            self._health_task = None


# Singleton instance
_platform_manager: PlatformManager | None = None


def get_platform_manager() -> PlatformManager:
    """Get the singleton platform manager instance."""
    global _platform_manager
    if _platform_manager is None:
        _platform_manager = PlatformManager()
    return _platform_manager

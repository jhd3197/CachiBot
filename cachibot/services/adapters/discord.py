"""
Discord Platform Adapter

Uses discord.py library for Discord Bot integration.
"""

import asyncio
import io
import logging
from typing import Any, ClassVar

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import IncomingMedia, PlatformResponse
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler, StatusChangeHandler
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


@AdapterRegistry.register("discord")
class DiscordAdapter(BasePlatformAdapter):
    """Discord bot adapter using discord.py."""

    platform = ConnectionPlatform.discord
    platform_name: ClassVar[str] = "discord"
    display_name: ClassVar[str] = "Discord"
    required_config: ClassVar[list[str]] = ["token"]
    optional_config: ClassVar[dict[str, str]] = {"strip_markdown": "Strip markdown from responses"}

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
        on_status_change: StatusChangeHandler | None = None,
    ):
        super().__init__(connection, on_message, on_status_change)
        self._client: Any = None
        self._client_task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._intentional_disconnect = False

    @property
    def max_message_length(self) -> int:
        return 2000

    async def wait_until_ready(self, timeout: float = 30.0) -> None:
        """Wait until the Discord client fires on_ready."""
        await asyncio.wait_for(self._ready.wait(), timeout=timeout)

    def _setup_events(self) -> None:
        """Register Discord event handlers on the current client."""
        adapter = self

        @self._client.event  # type: ignore[untyped-decorator]
        async def on_ready() -> None:
            """Called when the bot is ready."""
            adapter._running = True
            adapter._ready.set()
            logger.info(
                f"Discord bot connected as {adapter._client.user} "
                f"for connection {adapter.connection_id}"
            )

        @self._client.event  # type: ignore[untyped-decorator]
        async def on_message(message: Any) -> None:
            """Handle incoming messages."""
            # Guard against NoneType client/user during startup or shutdown
            if not adapter._client or not adapter._client.user:
                return

            # Ignore messages from the bot itself
            if message.author == adapter._client.user:
                return

            # Only respond to mentions or DMs
            is_dm = message.guild is None
            is_mention = adapter._client.user in message.mentions if message.mentions else False

            if not (is_dm or is_mention):
                return

            if not adapter.on_message:
                return

            try:
                # Clean the message (remove mention)
                content = message.content
                if is_mention:
                    content = content.replace(f"<@{adapter._client.user.id}>", "").strip()
                    content = content.replace(f"<@!{adapter._client.user.id}>", "").strip()

                # Download attached media
                attachments: list[IncomingMedia] = []
                for att in message.attachments:
                    try:
                        data = await att.read()
                        mime = att.content_type or "application/octet-stream"
                        attachments.append(IncomingMedia(mime, data, att.filename))
                    except Exception as e:
                        logger.warning(f"Failed to download Discord attachment: {e}")

                # Skip if no text and no attachments
                if not content and not attachments:
                    return

                # Get channel info
                channel_id = str(message.channel.id)
                metadata: dict[str, Any] = {
                    "platform": "discord",
                    "channel_id": channel_id,
                    "guild_id": (str(message.guild.id) if message.guild else None),
                    "guild_name": (message.guild.name if message.guild else None),
                    "channel_name": getattr(message.channel, "name", "DM"),
                    "user_id": str(message.author.id),
                    "username": message.author.name,
                    "is_dm": is_dm,
                }

                # Pass media attachments in metadata
                if attachments:
                    metadata["attachments"] = attachments

                # Capture reply context
                if message.reference and message.reference.resolved:
                    ref_msg = message.reference.resolved
                    if hasattr(ref_msg, "content"):
                        metadata["reply_to_platform_msg_id"] = str(ref_msg.id)
                        metadata["reply_to_text"] = ref_msg.content or ""

                # Call the message handler to get bot response
                response = await adapter.on_message(
                    adapter.connection_id,
                    channel_id,
                    content,
                    metadata,
                )

                # Send response back with media support
                if response.text or response.media:
                    await adapter._send_platform_response(message.channel, response)

            except Exception as e:
                logger.error(f"Error handling Discord message: {e}")
                await message.channel.send("Sorry, I encountered an error processing your message.")

    async def connect(self) -> None:
        """Start the Discord bot."""
        if self._running:
            return

        try:
            import discord
            from discord import Intents

            token = self.connection.config.get("token")
            if not token:
                raise ValueError("Discord bot token is required")

            # Set up intents
            intents = Intents.default()
            intents.message_content = True
            intents.guilds = True

            # Create client and register event handlers
            self._client = discord.Client(intents=intents)
            self._ready.clear()
            self._intentional_disconnect = False
            self._setup_events()

            # Start the client in background — _running is set in on_ready
            self._client_task = asyncio.create_task(self._run_client(token))
            logger.info(f"Discord adapter starting for connection {self.connection_id}")

        except ImportError:
            raise RuntimeError("discord.py is not installed. Run: pip install discord.py")
        except Exception as e:
            self._running = False
            raise RuntimeError(f"Failed to start Discord bot: {e}")

    async def _run_client(self, token: str) -> None:
        """Run the Discord client with automatic reconnection."""
        import discord
        from discord import Intents

        max_retries = 5
        base_delay = 5.0
        max_delay = 120.0

        for attempt in range(max_retries + 1):
            try:
                await self._client.start(token)
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.error(f"Discord client error (attempt {attempt + 1}): {e}")
            finally:
                self._running = False
                self._ready.clear()

            # Don't retry if intentionally disconnected
            if self._intentional_disconnect:
                return

            if attempt >= max_retries:
                logger.error(
                    f"Discord adapter exhausted {max_retries} retries for {self.connection_id}"
                )
                if self.on_status_change:
                    await self.on_status_change(self.connection_id, "error")
                return

            # Exponential backoff
            delay = min(base_delay * (2**attempt), max_delay)
            logger.info(f"Discord reconnecting in {delay}s (attempt {attempt + 1}/{max_retries})")
            await asyncio.sleep(delay)

            # Recreate client and re-register handlers
            try:
                intents = Intents.default()
                intents.message_content = True
                intents.guilds = True
                self._client = discord.Client(intents=intents)
                self._ready.clear()
                self._setup_events()
            except Exception as e:
                logger.error(f"Failed to recreate Discord client: {e}")
                continue

        # If we get here after successful reconnect, notify
        if self._running and self.on_status_change:
            await self.on_status_change(self.connection_id, "connected")

    async def disconnect(self) -> None:
        """Stop the Discord bot."""
        if not self._running and not self._client_task:
            return

        self._intentional_disconnect = True
        self._running = False
        self._ready.clear()

        # Close the client with timeout
        if self._client:
            try:
                await asyncio.wait_for(self._client.close(), timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning(f"Discord client.close() timed out for {self.connection_id}")

        # Cancel the client task
        if self._client_task and not self._client_task.done():
            self._client_task.cancel()
            try:
                await self._client_task
            except asyncio.CancelledError:
                pass

        self._client = None
        self._client_task = None
        logger.info(f"Discord adapter stopped for connection {self.connection_id}")

    async def _send_platform_response(self, channel: Any, response: PlatformResponse) -> None:
        """Send a PlatformResponse with media and text to a Discord channel."""
        import discord

        # Send each media item as a Discord file attachment
        for item in response.media:
            try:
                file = discord.File(io.BytesIO(item.data), filename=item.filename)
                caption = item.metadata_text or item.alt_text or None
                # Chunk captions too if they exceed limit
                if caption and len(caption) > self.max_message_length:
                    chunks = self.chunk_message(caption)
                    await channel.send(content=chunks[0], file=file)
                    for chunk in chunks[1:]:
                        await channel.send(chunk)
                else:
                    await channel.send(content=caption, file=file)
            except Exception as e:
                logger.error(f"Failed to send Discord media ({item.media_type}): {e}")

        # Send text portion with chunking for the 2000-char limit
        if response.text:
            formatted = self.format_outgoing_message(response.text)
            if formatted:
                for chunk in self.chunk_message(formatted):
                    await channel.send(chunk)

    async def send_message(self, channel_id: str, message: str) -> bool:
        """Send a message to a Discord channel."""
        if not self._client or not self._running:
            return False

        try:
            channel = self._client.get_channel(int(channel_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(channel_id))

            if channel:
                # Strip markdown if configured for this connection
                formatted_message = self.format_outgoing_message(message)
                for chunk in self.chunk_message(formatted_message):
                    await channel.send(chunk)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """Send a typing indicator to a Discord channel."""
        if not self._client or not self._running:
            return
        try:
            channel = self._client.get_channel(int(chat_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(chat_id))
            if channel:
                await channel.typing()
        except Exception as e:
            logger.debug(f"Failed to send typing indicator: {e}")

    async def send_and_get_id(self, chat_id: str, message: str) -> str | None:
        """Send a message and return its Discord message ID."""
        if not self._client or not self._running:
            return None
        try:
            channel = self._client.get_channel(int(chat_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(chat_id))
            if channel:
                formatted = self.format_outgoing_message(message)
                msg = await channel.send(formatted)
                return str(msg.id)
            return None
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return None

    async def edit_message(self, chat_id: str, message_id: str, text: str) -> bool:
        """Edit a Discord message in place."""
        if not self._client or not self._running:
            return False
        try:
            channel = self._client.get_channel(int(chat_id))
            if channel is None:
                channel = await self._client.fetch_channel(int(chat_id))
            if channel:
                formatted = self.format_outgoing_message(text)
                # Discord limit is 2000 chars
                if len(formatted) > 2000:
                    formatted = formatted[:1997] + "..."
                msg = await channel.fetch_message(int(message_id))
                await msg.edit(content=formatted)
                return True
            return False
        except Exception as e:
            logger.debug(f"Failed to edit Discord message: {e}")
            return False

"""
Discord Platform Adapter

Uses discord.py library for Discord Bot integration.
"""

import asyncio
import io
import logging
from typing import Any

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import IncomingMedia, PlatformResponse
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler

logger = logging.getLogger(__name__)


class DiscordAdapter(BasePlatformAdapter):
    """Discord bot adapter using discord.py."""

    platform = ConnectionPlatform.discord

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
    ):
        super().__init__(connection, on_message)
        self._client: Any = None
        self._client_task: asyncio.Task | None = None

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

            # Create client
            self._client = discord.Client(intents=intents)
            adapter = self  # Capture self for closures

            @self._client.event
            async def on_ready() -> None:
                """Called when the bot is ready."""
                logger.info(
                    f"Discord bot connected as {self._client.user} "
                    f"for connection {adapter.connection_id}"
                )

            @self._client.event
            async def on_message(message: discord.Message) -> None:
                """Handle incoming messages."""
                # Ignore messages from the bot itself
                if message.author == self._client.user:
                    return

                # Only respond to mentions or DMs
                is_dm = message.guild is None
                is_mention = self._client.user in message.mentions if message.mentions else False

                if not (is_dm or is_mention):
                    return

                if not adapter.on_message:
                    return

                try:
                    # Clean the message (remove mention)
                    content = message.content
                    if is_mention:
                        content = content.replace(f"<@{self._client.user.id}>", "").strip()
                        content = content.replace(f"<@!{self._client.user.id}>", "").strip()

                    # Download attached media
                    attachments: list[IncomingMedia] = []
                    for att in message.attachments:
                        try:
                            data = await att.read()
                            mime = att.content_type or "application/octet-stream"
                            attachments.append(
                                IncomingMedia(mime, data, att.filename)
                            )
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
                        "guild_id": str(message.guild.id) if message.guild else None,
                        "guild_name": message.guild.name if message.guild else None,
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
                    await message.channel.send(
                        "Sorry, I encountered an error processing your message."
                    )

            # Start the client in background
            self._running = True
            self._client_task = asyncio.create_task(self._run_client(token))
            logger.info(f"Discord adapter starting for connection {self.connection_id}")

        except ImportError:
            raise RuntimeError("discord.py is not installed. Run: pip install discord.py")
        except Exception as e:
            self._running = False
            raise RuntimeError(f"Failed to start Discord bot: {e}")

    async def _run_client(self, token: str) -> None:
        """Run the Discord client."""
        try:
            await self._client.start(token)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Discord client error: {e}")
        finally:
            self._running = False

    async def disconnect(self) -> None:
        """Stop the Discord bot."""
        if not self._running:
            return

        self._running = False

        # Close the client
        if self._client:
            await self._client.close()

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
                await channel.send(content=caption, file=file)
            except Exception as e:
                logger.error(f"Failed to send Discord media ({item.media_type}): {e}")

        # Send text portion
        if response.text:
            formatted = self.format_outgoing_message(response.text)
            if formatted:
                await channel.send(formatted)

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
                await channel.send(formatted_message)
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to send Discord message: {e}")
            return False

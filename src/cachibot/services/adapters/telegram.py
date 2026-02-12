"""
Telegram Platform Adapter

Uses aiogram library for Telegram Bot API integration.
"""

import asyncio
import io
import logging
from typing import Any

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import IncomingMedia, PlatformResponse
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler

logger = logging.getLogger(__name__)


async def _download_file(bot: Any, file_id: str) -> bytes:
    """Download a file from Telegram by file_id and return raw bytes."""
    file = await bot.get_file(file_id)
    buf = io.BytesIO()
    await bot.download_file(file.file_path, buf)
    return buf.getvalue()


class TelegramAdapter(BasePlatformAdapter):
    """Telegram bot adapter using aiogram."""

    platform = ConnectionPlatform.telegram

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
    ):
        super().__init__(connection, on_message)
        self._bot: Any = None
        self._dispatcher: Any = None
        self._polling_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Start the Telegram bot with polling."""
        if self._running:
            return

        try:
            from aiogram import Bot, Dispatcher
            from aiogram.types import Message

            token = self.connection.config.get("token")
            if not token:
                raise ValueError("Telegram bot token is required")

            # Create bot and dispatcher
            self._bot = Bot(token=token)
            self._dispatcher = Dispatcher()

            # Register a single message handler for all messages (including commands)
            # Commands are now handled by the CommandProcessor in PlatformManager
            @self._dispatcher.message()
            async def handle_message(message: Message) -> None:
                """Handle all incoming messages including commands."""
                if not self.on_message:
                    return

                try:
                    # Extract text from message or caption
                    text = message.text or message.caption or ""

                    # Download attached media
                    attachments: list[IncomingMedia] = []

                    if message.photo:
                        # Largest photo is the last in the list
                        photo = message.photo[-1]
                        data = await _download_file(self._bot, photo.file_id)
                        attachments.append(
                            IncomingMedia("image/jpeg", data, "photo.jpg")
                        )

                    if message.voice:
                        data = await _download_file(self._bot, message.voice.file_id)
                        attachments.append(
                            IncomingMedia("audio/ogg", data, "voice.ogg")
                        )

                    if message.audio:
                        data = await _download_file(self._bot, message.audio.file_id)
                        mime = message.audio.mime_type or "audio/mpeg"
                        fname = message.audio.file_name or "audio.mp3"
                        attachments.append(IncomingMedia(mime, data, fname))

                    if message.document:
                        data = await _download_file(self._bot, message.document.file_id)
                        mime = message.document.mime_type or "application/octet-stream"
                        fname = message.document.file_name or "document"
                        attachments.append(IncomingMedia(mime, data, fname))

                    if message.video:
                        data = await _download_file(self._bot, message.video.file_id)
                        mime = message.video.mime_type or "video/mp4"
                        fname = message.video.file_name or "video.mp4"
                        attachments.append(IncomingMedia(mime, data, fname))

                    if message.sticker and not message.sticker.is_animated:
                        data = await _download_file(self._bot, message.sticker.file_id)
                        attachments.append(
                            IncomingMedia("image/webp", data, "sticker.webp")
                        )

                    # Skip if no text and no media
                    if not text and not attachments:
                        return

                    # Get chat info
                    chat_id = str(message.chat.id)
                    user = message.from_user
                    metadata: dict[str, Any] = {
                        "platform": "telegram",
                        "chat_id": chat_id,
                        "chat_type": message.chat.type,
                        "user_id": str(user.id) if user else None,
                        "username": user.username if user else None,
                        "first_name": user.first_name if user else None,
                    }

                    # Pass media attachments in metadata
                    if attachments:
                        metadata["attachments"] = attachments

                    # Capture reply context
                    if message.reply_to_message:
                        reply = message.reply_to_message
                        metadata["reply_to_platform_msg_id"] = str(reply.message_id)
                        metadata["reply_to_text"] = (
                            reply.text or reply.caption or ""
                        )

                    # Call the message handler to get bot response
                    # Commands are intercepted by PlatformManager's CommandProcessor
                    response = await self.on_message(
                        self.connection_id,
                        chat_id,
                        text,
                        metadata,
                    )

                    # Send response back with media support
                    if response.text or response.media:
                        await self._send_platform_response(message.chat.id, response)

                except Exception as e:
                    logger.error(f"Error handling Telegram message: {e}")
                    await message.answer("Sorry, I encountered an error processing your message.")

            # Delete any pending webhook (in case it was set by another instance)
            await self._bot.delete_webhook(drop_pending_updates=True)

            # Start polling in background
            self._running = True
            self._polling_task = asyncio.create_task(self._run_polling())
            logger.info(f"Telegram adapter started for connection {self.connection_id}")

        except ImportError:
            raise RuntimeError("aiogram is not installed. Run: pip install aiogram")
        except Exception as e:
            self._running = False
            error_msg = str(e)
            if "Conflict" in error_msg:
                raise RuntimeError(
                    "Another bot instance is already running with this token. "
                    "Please stop any other instances or restart your server."
                )
            raise RuntimeError(f"Failed to start Telegram bot: {e}")

    async def _run_polling(self) -> None:
        """Run the polling loop."""
        try:
            # Use drop_pending_updates to clear old state and reduce conflicts
            await self._dispatcher.start_polling(
                self._bot,
                drop_pending_updates=True,
                allowed_updates=["message"],  # Only listen for messages
            )
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Telegram polling error: {e}")
        finally:
            self._running = False

    async def disconnect(self) -> None:
        """Stop the Telegram bot."""
        was_running = self._running
        self._running = False

        # Cancel polling task first
        if self._polling_task and not self._polling_task.done():
            self._polling_task.cancel()
            try:
                await self._polling_task
            except asyncio.CancelledError:
                pass

        # Stop dispatcher only if it was actually polling
        if self._dispatcher and was_running:
            try:
                await self._dispatcher.stop_polling()
            except RuntimeError:
                # Polling may not have been started or already stopped
                pass

        # Close bot session
        if self._bot:
            try:
                await self._bot.session.close()
            except Exception:
                pass

        self._bot = None
        self._dispatcher = None
        self._polling_task = None
        logger.info(f"Telegram adapter stopped for connection {self.connection_id}")

    async def _send_platform_response(
        self, chat_id: int, response: PlatformResponse
    ) -> None:
        """Send a PlatformResponse with media and text to a Telegram chat."""
        from aiogram.types import BufferedInputFile

        # Send each media item as a native Telegram message
        for item in response.media:
            try:
                input_file = BufferedInputFile(item.data, filename=item.filename)
                caption = item.metadata_text or item.alt_text or None

                if item.media_type.startswith("image/"):
                    await self._bot.send_photo(
                        chat_id=chat_id, photo=input_file, caption=caption
                    )
                elif item.media_type.startswith("audio/"):
                    await self._bot.send_voice(
                        chat_id=chat_id, voice=input_file, caption=caption
                    )
                else:
                    await self._bot.send_document(
                        chat_id=chat_id, document=input_file, caption=caption
                    )
            except Exception as e:
                logger.error(f"Failed to send Telegram media ({item.media_type}): {e}")

        # Send text portion
        if response.text:
            formatted = self.format_outgoing_message(response.text)
            if formatted:
                await self._bot.send_message(chat_id=chat_id, text=formatted)

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a message to a Telegram chat."""
        if not self._bot or not self._running:
            return False

        try:
            # Strip markdown if configured for this connection
            formatted_message = self.format_outgoing_message(message)
            await self._bot.send_message(chat_id=int(chat_id), text=formatted_message)
            return True
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
            return False

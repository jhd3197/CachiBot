"""
Telegram Platform Adapter

Uses aiogram library for Telegram Bot API integration.
"""

import asyncio
import logging
from typing import Any

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler

logger = logging.getLogger(__name__)


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
                if not message.text or not self.on_message:
                    return

                try:
                    # Get chat info
                    chat_id = str(message.chat.id)
                    user = message.from_user
                    metadata = {
                        "platform": "telegram",
                        "chat_id": chat_id,
                        "chat_type": message.chat.type,
                        "user_id": str(user.id) if user else None,
                        "username": user.username if user else None,
                        "first_name": user.first_name if user else None,
                    }

                    # Call the message handler to get bot response
                    # Commands are intercepted by PlatformManager's CommandProcessor
                    response = await self.on_message(
                        self.connection_id,
                        chat_id,
                        message.text,
                        metadata,
                    )

                    # Send response back (strip markdown if configured)
                    if response:
                        await message.answer(self.format_outgoing_message(response))

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

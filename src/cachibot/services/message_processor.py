"""
Platform Message Processor

Handles incoming messages from Telegram/Discord by routing them through the bot's agent.
"""

import asyncio
import logging
import uuid
from datetime import datetime

from cachibot.agent import CachibotAgent
from cachibot.config import Config
from cachibot.models.knowledge import BotMessage
from cachibot.models.websocket import WSMessage
from cachibot.services.context_builder import get_context_builder
from cachibot.storage.repository import BotRepository, ChatRepository, KnowledgeRepository

logger = logging.getLogger(__name__)


class MessageProcessor:
    """Processes incoming platform messages through the bot's agent."""

    def __init__(self):
        self._bot_repo = BotRepository()
        self._chat_repo = ChatRepository()
        self._knowledge_repo = KnowledgeRepository()
        self._config = Config.load()

    async def _broadcast_message(
        self,
        bot_id: str,
        chat_id: str,
        role: str,
        content: str,
        message_id: str,
        platform: str,
        metadata: dict | None = None,
    ) -> None:
        """Broadcast a platform message to all connected WebSocket clients."""
        try:
            # Lazy import to avoid circular dependency
            from cachibot.api.websocket import get_ws_manager

            ws_manager = get_ws_manager()
            msg = WSMessage.platform_message(
                bot_id=bot_id,
                chat_id=chat_id,
                role=role,
                content=content,
                message_id=message_id,
                platform=platform,
                metadata=metadata,
            )
            await ws_manager.broadcast(msg)
        except Exception as e:
            # Don't fail message processing if broadcast fails
            logger.warning(f"Failed to broadcast platform message: {e}")

    async def process_message(
        self,
        bot_id: str,
        platform_chat_id: str,
        message: str,
        metadata: dict,
    ) -> str:
        """
        Process an incoming message from a platform.

        Args:
            bot_id: The bot ID to use
            platform_chat_id: The platform's chat/conversation ID
            message: The message content
            metadata: Platform-specific metadata (user info, etc.)

        Returns:
            The bot's response text
        """
        # Get bot configuration
        bot = await self._bot_repo.get_bot(bot_id)
        if bot is None:
            logger.warning(f"Bot not found: {bot_id}")
            return "Bot configuration not found. Please sync the bot from the app."

        # Get or create the platform chat
        platform = metadata.get("platform", "unknown")
        username = metadata.get("username") or metadata.get("first_name") or "User"
        chat_title = f"{platform.title()}: {username}"

        chat = await self._chat_repo.get_or_create_platform_chat(
            bot_id=bot_id,
            platform=platform,
            platform_chat_id=platform_chat_id,
            title=chat_title,
        )

        # If chat is archived, ignore the message
        if chat is None:
            logger.debug(f"Ignoring message for archived chat: {platform_chat_id}")
            return ""  # Return empty - no response for archived chats

        # Use the internal chat ID for message storage
        chat_id = chat.id

        # Update chat timestamp
        await self._chat_repo.update_chat_timestamp(chat_id)

        # Save user message to history
        user_msg_id = str(uuid.uuid4())
        user_msg = BotMessage(
            id=user_msg_id,
            bot_id=bot_id,
            chat_id=chat_id,
            role="user",
            content=message,
            timestamp=datetime.utcnow(),
            metadata=metadata,
        )
        await self._knowledge_repo.save_bot_message(user_msg)

        # Broadcast user message to connected WebSocket clients
        await self._broadcast_message(
            bot_id=bot_id,
            chat_id=chat_id,
            role="user",
            content=message,
            message_id=user_msg_id,
            platform=platform,
        )

        # Build enhanced system prompt with context
        try:
            context_builder = get_context_builder()
            enhanced_prompt = await context_builder.build_enhanced_system_prompt(
                base_prompt=bot.system_prompt,
                bot_id=bot_id,
                user_message=message,
                chat_id=chat_id,
                include_contacts=bot.capabilities.get("contacts", False),
            )
        except Exception as e:
            logger.warning(f"Context building failed: {e}")
            enhanced_prompt = bot.system_prompt

        # Create agent
        agent = CachibotAgent(
            config=self._config,
            system_prompt_override=enhanced_prompt,
            # Platform messages get limited tool access for safety
            allowed_tools={"task_complete"},
        )

        # Run agent in executor (blocking call)
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(None, agent.run, message)

            # Get usage data from agent
            usage = agent.get_usage()

            # Save assistant response to history with usage metadata
            assistant_msg_id = str(uuid.uuid4())
            assistant_msg = BotMessage(
                id=assistant_msg_id,
                bot_id=bot_id,
                chat_id=chat_id,
                role="assistant",
                content=response,
                timestamp=datetime.utcnow(),
                metadata={
                    "tokens": usage.get("total_tokens", 0),
                    "promptTokens": usage.get("prompt_tokens", 0),
                    "completionTokens": usage.get("completion_tokens", 0),
                    "cost": usage.get("total_cost", 0.0),
                    "elapsedMs": usage.get("elapsed_ms", 0.0),
                    "tokensPerSecond": usage.get("tokens_per_second", 0.0),
                    "model": bot.model,
                    "platform": platform,
                },
            )
            await self._knowledge_repo.save_bot_message(assistant_msg)

            # Broadcast assistant message to connected WebSocket clients (with usage metadata)
            await self._broadcast_message(
                bot_id=bot_id,
                chat_id=chat_id,
                role="assistant",
                content=response,
                message_id=assistant_msg_id,
                platform=platform,
                metadata={
                    "tokens": usage.get("total_tokens", 0),
                    "promptTokens": usage.get("prompt_tokens", 0),
                    "completionTokens": usage.get("completion_tokens", 0),
                    "cost": usage.get("total_cost", 0.0),
                    "elapsedMs": usage.get("elapsed_ms", 0.0),
                    "tokensPerSecond": usage.get("tokens_per_second", 0.0),
                    "model": bot.model,
                },
            )

            return response

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return "Sorry, I encountered an error processing your message."

# Singleton instance
_message_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    """Get the singleton message processor instance."""
    global _message_processor
    if _message_processor is None:
        _message_processor = MessageProcessor()
    return _message_processor

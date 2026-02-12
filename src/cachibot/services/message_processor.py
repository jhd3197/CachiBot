"""
Platform Message Processor

Handles incoming messages from Telegram/Discord by routing them through the bot's agent.
"""

import copy
import json
import logging
import uuid
from datetime import datetime
from typing import Any

from cachibot.agent import CachibotAgent
from cachibot.config import Config
from cachibot.models.knowledge import BotMessage
from cachibot.models.platform import PlatformResponse
from cachibot.models.websocket import WSMessage
from cachibot.services.context_builder import get_context_builder
from cachibot.storage.repository import BotRepository, ChatRepository, KnowledgeRepository
from cachibot.utils.markdown import extract_media_from_steps, extract_media_from_text

logger = logging.getLogger(__name__)

# Max chars for tool results sent through WebSocket (avoid huge base64 payloads)
_MAX_WS_TOOL_RESULT = 2000


def _extract_tool_calls_from_steps(steps: list) -> list[dict[str, Any]]:
    """Convert AgentResult steps into ToolCall dicts for the frontend.

    Pairs tool_call steps with their subsequent tool_result steps
    sequentially and formats them to match the frontend ToolCall interface.
    """
    tool_calls: list[dict[str, Any]] = []
    # Queue of pending tool_call entries waiting for their result
    pending: list[dict[str, Any]] = []

    for step in steps:
        if not hasattr(step, "step_type"):
            continue
        st = step.step_type.value

        if st == "tool_call":
            args = step.tool_args or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except (json.JSONDecodeError, TypeError):
                    args = {"raw": args}

            entry = {
                "id": f"tc-{len(tool_calls)}",
                "tool": step.tool_name or "unknown",
                "args": args,
                "startTime": int(step.timestamp * 1000) if step.timestamp else 0,
            }
            pending.append(entry)
            tool_calls.append(entry)

        elif st == "tool_result":
            result_str = step.tool_result or step.content or ""
            # Preserve media data URIs so the web UI can render them inline.
            # Only truncate plain-text results to keep payloads small.
            has_media = "data:image/" in result_str or "data:audio/" in result_str
            if not has_media and len(result_str) > _MAX_WS_TOOL_RESULT:
                result_str = result_str[:_MAX_WS_TOOL_RESULT] + "\n[... truncated ...]"

            if pending:
                # Pair with the oldest pending tool_call
                entry = pending.pop(0)
                entry["result"] = result_str
                entry["success"] = not result_str.startswith("Error:")
                entry["endTime"] = int(step.timestamp * 1000) if step.timestamp else 0

    return tool_calls


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
    ) -> PlatformResponse:
        """
        Process an incoming message from a platform.

        Args:
            bot_id: The bot ID to use
            platform_chat_id: The platform's chat/conversation ID
            message: The message content
            metadata: Platform-specific metadata (user info, etc.)

        Returns:
            A PlatformResponse with text and optional media attachments.
        """
        # Get bot configuration
        bot = await self._bot_repo.get_bot(bot_id)
        if bot is None:
            logger.warning(f"Bot not found: {bot_id}")
            return PlatformResponse(
                text="Bot configuration not found. Please sync the bot from the app."
            )

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
            return PlatformResponse()  # Empty - no response for archived chats

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

        # Determine agent config — override model if bot has multi-model slots
        agent_config = self._config
        if bot.models and bot.models.get("default"):
            agent_config = copy.deepcopy(self._config)
            agent_config.agent.model = bot.models["default"]

        # Create agent with bot capabilities for tool access
        agent = CachibotAgent(
            config=agent_config,
            system_prompt_override=enhanced_prompt,
            capabilities=bot.capabilities or None,
            bot_id=bot_id,
            bot_models=bot.models,
        )

        # Run async agent directly
        try:
            result = await agent.run(message)
            response_text = result.output_text or "Task completed."
            run_usage = result.run_usage

            # Extract media from tool result steps (full non-truncated data)
            media_items = extract_media_from_steps(result.steps)
            if media_items:
                cleaned_text, _ = extract_media_from_text(response_text)
                response_text = cleaned_text or response_text

            # Extract tool calls from steps for web UI display
            tool_calls = _extract_tool_calls_from_steps(result.steps)

            # Save assistant response to history with usage metadata
            assistant_msg_id = str(uuid.uuid4())
            usage_metadata: dict[str, Any] = {
                "tokens": run_usage.get("total_tokens", 0),
                "promptTokens": run_usage.get("prompt_tokens", 0),
                "completionTokens": run_usage.get("completion_tokens", 0),
                "cost": run_usage.get("cost", 0.0),
                "elapsedMs": run_usage.get("total_elapsed_ms", 0.0),
                "tokensPerSecond": run_usage.get("tokens_per_second", 0.0),
                "callCount": run_usage.get("call_count", 0),
                "errors": run_usage.get("errors", 0),
                "model": bot.model,
                "platform": platform,
            }
            if tool_calls:
                usage_metadata["toolCalls"] = tool_calls

            assistant_msg = BotMessage(
                id=assistant_msg_id,
                bot_id=bot_id,
                chat_id=chat_id,
                role="assistant",
                content=response_text,
                timestamp=datetime.utcnow(),
                metadata=usage_metadata,
            )
            await self._knowledge_repo.save_bot_message(assistant_msg)

            # Broadcast assistant message to connected WebSocket clients (with usage metadata)
            await self._broadcast_message(
                bot_id=bot_id,
                chat_id=chat_id,
                role="assistant",
                content=response_text,
                message_id=assistant_msg_id,
                platform=platform,
                metadata=usage_metadata,
            )

            return PlatformResponse(text=response_text, media=media_items)

        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return PlatformResponse(
                text="Sorry, I encountered an error processing your message."
            )


# Singleton instance
_message_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    """Get the singleton message processor instance."""
    global _message_processor
    if _message_processor is None:
        _message_processor = MessageProcessor()
    return _message_processor

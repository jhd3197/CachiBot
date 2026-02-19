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

from cachibot.agent import CachibotAgent, load_disabled_capabilities, load_dynamic_instructions
from cachibot.config import Config
from cachibot.models.knowledge import BotMessage
from cachibot.models.platform import IncomingMedia, PlatformResponse
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


_MAX_PDF_TEXT = 4000  # Max characters to extract from a PDF


async def _transcribe_audio(audio: IncomingMedia) -> str:
    """Transcribe an audio attachment using the STT driver."""
    from prompture.drivers.audio_registry import get_async_stt_driver_for_model

    stt = get_async_stt_driver_for_model("openai/whisper-1")
    result = await stt.transcribe(audio.data, {"filename": audio.filename})
    return result.get("text", "")


def _extract_pdf_text(pdf: IncomingMedia) -> str:
    """Extract text from a PDF attachment using pymupdf."""
    try:
        import pymupdf
    except ImportError:
        logger.warning("pymupdf not installed — cannot extract PDF text")
        return ""

    try:
        doc = pymupdf.open(stream=pdf.data, filetype="pdf")
        pages: list[str] = []
        for page in doc:
            pages.append(page.get_text())
        doc.close()
        text = "\n".join(pages).strip()
        if len(text) > _MAX_PDF_TEXT:
            text = text[:_MAX_PDF_TEXT] + "\n[... truncated ...]"
        return text
    except Exception as e:
        logger.warning(f"Failed to extract PDF text: {e}")
        return ""


def _extract_text_file(attachment: IncomingMedia) -> str:
    """Decode a plain text or markdown file attachment."""
    try:
        text = attachment.data.decode("utf-8", errors="replace").strip()
        if len(text) > _MAX_PDF_TEXT:
            text = text[:_MAX_PDF_TEXT] + "\n[... truncated ...]"
        return text
    except Exception as e:
        logger.warning(f"Failed to decode text file: {e}")
        return ""


async def _process_attachments(
    attachments: list[IncomingMedia],
    message: str,
) -> tuple[str, list[bytes]]:
    """Process incoming media attachments.

    Returns:
        A tuple of (augmented_message_text, image_bytes_list).
    """
    images: list[bytes] = []
    extra_parts: list[str] = []

    for att in attachments:
        if att.media_type.startswith("audio/"):
            try:
                transcript = await _transcribe_audio(att)
                if transcript:
                    extra_parts.append(f"[Audio transcription]: {transcript}")
            except Exception as e:
                logger.warning(f"Audio transcription failed: {e}")

        elif att.media_type == "application/pdf":
            text = _extract_pdf_text(att)
            if text:
                extra_parts.append(f"[Document: {att.filename}]\n{text}")

        elif att.media_type in ("text/plain", "text/markdown") or att.filename.endswith(
            (".txt", ".md")
        ):
            text = _extract_text_file(att)
            if text:
                extra_parts.append(f"[Document: {att.filename}]\n{text}")

        elif att.media_type.startswith("image/"):
            images.append(att.data)

    # Build augmented message
    augmented = message
    if extra_parts:
        joined = "\n\n".join(extra_parts)
        augmented = joined + "\n\n" + augmented if augmented else joined

    return augmented, images


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

        # Process incoming media attachments
        attachments: list[IncomingMedia] = metadata.pop("attachments", [])
        agent_images: list[bytes] = []

        if attachments:
            message, agent_images = await _process_attachments(attachments, message)
            # Store media metadata (without raw bytes) for frontend indicators
            metadata["media"] = [
                {"type": m.media_type, "filename": m.filename} for m in attachments
            ]

        # Prepend reply context if present
        reply_text = metadata.get("reply_to_text")
        if reply_text:
            snippet = reply_text[:200]
            message = f'[Replying to: "{snippet}"]\n{message}'

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

        # Send typing indicator before agent processing
        connection_id = metadata.get("connection_id")
        if connection_id:
            try:
                from cachibot.services.platform_manager import get_platform_manager

                pm = get_platform_manager()
                adapter = pm.get_adapter(connection_id)
                if adapter:
                    await adapter.send_typing(platform_chat_id)
            except Exception as e:
                logger.debug(f"Failed to send typing indicator: {e}")

        # Resolve per-bot environment (keys, temperature, etc.)
        resolved_env = None
        per_bot_driver = None
        merged_tool_configs: dict = {}
        try:
            from cachibot.services.bot_environment import BotEnvironmentService
            from cachibot.services.driver_factory import build_driver_with_key
            from cachibot.services.encryption import get_encryption_service
            from cachibot.storage.db import ensure_initialized

            session_maker = ensure_initialized()
            async with session_maker() as session:
                encryption = get_encryption_service()
                env_service = BotEnvironmentService(session, encryption)
                resolved_env = await env_service.resolve(bot_id, platform=platform)

            # Build a per-bot driver if we have a key/endpoint for the effective provider
            effective_model = agent_config.agent.model
            if effective_model and "/" in effective_model:
                provider = effective_model.split("/", 1)[0].lower()
                provider_value = resolved_env.provider_keys.get(provider)
                if provider_value:
                    from cachibot.api.routes.providers import PROVIDERS

                    provider_info = PROVIDERS.get(provider, {})
                    if provider_info.get("type") == "endpoint":
                        per_bot_driver = build_driver_with_key(
                            effective_model, endpoint=provider_value
                        )
                    else:
                        per_bot_driver = build_driver_with_key(
                            effective_model, api_key=provider_value
                        )

            # Merge skill configs from resolved environment
            if resolved_env.skill_configs:
                merged_tool_configs = dict(resolved_env.skill_configs)
        except Exception:
            logger.warning(
                "Per-bot environment resolution failed for bot %s; using global keys",
                bot_id,
                exc_info=True,
            )

        # Create agent with bot capabilities for tool access
        disabled_caps = await load_disabled_capabilities()
        agent = CachibotAgent(
            config=agent_config,
            system_prompt_override=enhanced_prompt,
            capabilities=bot.capabilities or None,
            bot_id=bot_id,
            chat_id=chat_id,
            bot_models=bot.models,
            tool_configs=merged_tool_configs,
            driver=per_bot_driver,
            provider_environment=resolved_env,
            disabled_capabilities=disabled_caps,
        )

        # Load custom instructions from DB (async)
        await load_dynamic_instructions(agent)

        # Run async agent directly (pass images for vision if any)
        try:
            result = await agent.run(message, images=agent_images if agent_images else None)
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
            logger.error("Error processing message for bot %s: %s", bot_id, e, exc_info=True)
            return PlatformResponse(text="Sorry, I encountered an error processing your message.")


# Singleton instance
_message_processor: MessageProcessor | None = None


def get_message_processor() -> MessageProcessor:
    """Get the singleton message processor instance."""
    global _message_processor
    if _message_processor is None:
        _message_processor = MessageProcessor()
    return _message_processor

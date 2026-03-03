"""
OpenAI-Compatible API Endpoint

Provides /v1/chat/completions and /v1/models for external tool integration
(Cursor, VS Code, custom apps). Authenticated via cb-* API keys.
"""

import copy
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from prompture import StreamEventType
from pydantic import BaseModel

from cachibot.agent import CachibotAgent, load_disabled_capabilities, load_dynamic_instructions
from cachibot.api.auth import resolve_api_key
from cachibot.api.helpers import require_found
from cachibot.config import Config
from cachibot.services.agent_factory import _resolve_public_id, resolve_bot_env
from cachibot.storage.repository import BotRepository

logger = logging.getLogger(__name__)

router = APIRouter(tags=["openai-compat"])

bot_repo = BotRepository()


# =============================================================================
# Request / Response Models
# =============================================================================


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatCompletionRequest(BaseModel):
    model: str | None = None
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float | None = None
    max_tokens: int | None = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str


class ChatCompletionUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: ChatCompletionUsage


class ModelEntry(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "cachibot"


class ModelsResponse(BaseModel):
    object: str = "list"
    data: list[ModelEntry]


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/v1/chat/completions", response_model=None)
async def chat_completions(
    body: ChatCompletionRequest,
    request: Request,
    api_key_info: tuple[str, str] = Depends(resolve_api_key),
) -> ChatCompletionResponse | StreamingResponse:
    """OpenAI-compatible chat completions endpoint."""
    bot_id, key_id = api_key_info

    # Load bot from DB
    bot = require_found(await bot_repo.get_bot(bot_id), "Bot")

    # Resolve per-bot environment and driver
    user_model = bot.model
    if bot.models and bot.models.get("default"):
        user_model = bot.models["default"]

    # Resolve public_id → real model_id (white-label support)
    effective_model = await _resolve_public_id(user_model)

    config = Config.load(workspace=request.app.state.workspace)
    agent_config = copy.deepcopy(config)
    agent_config.agent.model = effective_model

    resolved_env, per_bot_driver = await resolve_bot_env(
        bot_id, platform="api", effective_model=effective_model
    )

    # Build the user message (use the last user message, pass system as prompt)
    system_prompt = bot.system_prompt
    user_message = ""
    for msg in body.messages:
        if msg.role == "system":
            system_prompt = msg.content
        elif msg.role == "user":
            user_message = msg.content

    if not user_message:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="No user message provided")

    # Build agent (mirrors WebSocket handler pattern)
    disabled_caps = await load_disabled_capabilities()
    agent = CachibotAgent(
        config=agent_config,
        system_prompt_override=system_prompt,
        capabilities=bot.capabilities or {},
        bot_id=bot_id,
        bot_models=bot.models,
        driver=per_bot_driver,
        provider_environment=resolved_env,
        disabled_capabilities=disabled_caps,
    )
    await load_dynamic_instructions(agent)

    if body.stream:
        return StreamingResponse(
            _stream_response(agent, user_message, user_model),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )

    # Non-streaming: run agent and collect full response
    response_text = ""
    run_usage: dict[str, Any] = {}
    async for event in agent.run_stream(user_message):
        match event.event_type:
            case StreamEventType.text_delta:
                response_text += event.data
            case StreamEventType.output:
                if event.data:
                    response_text = event.data.output_text or response_text
                    run_usage = event.data.run_usage or {}

    # Emit webhook event (log the real model internally)
    try:
        from cachibot.services.webhook_delivery import emit_webhook_event

        emit_webhook_event(
            bot_id,
            "api.request",
            {"key_id": key_id, "model": effective_model, "response_length": len(response_text)},
        )
    except Exception:
        pass

    return ChatCompletionResponse(
        id=f"chatcmpl-{uuid.uuid4().hex[:24]}",
        created=int(time.time()),
        model=user_model,
        choices=[
            ChatCompletionChoice(
                index=0,
                message=ChatMessage(role="assistant", content=response_text),
                finish_reason="stop",
            )
        ],
        usage=ChatCompletionUsage(
            prompt_tokens=run_usage.get("prompt_tokens", 0),
            completion_tokens=run_usage.get("completion_tokens", 0),
            total_tokens=run_usage.get("total_tokens", 0),
        ),
    )


@router.get("/v1/models")
async def list_models(
    api_key_info: tuple[str, str] = Depends(resolve_api_key),
) -> ModelsResponse:
    """Return the bot's configured model in OpenAI format.

    Returns the public_id (white-label alias) so users never see
    the real provider model path.
    """
    bot_id, _ = api_key_info

    bot = require_found(await bot_repo.get_bot(bot_id), "Bot")

    model_id = bot.model
    if bot.models and bot.models.get("default"):
        model_id = bot.models["default"]

    # Don't resolve — keep the public_id as-is for the user
    return ModelsResponse(
        data=[
            ModelEntry(
                id=model_id,
                created=int(time.time()),
            )
        ]
    )


# =============================================================================
# Streaming Helper
# =============================================================================


async def _stream_response(
    agent: CachibotAgent,
    user_message: str,
    model: str,
) -> AsyncIterator[str]:
    """Yield SSE chunks in OpenAI streaming format."""
    completion_id = f"chatcmpl-{uuid.uuid4().hex[:24]}"
    created = int(time.time())

    async for event in agent.run_stream(user_message):
        if event.event_type == StreamEventType.text_delta:
            chunk = {
                "id": completion_id,
                "object": "chat.completion.chunk",
                "created": created,
                "model": model,
                "choices": [
                    {
                        "index": 0,
                        "delta": {"content": event.data},
                        "finish_reason": None,
                    }
                ],
            }
            yield f"data: {json.dumps(chunk)}\n\n"

    # Final chunk with finish_reason
    final_chunk = {
        "id": completion_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": {},
                "finish_reason": "stop",
            }
        ],
    }
    yield f"data: {json.dumps(final_chunk)}\n\n"
    yield "data: [DONE]\n\n"

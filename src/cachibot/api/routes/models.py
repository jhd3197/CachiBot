"""Models endpoint with Prompture integration for model discovery."""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel, Field

logger = logging.getLogger("cachibot.api.models")
router = APIRouter()

ENV_PATH = Path.cwd() / ".env"

# Default model if none configured
DEFAULT_MODEL = os.getenv("CACHIBOT_DEFAULT_MODEL", "moonshot/kimi-k2.5")


class ModelInfo(BaseModel):
    """Information about an available model."""

    id: str = Field(description="Model identifier (provider/model-id)")
    provider: str = Field(description="Provider name")
    context_window: int | None = Field(default=None, description="Context window size")
    max_output_tokens: int | None = Field(default=None, description="Max output tokens")
    supports_tool_use: bool = Field(default=False, description="Supports tool use")
    supports_vision: bool = Field(default=False, description="Supports vision")
    supports_structured_output: bool = Field(default=False, description="Supports structured output")
    is_reasoning: bool = Field(default=False, description="Is a reasoning model")
    pricing: dict | None = Field(default=None, description="Pricing per 1M tokens")


class ModelsResponse(BaseModel):
    """Grouped models response."""

    groups: dict[str, list[ModelInfo]] = Field(description="Models grouped by provider")


class DefaultModelResponse(BaseModel):
    """Default model response."""

    model: str = Field(description="Current default model ID")


class DefaultModelUpdate(BaseModel):
    """Request to update default model."""

    model: str = Field(description="New default model ID")


@router.get("/models", response_model=ModelsResponse)
async def get_models() -> ModelsResponse:
    """
    Get all available models from configured providers.

    Uses Prompture's model discovery to automatically detect which providers
    are configured and fetch their available models with capabilities.
    """
    groups: dict[str, list[ModelInfo]] = {}

    try:
        from prompture import get_available_models

        enriched = get_available_models(include_capabilities=True)
    except ImportError:
        logger.warning("Prompture not available, using fallback models")
        enriched = []
    except Exception as exc:
        logger.warning("Model discovery failed: %s", exc)
        enriched = []

    # Try to import pricing helper
    get_model_rates = None
    try:
        from prompture.model_rates import get_model_rates as _get_rates
        get_model_rates = _get_rates
    except ImportError:
        pass

    # Process discovered models
    for entry in enriched:
        provider = entry.get("provider", "unknown")
        raw_id = entry["model_id"]

        # Always prefix with the provider so we know which service to use
        if not raw_id.startswith(f"{provider}/"):
            model_id = f"{provider}/{raw_id}"
        else:
            model_id = raw_id

        caps = entry.get("capabilities") or {}

        # Fetch pricing if available
        pricing = None
        if get_model_rates is not None:
            try:
                rates = get_model_rates(provider, raw_id)
                if rates:
                    pricing = {
                        "input": rates.get("input"),
                        "output": rates.get("output"),
                    }
            except Exception:
                pass

        model_info = ModelInfo(
            id=model_id,
            provider=provider,
            context_window=caps.get("context_window"),
            max_output_tokens=caps.get("max_output_tokens"),
            supports_tool_use=bool(caps.get("supports_tool_use")),
            supports_vision=bool(caps.get("supports_vision")),
            supports_structured_output=bool(caps.get("supports_structured_output")),
            is_reasoning=bool(caps.get("is_reasoning")),
            pricing=pricing,
        )

        groups.setdefault(provider, []).append(model_info)

    # If no models discovered, provide fallback list
    if not groups:
        fallback_models = [
            ModelInfo(
                id="moonshot/kimi-k2.5",
                provider="moonshot",
                context_window=128000,
                supports_tool_use=True,
            ),
            ModelInfo(
                id="anthropic/claude-sonnet-4-20250514",
                provider="anthropic",
                context_window=200000,
                supports_tool_use=True,
                supports_vision=True,
            ),
            ModelInfo(
                id="anthropic/claude-3-5-haiku-20241022",
                provider="anthropic",
                context_window=200000,
                supports_tool_use=True,
                supports_vision=True,
            ),
            ModelInfo(
                id="openai/gpt-4o",
                provider="openai",
                context_window=128000,
                supports_tool_use=True,
                supports_vision=True,
            ),
            ModelInfo(
                id="openai/gpt-4o-mini",
                provider="openai",
                context_window=128000,
                supports_tool_use=True,
                supports_vision=True,
            ),
            ModelInfo(
                id="google/gemini-2.0-flash",
                provider="google",
                context_window=1000000,
                supports_tool_use=True,
                supports_vision=True,
            ),
            ModelInfo(
                id="groq/llama-3.3-70b-versatile",
                provider="groq",
                context_window=128000,
                supports_tool_use=True,
            ),
            ModelInfo(
                id="ollama/llama3.2",
                provider="ollama",
                context_window=128000,
                supports_tool_use=True,
            ),
        ]
        for m in fallback_models:
            groups.setdefault(m.provider, []).append(m)

    # Sort models within each group
    for provider in groups:
        groups[provider].sort(key=lambda m: m.id)

    return ModelsResponse(groups=groups)


@router.get("/models/default", response_model=DefaultModelResponse)
async def get_default_model() -> DefaultModelResponse:
    """Get the current default model."""
    model = os.getenv("CACHIBOT_DEFAULT_MODEL", DEFAULT_MODEL)
    return DefaultModelResponse(model=model)


@router.put("/models/default")
async def set_default_model(body: DefaultModelUpdate) -> dict:
    """
    Set the default model.

    Updates the .env file and environment variable so the change persists
    across restarts and takes effect immediately.
    """
    key = "CACHIBOT_DEFAULT_MODEL"
    value = body.model

    # Update .env file
    content = ""
    if ENV_PATH.exists():
        content = ENV_PATH.read_text(encoding="utf-8")

    pattern = re.compile(rf"^#?\s*{re.escape(key)}\s*=.*$", re.MULTILINE)
    replacement = f"{key}={value}"

    if pattern.search(content):
        content = pattern.sub(replacement, content, count=1)
    else:
        if content and not content.endswith("\n"):
            content += "\n"
        content += f"{replacement}\n"

    ENV_PATH.write_text(content, encoding="utf-8")

    # Update environment variable immediately
    os.environ[key] = value

    return {"ok": True, "model": value}

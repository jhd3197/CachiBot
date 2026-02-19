"""Models endpoint with Prompture integration for model discovery."""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from cachibot.api.auth import get_current_user
from cachibot.api.env_utils import set_env_value
from cachibot.models.auth import User

logger = logging.getLogger("cachibot.api.models")
router = APIRouter()


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
    supports_structured_output: bool = Field(
        default=False, description="Supports structured output"
    )
    supports_image_generation: bool = Field(default=False, description="Supports image generation")
    supports_audio: bool = Field(default=False, description="Supports audio (TTS/STT)")
    is_reasoning: bool = Field(default=False, description="Is a reasoning model")
    pricing: dict[str, Any] | None = Field(default=None, description="Pricing per 1M tokens")


class ModelsResponse(BaseModel):
    """Grouped models response."""

    groups: dict[str, list[ModelInfo]] = Field(description="Models grouped by provider")


class DefaultModelResponse(BaseModel):
    """Default model response."""

    model: str = Field(description="Current default model ID")


class DefaultModelUpdate(BaseModel):
    """Request to update default model."""

    model: str = Field(description="New default model ID")


# Known image generation model IDs (populated at discovery time from Prompture)
_KNOWN_IMAGE_GEN_IDS: set[str] = set()


def _is_image_generation_model(model_id: str, provider: str) -> bool:
    """Check if a model ID indicates an image generation model."""
    return model_id in _KNOWN_IMAGE_GEN_IDS


# Audio model patterns (TTS/STT)
_AUDIO_PATTERNS = {"tts-1", "whisper", "eleven_", "scribe"}
_AUDIO_PROVIDERS = {"elevenlabs"}


def _is_audio_model(model_id: str, provider: str) -> bool:
    """Check if a model ID indicates an audio model (TTS or STT)."""
    model_lower = model_id.lower()
    if provider.lower() in _AUDIO_PROVIDERS:
        return True
    return any(pattern in model_lower for pattern in _AUDIO_PATTERNS)


# Hardcoded fallback image generation models (used only when Prompture discovery is unavailable)
_IMAGE_MODEL_FALLBACKS = [
    ModelInfo(id="openai/dall-e-3", provider="openai", supports_image_generation=True),
    ModelInfo(id="openai/dall-e-2", provider="openai", supports_image_generation=True),
    ModelInfo(
        id="google/imagen-3.0-generate-002",
        provider="google",
        supports_image_generation=True,
    ),
    ModelInfo(
        id="google/imagen-3.0-fast-generate-001",
        provider="google",
        supports_image_generation=True,
    ),
    ModelInfo(
        id="stability/stable-image-core",
        provider="stability",
        supports_image_generation=True,
    ),
    ModelInfo(id="stability/sd3.5-large", provider="stability", supports_image_generation=True),
    ModelInfo(
        id="stability/sd3.5-large-turbo",
        provider="stability",
        supports_image_generation=True,
    ),
    ModelInfo(id="grok/grok-2-image", provider="grok", supports_image_generation=True),
]

# Hardcoded fallback audio models
_AUDIO_MODEL_FALLBACKS = [
    ModelInfo(id="openai/tts-1", provider="openai", supports_audio=True),
    ModelInfo(id="openai/tts-1-hd", provider="openai", supports_audio=True),
    ModelInfo(id="openai/whisper-1", provider="openai", supports_audio=True),
    ModelInfo(id="elevenlabs/eleven_multilingual_v2", provider="elevenlabs", supports_audio=True),
    ModelInfo(id="elevenlabs/eleven_turbo_v2_5", provider="elevenlabs", supports_audio=True),
    ModelInfo(id="elevenlabs/eleven_flash_v2_5", provider="elevenlabs", supports_audio=True),
    ModelInfo(id="elevenlabs/scribe_v1", provider="elevenlabs", supports_audio=True),
]


@router.get("/models", response_model=ModelsResponse)
async def get_models(user: User = Depends(get_current_user)) -> ModelsResponse:
    """
    Get all available models from configured providers.

    Uses Prompture's model discovery to automatically detect which providers
    are configured and fetch their available models with capabilities.
    """
    groups: dict[str, list[ModelInfo]] = {}

    enriched_models: list[dict[str, Any]] = []
    try:
        from prompture import get_available_models

        enriched_models = get_available_models(  # type: ignore[assignment]
            include_capabilities=True
        )
    except ImportError:
        logger.warning("Prompture not available, using fallback models")
    except Exception as exc:
        logger.warning("Model discovery failed: %s", exc)

    # Populate known image gen IDs from Prompture's image model discovery
    global _KNOWN_IMAGE_GEN_IDS
    try:
        from prompture import get_available_image_gen_models

        _KNOWN_IMAGE_GEN_IDS = set(get_available_image_gen_models())
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Image model discovery failed: %s", exc)

    # Try to import pricing helper
    get_model_rates = None
    try:
        from prompture.model_rates import get_model_rates as _get_rates

        get_model_rates = _get_rates
    except ImportError:
        pass

    # Process discovered models
    for entry in enriched_models:
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

        # Detect image generation and audio models
        is_image_gen = _is_image_generation_model(model_id, provider)
        is_audio = _is_audio_model(model_id, provider)

        model_info = ModelInfo(
            id=model_id,
            provider=provider,
            context_window=caps.get("context_window"),
            max_output_tokens=caps.get("max_output_tokens"),
            supports_tool_use=bool(caps.get("supports_tool_use")),
            supports_vision=bool(caps.get("supports_vision")),
            supports_structured_output=bool(caps.get("supports_structured_output")),
            supports_image_generation=is_image_gen,
            supports_audio=is_audio,
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
async def get_default_model(user: User = Depends(get_current_user)) -> DefaultModelResponse:
    """Get the current default model."""
    model = os.getenv("CACHIBOT_DEFAULT_MODEL", DEFAULT_MODEL)
    return DefaultModelResponse(model=model)


@router.put("/models/default", response_model=dict)
async def set_default_model(
    body: DefaultModelUpdate,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Set the default model.

    Updates the .env file and environment variable so the change persists
    across restarts and takes effect immediately.
    """
    key = "CACHIBOT_DEFAULT_MODEL"
    value = body.model

    # Reject values with newlines or control chars to prevent .env injection
    if any(c in value for c in ("\n", "\r", "\0")):
        raise HTTPException(status_code=400, detail="Invalid model ID")

    set_env_value(key, value)

    return {"ok": True, "model": value}


@router.get("/models/image", response_model=ModelsResponse)
async def get_image_models(user: User = Depends(get_current_user)) -> ModelsResponse:
    """
    Get models that support image generation.

    Uses Prompture's get_available_image_gen_models() for live discovery,
    falls back to hardcoded models if unavailable.
    """
    groups: dict[str, list[ModelInfo]] = {}

    # Try Prompture's live image model discovery
    try:
        from prompture import get_available_image_gen_models

        live_models = get_available_image_gen_models()
        for model_str in live_models:
            provider = model_str.split("/", 1)[0] if "/" in model_str else "unknown"
            groups.setdefault(provider, []).append(
                ModelInfo(id=model_str, provider=provider, supports_image_generation=True)
            )
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Image model discovery failed: %s", exc)

    # Also pull any image-flagged models from the main discovery
    try:
        all_models = await get_models(user)
        for provider, models in all_models.groups.items():
            existing_ids = {m.id for grp in groups.values() for m in grp}
            for m in models:
                if m.supports_image_generation and m.id not in existing_ids:
                    groups.setdefault(provider, []).append(m)
    except Exception:
        pass

    # Only add fallback image models if no live models were discovered
    if not groups:
        for fallback in _IMAGE_MODEL_FALLBACKS:
            groups.setdefault(fallback.provider, []).append(fallback)

    # Sort within groups
    for provider in groups:
        groups[provider].sort(key=lambda m: m.id)

    return ModelsResponse(groups=groups)


@router.get("/models/audio", response_model=ModelsResponse)
async def get_audio_models(user: User = Depends(get_current_user)) -> ModelsResponse:
    """
    Get models that support audio (TTS/STT).

    Returns discovered audio models plus hardcoded fallbacks for known providers.
    Also tries Prompture's live audio model discovery.
    """
    # Get all models first
    all_models = await get_models(user)

    groups: dict[str, list[ModelInfo]] = {}

    # Filter to audio models
    for provider, models in all_models.groups.items():
        audio_models = [m for m in models if m.supports_audio]
        if audio_models:
            groups[provider] = audio_models

    # Try Prompture's live audio discovery
    try:
        from prompture import get_available_audio_models

        live_models = get_available_audio_models()
        existing_ids = {m.id for grp in groups.values() for m in grp}
        for model_str in live_models:
            if model_str not in existing_ids:
                provider = model_str.split("/", 1)[0] if "/" in model_str else "unknown"
                groups.setdefault(provider, []).append(
                    ModelInfo(id=model_str, provider=provider, supports_audio=True)
                )
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("Audio model discovery failed: %s", exc)

    # Only add fallback audio models if no live models were discovered
    if not groups:
        for fallback in _AUDIO_MODEL_FALLBACKS:
            groups.setdefault(fallback.provider, []).append(fallback)

    # Sort within groups
    for provider in groups:
        groups[provider].sort(key=lambda m: m.id)

    return ModelsResponse(groups=groups)

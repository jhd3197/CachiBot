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
    modalities_input: list[str] = Field(default_factory=list, description="Input modalities")
    modalities_output: list[str] = Field(default_factory=list, description="Output modalities")
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


# Name-based pattern matching for models not yet in models.dev or Prompture's pricing dicts
_IMAGE_PATTERNS = ("image", "dall-e", "imagen", "stable-diffusion", "stable-image", "sdxl", "sd3")
_AUDIO_PATTERNS = ("tts", "whisper", "eleven_", "scribe")


@router.get("/models", response_model=ModelsResponse)
async def get_models(user: User = Depends(get_current_user)) -> ModelsResponse:
    """
    Get all available models from configured providers.

    Uses Prompture's model discovery with ``include_capabilities=True`` to get
    models and their modalities in a single call.  Image-generation and audio
    capability flags are derived from ``modalities_output`` (from models.dev)
    plus the dedicated Prompture discovery helpers as a supplement.
    """
    groups: dict[str, list[ModelInfo]] = {}

    # --- Discover all models with capabilities ---
    enriched_models: list[dict[str, Any]] = []
    try:
        from prompture.infra import get_available_models

        enriched_models = get_available_models(include_capabilities=True)
    except ImportError:
        logger.warning("Prompture not available — no models will be returned")
    except Exception as exc:
        logger.warning("Model discovery failed: %s", exc)

    # --- Supplemental: dedicated image/audio discovery (catches driver-specific models) ---
    image_gen_ids: set[str] = set()
    try:
        from prompture.infra import get_available_image_gen_models

        image_gen_ids = set(get_available_image_gen_models())
    except (ImportError, Exception):
        pass

    audio_ids: set[str] = set()
    try:
        from prompture.infra import get_available_audio_models

        audio_ids = set(get_available_audio_models())
    except (ImportError, Exception):
        pass

    # --- Pricing helper (optional) ---
    get_model_rates = None
    try:
        from prompture.model_rates import get_model_rates as _get_rates

        get_model_rates = _get_rates
    except ImportError:
        pass

    # --- Process models ---
    seen_ids: set[str] = set()

    for entry in enriched_models:
        provider = entry.get("provider", "unknown")
        raw_id = entry["model_id"]

        # Always prefix with the provider so we know which service to use
        if not raw_id.startswith(f"{provider}/"):
            model_id = f"{provider}/{raw_id}"
        else:
            model_id = raw_id

        caps = entry.get("capabilities") or {}

        # Determine image/audio capability via three layers:
        #  1. modalities_output from models.dev (most reliable when present)
        #  2. Dedicated Prompture discovery sets (IMAGE_PRICING / AUDIO_PRICING)
        #  3. Name-based pattern matching (catches new models not yet in models.dev)
        modalities_out = caps.get("modalities_output") or ()
        name_lower = raw_id.lower()
        is_image_gen = (
            "image" in modalities_out
            or model_id in image_gen_ids
            or any(p in name_lower for p in _IMAGE_PATTERNS)
        )
        is_audio = (
            "audio" in modalities_out
            or model_id in audio_ids
            or any(p in name_lower for p in _AUDIO_PATTERNS)
        )

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
            supports_image_generation=is_image_gen,
            supports_audio=is_audio,
            is_reasoning=bool(caps.get("is_reasoning")),
            modalities_input=list(caps.get("modalities_input") or ()),
            modalities_output=list(caps.get("modalities_output") or ()),
            pricing=pricing,
        )

        groups.setdefault(provider, []).append(model_info)
        seen_ids.add(model_id)

    # --- Append image-only models not already in results ---
    for img_id in sorted(image_gen_ids - seen_ids):
        provider = img_id.split("/", 1)[0] if "/" in img_id else "unknown"
        groups.setdefault(provider, []).append(
            ModelInfo(id=img_id, provider=provider, supports_image_generation=True)
        )
        seen_ids.add(img_id)

    # --- Append audio-only models not already in results ---
    for aud_id in sorted(audio_ids - seen_ids):
        provider = aud_id.split("/", 1)[0] if "/" in aud_id else "unknown"
        groups.setdefault(provider, []).append(
            ModelInfo(id=aud_id, provider=provider, supports_audio=True)
        )

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

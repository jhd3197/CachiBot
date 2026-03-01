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


# Default model if none configured (empty = user must set one)
DEFAULT_MODEL = os.getenv("CACHIBOT_DEFAULT_MODEL", "")


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
    supports_embedding: bool = Field(default=False, description="Supports text embedding")
    is_reasoning: bool = Field(default=False, description="Is a reasoning model")
    modalities_input: list[str] = Field(default_factory=list, description="Input modalities")
    modalities_output: list[str] = Field(default_factory=list, description="Output modalities")
    embedding_dimensions: int | None = Field(
        default=None, description="Embedding vector dimensions"
    )
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
_EMBEDDING_PATTERNS = ("embed", "embedding", "bge-", "nomic-embed", "e5-", "minilm")


async def _load_public_id_map() -> dict[str, str]:
    """Load model_id → public_id mappings from the shared model_toggles table.

    Returns a dict like {"openai/gpt-4o": "cachibot/gpt-4", ...}.
    Only includes rows where public_id is set.
    """
    mapping: dict[str, str] = {}
    try:
        from sqlalchemy import text as sa_text
        from cachibot.storage.db import ensure_initialized

        session_maker = ensure_initialized()
        async with session_maker() as session:
            result = await session.execute(
                sa_text("SELECT model_id, public_id FROM model_toggles WHERE public_id IS NOT NULL")
            )
            for row in result:
                mapping[row[0]] = row[1]
    except Exception:
        logger.debug("Could not load public_id mappings", exc_info=True)
    return mapping


async def _apply_public_ids(groups: dict[str, list[ModelInfo]]) -> dict[str, list[ModelInfo]]:
    """Replace real model IDs with public_ids and regroup by new provider prefix."""
    pid_map = await _load_public_id_map()
    if not pid_map:
        return groups

    new_groups: dict[str, list[ModelInfo]] = {}
    for _provider, models in groups.items():
        for model in models:
            public_id = pid_map.get(model.id)
            if public_id:
                model.id = public_id
                model.provider = public_id.split("/", 1)[0] if "/" in public_id else model.provider
            new_groups.setdefault(model.provider, []).append(model)
    return new_groups


@router.get("/models", response_model=ModelsResponse)
async def get_models(user: User = Depends(get_current_user)) -> ModelsResponse:
    """
    Get all available models from configured providers.

    Uses Prompture's model discovery with ``include_capabilities=True`` to get
    models and their modalities in a single call.  Image-generation, audio, and
    embedding capability flags are derived from dedicated Prompture discovery
    helpers plus name-based pattern matching.
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

    # --- Supplemental: dedicated image/audio/embedding discovery ---
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

    embedding_ids: set[str] = set()
    embedding_dims: dict[str, int] = {}
    try:
        from prompture.drivers.embedding_base import EMBEDDING_MODEL_DIMENSIONS
        from prompture.infra import get_available_embedding_models

        embedding_ids = set(get_available_embedding_models())
        embedding_dims = EMBEDDING_MODEL_DIMENSIONS
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
        is_embedding = model_id in embedding_ids or any(
            p in name_lower for p in _EMBEDDING_PATTERNS
        )

        # Resolve embedding dimensions
        emb_dims = embedding_dims.get(raw_id) if is_embedding else None

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
            supports_embedding=is_embedding,
            is_reasoning=bool(caps.get("is_reasoning")),
            modalities_input=list(caps.get("modalities_input") or ()),
            modalities_output=list(caps.get("modalities_output") or ()),
            embedding_dimensions=emb_dims,
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
        seen_ids.add(aud_id)

    # --- Append embedding-only models not already in results ---
    for emb_id in sorted(embedding_ids - seen_ids):
        provider = emb_id.split("/", 1)[0] if "/" in emb_id else "unknown"
        model_part = emb_id.split("/", 1)[1] if "/" in emb_id else emb_id
        dims = embedding_dims.get(model_part)
        groups.setdefault(provider, []).append(
            ModelInfo(
                id=emb_id,
                provider=provider,
                supports_embedding=True,
                embedding_dimensions=dims,
            )
        )

    # --- Apply public_id white-labeling from model_toggles ---
    groups = await _apply_public_ids(groups)

    # Sort models within each group
    for provider in groups:
        groups[provider].sort(key=lambda m: m.id)

    return ModelsResponse(groups=groups)


class AllDefaultsResponse(BaseModel):
    """All default model slots in one response."""

    default: str = Field(description="Default chat model")
    embedding: str = Field(description="Default embedding model")
    utility: str = Field(description="Default utility model")


@router.get("/models/defaults", response_model=AllDefaultsResponse)
async def get_all_defaults(user: User = Depends(get_current_user)) -> AllDefaultsResponse:
    """Get all default model slots in a single request."""
    from cachibot.config import Config

    config = Config.load()
    return AllDefaultsResponse(
        default=os.getenv("CACHIBOT_DEFAULT_MODEL", DEFAULT_MODEL),
        embedding=config.knowledge.embedding_model,
        utility=os.getenv("CACHIBOT_UTILITY_MODEL", ""),
    )


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


# ── Utility Model Endpoints ───────────────────────────────────────────────


@router.get("/models/utility/default", response_model=DefaultModelResponse)
async def get_default_utility_model(
    user: User = Depends(get_current_user),
) -> DefaultModelResponse:
    """Get the current default utility model."""
    model = os.getenv("CACHIBOT_UTILITY_MODEL", "")
    return DefaultModelResponse(model=model)


@router.put("/models/utility/default", response_model=dict)
async def set_default_utility_model(
    body: DefaultModelUpdate,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Set the default utility model.

    Updates the CACHIBOT_UTILITY_MODEL env var so the change persists.
    """
    value = body.model
    if any(c in value for c in ("\n", "\r", "\0")):
        raise HTTPException(status_code=400, detail="Invalid model ID")

    set_env_value("CACHIBOT_UTILITY_MODEL", value)

    return {"ok": True, "model": value}


# ── Embedding Model Endpoints ─────────────────────────────────────────────


class EmbeddingModelInfo(BaseModel):
    """Information about an available embedding model."""

    id: str = Field(description="Model identifier (provider/model-id)")
    provider: str = Field(description="Provider name")
    dimensions: int | None = Field(default=None, description="Embedding vector dimensions")


@router.get("/models/embedding")
async def get_embedding_models(
    user: User = Depends(get_current_user),
) -> list[EmbeddingModelInfo]:
    """Get available embedding models with dimensions."""
    models: list[EmbeddingModelInfo] = []

    try:
        from prompture.drivers.embedding_base import EMBEDDING_MODEL_DIMENSIONS
        from prompture.infra import get_available_embedding_models

        for model_str in get_available_embedding_models():
            parts = model_str.split("/", 1)
            provider = parts[0]
            model_id = parts[1] if len(parts) > 1 else parts[0]
            dims = EMBEDDING_MODEL_DIMENSIONS.get(model_id)
            models.append(EmbeddingModelInfo(id=model_str, provider=provider, dimensions=dims))
    except (ImportError, Exception) as exc:
        logger.warning("Embedding model discovery failed: %s", exc)

    return models


@router.get("/models/embedding/default", response_model=DefaultModelResponse)
async def get_default_embedding_model(
    user: User = Depends(get_current_user),
) -> DefaultModelResponse:
    """Get the current default embedding model from config."""
    from cachibot.config import Config

    config = Config.load()
    return DefaultModelResponse(model=config.knowledge.embedding_model)


@router.put("/models/embedding/default", response_model=dict)
async def set_default_embedding_model(
    body: DefaultModelUpdate,
    user: User = Depends(get_current_user),
) -> dict[str, Any]:
    """Set the default embedding model.

    Updates the CACHIBOT_EMBEDDING_MODEL env var so the change persists.
    """
    value = body.model
    if any(c in value for c in ("\n", "\r", "\0")):
        raise HTTPException(status_code=400, detail="Invalid model ID")

    set_env_value("CACHIBOT_EMBEDDING_MODEL", value)

    # Reset the singleton so it picks up the new model on next use

    import cachibot.services.vector_store as vs_module

    vs_module._vector_store = None

    return {"ok": True, "model": value}

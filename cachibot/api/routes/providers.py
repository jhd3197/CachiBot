"""Provider API key management endpoints.

DEPRECATED: These endpoints manage global API keys via the .env file.
Use the per-bot environment system instead:
  - PUT /api/bots/{bot_id}/environment/{key}
  - PUT /api/platforms/{platform}/environment/{key}
"""

from __future__ import annotations

import logging
import os
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cachibot.api.auth import get_current_user
from cachibot.api.env_utils import read_env_file, remove_env_value, set_env_value
from cachibot.models.auth import User

logger = logging.getLogger("cachibot.api.providers")
router = APIRouter()

PROVIDERS: dict[str, dict[str, Any]] = {
    "openai": {"env_key": "OPENAI_API_KEY", "type": "api_key"},
    "claude": {"env_key": "CLAUDE_API_KEY", "type": "api_key"},
    "google": {"env_key": "GOOGLE_API_KEY", "type": "api_key"},
    "groq": {"env_key": "GROQ_API_KEY", "type": "api_key"},
    "grok": {"env_key": "GROK_API_KEY", "type": "api_key"},
    "openrouter": {"env_key": "OPENROUTER_API_KEY", "type": "api_key"},
    "moonshot": {"env_key": "MOONSHOT_API_KEY", "type": "api_key"},
    "zai": {"env_key": "ZHIPU_API_KEY", "type": "api_key"},
    "modelscope": {"env_key": "MODELSCOPE_API_KEY", "type": "api_key"},
    "cachibot": {"env_key": "CACHIBOT_API_KEY", "type": "api_key"},
    "stability": {"env_key": "STABILITY_API_KEY", "type": "api_key"},
    "elevenlabs": {"env_key": "ELEVENLABS_API_KEY", "type": "api_key"},
    "azure": {
        "env_key": "AZURE_API_KEY",
        "type": "api_key",
        "extra_keys": [
            "AZURE_API_ENDPOINT",
            "AZURE_DEPLOYMENT_ID",
            "AZURE_CLAUDE_API_KEY",
            "AZURE_CLAUDE_ENDPOINT",
            "AZURE_MISTRAL_API_KEY",
            "AZURE_MISTRAL_ENDPOINT",
        ],
    },
    "ollama": {
        "env_key": "OLLAMA_ENDPOINT",
        "type": "endpoint",
        "default": "http://localhost:11434/api/generate",
    },
    "lmstudio": {
        "env_key": "LMSTUDIO_ENDPOINT",
        "type": "endpoint",
        "default": "http://127.0.0.1:1234/v1/chat/completions",
    },
    "local_http": {
        "env_key": "LOCAL_HTTP_ENDPOINT",
        "type": "endpoint",
        "default": "http://localhost:8000/generate",
    },
}

EXTRA_KEY_META: dict[str, dict[str, str]] = {
    "AZURE_API_ENDPOINT": {"type": "endpoint", "label": "API Endpoint", "group": "primary"},
    "AZURE_DEPLOYMENT_ID": {"type": "text", "label": "Deployment ID", "group": "primary"},
    "AZURE_CLAUDE_API_KEY": {"type": "api_key", "label": "Claude API Key", "group": "claude"},
    "AZURE_CLAUDE_ENDPOINT": {"type": "endpoint", "label": "Claude Endpoint", "group": "claude"},
    "AZURE_MISTRAL_API_KEY": {"type": "api_key", "label": "Mistral API Key", "group": "mistral"},
    "AZURE_MISTRAL_ENDPOINT": {"type": "endpoint", "label": "Mistral Endpoint", "group": "mistral"},
}


def _mask_value(value: str, provider_type: str) -> str:
    """Mask API keys (show last 4 chars), show full value for endpoints and text."""
    if provider_type in ("endpoint", "text"):
        return value
    if len(value) <= 4:
        return "****"
    return "*" * (len(value) - 4) + value[-4:]


# _read_env_file, _write_env_file, _set_env_value, _remove_env_value
# moved to cachibot.api.env_utils — kept as local aliases for internal use.
_read_env_file = read_env_file
_set_env_value = set_env_value
_remove_env_value = remove_env_value


class ProviderUpdate(BaseModel):
    value: str


@router.get("/providers")
async def list_providers(user: User = Depends(get_current_user)) -> dict[str, Any]:
    """Return all known providers with configuration status."""
    env_file_values: dict[str, str] = {}
    content = _read_env_file()
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, _, v = line.partition("=")
            env_file_values[k.strip()] = v.strip()

    result = []
    for name, info in PROVIDERS.items():
        env_key = info["env_key"]
        value = os.environ.get(env_key, "") or env_file_values.get(env_key, "")
        if value and not os.environ.get(env_key):
            os.environ[env_key] = value
        configured = bool(value)
        masked = _mask_value(value, info["type"]) if configured else ""
        # Build extra_keys array for providers that define them (e.g. Azure)
        extra_keys_list = []
        for ek in info.get("extra_keys", []):
            meta = EXTRA_KEY_META.get(ek)
            if not meta:
                continue
            ek_value = os.environ.get(ek, "") or env_file_values.get(ek, "")
            if ek_value and not os.environ.get(ek):
                os.environ[ek] = ek_value
            ek_configured = bool(ek_value)
            ek_masked = _mask_value(ek_value, meta["type"]) if ek_configured else ""
            extra_keys_list.append(
                {
                    "env_key": ek,
                    "type": meta["type"],
                    "configured": ek_configured,
                    "masked_value": ek_masked,
                    "label": meta["label"],
                    "group": meta["group"],
                }
            )

        result.append(
            {
                "name": name,
                "env_key": env_key,
                "type": info["type"],
                "configured": configured,
                "masked_value": masked,
                "default": info.get("default", ""),
                "extra_keys": extra_keys_list,
            }
        )
    return {"providers": result}


@router.put("/providers/{name}", response_model=dict)
async def update_provider(
    name: str,
    body: ProviderUpdate,
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """Set a provider's API key or endpoint.

    Deprecated: use PUT /api/bots/{bot_id}/environment/{key} or
    PUT /api/platforms/{platform}/environment/{key} instead.
    """
    logger.warning("Deprecated: PUT /providers/%s — use per-bot environment endpoints", name)
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    info = PROVIDERS[name]
    _set_env_value(info["env_key"], body.value)

    # Clear discovery cache and re-discover so new models appear immediately
    models = []
    try:
        from prompture.infra import clear_discovery_cache, get_available_models

        clear_discovery_cache()
        models = get_available_models()
    except Exception as exc:
        logger.warning("Model re-discovery after provider update failed: %s", exc)

    return JSONResponse(
        content={"ok": True, "models": models},
        headers={"Deprecation": "true", "Link": "</api/bots/{bot_id}/environment>; rel=successor"},
    )


@router.delete("/providers/{name}", status_code=204)
async def delete_provider(
    name: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove a provider's API key or endpoint.

    Deprecated: use DELETE /api/bots/{bot_id}/environment/{key} or
    DELETE /api/platforms/{platform}/environment/{key} instead.
    """
    logger.warning("Deprecated: DELETE /providers/%s — use per-bot environment endpoints", name)
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    info = PROVIDERS[name]
    _remove_env_value(info["env_key"])

    try:
        from prompture.infra import clear_discovery_cache

        clear_discovery_cache()
    except Exception:
        pass

    return None


class KeyUpdate(BaseModel):
    env_key: str
    value: str


@router.put("/providers/{name}/keys", response_model=dict)
async def update_provider_key(
    name: str,
    body: KeyUpdate,
    user: User = Depends(get_current_user),
) -> JSONResponse:
    """Set an individual extra key for a provider (e.g. Azure endpoint)."""
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    info = PROVIDERS[name]
    allowed_keys = set(info.get("extra_keys", []))
    if body.env_key not in allowed_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Key {body.env_key} does not belong to provider {name}",
        )

    _set_env_value(body.env_key, body.value)
    return JSONResponse(content={"ok": True})


@router.delete("/providers/{name}/keys/{env_key}", status_code=204)
async def delete_provider_key(
    name: str,
    env_key: str,
    user: User = Depends(get_current_user),
) -> None:
    """Remove an individual extra key for a provider."""
    if name not in PROVIDERS:
        raise HTTPException(status_code=404, detail=f"Unknown provider: {name}")

    info = PROVIDERS[name]
    allowed_keys = set(info.get("extra_keys", []))
    if env_key not in allowed_keys:
        raise HTTPException(
            status_code=400,
            detail=f"Key {env_key} does not belong to provider {name}",
        )

    _remove_env_value(env_key)
    return None

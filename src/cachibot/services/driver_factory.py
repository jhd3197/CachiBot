"""
Driver factory for per-bot environment key injection.

Builds Prompture async drivers with explicit API keys, bypassing
the global settings singleton so each bot can use its own credentials.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

# Maps provider name -> (module_path, class_name) for async drivers.
# Verified against prompture/drivers/async_registry.py.
DRIVER_MAP: dict[str, tuple[str, str]] = {
    "openai": ("prompture.drivers.async_openai_driver", "AsyncOpenAIDriver"),
    "claude": ("prompture.drivers.async_claude_driver", "AsyncClaudeDriver"),
    "anthropic": ("prompture.drivers.async_claude_driver", "AsyncClaudeDriver"),
    "google": ("prompture.drivers.async_google_driver", "AsyncGoogleDriver"),
    "gemini": ("prompture.drivers.async_google_driver", "AsyncGoogleDriver"),
    "groq": ("prompture.drivers.async_groq_driver", "AsyncGroqDriver"),
    "grok": ("prompture.drivers.async_grok_driver", "AsyncGrokDriver"),
    "xai": ("prompture.drivers.async_grok_driver", "AsyncGrokDriver"),
    "openrouter": ("prompture.drivers.async_openrouter_driver", "AsyncOpenRouterDriver"),
    "moonshot": ("prompture.drivers.async_moonshot_driver", "AsyncMoonshotDriver"),
    "zai": ("prompture.drivers.async_zai_driver", "AsyncZaiDriver"),
    "zhipu": ("prompture.drivers.async_zai_driver", "AsyncZaiDriver"),
    "modelscope": ("prompture.drivers.async_modelscope_driver", "AsyncModelScopeDriver"),
    "azure": ("prompture.drivers.async_azure_driver", "AsyncAzureDriver"),
    "ollama": ("prompture.drivers.async_ollama_driver", "AsyncOllamaDriver"),
    "lmstudio": ("prompture.drivers.async_lmstudio_driver", "AsyncLMStudioDriver"),
    "lm_studio": ("prompture.drivers.async_lmstudio_driver", "AsyncLMStudioDriver"),
    "lm-studio": ("prompture.drivers.async_lmstudio_driver", "AsyncLMStudioDriver"),
    "local_http": ("prompture.drivers.async_local_http_driver", "AsyncLocalHTTPDriver"),
    "chatgpt": ("prompture.drivers.async_openai_driver", "AsyncOpenAIDriver"),
}


def build_driver_with_key(
    model_str: str,
    api_key: str | None = None,
    **extra: Any,
) -> Any:
    """Build an async Prompture driver, optionally injecting an explicit API key.

    Args:
        model_str: Full model string in ``provider/model_id`` format.
        api_key: Explicit API key. When ``None``, falls back to the global
            registry (``get_async_driver_for_model``).
        **extra: Additional kwargs forwarded to the driver constructor
            (e.g. ``endpoint`` for Azure/Ollama/LMStudio).

    Returns:
        An instantiated async driver ready for use with ``AsyncAgent(driver=...)``.
    """
    if api_key is None and not extra:
        # No per-bot override — use the standard global registry
        from prompture.drivers.async_registry import get_async_driver_for_model

        return get_async_driver_for_model(model_str)

    parts = model_str.split("/", 1)
    provider = parts[0].lower()
    model_id = parts[1] if len(parts) > 1 else None

    if provider not in DRIVER_MAP:
        raise ValueError(
            f"Unknown provider '{provider}'. Known providers: {', '.join(sorted(DRIVER_MAP))}"
        )

    module_path, class_name = DRIVER_MAP[provider]
    module = importlib.import_module(module_path)
    driver_cls = getattr(module, class_name)

    kwargs: dict[str, Any] = {}
    if api_key is not None:
        kwargs["api_key"] = api_key
    if model_id is not None:
        kwargs["model"] = model_id
    kwargs.update(extra)

    return driver_cls(**kwargs)

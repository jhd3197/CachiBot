"""
Driver factory for per-bot environment key injection.

Thin wrapper around Prompture's ``get_async_driver_for_model`` with
``api_key=`` support, so each bot can use its own credentials without
duplicating a driver map.
"""

from __future__ import annotations

from typing import Any

from prompture.drivers.async_registry import get_async_driver_for_model


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
    return get_async_driver_for_model(model_str, api_key=api_key, **extra)

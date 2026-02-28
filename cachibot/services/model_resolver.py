"""Shared model resolution with per-bot override support.

Thin wrapper around Prompture's :class:`ModelResolver`, replacing the
duplicated fallback logic with a generic layered resolution chain.
"""

from __future__ import annotations

from typing import Any

from prompture.pipeline.resolver import (
    ModelResolver,
    NoModelConfiguredError,
    SLOT_DEFAULT,
    SLOT_UTILITY,
    attr_layer,
    dict_layer,
)

from cachibot.config import Config

# Re-export so existing callers keep their imports unchanged
__all__ = ["NoModelConfiguredError", "resolve_main_model", "resolve_utility_model"]


def _build_resolver(
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> ModelResolver:
    """Build a resolver with layers matching the original fallback chain.

    Layer order (highest → lowest priority):
    1. ``bot_models`` dict (per-bot slot from frontend)
    2. ``resolved_env`` object attrs (per-bot DB override)
    3. ``config.agent`` object attrs (global config)
    """
    layers = []
    if bot_models:
        layers.append(dict_layer(bot_models))
    if resolved_env:
        layers.append(attr_layer(resolved_env))
    try:
        config = Config.load()
        layers.append(attr_layer(config.agent))
    except Exception:
        pass
    return ModelResolver(layers=layers)


def resolve_utility_model(
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> str:
    """Resolve the model to use for cheap/fast background tasks.

    Raises :class:`NoModelConfiguredError` if nothing is set.
    """
    return _build_resolver(bot_models, resolved_env).resolve(SLOT_UTILITY)


def resolve_main_model(
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> str:
    """Resolve the main conversational model.

    Raises :class:`NoModelConfiguredError` if nothing is set.
    """
    return _build_resolver(bot_models, resolved_env).resolve(SLOT_DEFAULT)

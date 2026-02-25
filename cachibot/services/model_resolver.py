"""Shared model resolution with per-bot override support.

Centralizes the fallback chain for utility and main model selection,
replacing the duplicated _resolve_utility_model() helpers in
name_generator.py and bot_creation_service.py.
"""

from __future__ import annotations

import logging
from typing import Any

from cachibot.config import Config

logger = logging.getLogger(__name__)

class NoModelConfiguredError(Exception):
    """Raised when no model is configured anywhere in the fallback chain."""

    def __init__(self) -> None:
        super().__init__(
            "No AI model configured. Please set a default model in Settings."
        )


def resolve_utility_model(
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> str:
    """Resolve the model to use for cheap/fast background tasks.

    Fallback chain:
    1. bot_models["utility"]       — per-bot slot from frontend
    2. resolved_env.utility_model  — per-bot DB override
    3. config.agent.utility_model  — global config
    4. config.agent.model          — global main model

    Raises NoModelConfiguredError if nothing is set.
    """
    # 1. Per-bot slot
    if bot_models:
        slot = str(bot_models.get("utility", ""))
        if slot:
            return slot

    # 2. Per-bot DB override
    if resolved_env:
        env_utility = getattr(resolved_env, "utility_model", "")
        if env_utility:
            return env_utility

    # 3-4. Global config
    try:
        config = Config.load()
        model = config.agent.utility_model or config.agent.model
        if model:
            return model
    except Exception:
        pass

    raise NoModelConfiguredError()


def resolve_main_model(
    bot_models: dict[str, Any] | None = None,
    resolved_env: Any | None = None,
) -> str:
    """Resolve the main conversational model.

    Fallback chain:
    1. bot_models["default"]   — per-bot slot from frontend
    2. resolved_env.model      — per-bot DB override
    3. config.agent.model      — global config

    Raises NoModelConfiguredError if nothing is set.
    """
    # 1. Per-bot slot
    if bot_models:
        slot = str(bot_models.get("default", ""))
        if slot:
            return slot

    # 2. Per-bot DB override
    if resolved_env:
        env_model = getattr(resolved_env, "model", "")
        if env_model:
            return env_model

    # 3. Global config
    try:
        config = Config.load()
        if config.agent.model:
            return config.agent.model
    except Exception:
        pass

    raise NoModelConfiguredError()

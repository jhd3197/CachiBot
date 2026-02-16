"""
Adapter Registry

Self-registering registry for platform adapters, replacing the hardcoded factory pattern.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cachibot.models.connection import BotConnection
    from cachibot.services.adapters.base import (
        BasePlatformAdapter,
        MessageHandler,
        StatusChangeHandler,
    )

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """Registry of platform adapters that supports decorator-based self-registration."""

    _adapters: dict[str, type[BasePlatformAdapter]] = {}

    @classmethod
    def register(cls, platform_name: str) -> Callable:
        """Decorator to register an adapter class for a platform.

        Usage:
            @AdapterRegistry.register("telegram")
            class TelegramAdapter(BasePlatformAdapter):
                ...
        """

        def decorator(adapter_cls: type[BasePlatformAdapter]) -> type[BasePlatformAdapter]:
            if platform_name in cls._adapters:
                logger.warning(
                    f"Overwriting existing adapter for platform '{platform_name}': "
                    f"{cls._adapters[platform_name].__name__} -> {adapter_cls.__name__}"
                )
            cls._adapters[platform_name] = adapter_cls
            logger.debug(
                f"Registered adapter '{adapter_cls.__name__}' for platform '{platform_name}'"
            )
            return adapter_cls

        return decorator

    @classmethod
    def create(
        cls,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
        on_status_change: StatusChangeHandler | None = None,
    ) -> BasePlatformAdapter:
        """Create an adapter instance by looking up the connection's platform.

        Args:
            connection: The bot connection configuration.
            on_message: Callback for incoming messages.
            on_status_change: Callback for connection status changes.

        Returns:
            An initialized adapter instance.

        Raises:
            ValueError: If no adapter is registered for the platform.
        """
        platform_name = connection.platform.value
        adapter_cls = cls._adapters.get(platform_name)
        if not adapter_cls:
            registered = ", ".join(sorted(cls._adapters.keys())) or "(none)"
            raise ValueError(
                f"No adapter registered for platform '{platform_name}'. "
                f"Registered platforms: {registered}"
            )
        return adapter_cls(connection, on_message=on_message, on_status_change=on_status_change)

    @classmethod
    def get_adapter_class(cls, platform_name: str) -> type[BasePlatformAdapter] | None:
        """Get the adapter class for a platform name.

        Args:
            platform_name: The platform identifier (e.g., "telegram", "discord").

        Returns:
            The adapter class, or None if not registered.
        """
        return cls._adapters.get(platform_name)

    @classmethod
    def available_platforms(cls) -> dict[str, dict[str, Any]]:
        """Return metadata about all registered adapters.

        Returns:
            Dict mapping platform name to metadata dict with keys:
            name, display_name, required_config, optional_config.
        """
        result: dict[str, dict[str, Any]] = {}
        for name, adapter_cls in cls._adapters.items():
            result[name] = {
                "name": getattr(adapter_cls, "platform_name", name),
                "display_name": getattr(adapter_cls, "display_name", name.title()),
                "required_config": getattr(adapter_cls, "required_config", []),
                "optional_config": getattr(adapter_cls, "optional_config", {}),
            }
        return result

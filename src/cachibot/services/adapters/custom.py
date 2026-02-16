"""
Custom Platform Adapter

HTTP-based adapter for user-provided APIs.
Inbound messages arrive via a CachiBot webhook.
Outbound responses are POSTed to the user's base URL.
"""

import logging
import time
from typing import Any, ClassVar

import aiohttp

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.services.adapters.base import (
    AdapterHealth,
    BasePlatformAdapter,
    MessageHandler,
    StatusChangeHandler,
)
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


@AdapterRegistry.register("custom")
class CustomAdapter(BasePlatformAdapter):
    """Custom HTTP adapter for user-provided APIs."""

    platform = ConnectionPlatform.custom
    platform_name: ClassVar[str] = "custom"
    display_name: ClassVar[str] = "Custom"
    required_config: ClassVar[list[str]] = ["base_url"]
    optional_config: ClassVar[dict[str, str]] = {
        "send_messages": "Send message responses to your API",
        "typing_indicator": "Send typing indicators to your API",
        "read_receipts": "Send read receipts to your API",
        "message_status": "Send message status updates to your API",
        "strip_markdown": "Strip markdown from responses",
    }

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
        on_status_change: StatusChangeHandler | None = None,
    ):
        super().__init__(connection, on_message, on_status_change)
        self._session: aiohttp.ClientSession | None = None
        self._base_url: str = ""

    def _capability_enabled(self, key: str, default: bool = False) -> bool:
        """Check whether a capability toggle is enabled in the connection config."""
        default_str = "true" if default else "false"
        return self.connection.config.get(key, default_str).lower() == "true"

    async def connect(self) -> None:
        """Start the custom adapter by creating an HTTP session."""
        if self._running:
            return

        self._base_url = self.connection.config.get("base_url", "").rstrip("/")
        if not self._base_url:
            raise ValueError("base_url is required for custom adapter")

        # Build headers
        headers: dict[str, str] = {"Content-Type": "application/json"}
        api_key = self.connection.config.get("api_key", "")
        if api_key:
            headers["X-API-Key"] = api_key

        self._session = aiohttp.ClientSession(headers=headers)

        # Optionally ping the base URL to verify reachability (warn on failure, don't block)
        try:
            async with self._session.head(self._base_url, timeout=aiohttp.ClientTimeout(total=5)):
                pass
        except Exception as e:
            logger.warning(
                f"Custom adapter: base_url ping failed for {self.connection_id}: {e}. "
                "Connection will proceed anyway."
            )

        self._running = True
        logger.info(f"Custom adapter started for connection {self.connection_id}")

    async def disconnect(self) -> None:
        """Stop the custom adapter and close the HTTP session."""
        self._running = False
        if self._session:
            await self._session.close()
            self._session = None
        logger.info(f"Custom adapter stopped for connection {self.connection_id}")

    async def send_message(self, chat_id: str, message: str) -> bool:
        """POST a message to {base_url}/messages."""
        if not self._capability_enabled("send_messages", default=True):
            return True  # no-op when disabled

        if not self._session or not self._running:
            return False

        try:
            formatted = self.format_outgoing_message(message)
            payload: dict[str, Any] = {
                "chat_id": chat_id,
                "message": formatted,
                "metadata": {"connection_id": self.connection_id, "bot_id": self.bot_id},
            }
            async with self._session.post(
                f"{self._base_url}/messages",
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status >= 400:
                    body = await resp.text()
                    logger.error(
                        f"Custom adapter send_message failed ({resp.status}): {body[:200]}"
                    )
                    return False
                return True
        except Exception as e:
            logger.error(f"Custom adapter send_message error: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """POST a typing indicator to {base_url}/typing if enabled."""
        if not self._capability_enabled("typing_indicator"):
            return

        if not self._session or not self._running:
            return

        try:
            async with self._session.post(
                f"{self._base_url}/typing",
                json={"chat_id": chat_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except Exception as e:
            logger.debug(f"Custom adapter send_typing error: {e}")

    async def send_read_receipt(self, chat_id: str, message_id: str) -> None:
        """POST a read receipt to {base_url}/read if enabled."""
        if not self._capability_enabled("read_receipts"):
            return

        if not self._session or not self._running:
            return

        try:
            async with self._session.post(
                f"{self._base_url}/read",
                json={"chat_id": chat_id, "message_id": message_id},
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except Exception as e:
            logger.debug(f"Custom adapter send_read_receipt error: {e}")

    async def send_message_status(self, chat_id: str, message_id: str, status: str) -> None:
        """POST a message status to {base_url}/status if enabled."""
        if not self._capability_enabled("message_status"):
            return

        if not self._session or not self._running:
            return

        try:
            async with self._session.post(
                f"{self._base_url}/status",
                json={"chat_id": chat_id, "message_id": message_id, "status": status},
                timeout=aiohttp.ClientTimeout(total=5),
            ):
                pass
        except Exception as e:
            logger.debug(f"Custom adapter send_message_status error: {e}")

    async def health_check(self) -> AdapterHealth:
        """HEAD to base_url and return latency."""
        if not self._session or not self._running:
            return AdapterHealth(healthy=False, details={"running": False})

        try:
            start = time.monotonic()
            async with self._session.head(
                self._base_url, timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                latency = (time.monotonic() - start) * 1000
                return AdapterHealth(
                    healthy=resp.status < 500,
                    latency_ms=round(latency, 1),
                    details={"status_code": resp.status},
                )
        except Exception as e:
            return AdapterHealth(healthy=False, details={"error": str(e)})

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate custom adapter configuration."""
        errors: list[str] = []
        base_url = config.get("base_url", "").strip()
        if not base_url:
            errors.append("Custom base_url is required")
        elif not (base_url.startswith("http://") or base_url.startswith("https://")):
            errors.append("Custom base_url must start with http:// or https://")
        return errors

"""
WhatsApp Cloud API Platform Adapter

Uses the Meta Business Platform (Graph API) for WhatsApp Business integration.
This is a webhook-based adapter — incoming messages arrive via HTTP webhooks,
and outgoing messages are sent via the Graph API.
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

GRAPH_API_BASE = "https://graph.facebook.com/v21.0"


@AdapterRegistry.register("whatsapp")
class WhatsAppAdapter(BasePlatformAdapter):
    """WhatsApp Cloud API adapter using Meta Graph API."""

    platform = ConnectionPlatform.whatsapp
    platform_name: ClassVar[str] = "whatsapp"
    display_name: ClassVar[str] = "WhatsApp"
    required_config: ClassVar[list[str]] = [
        "phone_number_id",
        "access_token",
        "verify_token",
        "app_secret",
    ]
    optional_config: ClassVar[dict[str, str]] = {
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
        self._phone_number_id: str = ""
        self._access_token: str = ""

    @property
    def max_message_length(self) -> int:
        return 4096

    async def connect(self) -> None:
        """Mark the adapter as ready and create an HTTP session for outbound calls.

        WhatsApp is webhook-based, so connect() does not open a persistent socket.
        Incoming messages are delivered to the webhook route instead.
        """
        if self._running:
            return

        self._phone_number_id = self.connection.config.get("phone_number_id", "")
        self._access_token = self.connection.config.get("access_token", "")

        if not self._phone_number_id:
            raise ValueError("WhatsApp phone_number_id is required")
        if not self._access_token:
            raise ValueError("WhatsApp access_token is required")

        self._session = aiohttp.ClientSession(
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
            },
        )
        self._running = True
        logger.info(f"WhatsApp adapter started for connection {self.connection_id}")

    async def disconnect(self) -> None:
        """Close the HTTP session and mark the adapter as stopped."""
        self._running = False

        if self._session and not self._session.closed:
            await self._session.close()

        self._session = None
        logger.info(f"WhatsApp adapter stopped for connection {self.connection_id}")

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a text message to a WhatsApp user.

        Args:
            chat_id: The recipient phone number (in international format).
            message: The message content.

        Returns:
            True if all chunks sent successfully, False otherwise.
        """
        if not self._session or not self._running:
            return False

        url = f"{GRAPH_API_BASE}/{self._phone_number_id}/messages"

        formatted_message = self.format_outgoing_message(message)
        success = True

        for chunk in self.chunk_message(formatted_message):
            payload: dict[str, Any] = {
                "messaging_product": "whatsapp",
                "to": chat_id,
                "type": "text",
                "text": {"body": chunk},
            }

            try:
                async with self._session.post(url, json=payload) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"WhatsApp send failed (HTTP {resp.status}): {body}")
                        success = False
            except Exception as e:
                logger.error(f"Failed to send WhatsApp message: {e}")
                success = False

        return success

    async def send_typing(self, chat_id: str) -> None:
        """Mark the last received message as read (serves as a typing indicator).

        WhatsApp does not have a true "typing" API. Marking messages as read
        is the closest equivalent and is only possible when we have a message_id.
        This is a best-effort no-op when no session is available.

        Args:
            chat_id: The chat/phone number (unused; kept for interface compatibility).
        """
        # WhatsApp requires a specific message_id to mark as read.
        # Since we don't have it in the base interface, this is a no-op.
        pass

    async def mark_as_read(self, message_id: str) -> None:
        """Mark a specific WhatsApp message as read.

        Args:
            message_id: The WhatsApp message ID to mark as read.
        """
        if not self._session or not self._running:
            return

        url = f"{GRAPH_API_BASE}/{self._phone_number_id}/messages"
        payload: dict[str, Any] = {
            "messaging_product": "whatsapp",
            "status": "read",
            "message_id": message_id,
        }

        try:
            async with self._session.post(url, json=payload) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.warning(f"WhatsApp mark-as-read failed (HTTP {resp.status}): {body}")
        except Exception as e:
            logger.warning(f"Failed to mark WhatsApp message as read: {e}")

    async def health_check(self) -> AdapterHealth:
        """Check connectivity to the WhatsApp Graph API.

        Performs a GET on the phone number endpoint to verify the token and
        phone number ID are valid.
        """
        if not self._session or not self._running:
            return AdapterHealth(healthy=False, details={"running": False})

        url = f"{GRAPH_API_BASE}/{self._phone_number_id}"

        try:
            start = time.monotonic()
            async with self._session.get(url) as resp:
                latency_ms = (time.monotonic() - start) * 1000
                healthy = resp.status == 200
                details: dict[str, Any] = {
                    "running": True,
                    "api_status": resp.status,
                }
                if not healthy:
                    body = await resp.text()
                    details["error"] = body
                return AdapterHealth(healthy=healthy, latency_ms=latency_ms, details=details)
        except Exception as e:
            return AdapterHealth(
                healthy=False,
                details={"running": True, "error": str(e)},
            )

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate WhatsApp-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        for key in cls.required_config:
            if key not in config or not config[key]:
                errors.append(f"WhatsApp {key} is required")
        return errors

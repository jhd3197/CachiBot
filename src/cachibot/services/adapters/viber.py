"""
Viber Platform Adapter

Uses aiohttp for Viber REST API integration via webhooks.
"""

import hashlib
import hmac
import logging
import time
from typing import Any, ClassVar

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.services.adapters.base import (
    AdapterHealth,
    BasePlatformAdapter,
    MessageHandler,
    StatusChangeHandler,
)
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)

VIBER_API_URL = "https://chatapi.viber.com/pa"


@AdapterRegistry.register("viber")
class ViberAdapter(BasePlatformAdapter):
    """Viber bot adapter using aiohttp for REST API calls."""

    platform = ConnectionPlatform.viber
    platform_name: ClassVar[str] = "viber"
    display_name: ClassVar[str] = "Viber"
    required_config: ClassVar[list[str]] = ["auth_token", "bot_name"]
    optional_config: ClassVar[dict[str, str]] = {
        "bot_avatar": "URL for bot avatar",
        "strip_markdown": "Strip markdown from responses",
    }

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
        on_status_change: StatusChangeHandler | None = None,
    ):
        super().__init__(connection, on_message, on_status_change)
        self._session: Any = None
        self._auth_token: str = self.connection.config.get("auth_token", "")
        self._bot_name: str = self.connection.config.get("bot_name", "")
        self._bot_avatar: str = self.connection.config.get("bot_avatar", "")

    @property
    def max_message_length(self) -> int:
        return 7000

    async def connect(self) -> None:
        """Start the Viber adapter by creating a session and validating the token."""
        if self._running:
            return

        try:
            import aiohttp

            if not self._auth_token:
                raise ValueError("Viber auth_token is required")
            if not self._bot_name:
                raise ValueError("Viber bot_name is required")

            # Create aiohttp session
            self._session = aiohttp.ClientSession()

            # Validate token by calling get_account_info
            headers = {"X-Viber-Auth-Token": self._auth_token}
            async with self._session.post(
                f"{VIBER_API_URL}/get_account_info", headers=headers
            ) as resp:
                data = await resp.json()
                if data.get("status") != 0:
                    status_msg = data.get("status_message", "Unknown error")
                    await self._session.close()
                    self._session = None
                    raise ValueError(f"Viber token validation failed: {status_msg}")

            self._running = True
            logger.info(f"Viber adapter started for connection {self.connection_id}")

        except ImportError:
            raise RuntimeError("aiohttp is not installed. Run: pip install aiohttp")
        except Exception as e:
            self._running = False
            if self._session:
                await self._session.close()
                self._session = None
            if isinstance(e, (ValueError, RuntimeError)):
                raise
            raise RuntimeError(f"Failed to start Viber bot: {e}")

    async def disconnect(self) -> None:
        """Stop the Viber adapter and close the session."""
        self._running = False

        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None

        logger.info(f"Viber adapter stopped for connection {self.connection_id}")

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a text message to a Viber user.

        Args:
            chat_id: The Viber user ID (receiver).
            message: The message content.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._session or not self._running:
            return False

        try:
            formatted_message = self.format_outgoing_message(message)
            headers = {"X-Viber-Auth-Token": self._auth_token}

            for chunk in self.chunk_message(formatted_message):
                payload: dict[str, Any] = {
                    "receiver": chat_id,
                    "min_api_version": 1,
                    "sender": {
                        "name": self._bot_name,
                    },
                    "type": "text",
                    "text": chunk,
                }
                if self._bot_avatar:
                    payload["sender"]["avatar"] = self._bot_avatar

                async with self._session.post(
                    f"{VIBER_API_URL}/send_message",
                    json=payload,
                    headers=headers,
                ) as resp:
                    data = await resp.json()
                    if data.get("status") != 0:
                        status_msg = data.get("status_message", "Unknown error")
                        logger.error(f"Failed to send Viber message: {status_msg}")
                        return False

            return True
        except Exception as e:
            logger.error(f"Failed to send Viber message: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """No-op: Viber does not have a direct typing indicator API."""
        pass

    async def health_check(self) -> AdapterHealth:
        """Check adapter health by calling get_account_info."""
        if not self._session or not self._running:
            return AdapterHealth(healthy=False, details={"running": False})

        try:
            headers = {"X-Viber-Auth-Token": self._auth_token}
            start = time.monotonic()
            async with self._session.post(
                f"{VIBER_API_URL}/get_account_info", headers=headers
            ) as resp:
                data = await resp.json()
                latency = (time.monotonic() - start) * 1000
                healthy = data.get("status") == 0
                return AdapterHealth(
                    healthy=healthy,
                    latency_ms=round(latency, 2),
                    details={"status": data.get("status"), "running": self._running},
                )
        except Exception as e:
            logger.error(f"Viber health check failed: {e}")
            return AdapterHealth(healthy=False, details={"error": str(e)})

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate Viber-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors = super().validate_config(config)
        return errors

    async def set_webhook(self, url: str) -> dict[str, Any]:
        """Register a webhook URL with Viber.

        Args:
            url: The publicly accessible webhook URL.

        Returns:
            The Viber API response dict.

        Raises:
            RuntimeError: If the session is not active.
        """
        if not self._session:
            raise RuntimeError("Viber adapter is not connected")

        headers = {"X-Viber-Auth-Token": self._auth_token}
        payload = {
            "url": url,
            "event_types": [
                "delivered",
                "seen",
                "failed",
                "message",
                "conversation_started",
            ],
        }

        async with self._session.post(
            f"{VIBER_API_URL}/set_webhook",
            json=payload,
            headers=headers,
        ) as resp:
            data = await resp.json()
            if data.get("status") != 0:
                status_msg = data.get("status_message", "Unknown error")
                logger.error(f"Failed to set Viber webhook: {status_msg}")
            else:
                logger.info(f"Viber webhook set to {url}")
            return data

    def _validate_signature(self, body: bytes, signature: str) -> bool:
        """Validate the Viber webhook signature.

        Args:
            body: The raw request body bytes.
            signature: The X-Viber-Content-Signature header value.

        Returns:
            True if the signature is valid, False otherwise.
        """
        expected = hmac.new(
            self._auth_token.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
        return hmac.compare_digest(expected, signature)

    async def process_webhook(self, body: dict[str, Any], raw_body: bytes, signature: str) -> None:
        """Process an incoming Viber webhook event.

        Validates the signature and routes the event to the appropriate handler.

        Args:
            body: The parsed JSON body of the webhook request.
            raw_body: The raw request body bytes for signature validation.
            signature: The X-Viber-Content-Signature header value.
        """
        # Validate signature
        if not self._validate_signature(raw_body, signature):
            logger.warning(f"Invalid Viber webhook signature for connection {self.connection_id}")
            return

        event_type = body.get("event")

        if event_type == "message":
            await self._handle_message_event(body)
        elif event_type == "conversation_started":
            await self._handle_conversation_started(body)
        elif event_type in ("subscribed", "unsubscribed"):
            user = body.get("user", {})
            user_name = user.get("name", "Unknown")
            logger.info(f"Viber user {user_name} {event_type} for connection {self.connection_id}")
        elif event_type == "webhook":
            # Viber sends this as confirmation when webhook is set
            logger.info(f"Viber webhook confirmed for connection {self.connection_id}")
        else:
            logger.debug(f"Unhandled Viber event type: {event_type}")

    async def _handle_message_event(self, body: dict[str, Any]) -> None:
        """Handle a Viber 'message' event.

        Args:
            body: The parsed webhook body containing sender and message data.
        """
        if not self.on_message:
            return

        try:
            sender = body.get("sender", {})
            message = body.get("message", {})

            user_id = sender.get("id", "")
            username = sender.get("name", "")
            avatar = sender.get("avatar", "")
            text = message.get("text", "")

            # Skip empty messages
            if not text:
                return

            metadata: dict[str, Any] = {
                "platform": "viber",
                "user_id": user_id,
                "username": username,
                "avatar": avatar,
                "event_type": "message",
                "message_token": body.get("message_token"),
            }

            # Call the message handler
            response = await self.on_message(
                self.connection_id,
                user_id,
                text,
                metadata,
            )

            # Send response back
            if response.text or response.media:
                await self.send_response(user_id, response)

        except Exception as e:
            logger.error(f"Error handling Viber message: {e}")

    async def _handle_conversation_started(self, body: dict[str, Any]) -> None:
        """Handle a Viber 'conversation_started' event (new user).

        Sends a welcome message to the new user.

        Args:
            body: The parsed webhook body.
        """
        user = body.get("user", {})
        user_id = user.get("id", "")
        user_name = user.get("name", "Unknown")

        logger.info(
            f"Viber conversation started with {user_name} for connection {self.connection_id}"
        )

        # Send a welcome message
        if user_id:
            await self.send_message(
                user_id,
                f"Hello {user_name}! How can I help you today?",
            )

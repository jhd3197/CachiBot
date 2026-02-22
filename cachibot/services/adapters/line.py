"""
LINE Platform Adapter

Uses aiohttp for async REST calls to the LINE Messaging API.
"""

import base64
import hashlib
import hmac
import logging
import time
from typing import Any, ClassVar

import aiohttp

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import PlatformResponse
from cachibot.services.adapters.base import BasePlatformAdapter, MessageHandler, StatusChangeHandler
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)

LINE_API_BASE = "https://api.line.me"


@AdapterRegistry.register("line")
class LineAdapter(BasePlatformAdapter):
    """LINE bot adapter using aiohttp for async REST calls."""

    platform = ConnectionPlatform.line
    platform_name: ClassVar[str] = "line"
    display_name: ClassVar[str] = "LINE"
    required_config: ClassVar[list[str]] = ["channel_access_token", "channel_secret"]
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
        self._channel_access_token: str = connection.config.get("channel_access_token", "")
        self._channel_secret: str = connection.config.get("channel_secret", "")

    @property
    def max_message_length(self) -> int:
        return 5000

    async def connect(self) -> None:
        """Start the LINE adapter by creating an HTTP session and validating the token."""
        if self._running:
            return

        if not self._channel_access_token:
            raise ValueError("LINE channel_access_token is required")
        if not self._channel_secret:
            raise ValueError("LINE channel_secret is required")

        try:
            self._session = aiohttp.ClientSession(
                headers={
                    "Authorization": f"Bearer {self._channel_access_token}",
                    "Content-Type": "application/json",
                },
            )

            # Validate token by fetching bot info
            async with self._session.get(f"{LINE_API_BASE}/v2/bot/info") as resp:
                if resp.status != 200:
                    body = await resp.text()
                    await self._session.close()
                    self._session = None
                    raise RuntimeError(f"LINE token validation failed (HTTP {resp.status}): {body}")
                bot_info = await resp.json()
                logger.info(
                    f"LINE bot connected: {bot_info.get('displayName', 'unknown')} "
                    f"for connection {self.connection_id}"
                )

            self._running = True

        except aiohttp.ClientError as e:
            if self._session:
                await self._session.close()
                self._session = None
            raise RuntimeError(f"Failed to connect LINE adapter: {e}")

    async def disconnect(self) -> None:
        """Stop the LINE adapter and close the HTTP session."""
        self._running = False

        if self._session:
            await self._session.close()
            self._session = None

        logger.info(f"LINE adapter stopped for connection {self.connection_id}")

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a push message to a LINE user or group.

        Args:
            chat_id: The LINE user ID, group ID, or room ID.
            message: The message content.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._session or not self._running:
            return False

        try:
            formatted = self.format_outgoing_message(message)
            chunks = self.chunk_message(formatted)

            # LINE allows max 5 message objects per push request
            for i in range(0, len(chunks), 5):
                batch = chunks[i : i + 5]
                messages = [{"type": "text", "text": chunk} for chunk in batch]

                async with self._session.post(
                    f"{LINE_API_BASE}/v2/bot/message/push",
                    json={"to": chat_id, "messages": messages},
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"Failed to push LINE message (HTTP {resp.status}): {body}")
                        return False

            return True
        except Exception as e:
            logger.error(f"Failed to send LINE message: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """Send a loading animation to a LINE chat.

        Args:
            chat_id: The LINE user ID.
        """
        if not self._session or not self._running:
            return

        try:
            async with self._session.post(
                f"{LINE_API_BASE}/v2/bot/chat/loading/start",
                json={"chatId": chat_id},
            ) as resp:
                if resp.status != 200:
                    logger.debug(f"LINE loading indicator failed (HTTP {resp.status})")
        except Exception as e:
            logger.debug(f"Failed to send LINE typing indicator: {e}")

    async def health_check(self) -> Any:
        """Check the health of this adapter by calling the bot info endpoint."""
        from cachibot.services.adapters.base import AdapterHealth

        if not self._session or not self._running:
            return AdapterHealth(healthy=False, details={"running": False})

        try:
            start = time.monotonic()
            async with self._session.get(f"{LINE_API_BASE}/v2/bot/info") as resp:
                latency = (time.monotonic() - start) * 1000
                healthy = resp.status == 200
                return AdapterHealth(
                    healthy=healthy,
                    latency_ms=latency,
                    details={"status_code": resp.status, "running": self._running},
                )
        except Exception as e:
            return AdapterHealth(healthy=False, details={"error": str(e), "running": self._running})

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate LINE-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        for key in cls.required_config:
            if key not in config or not config[key]:
                errors.append(f"LINE {key} is required")
        return errors

    def _validate_signature(self, body: bytes, signature: str) -> bool:
        """Validate the X-Line-Signature header using HMAC-SHA256.

        Args:
            body: The raw request body bytes.
            signature: The X-Line-Signature header value.

        Returns:
            True if the signature is valid.
        """
        digest = hmac.new(
            self._channel_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(digest).decode("utf-8")
        return hmac.compare_digest(expected, signature)

    async def reply_message(self, reply_token: str, text: str) -> bool:
        """Send a reply using a webhook reply token.

        Args:
            reply_token: The reply token from a webhook event.
            text: The message text.

        Returns:
            True if sent successfully, False otherwise.
        """
        if not self._session or not self._running:
            return False

        try:
            formatted = self.format_outgoing_message(text)
            chunks = self.chunk_message(formatted)

            # Reply API also allows max 5 message objects
            messages = [{"type": "text", "text": chunk} for chunk in chunks[:5]]

            async with self._session.post(
                f"{LINE_API_BASE}/v2/bot/message/reply",
                json={"replyToken": reply_token, "messages": messages},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    logger.error(f"Failed to reply LINE message (HTTP {resp.status}): {body}")
                    return False

            # If more than 5 chunks, send remaining via push (need user_id for that)
            return True
        except Exception as e:
            logger.error(f"Failed to reply LINE message: {e}")
            return False

    async def process_webhook(self, body: dict[str, Any], raw_body: bytes, signature: str) -> None:
        """Process an incoming LINE webhook request.

        Validates the signature, parses events, and dispatches messages
        to the on_message handler.

        Args:
            body: The parsed JSON request body.
            raw_body: The raw request body bytes for signature validation.
            signature: The X-Line-Signature header value.
        """
        # Validate signature
        if not self._validate_signature(raw_body, signature):
            logger.warning(f"Invalid LINE webhook signature for connection {self.connection_id}")
            raise ValueError("Invalid signature")

        events = body.get("events", [])
        if not events:
            return

        for event in events:
            try:
                await self._handle_event(event)
            except Exception as e:
                logger.error(f"Error handling LINE event: {e}")

    async def _handle_event(self, event: dict[str, Any]) -> None:
        """Handle a single LINE webhook event.

        Args:
            event: A LINE webhook event dict.
        """
        event_type = event.get("type")
        if event_type != "message":
            return

        message = event.get("message", {})
        if message.get("type") != "text":
            return

        text = message.get("text", "")
        if not text:
            return

        if not self.on_message:
            return

        # Extract source info
        source = event.get("source", {})
        user_id = source.get("userId", "")
        source_type = source.get("type", "user")
        reply_token = event.get("replyToken", "")

        # Determine chat_id based on source type
        if source_type == "group":
            chat_id = source.get("groupId", user_id)
        elif source_type == "room":
            chat_id = source.get("roomId", user_id)
        else:
            chat_id = user_id

        metadata: dict[str, Any] = {
            "platform": "line",
            "user_id": user_id,
            "chat_id": chat_id,
            "source_type": source_type,
            "reply_token": reply_token,
            "message_id": message.get("id", ""),
        }

        # Call message handler
        response: PlatformResponse = await self.on_message(
            self.connection_id,
            chat_id,
            text,
            metadata,
        )

        # Send response back
        if response.text:
            # Try reply first (faster, uses reply token)
            if reply_token:
                sent = await self.reply_message(reply_token, response.text)
                if sent:
                    return

            # Fall back to push message
            await self.send_response(chat_id, response)

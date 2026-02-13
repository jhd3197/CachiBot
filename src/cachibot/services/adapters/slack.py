"""
Slack Platform Adapter

Uses slack-bolt and slack-sdk libraries for Slack Bot integration via Socket Mode.
"""

import asyncio
import logging
from typing import Any, ClassVar

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import IncomingMedia, PlatformResponse
from cachibot.services.adapters.base import AdapterHealth, BasePlatformAdapter, MessageHandler
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


@AdapterRegistry.register("slack")
class SlackAdapter(BasePlatformAdapter):
    """Slack bot adapter using slack-bolt with Socket Mode."""

    platform = ConnectionPlatform.slack
    platform_name: ClassVar[str] = "slack"
    display_name: ClassVar[str] = "Slack"
    required_config: ClassVar[list[str]] = ["bot_token", "app_token", "signing_secret"]
    optional_config: ClassVar[dict[str, str]] = {"strip_markdown": "Strip markdown from responses"}

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
    ):
        super().__init__(connection, on_message)
        self._app: Any = None
        self._socket_handler: Any = None
        self._task: asyncio.Task | None = None

    @property
    def max_message_length(self) -> int:
        return 4000

    async def connect(self) -> None:
        """Start the Slack bot with Socket Mode."""
        if self._running:
            return

        try:
            from slack_bolt.async_app import AsyncApp
        except ImportError:
            raise RuntimeError(
                "slack-bolt and slack-sdk are not installed. Run: pip install slack-bolt slack-sdk"
            )

        try:
            bot_token = self.connection.config.get("bot_token")
            app_token = self.connection.config.get("app_token")
            signing_secret = self.connection.config.get("signing_secret")

            if not bot_token:
                raise ValueError("Slack bot_token is required")
            if not app_token:
                raise ValueError("Slack app_token is required")
            if not signing_secret:
                raise ValueError("Slack signing_secret is required")

            # Create the Bolt async app
            self._app = AsyncApp(token=bot_token, signing_secret=signing_secret)
            adapter = self  # Capture self for closures

            @self._app.event("message")
            async def handle_message(event: dict, say: Any, client: Any) -> None:
                """Handle incoming Slack messages."""
                if not adapter.on_message:
                    return

                try:
                    # Ignore bot messages and message_changed subtypes
                    subtype = event.get("subtype")
                    if subtype in ("bot_message", "message_changed", "message_deleted"):
                        return

                    # Extract message content
                    text = event.get("text", "")
                    channel_id = event.get("channel", "")
                    user_id = event.get("user", "")
                    thread_ts = event.get("thread_ts")
                    files = event.get("files", [])

                    # Skip messages without text and without files
                    if not text and not files:
                        return

                    # Resolve username via users.info
                    username = ""
                    if user_id:
                        try:
                            user_info = await client.users_info(user=user_id)
                            if user_info.get("ok"):
                                user_data = user_info.get("user", {})
                                username = (
                                    user_data.get("profile", {}).get("display_name")
                                    or user_data.get("real_name")
                                    or user_data.get("name", "")
                                )
                        except Exception as e:
                            logger.warning(f"Failed to fetch Slack user info: {e}")

                    # Determine if this is a DM
                    is_dm = False
                    try:
                        conv_info = await client.conversations_info(channel=channel_id)
                        if conv_info.get("ok"):
                            channel_type = conv_info["channel"].get("is_im", False)
                            is_dm = channel_type
                    except Exception as e:
                        logger.warning(f"Failed to fetch Slack channel info: {e}")

                    # Build metadata
                    metadata: dict[str, Any] = {
                        "platform": "slack",
                        "channel_id": channel_id,
                        "user_id": user_id,
                        "username": username,
                        "team_id": event.get("team", ""),
                        "is_dm": is_dm,
                        "thread_ts": thread_ts,
                    }

                    # Download file attachments
                    attachments: list[IncomingMedia] = []
                    for file_info in files:
                        try:
                            file_url = file_info.get("url_private")
                            if not file_url:
                                continue

                            # Download file using bot token for auth
                            import aiohttp

                            headers = {"Authorization": f"Bearer {bot_token}"}
                            async with aiohttp.ClientSession() as session:
                                async with session.get(file_url, headers=headers) as resp:
                                    if resp.status == 200:
                                        data = await resp.read()
                                        mime = file_info.get("mimetype", "application/octet-stream")
                                        fname = file_info.get("name", "file")
                                        attachments.append(IncomingMedia(mime, data, fname))
                        except Exception as e:
                            logger.warning(f"Failed to download Slack file attachment: {e}")

                    if attachments:
                        metadata["attachments"] = attachments

                    # Call the message handler to get bot response
                    response = await adapter.on_message(
                        adapter.connection_id,
                        channel_id,
                        text,
                        metadata,
                    )

                    # Send response back to channel
                    if response.text or response.media:
                        await adapter._send_platform_response(client, channel_id, response)

                except Exception as e:
                    logger.error(f"Error handling Slack message: {e}")
                    try:
                        await say("Sorry, I encountered an error processing your message.")
                    except Exception:
                        pass

            # Create Socket Mode handler and start in background
            from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

            self._socket_handler = AsyncSocketModeHandler(self._app, app_token)
            self._running = True
            self._task = asyncio.create_task(self._run_socket_mode())
            logger.info(f"Slack adapter started for connection {self.connection_id}")

        except ImportError:
            raise RuntimeError(
                "slack-bolt and slack-sdk are not installed. Run: pip install slack-bolt slack-sdk"
            )
        except Exception as e:
            self._running = False
            raise RuntimeError(f"Failed to start Slack bot: {e}")

    async def _run_socket_mode(self) -> None:
        """Run the Socket Mode connection."""
        try:
            await self._socket_handler.start_async()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Slack Socket Mode error: {e}")
        finally:
            self._running = False

    async def disconnect(self) -> None:
        """Stop the Slack bot."""
        if not self._running and not self._task:
            return

        self._running = False

        # Close the socket handler
        if self._socket_handler:
            try:
                await self._socket_handler.close_async()
            except Exception:
                pass

        # Cancel the background task
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._app = None
        self._socket_handler = None
        self._task = None
        logger.info(f"Slack adapter stopped for connection {self.connection_id}")

    async def _send_platform_response(
        self, client: Any, channel_id: str, response: PlatformResponse
    ) -> None:
        """Send a PlatformResponse with media and text to a Slack channel."""
        # Send each media item as a file upload
        for item in response.media:
            try:
                await client.files_upload_v2(
                    channel=channel_id,
                    content=item.data,
                    filename=item.filename,
                    title=item.alt_text or item.filename,
                    initial_comment=item.metadata_text or "",
                )
            except Exception as e:
                logger.error(f"Failed to send Slack media ({item.media_type}): {e}")

        # Send text portion with chunking
        if response.text:
            formatted = self.format_outgoing_message(response.text)
            if formatted:
                for chunk in self.chunk_message(formatted):
                    await client.chat_postMessage(channel=channel_id, text=chunk)

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a message to a Slack channel."""
        if not self._app or not self._running:
            return False

        try:
            formatted_message = self.format_outgoing_message(message)
            for chunk in self.chunk_message(formatted_message):
                await self._app.client.chat_postMessage(channel=chat_id, text=chunk)
            return True
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """Send a typing indicator. Slack doesn't support typing indicators for bots."""
        pass

    async def health_check(self) -> AdapterHealth:
        """Check the health of the Slack connection."""
        if not self._app or not self._running:
            return AdapterHealth(healthy=False, details={"running": False})

        try:
            import time

            start = time.monotonic()
            result = await self._app.client.auth_test()
            latency_ms = (time.monotonic() - start) * 1000

            if result.get("ok"):
                return AdapterHealth(
                    healthy=True,
                    latency_ms=round(latency_ms, 2),
                    details={
                        "running": True,
                        "bot_user": result.get("user"),
                        "team": result.get("team"),
                    },
                )
            return AdapterHealth(
                healthy=False,
                details={"running": True, "error": result.get("error", "auth_test failed")},
            )
        except Exception as e:
            return AdapterHealth(healthy=False, details={"running": self._running, "error": str(e)})

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate Slack-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors = super().validate_config(config)

        # Validate app_token starts with xapp-
        app_token = config.get("app_token", "")
        if app_token and not app_token.startswith("xapp-"):
            errors.append("Slack app_token should start with 'xapp-'")

        # Validate bot_token starts with xoxb-
        bot_token = config.get("bot_token", "")
        if bot_token and not bot_token.startswith("xoxb-"):
            errors.append("Slack bot_token should start with 'xoxb-'")

        return errors

"""
Microsoft Teams Platform Adapter

Uses Bot Framework SDK (botbuilder-core) for Microsoft Teams Bot integration.
"""

import logging
from typing import Any, ClassVar

from cachibot.models.connection import BotConnection, ConnectionPlatform
from cachibot.models.platform import PlatformResponse
from cachibot.services.adapters.base import AdapterHealth, BasePlatformAdapter, MessageHandler
from cachibot.services.adapters.registry import AdapterRegistry

logger = logging.getLogger(__name__)


@AdapterRegistry.register("teams")
class TeamsAdapter(BasePlatformAdapter):
    """Microsoft Teams bot adapter using Bot Framework SDK."""

    platform = ConnectionPlatform.teams
    platform_name: ClassVar[str] = "teams"
    display_name: ClassVar[str] = "Microsoft Teams"
    required_config: ClassVar[list[str]] = ["app_id", "app_password"]
    optional_config: ClassVar[dict[str, str]] = {
        "tenant_id": "Tenant ID for single-tenant apps",
        "strip_markdown": "Strip markdown from responses",
    }

    def __init__(
        self,
        connection: BotConnection,
        on_message: MessageHandler | None = None,
    ):
        super().__init__(connection, on_message)
        self._adapter: Any = None
        self._conversation_references: dict[str, Any] = {}
        self._web_app: Any = None
        self._runner: Any = None
        self._site: Any = None

    @property
    def max_message_length(self) -> int:
        return 28000

    async def connect(self) -> None:
        """Start the Teams bot with an aiohttp webhook server."""
        if self._running:
            return

        try:
            from aiohttp import web
            from botbuilder.core import (
                BotFrameworkAdapter,
                BotFrameworkAdapterSettings,
                TurnContext,
            )
            from botbuilder.schema import Activity, ActivityTypes

            app_id = self.connection.config.get("app_id")
            app_password = self.connection.config.get("app_password")
            if not app_id or not app_password:
                raise ValueError("Teams app_id and app_password are required")

            tenant_id = self.connection.config.get("tenant_id", "")

            # Create adapter settings and adapter
            settings = BotFrameworkAdapterSettings(
                app_id=app_id,
                app_password=app_password,
                channel_auth_tenant=tenant_id or None,
            )
            self._adapter = BotFrameworkAdapter(settings)

            adapter_self = self  # Capture self for closure

            async def on_turn(turn_context: TurnContext) -> None:
                """Handle incoming activities from Teams."""
                activity = turn_context.activity

                if activity.type == ActivityTypes.message:
                    text = activity.text or ""
                    chat_id = activity.conversation.id if activity.conversation else ""
                    user_id = activity.from_property.id if activity.from_property else ""
                    username = activity.from_property.name if activity.from_property else ""

                    # Store conversation reference for proactive messaging
                    ref = TurnContext.get_conversation_reference(activity)
                    adapter_self._conversation_references[chat_id] = ref

                    # Build metadata
                    metadata: dict[str, Any] = {
                        "platform": "teams",
                        "channel_id": (activity.channel_id if activity.channel_id else ""),
                        "user_id": user_id,
                        "username": username,
                        "conversation_type": (
                            activity.conversation.conversation_type
                            if activity.conversation
                            else None
                        ),
                        "tenant_id": (
                            activity.conversation.tenant_id if activity.conversation else None
                        ),
                    }

                    if not adapter_self.on_message:
                        return

                    try:
                        # Send typing indicator
                        typing_activity = Activity(type=ActivityTypes.typing)
                        await turn_context.send_activity(typing_activity)

                        # Call the message handler to get bot response
                        response = await adapter_self.on_message(
                            adapter_self.connection_id,
                            chat_id,
                            text,
                            metadata,
                        )

                        # Send response back
                        if response.text or response.media:
                            await adapter_self._send_turn_response(turn_context, response)

                    except Exception as e:
                        logger.error(f"Error handling Teams message: {e}")
                        await turn_context.send_activity(
                            "Sorry, I encountered an error processing your message."
                        )

                elif activity.type == ActivityTypes.conversation_update:
                    # Store conversation reference when members are added
                    if activity.members_added:
                        ref = TurnContext.get_conversation_reference(activity)
                        chat_id = activity.conversation.id if activity.conversation else ""
                        if chat_id:
                            adapter_self._conversation_references[chat_id] = ref

            # Set up aiohttp web app for receiving messages
            self._web_app = web.Application()

            async def handle_messages(request: web.Request) -> web.Response:
                """Handle incoming Bot Framework messages via HTTP POST."""
                if request.content_type != "application/json":
                    return web.Response(status=415, text="Unsupported media type")

                body = await request.json()
                activity = Activity().deserialize(body)
                auth_header = request.headers.get("Authorization", "")

                try:
                    await self._adapter.process_activity(activity, auth_header, on_turn)
                    return web.Response(status=200)
                except Exception as e:
                    logger.error(f"Error processing Teams activity: {e}")
                    return web.Response(status=500, text="Internal server error")

            self._web_app.router.add_post("/api/messages", handle_messages)

            # Start aiohttp server
            port = int(self.connection.config.get("port", "3978"))
            self._runner = web.AppRunner(self._web_app)
            await self._runner.setup()
            self._site = web.TCPSite(self._runner, "0.0.0.0", port)
            await self._site.start()

            self._running = True
            logger.info(f"Teams adapter started for connection {self.connection_id} on port {port}")

        except ImportError:
            raise RuntimeError(
                "Bot Framework SDK is not installed. "
                "Run: pip install botbuilder-core botbuilder-schema aiohttp"
            )
        except Exception as e:
            self._running = False
            raise RuntimeError(f"Failed to start Teams bot: {e}")

    async def disconnect(self) -> None:
        """Stop the Teams bot and clean up the web server."""
        if not self._running and not self._site:
            return

        self._running = False

        # Stop the aiohttp site
        if self._site:
            try:
                await self._site.stop()
            except Exception:
                pass

        # Clean up the runner
        if self._runner:
            try:
                await self._runner.cleanup()
            except Exception:
                pass

        self._adapter = None
        self._web_app = None
        self._runner = None
        self._site = None
        self._conversation_references.clear()
        logger.info(f"Teams adapter stopped for connection {self.connection_id}")

    async def _send_turn_response(self, turn_context: Any, response: PlatformResponse) -> None:
        """Send a PlatformResponse via the current turn context."""
        # Teams doesn't have native media upload like Telegram/Discord,
        # so media items are skipped (could be extended with Adaptive Cards later).

        if response.text:
            formatted = self.format_outgoing_message(response.text)
            if formatted:
                for chunk in self.chunk_message(formatted):
                    await turn_context.send_activity(chunk)

    async def send_message(self, chat_id: str, message: str) -> bool:
        """Send a proactive message to a Teams conversation."""
        if not self._adapter or not self._running:
            return False

        ref = self._conversation_references.get(chat_id)
        if not ref:
            logger.warning(
                f"No conversation reference found for chat_id={chat_id}. "
                "Cannot send proactive message until the user messages first."
            )
            return False

        try:
            from botbuilder.core import TurnContext

            formatted_message = self.format_outgoing_message(message)

            async def send_callback(turn_context: TurnContext) -> None:
                for chunk in self.chunk_message(formatted_message):
                    await turn_context.send_activity(chunk)

            await self._adapter.continue_conversation(
                ref, send_callback, self._adapter._credentials.microsoft_app_id
            )
            return True
        except Exception as e:
            logger.error(f"Failed to send Teams proactive message: {e}")
            return False

    async def send_typing(self, chat_id: str) -> None:
        """Send a typing indicator to a Teams conversation.

        Note: Typing indicators are sent inline during on_turn message handling.
        Proactive typing indicators require a conversation reference.

        Args:
            chat_id: The conversation ID.
        """
        if not self._adapter or not self._running:
            return

        ref = self._conversation_references.get(chat_id)
        if not ref:
            return

        try:
            from botbuilder.core import TurnContext
            from botbuilder.schema import Activity, ActivityTypes

            async def typing_callback(turn_context: TurnContext) -> None:
                typing_activity = Activity(type=ActivityTypes.typing)
                await turn_context.send_activity(typing_activity)

            await self._adapter.continue_conversation(
                ref, typing_callback, self._adapter._credentials.microsoft_app_id
            )
        except Exception as e:
            logger.debug(f"Failed to send Teams typing indicator: {e}")

    async def health_check(self) -> AdapterHealth:
        """Check if the Teams webhook server is running.

        Returns:
            AdapterHealth with status and details about the web server.
        """
        details: dict[str, Any] = {"running": self._running}

        if self._site:
            details["server"] = "aiohttp"
            details["conversations_tracked"] = len(self._conversation_references)

        return AdapterHealth(healthy=self._running, details=details)

    @classmethod
    def validate_config(cls, config: dict[str, str]) -> list[str]:
        """Validate Teams-specific configuration.

        Args:
            config: The configuration dict to validate.

        Returns:
            List of error messages. Empty list means valid.
        """
        errors: list[str] = []
        for key in cls.required_config:
            if key not in config or not config[key]:
                errors.append(f"Microsoft Teams {key} is required")
        return errors

    async def process_activity(self, body: dict, auth_header: str) -> None:
        """Process a Bot Framework activity from an external webhook.

        This method allows the FastAPI webhook route to forward activities
        to this adapter without going through the built-in aiohttp server.

        Args:
            body: The raw activity JSON body.
            auth_header: The Authorization header value.
        """
        if not self._adapter:
            raise RuntimeError("Teams adapter is not connected")

        from botbuilder.core import TurnContext
        from botbuilder.schema import Activity, ActivityTypes

        activity = Activity().deserialize(body)
        adapter_self = self

        async def on_turn(turn_context: TurnContext) -> None:
            """Handle the forwarded activity."""
            act = turn_context.activity

            if act.type == ActivityTypes.message:
                text = act.text or ""
                chat_id = act.conversation.id if act.conversation else ""
                user_id = act.from_property.id if act.from_property else ""
                username = act.from_property.name if act.from_property else ""

                ref = TurnContext.get_conversation_reference(act)
                adapter_self._conversation_references[chat_id] = ref

                metadata: dict[str, Any] = {
                    "platform": "teams",
                    "channel_id": act.channel_id or "",
                    "user_id": user_id,
                    "username": username,
                    "conversation_type": (
                        act.conversation.conversation_type if act.conversation else None
                    ),
                    "tenant_id": (act.conversation.tenant_id if act.conversation else None),
                }

                if adapter_self.on_message:
                    try:
                        typing_activity = Activity(type=ActivityTypes.typing)
                        await turn_context.send_activity(typing_activity)

                        response = await adapter_self.on_message(
                            adapter_self.connection_id,
                            chat_id,
                            text,
                            metadata,
                        )

                        if response.text or response.media:
                            await adapter_self._send_turn_response(turn_context, response)
                    except Exception as e:
                        logger.error(f"Error handling Teams webhook activity: {e}")
                        await turn_context.send_activity(
                            "Sorry, I encountered an error processing your message."
                        )

            elif act.type == ActivityTypes.conversation_update:
                if act.members_added:
                    ref = TurnContext.get_conversation_reference(act)
                    chat_id = act.conversation.id if act.conversation else ""
                    if chat_id:
                        adapter_self._conversation_references[chat_id] = ref

        await self._adapter.process_activity(activity, auth_header, on_turn)

"""
Platform plugin — telegram_send, discord_send tools.
"""

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


async def _send_platform_message(
    bot_id: str | None, platform: str, chat_id: str, message: str
) -> str:
    """Send a message to a platform (telegram/discord)."""
    from cachibot.models.connection import ConnectionPlatform
    from cachibot.services.platform_manager import get_platform_manager

    if not bot_id:
        return "Error: No bot ID configured for platform messaging"

    platform_enum = (
        ConnectionPlatform.telegram if platform == "telegram" else ConnectionPlatform.discord
    )

    manager = get_platform_manager()
    try:
        success = await manager.send_to_bot_connection(bot_id, platform_enum, chat_id, message)
        if success:
            return f"Message sent to {platform.title()} {chat_id}"
        else:
            return f"Error: Failed to send. Check {platform.title()} connection status."
    except Exception as e:
        return f"Error sending {platform.title()} message: {e}"


class PlatformPlugin(CachibotPlugin):
    """Provides telegram_send and discord_send tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("platform", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="platform",
            display_name="Platform Connections",
            icon="globe",
            group="Integrations",
            requires=PluginRequirements(network=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="telegram_send",
            description="Send a message to a Telegram chat. "
            "This tool sends a message through the bot's connected Telegram account.",
            category="platform",
            tags=["telegram", "send", "message"],
            is_async=True,
            side_effects=True,
            requires_network=True,
            display_name="Send Telegram Message",
            icon="send",
            risk_level=RiskLevel.MODERATE,
        )
        async def telegram_send(chat_id: str, message: str) -> str:
            """Send a message to a Telegram chat.

            Args:
                chat_id: The Telegram chat ID to send the message to
                message: The message content to send

            Returns:
                Success or error message
            """
            return await _send_platform_message(ctx.bot_id, "telegram", chat_id, message)

        @skill(
            name="discord_send",
            description="Send a message to a Discord channel. "
            "This tool sends a message through the bot's connected Discord account.",
            category="platform",
            tags=["discord", "send", "message"],
            is_async=True,
            side_effects=True,
            requires_network=True,
            display_name="Send Discord Message",
            icon="message-circle",
            risk_level=RiskLevel.MODERATE,
        )
        async def discord_send(channel_id: str, message: str) -> str:
            """Send a message to a Discord channel.

            Args:
                channel_id: The Discord channel ID to send the message to
                message: The message content to send

            Returns:
                Success or error message
            """
            return await _send_platform_message(ctx.bot_id, "discord", channel_id, message)

        return {
            "telegram_send": telegram_send.__skill__,
            "discord_send": discord_send.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

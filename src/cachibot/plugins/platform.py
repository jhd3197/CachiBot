"""
Platform plugin — dynamically generates {platform}_send tools from the adapter registry.
"""

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


async def _send_platform_message(
    bot_id: str | None, platform: str, chat_id: str, message: str
) -> str:
    """Send a message to a platform via the platform manager."""
    from cachibot.services.platform_manager import get_platform_manager

    if not bot_id:
        return "Error: No bot ID configured for platform messaging"

    manager = get_platform_manager()
    try:
        success = await manager.send_to_bot_connection(bot_id, platform, chat_id, message)
        if success:
            return f"Message sent to {platform.title()} {chat_id}"
        else:
            return f"Error: Failed to send. Check {platform.title()} connection status."
    except Exception as e:
        return f"Error sending {platform.title()} message: {e}"


class PlatformPlugin(CachibotPlugin):
    """Dynamically provides {platform}_send tools for all registered adapters."""

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
        from cachibot.services.adapters.registry import AdapterRegistry

        ctx = self.ctx
        skills: dict[str, Skill] = {}

        for platform_name, meta in AdapterRegistry.available_platforms().items():
            display = meta.get("display_name", platform_name.title())
            # Determine the chat_id parameter name based on platform conventions
            chat_param = "channel_id" if platform_name == "discord" else "chat_id"
            chat_param_desc = (
                f"The {display} channel ID to send the message to"
                if platform_name == "discord"
                else f"The {display} chat ID to send the message to"
            )
            skill_name = f"{platform_name}_send"

            # Build the skill function with a closure over platform_name/chat_param
            def _make_skill(
                p_name: str, p_display: str, s_name: str, c_param: str, c_param_desc: str
            ) -> Skill:
                @skill(
                    name=s_name,
                    description=f"Send a message to a {p_display} chat. "
                    f"This tool sends a message through the bot's connected {p_display} account.",
                    category="platform",
                    tags=[p_name, "send", "message"],
                    is_async=True,
                    side_effects=True,
                    requires_network=True,
                    display_name=f"Send {p_display} Message",
                    icon="send" if p_name != "discord" else "message-circle",
                    risk_level=RiskLevel.MODERATE,
                )
                async def platform_send(**kwargs: str) -> str:
                    chat_id = kwargs.get(c_param, "")
                    message = kwargs.get("message", "")
                    return await _send_platform_message(ctx.bot_id, p_name, chat_id, message)

                # Set proper parameter annotations for the skill function
                import inspect

                params = [
                    inspect.Parameter(
                        c_param,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=str,
                    ),
                    inspect.Parameter(
                        "message",
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        annotation=str,
                    ),
                ]
                platform_send.__signature__ = inspect.Signature(  # type: ignore[attr-defined]
                    params, return_annotation=str
                )
                platform_send.__doc__ = (
                    f"Send a message to a {p_display} chat.\n\n"
                    f"Args:\n"
                    f"    {c_param}: {c_param_desc}\n"
                    f"    message: The message content to send\n\n"
                    f"Returns:\n"
                    f"    Success or error message"
                )

                return platform_send.__skill__  # type: ignore[attr-defined]

            skills[skill_name] = _make_skill(
                platform_name, display, skill_name, chat_param, chat_param_desc
            )

        return skills

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

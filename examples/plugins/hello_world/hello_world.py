"""
Hello World Plugin — minimal CachiBot plugin.

Demonstrates the simplest possible plugin structure:
one skill with no dependencies, no config, no side effects.
"""

from __future__ import annotations

from tukuy.skills import Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class HelloWorldPlugin(CachibotPlugin):
    """A minimal plugin with one greeting skill."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("hello_world", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="hello",
            description="Say hello with a friendly greeting.",
            category="examples",
            tags=["greeting", "demo"],
        )
        async def hello(name: str = "World") -> str:
            """Generate a friendly greeting.

            Args:
                name: Who to greet (default: "World").
            """
            return f"Hello, {name}! Welcome to CachiBot plugins."

        return {"hello": hello.__skill__}

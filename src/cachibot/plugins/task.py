"""
Task plugin — always-enabled task_complete tool.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class TaskPlugin(CachibotPlugin):
    """Provides the task_complete tool (always enabled)."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("task", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(name="task", display_name="Task", icon="check-circle", group="Core")

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="task_complete",
            description="Signal that the current task is complete. "
            "Call this when you have finished helping the user with their request.",
            category="task",
            tags=["task", "complete"],
            idempotent=True,
            display_name="Complete Task",
            icon="check-circle",
            risk_level=RiskLevel.SAFE,
        )
        def task_complete(summary: str) -> str:
            """Signal that the current task is complete.

            Args:
                summary: Brief summary of what was accomplished

            Returns:
                Completion confirmation
            """
            return f"Task completed: {summary}"

        return {"task_complete": task_complete.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

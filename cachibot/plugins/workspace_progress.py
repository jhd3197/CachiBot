"""
Workspace Progress plugin — task checklist tools for workspace mode.

Provides plan_tasks and update_task tools that emit __workspace_progress__
markers, which the WebSocket handler routes as WORKSPACE_PROGRESS messages
to the frontend for inline task checklist display.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class WorkspaceProgressPlugin(CachibotPlugin):
    """Provides workspace task progress tracking tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("workspace_progress", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="workspace_progress",
            display_name="Workspace Progress",
            icon="list-checks",
            group="Workspace",
        )

    def _build_skills(self) -> dict[str, Skill]:
        @skill(  # type: ignore[untyped-decorator]
            name="plan_tasks",
            description=(
                "Create a task checklist for the current workspace operation. "
                "Call this at the start of a multi-step task to show the user "
                "a progress tracker. Each task is a short description of a step."
            ),
            category="workspace",
            tags=["workspace", "progress", "plan"],
            idempotent=False,
            display_name="Plan Tasks",
            icon="list-checks",
            risk_level=RiskLevel.SAFE,
        )
        def plan_tasks(tasks: list[str]) -> dict[str, object]:
            """Create a task checklist for workspace progress tracking.

            Args:
                tasks: List of task descriptions (short step names)

            Returns:
                Progress marker dict routed by WebSocket handler
            """
            task_items = [{"description": desc, "status": "pending"} for desc in tasks]
            return {
                "__workspace_progress__": True,
                "action": "plan",
                "tasks": task_items,
            }

        @skill(  # type: ignore[untyped-decorator]
            name="update_task",
            description=(
                "Update the status of a task in the workspace progress checklist. "
                "Use this to mark steps as in_progress, done, or failed."
            ),
            category="workspace",
            tags=["workspace", "progress", "update"],
            idempotent=True,
            display_name="Update Task",
            icon="check-circle",
            risk_level=RiskLevel.SAFE,
        )
        def update_task(task_number: int, status: str) -> dict[str, object]:
            """Update a task's status in the workspace progress checklist.

            Args:
                task_number: 1-based task number to update
                status: New status — "in_progress", "done", or "failed"

            Returns:
                Progress marker dict routed by WebSocket handler
            """
            if status not in ("pending", "in_progress", "done", "failed"):
                return {"error": f"Invalid status: {status}. Use pending/in_progress/done/failed."}
            return {
                "__workspace_progress__": True,
                "action": "update",
                "task_number": task_number,
                "status": status,
            }

        return {
            "plan_tasks": plan_tasks.__skill__,
            "update_task": update_task.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

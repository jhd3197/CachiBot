"""
Side task tools — side_task_start and start_helpers.

Tools the bot can call to hand work to side tasks: child chats of the main
chat that run in parallel in their own git worktrees and merge their
changes back automatically when they finish. The tool descriptions (not
any phrasing detection) tell the model when to use them.

The tools are only offered in a main chat: ``build_bot_agent`` excludes
them from the registry when the chat is itself a side task, and the side
task service rejects starts from a side chat as a second layer (side
tasks are one level deep).
"""

from typing import Any

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext, skill_of

# Tools this plugin offers; build_bot_agent removes them from the registry
# inside a side task or helper chat (one level only).
SIDE_TASK_TOOL_NAMES = ("side_task_start", "start_helpers")


class SideTaskToolsPlugin(CachibotPlugin):
    """Provides the side task / helper starter tools for the bot."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("side_tasks", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="side_tasks",
            display_name="Side Tasks",
            icon="git-branch",
            group="Core",
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(
            name="side_task_start",
            description=(
                "Start a side task: a child chat of this conversation that works in "
                "parallel in its own git worktree (on a side/ branch) and merges its "
                "changes back into the main workspace automatically when it finishes. "
                "Use this when the user asks to do something 'on the side', or when a "
                "self-contained piece of work can run in parallel with the current "
                "task without blocking it (for example an isolated fix, a research "
                "question, or a check). At most 4 side tasks run at once per "
                "conversation; extras wait for a free slot. A side task is one level "
                "deep: its own sub-steps are steps inside it (use plan_tasks and "
                "update_task), never more side tasks."
            ),
            category="work",
            tags=["side-task", "parallel", "work"],
            is_async=True,
            side_effects=True,
            display_name="Start Side Task",
            icon="git-branch",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {
                    "prompt": {
                        "type": "string",
                        "description": (
                            "What the side task should do, with enough context to "
                            "run on its own in a copy of the workspace."
                        ),
                    },
                    "title": {
                        "type": "string",
                        "description": (
                            "Short name shown on the card and in the sidebar "
                            "(derived from the prompt if omitted)."
                        ),
                    },
                },
                "required": ["prompt"],
                "additionalProperties": False,
            },
        )
        async def side_task_start(prompt: str, title: str = "") -> str:
            """Start a side task that works in parallel and reports back.

            Args:
                prompt: What the side task should do
                title: Short name (derived from the prompt if omitted)

            Returns:
                JSON with the side task's id, title, status and chat id
            """
            import json

            if not ctx.bot_id or not ctx.chat_id:
                return "Error: side tasks can only be started within a chat"

            from cachibot.services.side_task_service import (
                SideTaskStartError,
                get_side_task_service,
            )

            try:
                from cachibot.models.side_task import SideTaskKind, SideTaskStartedBy

                side_task = await get_side_task_service().start(
                    parent_chat_id=ctx.chat_id,
                    bot_id=ctx.bot_id,
                    prompt=prompt,
                    title=title or None,
                    started_by=SideTaskStartedBy.BOT,
                    kind=SideTaskKind.SIDE,
                )
            except SideTaskStartError as e:
                return f"Error: {e}"
            except Exception as e:
                return f"Error starting side task: {e}"

            return json.dumps(
                {
                    "id": side_task.id,
                    "title": side_task.title,
                    "status": side_task.status.value,
                    "chat_id": side_task.chat_id,
                },
                indent=2,
            )

        @skill(
            name="start_helpers",
            description=(
                "Start a group of helpers: bot-started side tasks, one per item, "
                "shown to the user as a single group card (for example one helper "
                "per Python version, or one per file). Use this when work fans out "
                "into several independent pieces that can run in parallel. Each "
                "helper works in its own git worktree and merges its changes back "
                "automatically when it finishes; at most 4 helpers run at once per "
                "conversation and the rest wait for a free slot."
            ),
            category="work",
            tags=["side-task", "helpers", "parallel", "work"],
            is_async=True,
            side_effects=True,
            display_name="Start Helpers",
            icon="users",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "description": "One helper per item.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "prompt": {
                                    "type": "string",
                                    "description": (
                                        "What this helper should do, with enough "
                                        "context to run on its own."
                                    ),
                                },
                                "title": {
                                    "type": "string",
                                    "description": "Short name for this helper.",
                                },
                            },
                            "required": ["prompt"],
                            "additionalProperties": False,
                        },
                        "minItems": 1,
                    },
                    "group_title": {
                        "type": "string",
                        "description": (
                            "Short name for the whole group (shown on the group card)."
                        ),
                    },
                },
                "required": ["items"],
                "additionalProperties": False,
            },
        )
        async def start_helpers(items: list[dict[str, Any]], group_title: str = "") -> str:
            """Start one helper side task per item, grouped under one group id.

            Args:
                items: One {"prompt": ..., "title": ...} object per helper
                group_title: Short name for the whole group

            Returns:
                JSON with the group id and each helper's id, title and status
            """
            import json

            if not ctx.bot_id or not ctx.chat_id:
                return "Error: helpers can only be started within a chat"

            from cachibot.services.side_task_service import (
                SideTaskStartError,
                get_side_task_service,
            )

            try:
                group_id, helpers = await get_side_task_service().start_helpers(
                    parent_chat_id=ctx.chat_id,
                    bot_id=ctx.bot_id,
                    items=items,
                    group_title=group_title or None,
                )
            except SideTaskStartError as e:
                return f"Error: {e}"
            except Exception as e:
                return f"Error starting helpers: {e}"

            return json.dumps(
                {
                    "group_id": group_id,
                    "group_title": group_title or None,
                    "helpers": [
                        {"id": h.id, "title": h.title, "status": h.status.value} for h in helpers
                    ],
                },
                indent=2,
            )

        return {
            "side_task_start": skill_of(side_task_start),
            "start_helpers": skill_of(start_helpers),
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

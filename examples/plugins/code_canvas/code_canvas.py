"""
Code Canvas Plugin — Canvas-style code editing.

Skills:
    - create_code: Create a new code artifact in the side panel
    - update_code: Update an existing code artifact
"""

from __future__ import annotations

from tukuy.skill import Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.sdk import artifact_update, code_artifact


class CodeCanvasPlugin(CachibotPlugin):
    """Plugin for Canvas-style code editing in a side panel."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("code_canvas", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="create_code",
            description=(
                "Create a code artifact that renders in an editable side panel "
                "with syntax highlighting. Use this when generating or writing "
                "code that the user wants to view, edit, and iterate on."
            ),
            category="creative",
            tags=["code", "canvas", "artifact"],
        )
        async def create_code(
            language: str,
            title: str,
            content: str,
        ) -> dict:
            """Create a new code artifact in the side panel.

            Args:
                language: Programming language (python, typescript, html, etc.).
                title: Display title (e.g. "main.py", "API Handler").
                content: The source code content.
            """
            return code_artifact(title=title, content=content, language=language)

        @skill(
            name="update_code",
            description=(
                "Update an existing code artifact in the side panel. "
                "Use this when the user asks to modify code that's already "
                "displayed in the Canvas panel."
            ),
            category="creative",
            tags=["code", "canvas", "artifact", "update"],
        )
        async def update_code(
            artifact_id: str,
            content: str,
            version: int = 2,
        ) -> dict:
            """Update an existing code artifact.

            Args:
                artifact_id: ID of the artifact to update.
                content: The updated source code.
                version: Version number (should increment).
            """
            return artifact_update(
                artifact_id=artifact_id,
                content=content,
                version=version,
            )

        return {
            "create_code": create_code.__skill__,
            "update_code": update_code.__skill__,
        }

"""
HTML Preview Plugin — live HTML preview in side panel.

Skills:
    - preview_html: Create an HTML artifact for live preview
    - update_preview: Update an existing HTML preview
"""

from __future__ import annotations

from tukuy.skills import Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.sdk import artifact_update, html_artifact


class HtmlPreviewPlugin(CachibotPlugin):
    """Plugin for live HTML/CSS/JS preview in a side panel."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("html_preview", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="preview_html",
            description=(
                "Create a live HTML preview in the side panel. "
                "The HTML content renders in a sandboxed iframe "
                "with full CSS and JavaScript support."
            ),
            category="creative",
            tags=["html", "preview", "artifact", "web"],
        )
        async def preview_html(
            title: str,
            html_content: str,
        ) -> dict:
            """Create an HTML artifact for live preview.

            Args:
                title: Display title (e.g. "Landing Page", "Dashboard").
                html_content: Complete HTML content (including <html>, <head>, <body>).
            """
            return html_artifact(title=title, content=html_content)

        @skill(
            name="update_preview",
            description=(
                "Update an existing HTML preview in the side panel. "
                "Use when the user requests changes to HTML already displayed."
            ),
            category="creative",
            tags=["html", "preview", "artifact", "update"],
        )
        async def update_preview(
            artifact_id: str,
            html_content: str,
            version: int = 2,
        ) -> dict:
            """Update an existing HTML preview.

            Args:
                artifact_id: ID of the artifact to update.
                html_content: The updated HTML content.
                version: Version number (should increment).
            """
            return artifact_update(
                artifact_id=artifact_id,
                content=html_content,
                version=version,
            )

        return {
            "preview_html": preview_html.__skill__,
            "update_preview": update_preview.__skill__,
        }

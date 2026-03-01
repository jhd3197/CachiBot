"""
Document Writer Plugin — rich document editing.

Skills:
    - create_document: Create a markdown document artifact
    - update_document: Update an existing document
"""

from __future__ import annotations

from tukuy.skill import Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext
from cachibot.plugins.sdk import artifact_update, markdown_artifact


class DocWriterPlugin(CachibotPlugin):
    """Plugin for Claude Artifacts-style document editing."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("doc_writer", ctx)
        self._skills_map = self._build_skills()

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

    def _build_skills(self) -> dict[str, Skill]:
        @skill(
            name="create_document",
            description=(
                "Create a rich markdown document in the side panel. "
                "Use this for writing reports, articles, documentation, "
                "or any structured text content."
            ),
            category="creative",
            tags=["document", "markdown", "artifact", "writing"],
        )
        async def create_document(
            title: str,
            content: str,
        ) -> dict:
            """Create a new markdown document artifact.

            Args:
                title: Document title (e.g. "Project Proposal", "API Reference").
                content: Markdown content for the document.
            """
            return markdown_artifact(title=title, content=content)

        @skill(
            name="update_document",
            description=(
                "Update an existing document in the side panel. "
                "Use when the user asks to revise, edit, or extend "
                "a document already displayed."
            ),
            category="creative",
            tags=["document", "markdown", "artifact", "update"],
        )
        async def update_document(
            artifact_id: str,
            content: str,
            version: int = 2,
        ) -> dict:
            """Update an existing document artifact.

            Args:
                artifact_id: ID of the artifact to update.
                content: The updated markdown content.
                version: Version number (should increment).
            """
            return artifact_update(
                artifact_id=artifact_id,
                content=content,
                version=version,
            )

        return {
            "create_document": create_document.__skill__,
            "update_document": update_document.__skill__,
        }

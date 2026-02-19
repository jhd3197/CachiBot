"""
Notes plugin — note_save, note_search, note_list.

Gives bots persistent memory they can write to and read from.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class NotesPlugin(CachibotPlugin):
    """Provides note-taking tools for persistent bot memory."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("notes", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="notes",
            display_name="Notes",
            icon="sticky-note",
            group="Core",
        )

    def _get_bot_id(self) -> str | None:
        return self.ctx.bot_id

    def _build_skills(self) -> dict[str, Skill]:
        get_bot_id = self._get_bot_id

        @skill(  # type: ignore[untyped-decorator]
            name="note_save",
            description="Save a note to your persistent memory. "
            "Use this to remember important information, user preferences, "
            "facts, or anything you want to recall in future conversations.",
            category="knowledge",
            tags=["notes", "memory", "save"],
            is_async=True,
            side_effects=True,
            display_name="Save Note",
            icon="sticky-note",
            risk_level=RiskLevel.SAFE,
        )
        async def note_save(
            title: str,
            content: str,
            tags: list[str] | None = None,
        ) -> str:
            """Save a note to persistent memory.

            Args:
                title: Brief title for the note
                content: The note content to remember
                tags: Optional tags for categorization (e.g. ["preference", "user-info"])

            Returns:
                JSON with the created note ID and details
            """
            import json
            import uuid
            from datetime import datetime

            from cachibot.models.knowledge import BotNote, NoteSource
            from cachibot.storage.repository import NotesRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = NotesRepository()
                now = datetime.utcnow()
                note = BotNote(
                    id=str(uuid.uuid4()),
                    bot_id=bot_id,
                    title=title,
                    content=content,
                    tags=tags or [],
                    source=NoteSource.BOT,
                    created_at=now,
                    updated_at=now,
                )
                await repo.save_note(note)
                return json.dumps(
                    {
                        "id": note.id,
                        "title": note.title,
                        "tags": note.tags,
                        "message": "Note saved successfully",
                    },
                    indent=2,
                )
            except Exception as e:
                return f"Error saving note: {e}"

        @skill(  # type: ignore[untyped-decorator]
            name="note_search",
            description="Search your saved notes by keyword or tags. "
            "Use this to recall information you previously saved.",
            category="knowledge",
            tags=["notes", "memory", "search"],
            is_async=True,
            idempotent=True,
            display_name="Search Notes",
            icon="search",
            risk_level=RiskLevel.SAFE,
        )
        async def note_search(
            query: str = "",
            tags: list[str] | None = None,
            limit: int = 10,
        ) -> str:
            """Search saved notes.

            Args:
                query: Search text to match against title and content
                tags: Optional tags to filter by
                limit: Maximum number of results

            Returns:
                JSON list of matching notes
            """
            import json

            from cachibot.storage.repository import NotesRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = NotesRepository()
                notes = await repo.get_notes_by_bot(
                    bot_id,
                    tags_filter=tags,
                    search=query if query else None,
                    limit=limit,
                )
                if not notes:
                    return "No notes found"
                result = [
                    {
                        "id": n.id,
                        "title": n.title,
                        "content": n.content,
                        "tags": n.tags,
                        "source": n.source.value,
                        "updated_at": n.updated_at.isoformat(),
                    }
                    for n in notes
                ]
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error searching notes: {e}"

        @skill(  # type: ignore[untyped-decorator]
            name="note_list",
            description="List your saved notes, optionally filtered by tags.",
            category="knowledge",
            tags=["notes", "memory", "list"],
            is_async=True,
            idempotent=True,
            display_name="List Notes",
            icon="list",
            risk_level=RiskLevel.SAFE,
        )
        async def note_list(
            tags: list[str] | None = None,
            limit: int = 20,
        ) -> str:
            """List saved notes.

            Args:
                tags: Optional tags to filter by
                limit: Maximum number of notes to return

            Returns:
                JSON list of notes
            """
            import json

            from cachibot.storage.repository import NotesRepository

            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                repo = NotesRepository()
                notes = await repo.get_notes_by_bot(
                    bot_id,
                    tags_filter=tags,
                    limit=limit,
                )
                if not notes:
                    return "No notes found"
                result = [
                    {
                        "id": n.id,
                        "title": n.title,
                        "content": n.content[:200] + "..." if len(n.content) > 200 else n.content,
                        "tags": n.tags,
                        "source": n.source.value,
                        "updated_at": n.updated_at.isoformat(),
                    }
                    for n in notes
                ]
                return json.dumps(result, indent=2)
            except Exception as e:
                return f"Error listing notes: {e}"

        return {
            "note_save": note_save.__skill__,
            "note_search": note_search.__skill__,
            "note_list": note_list.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

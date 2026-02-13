"""
Knowledge Base plugin — kb_search, kb_list.

Gives bots the ability to search and list their knowledge base
(documents and notes) using vector similarity and text search.
"""

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class KnowledgePlugin(CachibotPlugin):
    """Provides knowledge base search and listing tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("knowledge", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="knowledge",
            display_name="Knowledge Base",
            icon="book-open",
            group="Core",
        )

    def _get_bot_id(self) -> str | None:
        return self.ctx.bot_id

    def _build_skills(self) -> dict[str, Skill]:
        get_bot_id = self._get_bot_id

        @skill(
            name="kb_search",
            description="Search your knowledge base for relevant information. "
            "Searches both uploaded documents (via vector similarity) and saved notes "
            "(via text search). Use this when you need to find specific information "
            "from your knowledge base to answer user questions.",
            category="knowledge",
            tags=["knowledge", "search", "rag", "documents"],
            is_async=True,
            idempotent=True,
            display_name="Search Knowledge Base",
            icon="search",
            risk_level=RiskLevel.SAFE,
        )
        async def kb_search(
            query: str,
            limit: int = 5,
        ) -> str:
            """Search the knowledge base for relevant information.

            Args:
                query: The search query text
                limit: Maximum number of results to return (default 5)

            Returns:
                Formatted search results with source attribution
            """
            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                results_parts: list[str] = []

                # Search documents via vector similarity
                from cachibot.services.vector_store import get_vector_store

                vector_store = get_vector_store()
                doc_results = await vector_store.search_with_filenames(
                    bot_id, query, limit=limit, min_score=0.3
                )

                if doc_results:
                    results_parts.append("## Document Results\n")
                    for i, result in enumerate(doc_results, 1):
                        source = result.document_filename or "Unknown document"
                        score = f"{result.score:.0%}"
                        content = result.chunk.content.strip()
                        results_parts.append(
                            f"**[{i}] {source}** (relevance: {score})\n{content}\n"
                        )

                # Search notes via text search
                from cachibot.storage.repository import NotesRepository

                notes_repo = NotesRepository()
                note_results = await notes_repo.search_notes(bot_id, query, limit=limit)

                if note_results:
                    results_parts.append("## Note Results\n")
                    for i, note in enumerate(note_results, 1):
                        tags_str = f" [{', '.join(note.tags)}]" if note.tags else ""
                        content = note.content.strip()
                        results_parts.append(
                            f"**[{i}] {note.title}**{tags_str}\n{content}\n"
                        )

                if not results_parts:
                    return f"No results found for: {query}"

                return "\n".join(results_parts)

            except Exception as e:
                return f"Error searching knowledge base: {e}"

        @skill(
            name="kb_list",
            description="List all documents and notes in your knowledge base. "
            "Shows document names, statuses, note counts, and overall stats. "
            "Use this to understand what information is available in your knowledge base.",
            category="knowledge",
            tags=["knowledge", "list", "documents", "notes"],
            is_async=True,
            idempotent=True,
            display_name="List Knowledge Base",
            icon="list",
            risk_level=RiskLevel.SAFE,
        )
        async def kb_list() -> str:
            """List all knowledge base contents and stats.

            Returns:
                Formatted overview of the knowledge base
            """
            bot_id = get_bot_id()
            if not bot_id:
                return "Error: No bot ID configured"

            try:
                from cachibot.storage.repository import KnowledgeRepository, NotesRepository

                kb_repo = KnowledgeRepository()
                notes_repo = NotesRepository()

                # Get stats
                stats = await kb_repo.get_knowledge_stats(bot_id)

                # Get document list
                docs = await kb_repo.get_documents_by_bot(bot_id)

                # Get notes (summary only)
                notes = await notes_repo.get_notes_by_bot(bot_id, limit=50)

                parts: list[str] = []

                # Overall stats
                parts.append("## Knowledge Base Overview\n")
                parts.append(f"- Documents: {stats['total_documents']}")
                parts.append(f"- Chunks: {stats['total_chunks']}")
                parts.append(f"- Notes: {stats['total_notes']}")
                parts.append(f"- Has custom instructions: {stats['has_instructions']}")
                parts.append("")

                # Document list
                if docs:
                    parts.append("## Documents\n")
                    for doc in docs:
                        status = doc.status.value
                        size_kb = doc.file_size / 1024
                        parts.append(
                            f"- **{doc.filename}** ({size_kb:.1f} KB, "
                            f"{doc.chunk_count} chunks, status: {status})"
                        )
                    parts.append("")

                # Notes summary
                if notes:
                    parts.append("## Notes\n")
                    for note in notes:
                        tags_str = f" [{', '.join(note.tags)}]" if note.tags else ""
                        preview = (
                            note.content[:100] + "..."
                            if len(note.content) > 100
                            else note.content
                        )
                        parts.append(f"- **{note.title}**{tags_str}: {preview}")
                    parts.append("")

                if not docs and not notes:
                    return "Knowledge base is empty. No documents or notes found."

                return "\n".join(parts)

            except Exception as e:
                return f"Error listing knowledge base: {e}"

        return {
            "kb_search": kb_search.__skill__,
            "kb_list": kb_list.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

"""
Context Builder Service for Knowledge Base.

Combines conversation history, custom instructions, and relevant document chunks
into context that gets injected into the LLM system prompt.
"""

import logging
from dataclasses import dataclass

from cachibot.services.vector_store import VectorStore, get_vector_store
from cachibot.storage.repository import (
    ContactsRepository,
    KnowledgeRepository,
    NotesRepository,
    SkillsRepository,
)

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeContext:
    """Assembled context from knowledge base."""

    instructions: str | None
    relevant_docs: str | None
    recent_history: str | None
    contacts: str | None
    skills: str | None
    notes: str | None = None

    def to_prompt_section(self) -> str:
        """Convert to prompt-ready string."""
        sections = []

        # Skills go first (high priority instructions)
        if self.skills:
            sections.append(f"## Active Skills\n{self.skills}")

        if self.instructions:
            sections.append(f"## Custom Instructions\n{self.instructions}")

        if self.notes:
            sections.append(f"## Notes\n{self.notes}")

        if self.contacts:
            sections.append(f"## Known Contacts\n{self.contacts}")

        if self.relevant_docs:
            sections.append(f"## Relevant Knowledge\n{self.relevant_docs}")

        if self.recent_history:
            sections.append(f"## Recent Conversation Summary\n{self.recent_history}")

        if not sections:
            return ""

        return "\n\n---\n\n".join(sections)


class ContextBuilder:
    """
    Builds context from knowledge base for LLM injection.

    Combines:
    1. Custom instructions (always included if set)
    2. Relevant document chunks (RAG based on user message)
    3. Recent conversation history (for continuity)
    """

    def __init__(
        self,
        max_history_messages: int = 10,
        max_document_chunks: int = 3,
        min_similarity_score: float = 0.3,
        vector_store: VectorStore | None = None,
    ):
        """
        Initialize the context builder.

        Args:
            max_history_messages: Maximum recent messages to include
            max_document_chunks: Maximum document chunks to retrieve
            min_similarity_score: Minimum similarity for document retrieval
            vector_store: VectorStore instance (uses singleton if not provided)
        """
        self.max_history_messages = max_history_messages
        self.max_document_chunks = max_document_chunks
        self.min_similarity_score = min_similarity_score
        self._vector_store = vector_store
        self._repo = KnowledgeRepository()
        self._contacts_repo = ContactsRepository()
        self._skills_repo = SkillsRepository()
        self._notes_repo = NotesRepository()

    @property
    def vector_store(self) -> VectorStore:
        """Get the vector store (lazy initialization)."""
        if self._vector_store is None:
            self._vector_store = get_vector_store()
        return self._vector_store

    async def build_context(
        self,
        bot_id: str,
        user_message: str,
        chat_id: str | None = None,
        include_contacts: bool = False,
        enabled_skills: list[str] | None = None,
    ) -> KnowledgeContext:
        """
        Build context from all knowledge sources.

        Args:
            bot_id: Bot to build context for
            user_message: Current user message (for document retrieval)
            chat_id: Current chat ID (for history retrieval)
            include_contacts: Whether to include contacts (contacts capability)
            enabled_skills: List of enabled skill IDs (or None to auto-fetch from bot)

        Returns:
            KnowledgeContext with assembled sections
        """
        logger.debug(f"Building context for bot {bot_id}")

        # 1. Get skill instructions
        skills = await self._get_skills_instructions(bot_id, enabled_skills)

        # 2. Get custom instructions
        instructions = await self._get_instructions(bot_id)

        # 3. Get contacts if enabled
        contacts = await self._get_contacts(bot_id, include_contacts)

        # 4. Get relevant notes
        notes = await self._get_relevant_notes(bot_id, user_message)

        # 5. Get relevant document chunks
        relevant_docs = await self._get_relevant_docs(bot_id, user_message)

        # 6. Get recent conversation history
        recent_history = await self._get_recent_history(bot_id, chat_id)

        return KnowledgeContext(
            instructions=instructions,
            relevant_docs=relevant_docs,
            recent_history=recent_history,
            contacts=contacts,
            skills=skills,
            notes=notes,
        )

    async def _get_skills_instructions(
        self,
        bot_id: str,
        enabled_skills: list[str] | None = None,
    ) -> str | None:
        """Get combined instructions from enabled skills."""
        try:
            # If skill IDs provided, fetch those skills
            # Otherwise, get skills activated for this bot
            if enabled_skills is not None:
                # Fetch skill definitions for the provided IDs
                skill_defs = []
                for skill_id in enabled_skills:
                    skill = await self._skills_repo.get_skill(skill_id)
                    if skill:
                        skill_defs.append(skill)
            else:
                # Get all enabled skills for this bot
                skill_defs = await self._skills_repo.get_bot_skill_definitions(bot_id)

            if not skill_defs:
                return None

            # Format skill instructions
            instructions = []
            for skill in skill_defs:
                instructions.append(f"### {skill.name}\n{skill.instructions}")

            return "\n\n".join(instructions)

        except Exception as e:
            logger.warning(f"Skills retrieval failed: {e}")
            return None

    async def _get_instructions(self, bot_id: str) -> str | None:
        """Get custom instructions for bot."""
        instructions = await self._repo.get_instructions(bot_id)
        if instructions and instructions.content.strip():
            return instructions.content
        return None

    async def _get_contacts(self, bot_id: str, include_contacts: bool) -> str | None:
        """Get contacts for bot if capability is enabled."""
        if not include_contacts:
            return None

        try:
            contacts = await self._contacts_repo.get_contacts_by_bot(bot_id)
            if not contacts:
                return None

            # Format contacts for prompt
            formatted = []
            for contact in contacts:
                entry = f"- {contact.name}"
                if contact.details:
                    entry += f": {contact.details}"
                formatted.append(entry)

            return "\n".join(formatted)

        except Exception as e:
            logger.warning(f"Contacts retrieval failed: {e}")
            return None

    async def _get_relevant_notes(self, bot_id: str, query: str) -> str | None:
        """Get relevant notes for the bot."""
        try:
            # Get recent notes, optionally filtered by query relevance
            if query.strip():
                notes = await self._notes_repo.search_notes(bot_id, query, limit=5)
            else:
                notes = []

            # Always include the most recent notes as well
            recent_notes = await self._notes_repo.get_notes_by_bot(bot_id, limit=5)

            # Merge and deduplicate
            seen_ids: set[str] = set()
            all_notes = []
            for note in notes + recent_notes:
                if note.id not in seen_ids:
                    seen_ids.add(note.id)
                    all_notes.append(note)

            if not all_notes:
                return None

            formatted = []
            for note in all_notes[:10]:  # Cap at 10
                tags_str = f" [{', '.join(note.tags)}]" if note.tags else ""
                content = note.content[:500] + "..." if len(note.content) > 500 else note.content
                formatted.append(f"### {note.title}{tags_str}\n{content}")

            return "\n\n".join(formatted)

        except Exception as e:
            logger.warning(f"Notes retrieval failed: {e}")
            return None

    async def _get_relevant_docs(self, bot_id: str, query: str) -> str | None:
        """Search for relevant document chunks."""
        if not query.strip():
            return None

        try:
            results = await self.vector_store.search_with_filenames(
                bot_id=bot_id,
                query=query,
                limit=self.max_document_chunks,
                min_score=self.min_similarity_score,
            )

            if not results:
                return None

            # Format results with source attribution
            formatted = []
            for result in results:
                source = result.document_filename or "Unknown document"
                formatted.append(f"[From: {source}]\n{result.chunk.content}")

            return "\n\n".join(formatted)

        except Exception as e:
            logger.warning(f"Document search failed: {e}")
            return None

    async def _get_recent_history(
        self,
        bot_id: str,
        chat_id: str | None,
    ) -> str | None:
        """Get recent conversation history."""
        if not chat_id:
            return None

        try:
            messages = await self._repo.get_bot_messages(
                bot_id=bot_id,
                chat_id=chat_id,
                limit=self.max_history_messages,
            )

            if not messages:
                return None

            # Format as conversation summary with message IDs for citation
            formatted = []
            for msg in messages:
                role = "User" if msg.role == "user" else "Assistant"
                # Truncate long messages
                content = msg.content[:300] + "..." if len(msg.content) > 300 else msg.content
                formatted.append(f"[{msg.id}] {role}: {content}")

            return "\n".join(formatted)

        except Exception as e:
            logger.warning(f"History retrieval failed: {e}")
            return None

    async def build_enhanced_system_prompt(
        self,
        base_prompt: str | None,
        bot_id: str,
        user_message: str,
        chat_id: str | None = None,
        include_contacts: bool = False,
        enabled_skills: list[str] | None = None,
    ) -> str:
        """
        Build a complete system prompt with knowledge context.

        Args:
            base_prompt: Base system prompt (bot personality)
            bot_id: Bot ID for context retrieval
            user_message: Current user message
            chat_id: Current chat ID
            include_contacts: Whether to include contacts (contacts capability)
            enabled_skills: List of enabled skill IDs (or None to auto-fetch from bot)

        Returns:
            Enhanced system prompt with knowledge context
        """
        if not base_prompt:
            base_prompt = "You are a helpful AI assistant."

        # Build context
        context = await self.build_context(
            bot_id, user_message, chat_id, include_contacts, enabled_skills
        )
        context_section = context.to_prompt_section()

        if context_section:
            citation_instructions = (
                "\n\n---\n\n## Message Citations\n"
                "When referencing a specific earlier message from the conversation, use "
                "[cite:MESSAGE_ID] where MESSAGE_ID is the ID in brackets before each message "
                "in the history. This creates a visual reply link in the chat. Only cite when "
                "it genuinely clarifies which message you're referring to — don't overuse."
            )
            return f"{base_prompt}\n\n---\n\n{context_section}{citation_instructions}"

        return base_prompt


# Singleton instance
_builder: ContextBuilder | None = None


def get_context_builder() -> ContextBuilder:
    """Get the shared ContextBuilder instance."""
    global _builder
    if _builder is None:
        _builder = ContextBuilder()
    return _builder

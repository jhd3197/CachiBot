"""
Repository Classes for Data Access

Provides async CRUD operations using SQLAlchemy ORM with AsyncSession.
Migrated from raw aiosqlite queries to PostgreSQL via SQLAlchemy 2.0.
"""

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import delete, func, select, update

from cachibot.models.bot import Bot
from cachibot.models.capabilities import Contact
from cachibot.models.chat import ChatMessage, MessageRole
from cachibot.models.chat_model import Chat
from cachibot.models.connection import BotConnection, ConnectionPlatform, ConnectionStatus
from cachibot.models.job import Job, JobStatus
from cachibot.models.knowledge import (
    BotInstruction,
    BotMessage,
    BotNote,
    DocChunk,
    Document,
    DocumentStatus,
    NoteSource,
)
from cachibot.models.platform_tools import PlatformToolConfig as PlatformToolConfigSchema
from cachibot.models.platform_tools import PlatformToolConfigUpdate
from cachibot.models.skill import BotSkillActivation, SkillDefinition, SkillSource
from cachibot.storage import db
from cachibot.storage.models.bot import Bot as BotModel
from cachibot.storage.models.chat import Chat as ChatModel
from cachibot.storage.models.connection import BotConnection as BotConnectionModel
from cachibot.storage.models.contact import BotContact as BotContactModel
from cachibot.storage.models.job import Job as JobModel
from cachibot.storage.models.knowledge import (
    BotDocument as BotDocumentModel,
)
from cachibot.storage.models.knowledge import (
    BotInstruction as BotInstructionModel,
)
from cachibot.storage.models.knowledge import (
    BotNote as BotNoteModel,
)
from cachibot.storage.models.knowledge import (
    DocChunk as DocChunkModel,
)
from cachibot.storage.models.message import BotMessage as BotMessageModel
from cachibot.storage.models.message import Message as MessageModel
from cachibot.storage.models.platform_config import PlatformToolConfig as PlatformToolConfigModel
from cachibot.storage.models.skill import BotSkill as BotSkillModel
from cachibot.storage.models.skill import Skill as SkillModel

logger = logging.getLogger("cachibot.storage.repository")


def _escape_like(value: str) -> str:
    """Escape special characters for LIKE patterns."""
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class MessageRepository:
    """Repository for chat messages."""

    async def save_message(self, message: ChatMessage) -> None:
        """Save a message to the database."""
        async with db.ensure_initialized()() as session:
            obj = MessageModel(
                id=message.id,
                role=message.role.value,
                content=message.content,
                timestamp=message.timestamp,
                meta=message.metadata,
            )
            session.add(obj)
            await session.commit()

    async def get_message(self, message_id: str) -> ChatMessage | None:
        """Get a message by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(MessageModel).where(MessageModel.id == message_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return ChatMessage(
            id=row.id,
            role=MessageRole(row.role),
            content=row.content,
            timestamp=row.timestamp,
            metadata=row.meta,
        )

    async def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """Get messages with pagination."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(MessageModel)
                .order_by(MessageModel.timestamp.desc())
                .limit(limit)
                .offset(offset)
            )
            rows = result.scalars().all()

        return [
            ChatMessage(
                id=row.id,
                role=MessageRole(row.role),
                content=row.content,
                timestamp=row.timestamp,
                metadata=row.meta,
            )
            for row in reversed(rows)  # Return in chronological order
        ]

    async def get_message_count(self) -> int:
        """Get total message count."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(func.count()).select_from(MessageModel))
            return result.scalar_one()

    async def clear_messages(self) -> None:
        """Delete all messages."""
        async with db.ensure_initialized()() as session:
            await session.execute(delete(MessageModel))
            await session.commit()


class JobRepository:
    """Repository for jobs/tasks.

    .. deprecated::
        This repository is part of the legacy job system. New code should use
        ``WorkRepository`` and ``ExecutionLogRepository`` from
        ``cachibot.storage.automations_repository`` instead.
    """

    async def save_job(self, job: Job) -> None:
        """Save a job to the database."""
        async with db.ensure_initialized()() as session:
            obj = JobModel(
                id=job.id,
                status=job.status.value,
                message_id=job.message_id,
                created_at=job.created_at,
                started_at=job.started_at,
                completed_at=job.completed_at,
                result=job.result,
                error=job.error,
                progress=job.progress,
            )
            session.add(obj)
            await session.commit()

    async def update_job(self, job: Job) -> None:
        """Update an existing job."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(JobModel)
                .where(JobModel.id == job.id)
                .values(
                    status=job.status.value,
                    started_at=job.started_at,
                    completed_at=job.completed_at,
                    result=job.result,
                    error=job.error,
                    progress=job.progress,
                )
            )
            await session.commit()

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(JobModel).where(JobModel.id == job_id))
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._row_to_job(row)

    async def get_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """Get jobs with optional status filter."""
        stmt = select(JobModel)
        if status:
            stmt = stmt.where(JobModel.status == status.value)
        stmt = stmt.order_by(JobModel.created_at.desc()).limit(limit)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._row_to_job(row) for row in rows]

    def _row_to_job(self, row: JobModel) -> Job:
        """Convert a database row to a Job object."""
        return Job(
            id=row.id,
            status=JobStatus(row.status),
            message_id=row.message_id,
            created_at=row.created_at,
            started_at=row.started_at,
            completed_at=row.completed_at,
            result=row.result,
            error=row.error,
            progress=row.progress,
        )


class KnowledgeRepository:
    """Repository for knowledge base data (messages, instructions, documents, chunks)."""

    # ===== BOT MESSAGES =====

    async def save_bot_message(self, message: BotMessage) -> None:
        """Save a message to bot's conversation history."""
        async with db.ensure_initialized()() as session:
            obj = BotMessageModel(
                id=message.id,
                bot_id=message.bot_id,
                chat_id=message.chat_id,
                role=message.role,
                content=message.content,
                timestamp=message.timestamp,
                meta=message.metadata,
                reply_to_id=message.reply_to_id,
            )
            session.add(obj)
            await session.commit()

    async def get_bot_messages(
        self,
        bot_id: str,
        chat_id: str,
        limit: int = 50,
    ) -> list[BotMessage]:
        """Get messages for a specific bot and chat."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotMessageModel)
                .where(
                    BotMessageModel.bot_id == bot_id,
                    BotMessageModel.chat_id == chat_id,
                )
                .order_by(BotMessageModel.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()

        return [
            BotMessage(
                id=row.id,
                bot_id=row.bot_id,
                chat_id=row.chat_id,
                role=row.role,
                content=row.content,
                timestamp=row.timestamp,
                metadata=row.meta,
                reply_to_id=row.reply_to_id,
            )
            for row in reversed(rows)  # Return in chronological order
        ]

    async def get_recent_bot_messages(
        self,
        bot_id: str,
        limit: int = 20,
    ) -> list[BotMessage]:
        """Get recent messages across all chats for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotMessageModel)
                .where(BotMessageModel.bot_id == bot_id)
                .order_by(BotMessageModel.timestamp.desc())
                .limit(limit)
            )
            rows = result.scalars().all()

        return [
            BotMessage(
                id=row.id,
                bot_id=row.bot_id,
                chat_id=row.chat_id,
                role=row.role,
                content=row.content,
                timestamp=row.timestamp,
                metadata=row.meta,
                reply_to_id=row.reply_to_id,
            )
            for row in reversed(rows)
        ]

    async def delete_all_messages_for_bot(self, bot_id: str) -> int:
        """Delete all messages for a bot. Returns number of messages deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotMessageModel).where(BotMessageModel.bot_id == bot_id)
            )
            await session.commit()
            return result.rowcount

    async def delete_messages_for_chat(self, bot_id: str, chat_id: str) -> int:
        """Delete all messages for a specific chat. Returns number deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotMessageModel).where(
                    BotMessageModel.bot_id == bot_id,
                    BotMessageModel.chat_id == chat_id,
                )
            )
            await session.commit()
            return result.rowcount

    async def get_message_count_for_bot(self, bot_id: str) -> int:
        """Get the count of messages for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(func.count())
                .select_from(BotMessageModel)
                .where(BotMessageModel.bot_id == bot_id)
            )
            return result.scalar_one()

    # ===== BOT INSTRUCTIONS =====

    async def get_instructions(self, bot_id: str) -> BotInstruction | None:
        """Get custom instructions for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotInstructionModel).where(BotInstructionModel.bot_id == bot_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return BotInstruction(
            id=row.id,
            bot_id=row.bot_id,
            content=row.content,
            updated_at=row.updated_at,
        )

    async def upsert_instructions(self, bot_id: str, content: str) -> BotInstruction:
        """Create or update instructions for a bot."""
        now = datetime.now(timezone.utc)

        # Try to get existing
        existing = await self.get_instructions(bot_id)

        async with db.ensure_initialized()() as session:
            if existing:
                await session.execute(
                    update(BotInstructionModel)
                    .where(BotInstructionModel.bot_id == bot_id)
                    .values(content=content, updated_at=now)
                )
                instruction_id = existing.id
            else:
                instruction_id = str(uuid.uuid4())
                obj = BotInstructionModel(
                    id=instruction_id,
                    bot_id=bot_id,
                    content=content,
                    updated_at=now,
                )
                session.add(obj)

            await session.commit()

        return BotInstruction(
            id=instruction_id,
            bot_id=bot_id,
            content=content,
            updated_at=now,
        )

    async def delete_instructions(self, bot_id: str) -> bool:
        """Delete instructions for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotInstructionModel).where(BotInstructionModel.bot_id == bot_id)
            )
            await session.commit()
            return result.rowcount > 0

    # ===== DOCUMENTS =====

    async def save_document(self, doc: Document) -> None:
        """Save document metadata."""
        async with db.ensure_initialized()() as session:
            obj = BotDocumentModel(
                id=doc.id,
                bot_id=doc.bot_id,
                filename=doc.filename,
                file_type=doc.file_type,
                file_hash=doc.file_hash,
                file_size=doc.file_size,
                chunk_count=doc.chunk_count,
                status=doc.status.value,
                uploaded_at=doc.uploaded_at,
                processed_at=doc.processed_at,
            )
            session.add(obj)
            await session.commit()

    async def get_document(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotDocumentModel).where(BotDocumentModel.id == document_id)
            )
            row = result.scalar_one_or_none()

        if row is None:
            return None

        return self._row_to_document(row)

    async def get_documents_by_bot(self, bot_id: str) -> list[Document]:
        """Get all documents for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotDocumentModel)
                .where(BotDocumentModel.bot_id == bot_id)
                .order_by(BotDocumentModel.uploaded_at.desc())
            )
            rows = result.scalars().all()

        return [self._row_to_document(row) for row in rows]

    async def document_exists_by_hash(self, bot_id: str, file_hash: str) -> bool:
        """Check if a document with this hash already exists for the bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotDocumentModel.id).where(
                    BotDocumentModel.bot_id == bot_id,
                    BotDocumentModel.file_hash == file_hash,
                )
            )
            return result.scalar_one_or_none() is not None

    async def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        chunk_count: int | None = None,
    ) -> None:
        """Update document processing status."""
        now = datetime.now(timezone.utc)
        values: dict = {"status": status.value, "processed_at": now}
        if chunk_count is not None:
            values["chunk_count"] = chunk_count

        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotDocumentModel).where(BotDocumentModel.id == document_id).values(**values)
            )
            await session.commit()

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""
        async with db.ensure_initialized()() as session:
            # Chunks deleted via CASCADE
            result = await session.execute(
                delete(BotDocumentModel).where(BotDocumentModel.id == document_id)
            )
            await session.commit()
            return result.rowcount > 0

    def _row_to_document(self, row: BotDocumentModel) -> Document:
        """Convert a database row to Document."""
        return Document(
            id=row.id,
            bot_id=row.bot_id,
            filename=row.filename,
            file_type=row.file_type,
            file_hash=row.file_hash,
            file_size=row.file_size,
            chunk_count=row.chunk_count,
            status=DocumentStatus(row.status),
            uploaded_at=row.uploaded_at,
            processed_at=row.processed_at,
        )

    # ===== DOCUMENT CHUNKS =====

    async def save_chunks(self, chunks: list[DocChunk]) -> None:
        """Save document chunks (batch insert)."""
        if not chunks:
            return

        async with db.ensure_initialized()() as session:
            session.add_all(
                [
                    DocChunkModel(
                        id=chunk.id,
                        document_id=chunk.document_id,
                        bot_id=chunk.bot_id,
                        chunk_index=chunk.chunk_index,
                        content=chunk.content,
                        embedding=chunk.embedding,
                    )
                    for chunk in chunks
                ]
            )
            await session.commit()

    async def get_chunks_by_document(self, document_id: str) -> list[DocChunk]:
        """Get all chunks for a document."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(DocChunkModel)
                .where(DocChunkModel.document_id == document_id)
                .order_by(DocChunkModel.chunk_index)
            )
            rows = result.scalars().all()

        return [
            DocChunk(
                id=row.id,
                document_id=row.document_id,
                bot_id=row.bot_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
            )
            for row in rows
        ]

    async def get_all_chunks_by_bot(self, bot_id: str) -> list[DocChunk]:
        """Get all chunks for a bot (for vector search)."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(DocChunkModel)
                .where(DocChunkModel.bot_id == bot_id)
                .order_by(DocChunkModel.document_id, DocChunkModel.chunk_index)
            )
            rows = result.scalars().all()

        return [
            DocChunk(
                id=row.id,
                document_id=row.document_id,
                bot_id=row.bot_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
            )
            for row in rows
        ]

    async def delete_chunks_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(DocChunkModel).where(DocChunkModel.document_id == document_id)
            )
            await session.commit()
            return result.rowcount

    # ===== KNOWLEDGE STATS =====

    async def get_knowledge_stats(self, bot_id: str) -> dict:
        """Get aggregated knowledge stats for a bot."""
        async with db.ensure_initialized()() as session:
            # Document counts by status
            doc_result = await session.execute(
                select(BotDocumentModel.status, func.count())
                .where(BotDocumentModel.bot_id == bot_id)
                .group_by(BotDocumentModel.status)
            )
            doc_counts = {row[0]: row[1] for row in doc_result.all()}

            # Total chunks
            chunk_result = await session.execute(
                select(func.count())
                .select_from(DocChunkModel)
                .where(DocChunkModel.bot_id == bot_id)
            )
            total_chunks = chunk_result.scalar_one()

            # Total notes
            note_result = await session.execute(
                select(func.count()).select_from(BotNoteModel).where(BotNoteModel.bot_id == bot_id)
            )
            total_notes = note_result.scalar_one()

            # Instructions
            instr_result = await session.execute(
                select(BotInstructionModel.id).where(BotInstructionModel.bot_id == bot_id)
            )
            has_instructions = instr_result.scalar_one_or_none() is not None

        return {
            "total_documents": sum(doc_counts.values()),
            "documents_ready": doc_counts.get("ready", 0),
            "documents_processing": doc_counts.get("processing", 0),
            "documents_failed": doc_counts.get("failed", 0),
            "total_chunks": total_chunks,
            "total_notes": total_notes,
            "has_instructions": has_instructions,
        }

    async def reset_document_for_retry(self, document_id: str) -> bool:
        """Reset a failed document to processing status for retry."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotDocumentModel)
                .where(
                    BotDocumentModel.id == document_id,
                    BotDocumentModel.status == "failed",
                )
                .values(status="processing", processed_at=None, chunk_count=0)
            )
            # Also delete existing chunks
            await session.execute(
                delete(DocChunkModel).where(DocChunkModel.document_id == document_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def get_chunks_by_document_light(self, document_id: str) -> list[dict]:
        """Get chunks for a document without embedding BLOBs."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    DocChunkModel.id,
                    DocChunkModel.document_id,
                    DocChunkModel.chunk_index,
                    DocChunkModel.content,
                )
                .where(DocChunkModel.document_id == document_id)
                .order_by(DocChunkModel.chunk_index)
            )
            rows = result.all()

        return [
            {
                "id": row[0],
                "document_id": row[1],
                "chunk_index": row[2],
                "content": row[3],
            }
            for row in rows
        ]

    async def get_all_embeddings_by_bot(self, bot_id: str) -> list[dict]:
        """Get only embedding data for vector search (no content)."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(
                    DocChunkModel.id,
                    DocChunkModel.document_id,
                    DocChunkModel.embedding,
                ).where(
                    DocChunkModel.bot_id == bot_id,
                    DocChunkModel.embedding.isnot(None),
                )
            )
            rows = result.all()

        return [
            {
                "id": row[0],
                "document_id": row[1],
                "embedding": row[2],
            }
            for row in rows
        ]

    async def get_chunks_by_ids(self, chunk_ids: list[str]) -> list[DocChunk]:
        """Fetch specific chunks by ID list."""
        if not chunk_ids:
            return []

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(DocChunkModel).where(DocChunkModel.id.in_(chunk_ids))
            )
            rows = result.scalars().all()

        return [
            DocChunk(
                id=row.id,
                document_id=row.document_id,
                bot_id=row.bot_id,
                chunk_index=row.chunk_index,
                content=row.content,
                embedding=row.embedding,
            )
            for row in rows
        ]


class NotesRepository:
    """Repository for bot notes (persistent memory)."""

    async def save_note(self, note: BotNote) -> None:
        """Save a new note."""
        async with db.ensure_initialized()() as session:
            obj = BotNoteModel(
                id=note.id,
                bot_id=note.bot_id,
                title=note.title,
                content=note.content,
                tags=note.tags,
                source=note.source.value,
                created_at=note.created_at,
                updated_at=note.updated_at,
            )
            session.add(obj)
            await session.commit()

    async def get_note(self, note_id: str) -> BotNote | None:
        """Get a note by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(BotNoteModel).where(BotNoteModel.id == note_id))
            row = result.scalar_one_or_none()
        return self._row_to_note(row) if row else None

    async def get_notes_by_bot(
        self,
        bot_id: str,
        tags_filter: list[str] | None = None,
        search: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[BotNote]:
        """Get notes for a bot with optional tag filtering and search."""
        stmt = select(BotNoteModel).where(BotNoteModel.bot_id == bot_id)

        if tags_filter:
            from sqlalchemy import or_

            from cachibot.storage.db import db_type as _db_type

            if _db_type == "postgresql":
                # PostgreSQL JSONB containment operator
                tag_conditions = [BotNoteModel.tags.contains([tag]) for tag in tags_filter]
                stmt = stmt.where(or_(*tag_conditions))
            else:
                # SQLite: use JSON_EACH + LIKE fallback for JSON arrays
                # Cast tags column to text and check if any tag substring is present
                from sqlalchemy import String as SAString
                from sqlalchemy import cast

                tag_conditions = [
                    cast(BotNoteModel.tags, SAString).like(f'%"{_escape_like(tag)}"%', escape="\\")
                    for tag in tags_filter
                ]
                stmt = stmt.where(or_(*tag_conditions))

        if search:
            escaped = _escape_like(search)
            stmt = stmt.where(
                BotNoteModel.title.ilike(f"%{escaped}%", escape="\\")
                | BotNoteModel.content.ilike(f"%{escaped}%", escape="\\")
            )

        stmt = stmt.order_by(BotNoteModel.updated_at.desc()).limit(limit).offset(offset)

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()

        return [self._row_to_note(row) for row in rows]

    async def update_note(
        self,
        note_id: str,
        title: str | None = None,
        content: str | None = None,
        tags: list[str] | None = None,
    ) -> BotNote | None:
        """Partial update of a note."""
        now = datetime.now(timezone.utc)
        values: dict = {"updated_at": now}

        if title is not None:
            values["title"] = title
        if content is not None:
            values["content"] = content
        if tags is not None:
            values["tags"] = tags

        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotNoteModel).where(BotNoteModel.id == note_id).values(**values)
            )
            await session.commit()

        if result.rowcount == 0:
            return None
        return await self.get_note(note_id)

    async def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(BotNoteModel).where(BotNoteModel.id == note_id))
            await session.commit()
            return result.rowcount > 0

    async def get_all_tags(self, bot_id: str) -> list[str]:
        """Get all unique tags across all notes for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotNoteModel.tags).where(BotNoteModel.bot_id == bot_id)
            )
            rows = result.scalars().all()

        all_tags: set[str] = set()
        for tags in rows:
            if tags:
                all_tags.update(tags)
        return sorted(all_tags)

    async def search_notes(self, bot_id: str, query: str, limit: int = 10) -> list[BotNote]:
        """Simple text search on title + content."""
        escaped = _escape_like(query)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotNoteModel)
                .where(
                    BotNoteModel.bot_id == bot_id,
                    BotNoteModel.title.ilike(f"%{escaped}%", escape="\\")
                    | BotNoteModel.content.ilike(f"%{escaped}%", escape="\\"),
                )
                .order_by(BotNoteModel.updated_at.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
        return [self._row_to_note(row) for row in rows]

    def _row_to_note(self, row: BotNoteModel) -> BotNote:
        """Convert a database row to BotNote."""
        return BotNote(
            id=row.id,
            bot_id=row.bot_id,
            title=row.title,
            content=row.content,
            tags=row.tags if row.tags else [],
            source=NoteSource(row.source),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ContactsRepository:
    """Repository for bot contacts."""

    async def save_contact(self, contact: Contact) -> None:
        """Save a new contact."""
        async with db.ensure_initialized()() as session:
            obj = BotContactModel(
                id=contact.id,
                bot_id=contact.bot_id,
                name=contact.name,
                details=contact.details,
                created_at=contact.created_at,
                updated_at=contact.updated_at,
            )
            session.add(obj)
            await session.commit()

    async def get_contact(self, contact_id: str) -> Contact | None:
        """Get a contact by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotContactModel).where(BotContactModel.id == contact_id)
            )
            row = result.scalar_one_or_none()
            return self._row_to_contact(row) if row else None

    async def get_contacts_by_bot(self, bot_id: str) -> list[Contact]:
        """Get all contacts for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotContactModel)
                .where(BotContactModel.bot_id == bot_id)
                .order_by(BotContactModel.name)
            )
            rows = result.scalars().all()
            return [self._row_to_contact(row) for row in rows]

    async def update_contact(self, contact: Contact) -> None:
        """Update an existing contact."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotContactModel)
                .where(BotContactModel.id == contact.id)
                .values(
                    name=contact.name,
                    details=contact.details,
                    updated_at=contact.updated_at,
                )
            )
            await session.commit()

    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact by ID. Returns True if deleted, False if not found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotContactModel).where(BotContactModel.id == contact_id)
            )
            await session.commit()
            return result.rowcount > 0

    def _row_to_contact(self, row: BotContactModel) -> Contact:
        """Convert database row to Contact model."""
        return Contact(
            id=row.id,
            bot_id=row.bot_id,
            name=row.name,
            details=row.details,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class ConnectionRepository:
    """Repository for bot platform connections."""

    async def save_connection(self, connection: BotConnection) -> None:
        """Save a new connection."""
        from cachibot.services.encryption import get_encryption_service

        enc = get_encryption_service()
        encrypted_config = enc.encrypt_connection_config(connection.config, connection.bot_id)

        async with db.ensure_initialized()() as session:
            obj = BotConnectionModel(
                id=connection.id,
                bot_id=connection.bot_id,
                platform=connection.platform.value,
                name=connection.name,
                status=connection.status.value,
                config_encrypted=encrypted_config,
                message_count=connection.message_count,
                last_activity=connection.last_activity,
                error=connection.error,
                auto_connect=connection.auto_connect,
                created_at=connection.created_at,
                updated_at=connection.updated_at,
            )
            session.add(obj)
            await session.commit()

    async def get_connection(self, connection_id: str) -> BotConnection | None:
        """Get a connection by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotConnectionModel).where(BotConnectionModel.id == connection_id)
            )
            row = result.scalar_one_or_none()
            return self._row_to_connection(row) if row else None

    async def get_connections_by_bot(self, bot_id: str) -> list[BotConnection]:
        """Get all connections for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotConnectionModel)
                .where(BotConnectionModel.bot_id == bot_id)
                .order_by(BotConnectionModel.created_at.desc())
            )
            rows = result.scalars().all()
            return [self._row_to_connection(row) for row in rows]

    async def get_all_connected(self) -> list[BotConnection]:
        """Get all connections with 'connected' status."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotConnectionModel).where(
                    BotConnectionModel.status == ConnectionStatus.connected.value
                )
            )
            rows = result.scalars().all()
            return [self._row_to_connection(row) for row in rows]

    async def update_connection(self, connection: BotConnection) -> None:
        """Update an existing connection."""
        from cachibot.services.encryption import get_encryption_service

        enc = get_encryption_service()
        encrypted_config = enc.encrypt_connection_config(connection.config, connection.bot_id)

        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotConnectionModel)
                .where(BotConnectionModel.id == connection.id)
                .values(
                    name=connection.name,
                    status=connection.status.value,
                    config_encrypted=encrypted_config,
                    message_count=connection.message_count,
                    last_activity=connection.last_activity,
                    error=connection.error,
                    updated_at=connection.updated_at,
                )
            )
            await session.commit()

    async def update_connection_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        error: str | None = None,
    ) -> None:
        """Update connection status and optionally error message."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotConnectionModel)
                .where(BotConnectionModel.id == connection_id)
                .values(
                    status=status.value,
                    error=error,
                    updated_at=now,
                )
            )
            await session.commit()

    async def increment_message_count(self, connection_id: str) -> None:
        """Increment message count and update last_activity."""
        try:
            now = datetime.now(timezone.utc)
            async with db.ensure_initialized()() as session:
                await session.execute(
                    update(BotConnectionModel)
                    .where(BotConnectionModel.id == connection_id)
                    .values(
                        message_count=BotConnectionModel.message_count + 1,
                        last_activity=now,
                        updated_at=now,
                    )
                )
                await session.commit()
        except Exception:
            logger.warning(
                "Failed to increment message count for chat %s",
                connection_id,
                exc_info=True,
            )

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection by ID. Returns True if deleted, False if not found."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotConnectionModel).where(BotConnectionModel.id == connection_id)
            )
            await session.commit()
            return result.rowcount > 0

    async def bulk_reset_connected(self) -> int:
        """Reset all non-disconnected connections to disconnected in a single query."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(BotConnectionModel)
                .where(
                    BotConnectionModel.status.in_(
                        [
                            ConnectionStatus.connected.value,
                            ConnectionStatus.connecting.value,
                            ConnectionStatus.error.value,
                        ]
                    )
                )
                .values(status=ConnectionStatus.disconnected.value, updated_at=now)
            )
            await session.commit()
            return result.rowcount

    async def get_auto_connect_connections(self) -> list[BotConnection]:
        """Get all connections marked for auto-connect."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotConnectionModel).where(BotConnectionModel.auto_connect.is_(True))
            )
            rows = result.scalars().all()
            return [self._row_to_connection(row) for row in rows]

    async def set_auto_connect(self, connection_id: str, auto_connect: bool) -> None:
        """Set the auto_connect flag for a connection."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(BotConnectionModel)
                .where(BotConnectionModel.id == connection_id)
                .values(auto_connect=auto_connect, updated_at=now)
            )
            await session.commit()

    def _row_to_connection(self, row: BotConnectionModel) -> BotConnection:
        """Convert database row to BotConnection model."""
        from cachibot.services.encryption import get_encryption_service

        enc = get_encryption_service()
        config = enc.decrypt_connection_config(row.config_encrypted, row.bot_id)

        return BotConnection(
            id=row.id,
            bot_id=row.bot_id,
            platform=ConnectionPlatform(row.platform),
            name=row.name,
            status=ConnectionStatus(row.status),
            config=config,
            message_count=row.message_count,
            last_activity=row.last_activity,
            error=row.error,
            auto_connect=getattr(row, "auto_connect", False),
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class BotRepository:
    """Repository for bot configuration (synced from frontend)."""

    async def upsert_bot(self, bot: Bot) -> None:
        """Create or update a bot."""
        async with db.ensure_initialized()() as session:
            existing = await session.get(BotModel, bot.id)
            if existing:
                existing.name = bot.name
                existing.description = bot.description
                existing.icon = bot.icon
                existing.color = bot.color
                existing.model = bot.model
                existing.system_prompt = bot.system_prompt
                existing.capabilities = bot.capabilities
                existing.models = bot.models
                existing.updated_at = bot.updated_at
            else:
                session.add(
                    BotModel(
                        id=bot.id,
                        name=bot.name,
                        description=bot.description,
                        icon=bot.icon,
                        color=bot.color,
                        model=bot.model,
                        system_prompt=bot.system_prompt,
                        capabilities=bot.capabilities,
                        models=bot.models,
                        created_at=bot.created_at,
                        updated_at=bot.updated_at,
                    )
                )
            await session.commit()

    async def get_bot(self, bot_id: str) -> Bot | None:
        """Get a bot by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(BotModel).where(BotModel.id == bot_id))
            row = result.scalar_one_or_none()
            return self._row_to_bot(row) if row else None

    async def get_all_bots(self) -> list[Bot]:
        """Get all bots."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(BotModel).order_by(BotModel.name))
            rows = result.scalars().all()
            return [self._row_to_bot(row) for row in rows]

    async def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(BotModel).where(BotModel.id == bot_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_bot(self, row: BotModel) -> Bot:
        """Convert database row to Bot model."""
        return Bot(
            id=row.id,
            name=row.name,
            description=row.description,
            icon=row.icon,
            color=row.color,
            model=row.model,
            systemPrompt=row.system_prompt,
            capabilities=row.capabilities if row.capabilities else {},
            models=row.models,
            createdAt=row.created_at,
            updatedAt=row.updated_at,
        )


class ChatRepository:
    """Repository for chats (including platform conversations)."""

    async def create_chat(self, chat: Chat) -> None:
        """Create a new chat."""
        async with db.ensure_initialized()() as session:
            obj = ChatModel(
                id=chat.id,
                bot_id=chat.bot_id,
                title=chat.title,
                platform=chat.platform,
                platform_chat_id=chat.platform_chat_id,
                pinned=chat.pinned,
                archived=chat.archived,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
            )
            session.add(obj)
            await session.commit()

    async def get_chat(self, chat_id: str) -> Chat | None:
        """Get a chat by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(ChatModel).where(ChatModel.id == chat_id))
            row = result.scalar_one_or_none()
            return self._row_to_chat(row) if row else None

    async def get_or_create_platform_chat(
        self,
        bot_id: str,
        platform: str,
        platform_chat_id: str,
        title: str | None = None,
    ) -> Chat | None:
        """
        Get or create a chat for a platform conversation.

        Returns None if the chat exists but is archived (won't recreate archived chats).
        """
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(ChatModel).where(
                    ChatModel.bot_id == bot_id,
                    ChatModel.platform == platform,
                    ChatModel.platform_chat_id == platform_chat_id,
                )
            )
            row = result.scalar_one_or_none()
            if row:
                chat = self._row_to_chat(row)
                # Return None for archived chats - don't process messages
                if chat.archived:
                    return None
                return chat

            # Create new chat inside the same session to avoid race condition
            now = datetime.now(timezone.utc)
            chat = Chat(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                title=title or f"{platform.title()} Chat",
                platform=platform,
                platform_chat_id=platform_chat_id,
                pinned=False,
                archived=False,
                created_at=now,
                updated_at=now,
            )
            obj = ChatModel(
                id=chat.id,
                bot_id=chat.bot_id,
                title=chat.title,
                platform=chat.platform,
                platform_chat_id=chat.platform_chat_id,
                pinned=chat.pinned,
                archived=chat.archived,
                created_at=chat.created_at,
                updated_at=chat.updated_at,
            )
            session.add(obj)
            await session.commit()
            return chat

    async def get_chats_by_bot(self, bot_id: str, include_archived: bool = False) -> list[Chat]:
        """Get all chats for a bot. Excludes archived by default."""
        stmt = select(ChatModel).where(ChatModel.bot_id == bot_id)
        if not include_archived:
            stmt = stmt.where(ChatModel.archived.is_(False))
        stmt = stmt.order_by(ChatModel.pinned.desc(), ChatModel.updated_at.desc())

        async with db.ensure_initialized()() as session:
            result = await session.execute(stmt)
            rows = result.scalars().all()
            return [self._row_to_chat(row) for row in rows]

    async def update_chat(self, chat: Chat) -> None:
        """Update a chat."""
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(ChatModel)
                .where(ChatModel.id == chat.id)
                .values(
                    title=chat.title,
                    pinned=chat.pinned,
                    archived=chat.archived,
                    updated_at=chat.updated_at,
                )
            )
            await session.commit()

    async def archive_chat(self, chat_id: str, archived: bool = True) -> bool:
        """Archive or unarchive a chat. Returns True if chat was found."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                update(ChatModel)
                .where(ChatModel.id == chat_id)
                .values(archived=archived, updated_at=now)
            )
            await session.commit()
            return result.rowcount > 0

    async def update_chat_timestamp(self, chat_id: str) -> None:
        """Update the chat's updated_at timestamp."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            await session.execute(
                update(ChatModel).where(ChatModel.id == chat_id).values(updated_at=now)
            )
            await session.commit()

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(ChatModel).where(ChatModel.id == chat_id))
            await session.commit()
            return result.rowcount > 0

    async def delete_all_chats_for_bot(self, bot_id: str) -> int:
        """Delete all chats for a bot. Returns number of chats deleted."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(ChatModel).where(ChatModel.bot_id == bot_id))
            await session.commit()
            return result.rowcount

    def _row_to_chat(self, row: ChatModel) -> Chat:
        """Convert database row to Chat model."""
        return Chat(
            id=row.id,
            bot_id=row.bot_id,
            title=row.title,
            platform=row.platform,
            platform_chat_id=row.platform_chat_id,
            pinned=row.pinned,
            archived=row.archived,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )


class SkillsRepository:
    """Repository for skill definitions and bot skill activations."""

    # ===== SKILLS =====

    async def upsert_skill(self, skill: SkillDefinition) -> None:
        """Create or update a skill definition."""
        now = datetime.now(timezone.utc)

        async with db.ensure_initialized()() as session:
            existing = await session.get(SkillModel, skill.id)
            if existing:
                existing.name = skill.name
                existing.description = skill.description
                existing.version = skill.version
                existing.author = skill.author
                existing.tags = skill.tags
                existing.requires_tools = skill.requires_tools
                existing.instructions = skill.instructions
                existing.source = skill.source.value
                existing.filepath = skill.filepath
                existing.updated_at = now
            else:
                session.add(
                    SkillModel(
                        id=skill.id,
                        name=skill.name,
                        description=skill.description,
                        version=skill.version,
                        author=skill.author,
                        tags=skill.tags,
                        requires_tools=skill.requires_tools,
                        instructions=skill.instructions,
                        source=skill.source.value,
                        filepath=skill.filepath,
                        created_at=now,
                        updated_at=now,
                    )
                )
            await session.commit()

    async def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """Get a skill by ID."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(SkillModel).where(SkillModel.id == skill_id))
            row = result.scalar_one_or_none()
            return self._row_to_skill(row) if row else None

    async def get_all_skills(self) -> list[SkillDefinition]:
        """Get all skill definitions."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(select(SkillModel).order_by(SkillModel.name))
            rows = result.scalars().all()
            return [self._row_to_skill(row) for row in rows]

    async def get_skills_by_source(self, source: SkillSource) -> list[SkillDefinition]:
        """Get skills filtered by source."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(SkillModel)
                .where(SkillModel.source == source.value)
                .order_by(SkillModel.name)
            )
            rows = result.scalars().all()
            return [self._row_to_skill(row) for row in rows]

    async def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill by ID. Also removes all bot activations."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(delete(SkillModel).where(SkillModel.id == skill_id))
            await session.commit()
            return result.rowcount > 0

    def _row_to_skill(self, row: SkillModel) -> SkillDefinition:
        """Convert database row to SkillDefinition model."""
        return SkillDefinition(
            id=row.id,
            name=row.name,
            description=row.description or "",
            version=row.version or "1.0.0",
            author=row.author,
            tags=row.tags if row.tags else [],
            requires_tools=row.requires_tools if row.requires_tools else [],
            instructions=row.instructions,
            source=SkillSource(row.source) if row.source else SkillSource.LOCAL,
            filepath=row.filepath,
        )

    # ===== BOT SKILL ACTIVATIONS =====

    async def get_bot_skills(self, bot_id: str) -> list[str]:
        """Get list of enabled skill IDs for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotSkillModel.skill_id).where(
                    BotSkillModel.bot_id == bot_id,
                    BotSkillModel.enabled.is_(True),
                )
            )
            return [row[0] for row in result.all()]

    async def get_bot_skill_definitions(self, bot_id: str) -> list[SkillDefinition]:
        """Get full skill definitions for all enabled skills of a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(SkillModel)
                .join(BotSkillModel, SkillModel.id == BotSkillModel.skill_id)
                .where(
                    BotSkillModel.bot_id == bot_id,
                    BotSkillModel.enabled.is_(True),
                )
                .order_by(SkillModel.name)
            )
            rows = result.scalars().all()
            return [self._row_to_skill(row) for row in rows]

    async def activate_skill(self, bot_id: str, skill_id: str) -> None:
        """Activate a skill for a bot."""
        now = datetime.now(timezone.utc)

        async with db.ensure_initialized()() as session:
            existing = await session.get(BotSkillModel, (bot_id, skill_id))
            if existing:
                existing.enabled = True
                existing.activated_at = now
            else:
                session.add(
                    BotSkillModel(
                        bot_id=bot_id,
                        skill_id=skill_id,
                        enabled=True,
                        activated_at=now,
                    )
                )
            await session.commit()

    async def deactivate_skill(self, bot_id: str, skill_id: str) -> bool:
        """Deactivate a skill for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                delete(BotSkillModel).where(
                    BotSkillModel.bot_id == bot_id,
                    BotSkillModel.skill_id == skill_id,
                )
            )
            await session.commit()
            return result.rowcount > 0

    async def is_skill_activated(self, bot_id: str, skill_id: str) -> bool:
        """Check if a skill is activated for a bot."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotSkillModel.bot_id).where(
                    BotSkillModel.bot_id == bot_id,
                    BotSkillModel.skill_id == skill_id,
                    BotSkillModel.enabled.is_(True),
                )
            )
            return result.scalar_one_or_none() is not None

    async def get_skill_activation(self, bot_id: str, skill_id: str) -> BotSkillActivation | None:
        """Get activation details for a bot/skill pair."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(BotSkillModel).where(
                    BotSkillModel.bot_id == bot_id,
                    BotSkillModel.skill_id == skill_id,
                )
            )
            row = result.scalar_one_or_none()
            if row is None:
                return None
            return BotSkillActivation(
                bot_id=row.bot_id,
                skill_id=row.skill_id,
                enabled=row.enabled,
                activated_at=row.activated_at,
            )


class PlatformToolConfigRepository:
    """Repository for platform-wide tool visibility configuration."""

    _ROW_ID = "default"

    async def get_config(self) -> PlatformToolConfigSchema:
        """Return the global tool config, creating the default row if missing."""
        async with db.ensure_initialized()() as session:
            result = await session.execute(
                select(PlatformToolConfigModel).where(PlatformToolConfigModel.id == self._ROW_ID)
            )
            row = result.scalar_one_or_none()

        if row is None:
            # First access — upsert the default row
            return await self._upsert_default()

        return PlatformToolConfigSchema(
            disabled_capabilities=row.disabled_capabilities or [],
            disabled_skills=row.disabled_skills or [],
        )

    async def update_config(
        self,
        payload: PlatformToolConfigUpdate,
        user_id: str | None = None,
    ) -> PlatformToolConfigSchema:
        """Merge provided fields into the config row."""
        now = datetime.now(timezone.utc)

        # Ensure the row exists
        current = await self.get_config()

        caps = (
            payload.disabled_capabilities
            if payload.disabled_capabilities is not None
            else current.disabled_capabilities
        )
        skills = (
            payload.disabled_skills
            if payload.disabled_skills is not None
            else current.disabled_skills
        )

        async with db.ensure_initialized()() as session:
            await session.execute(
                update(PlatformToolConfigModel)
                .where(PlatformToolConfigModel.id == self._ROW_ID)
                .values(
                    disabled_capabilities=caps,
                    disabled_skills=skills,
                    updated_at=now,
                    updated_by=user_id,
                )
            )
            await session.commit()

        return PlatformToolConfigSchema(
            disabled_capabilities=caps,
            disabled_skills=skills,
        )

    async def get_disabled_capabilities(self) -> list[str]:
        """Convenience: return only the disabled capability keys."""
        cfg = await self.get_config()
        return cfg.disabled_capabilities

    async def get_disabled_skills(self) -> list[str]:
        """Convenience: return only the disabled skill IDs."""
        cfg = await self.get_config()
        return cfg.disabled_skills

    async def _upsert_default(self) -> PlatformToolConfigSchema:
        """Insert the default row if it doesn't exist."""
        now = datetime.now(timezone.utc)
        async with db.ensure_initialized()() as session:
            # Check again inside the session to avoid races
            result = await session.execute(
                select(PlatformToolConfigModel).where(PlatformToolConfigModel.id == self._ROW_ID)
            )
            existing = result.scalar_one_or_none()
            if existing:
                return PlatformToolConfigSchema(
                    disabled_capabilities=existing.disabled_capabilities or [],
                    disabled_skills=existing.disabled_skills or [],
                )

            session.add(
                PlatformToolConfigModel(
                    id=self._ROW_ID,
                    disabled_capabilities=[],
                    disabled_skills=[],
                    updated_at=now,
                )
            )
            await session.commit()

        return PlatformToolConfigSchema()

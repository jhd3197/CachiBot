"""
Repository Classes for Data Access

Provides async CRUD operations for messages and jobs.
"""

import json
from datetime import datetime

from cachibot.models.bot import Bot
from cachibot.models.capabilities import Contact
from cachibot.models.chat import ChatMessage, MessageRole
from cachibot.models.chat_model import Chat
from cachibot.models.connection import BotConnection, ConnectionPlatform, ConnectionStatus
from cachibot.models.job import Job, JobStatus
from cachibot.models.knowledge import (
    BotInstruction,
    BotMessage,
    DocChunk,
    Document,
    DocumentStatus,
)
from cachibot.models.skill import BotSkillActivation, SkillDefinition, SkillSource
from cachibot.storage.database import get_db


class ChatRepository:
    """Repository for chat messages."""

    async def save_message(self, message: ChatMessage) -> None:
        """Save a message to the database."""
        db = await get_db()

        await db.execute(
            """
            INSERT INTO messages (id, role, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.role.value,
                message.content,
                message.timestamp.isoformat(),
                json.dumps(message.metadata),
            ),
        )
        await db.commit()

    async def get_message(self, message_id: str) -> ChatMessage | None:
        """Get a message by ID."""
        db = await get_db()

        async with db.execute(
            "SELECT * FROM messages WHERE id = ?",
            (message_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return ChatMessage(
            id=row["id"],
            role=MessageRole(row["role"]),
            content=row["content"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            metadata=json.loads(row["metadata"]),
        )

    async def get_messages(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ChatMessage]:
        """Get messages with pagination."""
        db = await get_db()

        async with db.execute(
            """
            SELECT * FROM messages
            ORDER BY timestamp DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            ChatMessage(
                id=row["id"],
                role=MessageRole(row["role"]),
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in reversed(rows)  # Return in chronological order
        ]

    async def get_message_count(self) -> int:
        """Get total message count."""
        db = await get_db()

        async with db.execute("SELECT COUNT(*) as count FROM messages") as cursor:
            row = await cursor.fetchone()

        return row["count"] if row else 0

    async def clear_messages(self) -> None:
        """Delete all messages."""
        db = await get_db()
        await db.execute("DELETE FROM messages")
        await db.commit()


class JobRepository:
    """Repository for jobs/tasks."""

    async def save_job(self, job: Job) -> None:
        """Save a job to the database."""
        db = await get_db()

        await db.execute(
            """
            INSERT INTO jobs (id, status, message_id, created_at, started_at,
                completed_at, result, error, progress)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                job.id,
                job.status.value,
                job.message_id,
                job.created_at.isoformat(),
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                json.dumps(job.result) if job.result else None,
                job.error,
                job.progress,
            ),
        )
        await db.commit()

    async def update_job(self, job: Job) -> None:
        """Update an existing job."""
        db = await get_db()

        await db.execute(
            """
            UPDATE jobs SET
                status = ?,
                started_at = ?,
                completed_at = ?,
                result = ?,
                error = ?,
                progress = ?
            WHERE id = ?
            """,
            (
                job.status.value,
                job.started_at.isoformat() if job.started_at else None,
                job.completed_at.isoformat() if job.completed_at else None,
                json.dumps(job.result) if job.result else None,
                job.error,
                job.progress,
                job.id,
            ),
        )
        await db.commit()

    async def get_job(self, job_id: str) -> Job | None:
        """Get a job by ID."""
        db = await get_db()

        async with db.execute(
            "SELECT * FROM jobs WHERE id = ?",
            (job_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_job(row)

    async def get_jobs(
        self,
        status: JobStatus | None = None,
        limit: int = 50,
    ) -> list[Job]:
        """Get jobs with optional status filter."""
        db = await get_db()

        if status:
            async with db.execute(
                """
                SELECT * FROM jobs
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status.value, limit),
            ) as cursor:
                rows = await cursor.fetchall()
        else:
            async with db.execute(
                """
                SELECT * FROM jobs
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,),
            ) as cursor:
                rows = await cursor.fetchall()

        return [self._row_to_job(row) for row in rows]

    def _row_to_job(self, row) -> Job:
        """Convert a database row to a Job object."""
        started = row["started_at"]
        completed = row["completed_at"]
        return Job(
            id=row["id"],
            status=JobStatus(row["status"]),
            message_id=row["message_id"],
            created_at=datetime.fromisoformat(row["created_at"]),
            started_at=datetime.fromisoformat(started) if started else None,
            completed_at=datetime.fromisoformat(completed) if completed else None,
            result=json.loads(row["result"]) if row["result"] else None,
            error=row["error"],
            progress=row["progress"],
        )


class KnowledgeRepository:
    """Repository for knowledge base data (messages, instructions, documents, chunks)."""

    # ===== BOT MESSAGES =====

    async def save_bot_message(self, message: BotMessage) -> None:
        """Save a message to bot's conversation history."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO bot_messages (id, bot_id, chat_id, role, content, timestamp, metadata)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                message.id,
                message.bot_id,
                message.chat_id,
                message.role,
                message.content,
                message.timestamp.isoformat(),
                json.dumps(message.metadata),
            ),
        )
        await db.commit()

    async def get_bot_messages(
        self,
        bot_id: str,
        chat_id: str,
        limit: int = 50,
    ) -> list[BotMessage]:
        """Get messages for a specific bot and chat."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM bot_messages
            WHERE bot_id = ? AND chat_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (bot_id, chat_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            BotMessage(
                id=row["id"],
                bot_id=row["bot_id"],
                chat_id=row["chat_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in reversed(rows)  # Return in chronological order
        ]

    async def get_recent_bot_messages(
        self,
        bot_id: str,
        limit: int = 20,
    ) -> list[BotMessage]:
        """Get recent messages across all chats for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM bot_messages
            WHERE bot_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
            """,
            (bot_id, limit),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            BotMessage(
                id=row["id"],
                bot_id=row["bot_id"],
                chat_id=row["chat_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]),
            )
            for row in reversed(rows)
        ]

    async def delete_all_messages_for_bot(self, bot_id: str) -> int:
        """Delete all messages for a bot. Returns number of messages deleted."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_messages WHERE bot_id = ?",
            (bot_id,),
        )
        await db.commit()
        return cursor.rowcount

    async def delete_messages_for_chat(self, bot_id: str, chat_id: str) -> int:
        """Delete all messages for a specific chat. Returns number deleted."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_messages WHERE bot_id = ? AND chat_id = ?",
            (bot_id, chat_id),
        )
        await db.commit()
        return cursor.rowcount

    async def get_message_count_for_bot(self, bot_id: str) -> int:
        """Get the count of messages for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT COUNT(*) as count FROM bot_messages WHERE bot_id = ?",
            (bot_id,),
        ) as cursor:
            row = await cursor.fetchone()
        return row["count"] if row else 0

    # ===== BOT INSTRUCTIONS =====

    async def get_instructions(self, bot_id: str) -> BotInstruction | None:
        """Get custom instructions for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM bot_instructions WHERE bot_id = ?",
            (bot_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return BotInstruction(
            id=row["id"],
            bot_id=row["bot_id"],
            content=row["content"],
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    async def upsert_instructions(self, bot_id: str, content: str) -> BotInstruction:
        """Create or update instructions for a bot."""
        import uuid

        db = await get_db()
        now = datetime.utcnow()

        # Try to get existing
        existing = await self.get_instructions(bot_id)

        if existing:
            await db.execute(
                """
                UPDATE bot_instructions SET content = ?, updated_at = ?
                WHERE bot_id = ?
                """,
                (content, now.isoformat(), bot_id),
            )
            instruction_id = existing.id
        else:
            instruction_id = str(uuid.uuid4())
            await db.execute(
                """
                INSERT INTO bot_instructions (id, bot_id, content, updated_at)
                VALUES (?, ?, ?, ?)
                """,
                (instruction_id, bot_id, content, now.isoformat()),
            )

        await db.commit()

        return BotInstruction(
            id=instruction_id,
            bot_id=bot_id,
            content=content,
            updated_at=now,
        )

    async def delete_instructions(self, bot_id: str) -> bool:
        """Delete instructions for a bot."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_instructions WHERE bot_id = ?",
            (bot_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    # ===== DOCUMENTS =====

    async def save_document(self, doc: Document) -> None:
        """Save document metadata."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO bot_documents
            (id, bot_id, filename, file_type, file_hash, file_size,
                chunk_count, status, uploaded_at, processed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                doc.id,
                doc.bot_id,
                doc.filename,
                doc.file_type,
                doc.file_hash,
                doc.file_size,
                doc.chunk_count,
                doc.status.value,
                doc.uploaded_at.isoformat(),
                doc.processed_at.isoformat() if doc.processed_at else None,
            ),
        )
        await db.commit()

    async def get_document(self, document_id: str) -> Document | None:
        """Get a document by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT * FROM bot_documents WHERE id = ?",
            (document_id,),
        ) as cursor:
            row = await cursor.fetchone()

        if row is None:
            return None

        return self._row_to_document(row)

    async def get_documents_by_bot(self, bot_id: str) -> list[Document]:
        """Get all documents for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM bot_documents
            WHERE bot_id = ?
            ORDER BY uploaded_at DESC
            """,
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [self._row_to_document(row) for row in rows]

    async def document_exists_by_hash(self, bot_id: str, file_hash: str) -> bool:
        """Check if a document with this hash already exists for the bot."""
        db = await get_db()
        async with db.execute(
            "SELECT 1 FROM bot_documents WHERE bot_id = ? AND file_hash = ?",
            (bot_id, file_hash),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def update_document_status(
        self,
        document_id: str,
        status: DocumentStatus,
        chunk_count: int | None = None,
    ) -> None:
        """Update document processing status."""
        db = await get_db()
        now = datetime.utcnow()

        if chunk_count is not None:
            await db.execute(
                """
                UPDATE bot_documents
                SET status = ?, chunk_count = ?, processed_at = ?
                WHERE id = ?
                """,
                (status.value, chunk_count, now.isoformat(), document_id),
            )
        else:
            await db.execute(
                """
                UPDATE bot_documents SET status = ?, processed_at = ?
                WHERE id = ?
                """,
                (status.value, now.isoformat(), document_id),
            )

        await db.commit()

    async def delete_document(self, document_id: str) -> bool:
        """Delete a document and its chunks."""
        db = await get_db()
        # Chunks deleted via CASCADE
        cursor = await db.execute(
            "DELETE FROM bot_documents WHERE id = ?",
            (document_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_document(self, row) -> Document:
        """Convert a database row to Document."""
        processed = row["processed_at"]
        return Document(
            id=row["id"],
            bot_id=row["bot_id"],
            filename=row["filename"],
            file_type=row["file_type"],
            file_hash=row["file_hash"],
            file_size=row["file_size"],
            chunk_count=row["chunk_count"],
            status=DocumentStatus(row["status"]),
            uploaded_at=datetime.fromisoformat(row["uploaded_at"]),
            processed_at=datetime.fromisoformat(processed) if processed else None,
        )

    # ===== DOCUMENT CHUNKS =====

    async def save_chunks(self, chunks: list[DocChunk]) -> None:
        """Save document chunks (batch insert)."""
        if not chunks:
            return

        db = await get_db()
        await db.executemany(
            """
            INSERT INTO doc_chunks (id, document_id, bot_id, chunk_index, content, embedding)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    chunk.id,
                    chunk.document_id,
                    chunk.bot_id,
                    chunk.chunk_index,
                    chunk.content,
                    chunk.embedding,
                )
                for chunk in chunks
            ],
        )
        await db.commit()

    async def get_chunks_by_document(self, document_id: str) -> list[DocChunk]:
        """Get all chunks for a document."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM doc_chunks
            WHERE document_id = ?
            ORDER BY chunk_index
            """,
            (document_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            DocChunk(
                id=row["id"],
                document_id=row["document_id"],
                bot_id=row["bot_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                embedding=row["embedding"],
            )
            for row in rows
        ]

    async def get_all_chunks_by_bot(self, bot_id: str) -> list[DocChunk]:
        """Get all chunks for a bot (for vector search)."""
        db = await get_db()
        async with db.execute(
            """
            SELECT * FROM doc_chunks
            WHERE bot_id = ?
            ORDER BY document_id, chunk_index
            """,
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()

        return [
            DocChunk(
                id=row["id"],
                document_id=row["document_id"],
                bot_id=row["bot_id"],
                chunk_index=row["chunk_index"],
                content=row["content"],
                embedding=row["embedding"],
            )
            for row in rows
        ]

    async def delete_chunks_by_document(self, document_id: str) -> int:
        """Delete all chunks for a document."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM doc_chunks WHERE document_id = ?",
            (document_id,),
        )
        await db.commit()
        return cursor.rowcount


class ContactsRepository:
    """Repository for bot contacts."""

    async def save_contact(self, contact: Contact) -> None:
        """Save a new contact."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO bot_contacts (id, bot_id, name, details, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                contact.id,
                contact.bot_id,
                contact.name,
                contact.details,
                contact.created_at.isoformat(),
                contact.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def get_contact(self, contact_id: str) -> Contact | None:
        """Get a contact by ID."""
        db = await get_db()
        async with db.execute(
            "SELECT id, bot_id, name, details, created_at, updated_at FROM bot_contacts WHERE id = ?",
            (contact_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_contact(row) if row else None

    async def get_contacts_by_bot(self, bot_id: str) -> list[Contact]:
        """Get all contacts for a bot."""
        db = await get_db()
        async with db.execute(
            "SELECT id, bot_id, name, details, created_at, updated_at FROM bot_contacts WHERE bot_id = ? ORDER BY name",
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_contact(row) for row in rows]

    async def update_contact(self, contact: Contact) -> None:
        """Update an existing contact."""
        db = await get_db()
        await db.execute(
            """
            UPDATE bot_contacts SET name = ?, details = ?, updated_at = ? WHERE id = ?
            """,
            (contact.name, contact.details, contact.updated_at.isoformat(), contact.id),
        )
        await db.commit()

    async def delete_contact(self, contact_id: str) -> bool:
        """Delete a contact by ID. Returns True if deleted, False if not found."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_contacts WHERE id = ?",
            (contact_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_contact(self, row) -> Contact:
        """Convert database row to Contact model."""
        return Contact(
            id=row[0],
            bot_id=row[1],
            name=row[2],
            details=row[3],
            created_at=datetime.fromisoformat(row[4]),
            updated_at=datetime.fromisoformat(row[5]),
        )


class ConnectionRepository:
    """Repository for bot platform connections."""

    async def save_connection(self, connection: BotConnection) -> None:
        """Save a new connection."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO bot_connections
            (id, bot_id, platform, name, status, config_encrypted, message_count,
             last_activity, error, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                connection.id,
                connection.bot_id,
                connection.platform.value,
                connection.name,
                connection.status.value,
                json.dumps(connection.config),  # TODO: Add actual encryption
                connection.message_count,
                connection.last_activity.isoformat() if connection.last_activity else None,
                connection.error,
                connection.created_at.isoformat(),
                connection.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def get_connection(self, connection_id: str) -> BotConnection | None:
        """Get a connection by ID."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, bot_id, platform, name, status, config_encrypted,
                   message_count, last_activity, error, created_at, updated_at
            FROM bot_connections WHERE id = ?
            """,
            (connection_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_connection(row) if row else None

    async def get_connections_by_bot(self, bot_id: str) -> list[BotConnection]:
        """Get all connections for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, bot_id, platform, name, status, config_encrypted,
                   message_count, last_activity, error, created_at, updated_at
            FROM bot_connections WHERE bot_id = ? ORDER BY created_at DESC
            """,
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_connection(row) for row in rows]

    async def get_all_connected(self) -> list[BotConnection]:
        """Get all connections with 'connected' status."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, bot_id, platform, name, status, config_encrypted,
                   message_count, last_activity, error, created_at, updated_at
            FROM bot_connections WHERE status = ?
            """,
            (ConnectionStatus.connected.value,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_connection(row) for row in rows]

    async def update_connection(self, connection: BotConnection) -> None:
        """Update an existing connection."""
        db = await get_db()
        await db.execute(
            """
            UPDATE bot_connections SET
                name = ?, status = ?, config_encrypted = ?, message_count = ?,
                last_activity = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                connection.name,
                connection.status.value,
                json.dumps(connection.config),  # TODO: Add actual encryption
                connection.message_count,
                connection.last_activity.isoformat() if connection.last_activity else None,
                connection.error,
                connection.updated_at.isoformat(),
                connection.id,
            ),
        )
        await db.commit()

    async def update_connection_status(
        self,
        connection_id: str,
        status: ConnectionStatus,
        error: str | None = None,
    ) -> None:
        """Update connection status and optionally error message."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            """
            UPDATE bot_connections SET status = ?, error = ?, updated_at = ?
            WHERE id = ?
            """,
            (status.value, error, now.isoformat(), connection_id),
        )
        await db.commit()

    async def increment_message_count(self, connection_id: str) -> None:
        """Increment message count and update last_activity."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            """
            UPDATE bot_connections SET
                message_count = message_count + 1,
                last_activity = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (now.isoformat(), now.isoformat(), connection_id),
        )
        await db.commit()

    async def delete_connection(self, connection_id: str) -> bool:
        """Delete a connection by ID. Returns True if deleted, False if not found."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bot_connections WHERE id = ?",
            (connection_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_connection(self, row) -> BotConnection:
        """Convert database row to BotConnection model."""
        last_activity = row[7]
        return BotConnection(
            id=row[0],
            bot_id=row[1],
            platform=ConnectionPlatform(row[2]),
            name=row[3],
            status=ConnectionStatus(row[4]),
            config=json.loads(row[5]),  # TODO: Add actual decryption
            message_count=row[6],
            last_activity=datetime.fromisoformat(last_activity) if last_activity else None,
            error=row[8],
            created_at=datetime.fromisoformat(row[9]),
            updated_at=datetime.fromisoformat(row[10]),
        )


class BotRepository:
    """Repository for bot configuration (synced from frontend)."""

    async def upsert_bot(self, bot: Bot) -> None:
        """Create or update a bot."""
        db = await get_db()

        # Check if exists
        async with db.execute(
            "SELECT 1 FROM bots WHERE id = ?",
            (bot.id,),
        ) as cursor:
            exists = await cursor.fetchone() is not None

        if exists:
            await db.execute(
                """
                UPDATE bots SET
                    name = ?, description = ?, icon = ?, color = ?,
                    model = ?, system_prompt = ?, capabilities = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    bot.name,
                    bot.description,
                    bot.icon,
                    bot.color,
                    bot.model,
                    bot.system_prompt,
                    json.dumps(bot.capabilities),
                    bot.updated_at.isoformat(),
                    bot.id,
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO bots
                (id, name, description, icon, color, model, system_prompt,
                 capabilities, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    bot.id,
                    bot.name,
                    bot.description,
                    bot.icon,
                    bot.color,
                    bot.model,
                    bot.system_prompt,
                    json.dumps(bot.capabilities),
                    bot.created_at.isoformat(),
                    bot.updated_at.isoformat(),
                ),
            )

        await db.commit()

    async def get_bot(self, bot_id: str) -> Bot | None:
        """Get a bot by ID."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, name, description, icon, color, model, system_prompt,
                   capabilities, created_at, updated_at
            FROM bots WHERE id = ?
            """,
            (bot_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_bot(row) if row else None

    async def get_all_bots(self) -> list[Bot]:
        """Get all bots."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, name, description, icon, color, model, system_prompt,
                   capabilities, created_at, updated_at
            FROM bots ORDER BY name
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_bot(row) for row in rows]

    async def delete_bot(self, bot_id: str) -> bool:
        """Delete a bot by ID."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM bots WHERE id = ?",
            (bot_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_bot(self, row) -> Bot:
        """Convert database row to Bot model."""
        return Bot(
            id=row[0],
            name=row[1],
            description=row[2],
            icon=row[3],
            color=row[4],
            model=row[5],
            systemPrompt=row[6],
            capabilities=json.loads(row[7]) if row[7] else {},
            createdAt=datetime.fromisoformat(row[8]),
            updatedAt=datetime.fromisoformat(row[9]),
        )


class ChatRepository:
    """Repository for chats (including platform conversations)."""

    async def create_chat(self, chat: Chat) -> None:
        """Create a new chat."""
        db = await get_db()
        await db.execute(
            """
            INSERT INTO chats (id, bot_id, title, platform, platform_chat_id,
                               pinned, archived, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                chat.id,
                chat.bot_id,
                chat.title,
                chat.platform,
                chat.platform_chat_id,
                1 if chat.pinned else 0,
                1 if chat.archived else 0,
                chat.created_at.isoformat(),
                chat.updated_at.isoformat(),
            ),
        )
        await db.commit()

    async def get_chat(self, chat_id: str) -> Chat | None:
        """Get a chat by ID."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, bot_id, title, platform, platform_chat_id,
                   pinned, archived, created_at, updated_at
            FROM chats WHERE id = ?
            """,
            (chat_id,),
        ) as cursor:
            row = await cursor.fetchone()
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
        import uuid

        db = await get_db()

        # Try to find existing chat (including archived ones)
        async with db.execute(
            """
            SELECT id, bot_id, title, platform, platform_chat_id,
                   pinned, archived, created_at, updated_at
            FROM chats WHERE bot_id = ? AND platform = ? AND platform_chat_id = ?
            """,
            (bot_id, platform, platform_chat_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row:
                chat = self._row_to_chat(row)
                # Return None for archived chats - don't process messages
                if chat.archived:
                    return None
                return chat

        # Create new chat
        now = datetime.utcnow()
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
        await self.create_chat(chat)
        return chat

    async def get_chats_by_bot(
        self, bot_id: str, include_archived: bool = False
    ) -> list[Chat]:
        """Get all chats for a bot. Excludes archived by default."""
        db = await get_db()

        if include_archived:
            query = """
                SELECT id, bot_id, title, platform, platform_chat_id,
                       pinned, archived, created_at, updated_at
                FROM chats WHERE bot_id = ?
                ORDER BY pinned DESC, updated_at DESC
            """
        else:
            query = """
                SELECT id, bot_id, title, platform, platform_chat_id,
                       pinned, archived, created_at, updated_at
                FROM chats WHERE bot_id = ? AND archived = 0
                ORDER BY pinned DESC, updated_at DESC
            """

        async with db.execute(query, (bot_id,)) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_chat(row) for row in rows]

    async def update_chat(self, chat: Chat) -> None:
        """Update a chat."""
        db = await get_db()
        await db.execute(
            """
            UPDATE chats SET title = ?, pinned = ?, archived = ?, updated_at = ?
            WHERE id = ?
            """,
            (
                chat.title,
                1 if chat.pinned else 0,
                1 if chat.archived else 0,
                chat.updated_at.isoformat(),
                chat.id,
            ),
        )
        await db.commit()

    async def archive_chat(self, chat_id: str, archived: bool = True) -> bool:
        """Archive or unarchive a chat. Returns True if chat was found."""
        db = await get_db()
        now = datetime.utcnow()
        cursor = await db.execute(
            "UPDATE chats SET archived = ?, updated_at = ? WHERE id = ?",
            (1 if archived else 0, now.isoformat(), chat_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def update_chat_timestamp(self, chat_id: str) -> None:
        """Update the chat's updated_at timestamp."""
        db = await get_db()
        now = datetime.utcnow()
        await db.execute(
            "UPDATE chats SET updated_at = ? WHERE id = ?",
            (now.isoformat(), chat_id),
        )
        await db.commit()

    async def delete_chat(self, chat_id: str) -> bool:
        """Delete a chat by ID."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM chats WHERE id = ?",
            (chat_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def delete_all_chats_for_bot(self, bot_id: str) -> int:
        """Delete all chats for a bot. Returns number of chats deleted."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM chats WHERE bot_id = ?",
            (bot_id,),
        )
        await db.commit()
        return cursor.rowcount

    def _row_to_chat(self, row) -> Chat:
        """Convert database row to Chat model."""
        return Chat(
            id=row[0],
            bot_id=row[1],
            title=row[2],
            platform=row[3],
            platform_chat_id=row[4],
            pinned=bool(row[5]),
            archived=bool(row[6]),
            created_at=datetime.fromisoformat(row[7]),
            updated_at=datetime.fromisoformat(row[8]),
        )


class SkillsRepository:
    """Repository for skill definitions and bot skill activations."""

    # ===== SKILLS =====

    async def upsert_skill(self, skill: SkillDefinition) -> None:
        """Create or update a skill definition."""
        db = await get_db()
        now = datetime.utcnow()

        # Check if exists
        async with db.execute(
            "SELECT 1 FROM skills WHERE id = ?",
            (skill.id,),
        ) as cursor:
            exists = await cursor.fetchone() is not None

        if exists:
            await db.execute(
                """
                UPDATE skills SET
                    name = ?, description = ?, version = ?, author = ?,
                    tags = ?, requires_tools = ?, instructions = ?,
                    source = ?, filepath = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    skill.name,
                    skill.description,
                    skill.version,
                    skill.author,
                    json.dumps(skill.tags),
                    json.dumps(skill.requires_tools),
                    skill.instructions,
                    skill.source.value,
                    skill.filepath,
                    now.isoformat(),
                    skill.id,
                ),
            )
        else:
            await db.execute(
                """
                INSERT INTO skills
                (id, name, description, version, author, tags, requires_tools,
                 instructions, source, filepath, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    skill.id,
                    skill.name,
                    skill.description,
                    skill.version,
                    skill.author,
                    json.dumps(skill.tags),
                    json.dumps(skill.requires_tools),
                    skill.instructions,
                    skill.source.value,
                    skill.filepath,
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        await db.commit()

    async def get_skill(self, skill_id: str) -> SkillDefinition | None:
        """Get a skill by ID."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, name, description, version, author, tags, requires_tools,
                   instructions, source, filepath
            FROM skills WHERE id = ?
            """,
            (skill_id,),
        ) as cursor:
            row = await cursor.fetchone()
            return self._row_to_skill(row) if row else None

    async def get_all_skills(self) -> list[SkillDefinition]:
        """Get all skill definitions."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, name, description, version, author, tags, requires_tools,
                   instructions, source, filepath
            FROM skills ORDER BY name
            """
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_skill(row) for row in rows]

    async def get_skills_by_source(self, source: SkillSource) -> list[SkillDefinition]:
        """Get skills filtered by source."""
        db = await get_db()
        async with db.execute(
            """
            SELECT id, name, description, version, author, tags, requires_tools,
                   instructions, source, filepath
            FROM skills WHERE source = ? ORDER BY name
            """,
            (source.value,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_skill(row) for row in rows]

    async def delete_skill(self, skill_id: str) -> bool:
        """Delete a skill by ID. Also removes all bot activations."""
        db = await get_db()
        cursor = await db.execute(
            "DELETE FROM skills WHERE id = ?",
            (skill_id,),
        )
        await db.commit()
        return cursor.rowcount > 0

    def _row_to_skill(self, row) -> SkillDefinition:
        """Convert database row to SkillDefinition model."""
        return SkillDefinition(
            id=row[0],
            name=row[1],
            description=row[2] or "",
            version=row[3] or "1.0.0",
            author=row[4],
            tags=json.loads(row[5]) if row[5] else [],
            requires_tools=json.loads(row[6]) if row[6] else [],
            instructions=row[7],
            source=SkillSource(row[8]) if row[8] else SkillSource.LOCAL,
            filepath=row[9],
        )

    # ===== BOT SKILL ACTIVATIONS =====

    async def get_bot_skills(self, bot_id: str) -> list[str]:
        """Get list of enabled skill IDs for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT skill_id FROM bot_skills
            WHERE bot_id = ? AND enabled = 1
            """,
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [row[0] for row in rows]

    async def get_bot_skill_definitions(self, bot_id: str) -> list[SkillDefinition]:
        """Get full skill definitions for all enabled skills of a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT s.id, s.name, s.description, s.version, s.author, s.tags,
                   s.requires_tools, s.instructions, s.source, s.filepath
            FROM skills s
            INNER JOIN bot_skills bs ON s.id = bs.skill_id
            WHERE bs.bot_id = ? AND bs.enabled = 1
            ORDER BY s.name
            """,
            (bot_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [self._row_to_skill(row) for row in rows]

    async def activate_skill(self, bot_id: str, skill_id: str) -> None:
        """Activate a skill for a bot."""
        db = await get_db()
        now = datetime.utcnow()

        # Use INSERT OR REPLACE to handle both new activations and re-activations
        await db.execute(
            """
            INSERT OR REPLACE INTO bot_skills (bot_id, skill_id, enabled, activated_at)
            VALUES (?, ?, 1, ?)
            """,
            (bot_id, skill_id, now.isoformat()),
        )
        await db.commit()

    async def deactivate_skill(self, bot_id: str, skill_id: str) -> bool:
        """Deactivate a skill for a bot."""
        db = await get_db()
        cursor = await db.execute(
            """
            DELETE FROM bot_skills WHERE bot_id = ? AND skill_id = ?
            """,
            (bot_id, skill_id),
        )
        await db.commit()
        return cursor.rowcount > 0

    async def is_skill_activated(self, bot_id: str, skill_id: str) -> bool:
        """Check if a skill is activated for a bot."""
        db = await get_db()
        async with db.execute(
            """
            SELECT 1 FROM bot_skills
            WHERE bot_id = ? AND skill_id = ? AND enabled = 1
            """,
            (bot_id, skill_id),
        ) as cursor:
            return await cursor.fetchone() is not None

    async def get_skill_activation(
        self, bot_id: str, skill_id: str
    ) -> BotSkillActivation | None:
        """Get activation details for a bot/skill pair."""
        db = await get_db()
        async with db.execute(
            """
            SELECT bot_id, skill_id, enabled, activated_at FROM bot_skills
            WHERE bot_id = ? AND skill_id = ?
            """,
            (bot_id, skill_id),
        ) as cursor:
            row = await cursor.fetchone()
            if row is None:
                return None
            return BotSkillActivation(
                bot_id=row[0],
                skill_id=row[1],
                enabled=bool(row[2]),
                activated_at=datetime.fromisoformat(row[3]),
            )

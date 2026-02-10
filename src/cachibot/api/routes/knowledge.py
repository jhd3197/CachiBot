"""
Unified Knowledge Base API Routes.

Notes CRUD, knowledge stats, search, document retry, and chunk preview.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query

from cachibot.api.auth import require_bot_access
from cachibot.models.auth import User
from cachibot.models.knowledge import (
    BotNote,
    ChunkResponse,
    KnowledgeStats,
    NoteCreate,
    NoteResponse,
    NoteSource,
    NoteUpdate,
    SearchRequest,
    SearchResultResponse,
)
from cachibot.services.document_processor import get_document_processor
from cachibot.services.vector_store import get_vector_store
from cachibot.storage.repository import KnowledgeRepository, NotesRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots/{bot_id}/knowledge", tags=["knowledge"])


def _note_to_response(note: BotNote) -> NoteResponse:
    """Convert BotNote to response model."""
    return NoteResponse(
        id=note.id,
        bot_id=note.bot_id,
        title=note.title,
        content=note.content,
        tags=note.tags,
        source=note.source.value,
        created_at=note.created_at.isoformat(),
        updated_at=note.updated_at.isoformat(),
    )


# =============================================================================
# NOTES CRUD
# =============================================================================


@router.get("/notes", response_model=list[NoteResponse])
async def list_notes(
    bot_id: str,
    tags: str | None = Query(None, description="Comma-separated tags to filter by"),
    search: str | None = Query(None, description="Search text"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(require_bot_access),
) -> list[NoteResponse]:
    """List notes for a bot with optional filtering."""
    repo = NotesRepository()
    tags_list = [t.strip() for t in tags.split(",") if t.strip()] if tags else None
    notes = await repo.get_notes_by_bot(
        bot_id, tags_filter=tags_list, search=search, limit=limit, offset=offset
    )
    return [_note_to_response(n) for n in notes]


@router.post("/notes", response_model=NoteResponse, status_code=201)
async def create_note(
    bot_id: str,
    data: NoteCreate,
    user: User = Depends(require_bot_access),
) -> NoteResponse:
    """Create a new note (source='user')."""
    repo = NotesRepository()
    now = datetime.utcnow()
    note = BotNote(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
        source=NoteSource.USER,
        created_at=now,
        updated_at=now,
    )
    await repo.save_note(note)
    return _note_to_response(note)


@router.get("/notes/tags", response_model=list[str])
async def get_note_tags(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[str]:
    """Get all unique tags across notes for a bot."""
    repo = NotesRepository()
    return await repo.get_all_tags(bot_id)


@router.get("/notes/{note_id}", response_model=NoteResponse)
async def get_note(
    bot_id: str,
    note_id: str,
    user: User = Depends(require_bot_access),
) -> NoteResponse:
    """Get a specific note."""
    repo = NotesRepository()
    note = await repo.get_note(note_id)
    if note is None or note.bot_id != bot_id:
        raise HTTPException(404, "Note not found")
    return _note_to_response(note)


@router.put("/notes/{note_id}", response_model=NoteResponse)
async def update_note(
    bot_id: str,
    note_id: str,
    data: NoteUpdate,
    user: User = Depends(require_bot_access),
) -> NoteResponse:
    """Update a note."""
    repo = NotesRepository()
    # Verify ownership
    existing = await repo.get_note(note_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(404, "Note not found")

    updated = await repo.update_note(
        note_id,
        title=data.title,
        content=data.content,
        tags=data.tags,
    )
    if updated is None:
        raise HTTPException(404, "Note not found")
    return _note_to_response(updated)


@router.delete("/notes/{note_id}")
async def delete_note(
    bot_id: str,
    note_id: str,
    user: User = Depends(require_bot_access),
) -> dict:
    """Delete a note."""
    repo = NotesRepository()
    # Verify ownership
    existing = await repo.get_note(note_id)
    if existing is None or existing.bot_id != bot_id:
        raise HTTPException(404, "Note not found")

    await repo.delete_note(note_id)
    return {"status": "deleted", "note_id": note_id}


# =============================================================================
# KNOWLEDGE UTILITY ENDPOINTS
# =============================================================================


@router.get("/stats", response_model=KnowledgeStats)
async def get_knowledge_stats(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> KnowledgeStats:
    """Get knowledge base overview stats."""
    repo = KnowledgeRepository()
    stats = await repo.get_knowledge_stats(bot_id)
    return KnowledgeStats(**stats)


@router.post("/search", response_model=list[SearchResultResponse])
async def search_knowledge(
    bot_id: str,
    data: SearchRequest,
    user: User = Depends(require_bot_access),
) -> list[SearchResultResponse]:
    """Search the knowledge base (documents + notes)."""
    results: list[SearchResultResponse] = []

    # Search documents via vector store
    if data.include_documents:
        try:
            vector_store = get_vector_store()
            doc_results = await vector_store.search_with_filenames(
                bot_id=bot_id,
                query=data.query,
                limit=data.limit,
                min_score=0.2,
            )
            for r in doc_results:
                results.append(
                    SearchResultResponse(
                        type="document",
                        id=r.chunk.id,
                        title=r.document_filename or "Document chunk",
                        content=r.chunk.content[:500],
                        score=round(r.score, 3),
                        source=r.document_filename,
                    )
                )
        except Exception as e:
            logger.warning(f"Document search failed: {e}")

    # Search notes via text matching
    if data.include_notes:
        try:
            notes_repo = NotesRepository()
            notes = await notes_repo.search_notes(bot_id, data.query, limit=data.limit)
            for note in notes:
                results.append(
                    SearchResultResponse(
                        type="note",
                        id=note.id,
                        title=note.title,
                        content=note.content[:500],
                        score=None,
                        source=note.source.value,
                    )
                )
        except Exception as e:
            logger.warning(f"Notes search failed: {e}")

    # Sort: scored results first (desc), then unscored
    results.sort(key=lambda r: (r.score is not None, r.score or 0), reverse=True)
    return results[: data.limit]


@router.post("/documents/{document_id}/retry")
async def retry_document(
    bot_id: str,
    document_id: str,
    background_tasks: BackgroundTasks,
    user: User = Depends(require_bot_access),
) -> dict:
    """Retry processing a failed document."""
    repo = KnowledgeRepository()

    doc = await repo.get_document(document_id)
    if doc is None or doc.bot_id != bot_id:
        raise HTTPException(404, "Document not found")

    if doc.status.value != "failed":
        raise HTTPException(400, "Only failed documents can be retried")

    # Reset status
    success = await repo.reset_document_for_retry(document_id)
    if not success:
        raise HTTPException(500, "Failed to reset document")

    # Re-trigger processing
    from pathlib import Path

    upload_dir = Path.home() / ".cachibot" / "uploads"
    file_path = upload_dir / f"{doc.file_hash}.{doc.file_type}"

    if not file_path.exists():
        raise HTTPException(404, "Original file not found on disk")

    processor = get_document_processor()
    background_tasks.add_task(
        processor.process_document, document_id, bot_id, file_path, doc.file_type
    )

    return {"status": "retrying", "document_id": document_id}


@router.get("/documents/{document_id}/chunks", response_model=list[ChunkResponse])
async def get_document_chunks(
    bot_id: str,
    document_id: str,
    user: User = Depends(require_bot_access),
) -> list[ChunkResponse]:
    """Get all chunks for a document (without embeddings)."""
    repo = KnowledgeRepository()

    doc = await repo.get_document(document_id)
    if doc is None or doc.bot_id != bot_id:
        raise HTTPException(404, "Document not found")

    chunks = await repo.get_chunks_by_document_light(document_id)
    return [
        ChunkResponse(
            id=c["id"],
            document_id=c["document_id"],
            chunk_index=c["chunk_index"],
            content=c["content"],
        )
        for c in chunks
    ]

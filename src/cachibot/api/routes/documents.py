"""
Document Management API Routes.

Endpoints for uploading, listing, and deleting bot documents.
"""

import hashlib
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Annotated

import aiofiles
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.models.knowledge import Document, DocumentStatus
from cachibot.services.document_processor import get_document_processor
from cachibot.storage.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots/{bot_id}/documents", tags=["documents"])

# Configuration
UPLOAD_DIR = Path.home() / ".cachibot" / "uploads"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".docx"}


class DocumentResponse(BaseModel):
    """Response model for document operations."""

    id: str
    filename: str
    file_type: str
    file_size: int
    chunk_count: int
    status: str
    uploaded_at: str
    processed_at: str | None


class UploadResponse(BaseModel):
    """Response for document upload."""

    document_id: str
    status: str
    message: str


def _doc_to_response(doc: Document) -> DocumentResponse:
    """Convert Document to response model."""
    return DocumentResponse(
        id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        file_size=doc.file_size,
        chunk_count=doc.chunk_count,
        status=doc.status.value,
        uploaded_at=doc.uploaded_at.isoformat(),
        processed_at=doc.processed_at.isoformat() if doc.processed_at else None,
    )


async def _process_document_background(
    document_id: str,
    bot_id: str,
    file_path: Path,
    file_type: str,
) -> None:
    """Background task to process uploaded document."""
    processor = get_document_processor()
    try:
        await processor.process_document(document_id, bot_id, file_path, file_type)
    except Exception as e:
        logger.error(f"Background processing failed for {document_id}: {e}")


@router.post("/", response_model=UploadResponse)
async def upload_document(
    bot_id: str,
    file: Annotated[UploadFile, File()],
    background_tasks: BackgroundTasks,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> UploadResponse:
    """
    Upload a document to the bot's knowledge base.

    Accepts PDF, TXT, MD, and DOCX files up to 10MB.
    Processing happens in the background.
    """
    repo = KnowledgeRepository()

    # Validate file extension
    if not file.filename:
        raise HTTPException(400, "Filename required")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            400, f"File type '{ext}' not allowed. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    # Read file content
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(400, f"File too large. Maximum size: {MAX_FILE_SIZE // 1024 // 1024}MB")

    if len(content) == 0:
        raise HTTPException(400, "File is empty")

    # Compute hash for deduplication
    file_hash = hashlib.sha256(content).hexdigest()

    # Check for duplicates
    if await repo.document_exists_by_hash(bot_id, file_hash):
        raise HTTPException(409, "This document has already been uploaded")

    # Save file to disk
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    file_path = UPLOAD_DIR / f"{file_hash}{ext}"

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Create document record
    document_id = str(uuid.uuid4())
    doc = Document(
        id=document_id,
        bot_id=bot_id,
        filename=file.filename,
        file_type=ext[1:],  # Remove dot
        file_hash=file_hash,
        file_size=len(content),
        chunk_count=0,
        status=DocumentStatus.PROCESSING,
        uploaded_at=datetime.utcnow(),
    )
    await repo.save_document(doc)

    # Process in background
    background_tasks.add_task(
        _process_document_background,
        document_id,
        bot_id,
        file_path,
        ext[1:],
    )

    return UploadResponse(
        document_id=document_id,
        status="processing",
        message=f"Document '{file.filename}' uploaded. Processing in background.",
    )


@router.get("/", response_model=list[DocumentResponse])
async def list_documents(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[DocumentResponse]:
    """List all documents for a bot."""
    repo = KnowledgeRepository()
    docs = await repo.get_documents_by_bot(bot_id)
    return [_doc_to_response(doc) for doc in docs]


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    bot_id: str,
    document_id: str,
    user: User = Depends(require_bot_access),
) -> DocumentResponse:
    """Get a specific document."""
    repo = KnowledgeRepository()
    doc = await repo.get_document(document_id)

    if doc is None or doc.bot_id != bot_id:
        raise HTTPException(404, "Document not found")

    return _doc_to_response(doc)


@router.delete("/{document_id}")
async def delete_document(
    bot_id: str,
    document_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> dict:
    """Delete a document and its chunks."""
    repo = KnowledgeRepository()

    # Verify document exists and belongs to this bot
    doc = await repo.get_document(document_id)
    if doc is None or doc.bot_id != bot_id:
        raise HTTPException(404, "Document not found")

    # Delete from database (chunks cascade)
    await repo.delete_document(document_id)

    # Optionally delete file from disk
    file_path = UPLOAD_DIR / f"{doc.file_hash}.{doc.file_type}"
    if file_path.exists():
        file_path.unlink()

    return {"status": "deleted", "document_id": document_id}

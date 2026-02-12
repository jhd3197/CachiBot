"""
Custom Instructions API Routes.

Endpoints for managing bot custom instructions.
"""

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from cachibot.api.auth import require_bot_access
from cachibot.models.auth import User
from cachibot.storage.repository import KnowledgeRepository

router = APIRouter(prefix="/api/bots/{bot_id}/instructions", tags=["instructions"])


class InstructionsResponse(BaseModel):
    """Response model for instructions."""

    content: str
    updated_at: str | None = None


class InstructionsUpdate(BaseModel):
    """Request model for updating instructions."""

    content: str = Field(max_length=10000)


@router.get("/", response_model=InstructionsResponse)
async def get_instructions(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> InstructionsResponse:
    """Get custom instructions for a bot."""
    repo = KnowledgeRepository()
    instructions = await repo.get_instructions(bot_id)

    if instructions is None:
        return InstructionsResponse(content="")

    return InstructionsResponse(
        content=instructions.content,
        updated_at=instructions.updated_at.isoformat(),
    )


@router.put("/", response_model=InstructionsResponse)
async def update_instructions(
    bot_id: str,
    data: InstructionsUpdate,
    user: User = Depends(require_bot_access),
) -> InstructionsResponse:
    """Update custom instructions for a bot."""
    repo = KnowledgeRepository()
    instructions = await repo.upsert_instructions(bot_id, data.content)

    return InstructionsResponse(
        content=instructions.content,
        updated_at=instructions.updated_at.isoformat(),
    )


@router.delete("/")
async def delete_instructions(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> dict:
    """Delete custom instructions for a bot."""
    repo = KnowledgeRepository()
    deleted = await repo.delete_instructions(bot_id)

    return {
        "status": "deleted" if deleted else "not_found",
        "bot_id": bot_id,
    }

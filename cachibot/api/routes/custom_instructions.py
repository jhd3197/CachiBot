"""
Custom Instruction API Routes.

CRUD endpoints for managing bot custom instructions (LLM-powered tools),
including versioning, testing, and rollback.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access, require_bot_access_level
from cachibot.api.helpers import require_bot_ownership, require_found
from cachibot.models.auth import User
from cachibot.models.group import BotAccessLevel
from cachibot.models.instruction import (
    CreateInstructionRequest,
    InstructionModel,
    TestInstructionRequest,
    UpdateInstructionRequest,
)
from cachibot.storage.instruction_repository import InstructionRepository

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/bots/{bot_id}/custom-instructions",
    tags=["custom-instructions"],
)

repo = InstructionRepository()


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class InstructionResponse(BaseModel):
    """API response for a custom instruction."""

    id: str
    botId: str
    name: str
    description: str | None
    prompt: str
    systemPrompt: str | None
    outputFormat: str
    modelHint: str | None
    temperature: float | None
    maxTokens: int | None
    inputVariables: list[str]
    fewShotExamples: list[dict[str, Any]] | None
    version: int
    isActive: bool
    category: str
    tags: list[str]
    createdBy: str | None
    createdAt: str
    updatedAt: str

    @classmethod
    def from_model(cls, m: InstructionModel) -> "InstructionResponse":
        return cls(
            id=m.id,
            botId=m.bot_id,
            name=m.name,
            description=m.description,
            prompt=m.prompt,
            systemPrompt=m.system_prompt,
            outputFormat=m.output_format,
            modelHint=m.model_hint,
            temperature=m.temperature,
            maxTokens=m.max_tokens,
            inputVariables=m.input_variables,
            fewShotExamples=m.few_shot_examples,
            version=m.version,
            isActive=m.is_active,
            category=m.category,
            tags=m.tags,
            createdBy=m.created_by,
            createdAt=m.created_at.isoformat(),
            updatedAt=m.updated_at.isoformat(),
        )


class InstructionVersionResponse(BaseModel):
    """API response for an instruction version."""

    id: str
    instructionId: str
    version: int
    prompt: str
    systemPrompt: str | None
    outputFormat: str
    modelHint: str | None
    temperature: float | None
    maxTokens: int | None
    inputVariables: list[str]
    fewShotExamples: list[dict[str, Any]] | None
    author: str
    commitMessage: str | None
    createdAt: str


# =============================================================================
# LIST / CREATE
# =============================================================================


@router.get("/")
async def list_custom_instructions(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[InstructionResponse]:
    """List all custom instructions for a bot."""
    records = await repo.get_by_bot(bot_id)
    return [InstructionResponse.from_model(r) for r in records]


@router.post("/", status_code=201)
async def create_custom_instruction(
    bot_id: str,
    body: CreateInstructionRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> InstructionResponse:
    """Create a new custom instruction."""
    # Check for duplicate name
    existing = await repo.get_by_name(bot_id, body.name)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"An instruction named '{body.name}' already exists for this bot",
        )

    data = body.model_dump()
    record = await repo.create(data, bot_id, author=f"user:{user.id}")
    return InstructionResponse.from_model(record)


# =============================================================================
# GET / UPDATE / DELETE
# =============================================================================


@router.get("/{instruction_id}")
async def get_custom_instruction(
    bot_id: str,
    instruction_id: str,
    user: User = Depends(require_bot_access),
) -> InstructionResponse:
    """Get a custom instruction by ID."""
    record = require_found(await repo.get(instruction_id), "Instruction")
    require_bot_ownership(record, bot_id, "Instruction")
    return InstructionResponse.from_model(record)


@router.put("/{instruction_id}")
async def update_custom_instruction(
    bot_id: str,
    instruction_id: str,
    body: UpdateInstructionRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> InstructionResponse:
    """Update a custom instruction. Creates a new version."""
    record = await repo.get(instruction_id)
    require_bot_ownership(record, bot_id, "Instruction")

    changes = {
        k: v for k, v in body.model_dump().items() if v is not None and k != "commit_message"
    }
    if not changes:
        raise HTTPException(status_code=422, detail="No changes specified")

    updated = await repo.update(
        instruction_id,
        changes,
        author=f"user:{user.id}",
        commit_message=body.commit_message,
    )
    if not updated:
        raise HTTPException(status_code=500, detail="Failed to update instruction")

    return InstructionResponse.from_model(updated)


@router.delete("/{instruction_id}", status_code=204)
async def delete_custom_instruction(
    bot_id: str,
    instruction_id: str,
    user: User = Depends(require_bot_access_level(BotAccessLevel.EDITOR)),
) -> None:
    """Soft-delete a custom instruction."""
    record = await repo.get(instruction_id)
    require_bot_ownership(record, bot_id, "Instruction")

    await repo.delete(instruction_id)


# =============================================================================
# TEST
# =============================================================================


@router.post("/{instruction_id}/test")
async def test_custom_instruction(
    bot_id: str,
    instruction_id: str,
    body: TestInstructionRequest,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> dict[str, Any]:
    """Test a custom instruction with sample input."""
    from tukuy import SkillContext
    from tukuy.instruction import Instruction, InstructionDescriptor

    record = require_found(await repo.get(instruction_id), "Instruction")
    require_bot_ownership(record, bot_id, "Instruction")

    # Build the instruction
    descriptor = InstructionDescriptor(
        name=record.name,
        description=record.description or "",
        prompt=record.prompt,
        system_prompt=record.system_prompt,
        output_format=record.output_format,
        model_hint=record.model_hint,
        temperature=record.temperature,
        max_tokens=record.max_tokens,
        few_shot_examples=record.few_shot_examples,
    )
    instr = Instruction(descriptor=descriptor, fn=None)

    # Create LLM backend
    try:
        from prompture.bridges import create_tukuy_backend

        from cachibot.config import Config

        config = Config.load()
        model = record.model_hint or config.agent.model or "openai/gpt-4o"
        backend = create_tukuy_backend(model)
    except Exception:
        logger.exception("Could not create LLM backend for instruction test")
        raise HTTPException(
            status_code=500,
            detail="Could not create LLM backend",
        )

    ctx = SkillContext(config={"llm_backend": backend})
    result = await instr.ainvoke(context=ctx, **body.sample_input)

    if result.success:
        return {
            "success": True,
            "output": result.value,
            "meta": result.metadata or {},
        }
    else:
        return {
            "success": False,
            "error": result.error,
        }


# =============================================================================
# VERSIONS
# =============================================================================


@router.get("/{instruction_id}/versions")
async def list_versions(
    bot_id: str,
    instruction_id: str,
    user: User = Depends(require_bot_access),
) -> list[InstructionVersionResponse]:
    """List version history for an instruction."""
    record = require_found(await repo.get(instruction_id), "Instruction")
    require_bot_ownership(record, bot_id, "Instruction")

    versions = await repo.get_versions(instruction_id)
    return [
        InstructionVersionResponse(
            id=v.id,
            instructionId=v.instruction_id,
            version=v.version,
            prompt=v.prompt,
            systemPrompt=v.system_prompt,
            outputFormat=v.output_format,
            modelHint=v.model_hint,
            temperature=v.temperature,
            maxTokens=v.max_tokens,
            inputVariables=v.input_variables,
            fewShotExamples=v.few_shot_examples,
            author=v.author,
            commitMessage=v.commit_message,
            createdAt=v.created_at.isoformat(),
        )
        for v in versions
    ]


@router.post("/{instruction_id}/rollback")
async def rollback_instruction(
    bot_id: str,
    instruction_id: str,
    version: int,
    user: User = Depends(require_bot_access_level(BotAccessLevel.OPERATOR)),
) -> InstructionResponse:
    """Rollback an instruction to a previous version."""
    record = await repo.get(instruction_id)
    require_bot_ownership(record, bot_id, "Instruction")

    updated = await repo.rollback(
        instruction_id,
        version,
        author=f"user:{user.id}",
    )
    updated = require_found(updated, f"Version {version}")

    return InstructionResponse.from_model(updated)

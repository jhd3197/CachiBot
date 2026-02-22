"""Pydantic models for custom instructions."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class InstructionModel(BaseModel):
    """A custom instruction owned by a bot."""

    id: str
    bot_id: str
    name: str
    description: str | None = None
    prompt: str
    system_prompt: str | None = None
    output_format: str = "text"
    model_hint: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    input_variables: list[str] = Field(default_factory=list)
    few_shot_examples: list[dict[str, Any]] | None = None
    created_by: str | None = None
    version: int = 1
    is_active: bool = True
    category: str = "custom"
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class InstructionVersionModel(BaseModel):
    """A version snapshot of a custom instruction."""

    id: str
    instruction_id: str
    version: int
    prompt: str
    system_prompt: str | None = None
    output_format: str = "text"
    model_hint: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    input_variables: list[str] = Field(default_factory=list)
    few_shot_examples: list[dict[str, Any]] | None = None
    author: str
    commit_message: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CreateInstructionRequest(BaseModel):
    """Request to create a new custom instruction."""

    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    prompt: str = Field(min_length=1)
    system_prompt: str | None = None
    output_format: str = Field(default="text")
    model_hint: str | None = None
    temperature: float | None = Field(default=None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(default=None, ge=1, le=100000)
    input_variables: list[str] = Field(default_factory=list)
    few_shot_examples: list[dict[str, Any]] | None = None
    category: str = "custom"
    tags: list[str] = Field(default_factory=list)


class UpdateInstructionRequest(BaseModel):
    """Request to update an existing custom instruction."""

    name: str | None = None
    description: str | None = None
    prompt: str | None = None
    system_prompt: str | None = None
    output_format: str | None = None
    model_hint: str | None = None
    temperature: float | None = None
    max_tokens: int | None = None
    input_variables: list[str] | None = None
    few_shot_examples: list[dict[str, Any]] | None = None
    category: str | None = None
    tags: list[str] | None = None
    commit_message: str | None = None


class TestInstructionRequest(BaseModel):
    """Request to test an instruction with sample input."""

    sample_input: dict[str, str] = Field(description="Variable name -> value mapping")

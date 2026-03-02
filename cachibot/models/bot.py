"""
Pydantic models for Bot configuration.

Bot data synced from frontend to enable platform message processing.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class BotModels(BaseModel):
    """Multi-model slot configuration per bot."""

    default: str = ""  # Main conversational model
    image: str = ""  # Image generation model (e.g., openai/dall-e-3)
    audio: str = ""  # Audio model (planned)
    utility: str = ""  # Cheap/fast model for background tasks (name gen, routing, etc.)
    structured: str = ""  # Structured output model (planned)


class Bot(BaseModel):
    """Bot configuration stored in backend."""

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    model: str  # Legacy — prefer default_model property
    models: dict[str, Any] | None = None  # Multi-model slots (BotModels shape)
    system_prompt: str = Field(alias="systemPrompt")
    capabilities: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        populate_by_name = True

    @property
    def default_model(self) -> str:
        """Resolve the effective default model.

        Prefers ``models["default"]`` (the new multi-slot system) over the
        legacy ``model`` field.
        """
        if self.models and self.models.get("default"):
            return str(self.models["default"])
        return self.model


class BotCreate(BaseModel):
    """Request body for creating/updating a bot."""

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    model: str
    models: dict[str, Any] | None = None
    system_prompt: str = Field(alias="systemPrompt")
    capabilities: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


class BotResponse(BaseModel):
    """Response model for a bot."""

    id: str
    name: str
    description: str | None
    icon: str | None
    color: str | None
    model: str
    models: dict[str, Any] | None = None
    systemPrompt: str
    capabilities: dict[str, Any]
    createdAt: str
    updatedAt: str

    @classmethod
    def from_bot(cls, bot: Bot) -> "BotResponse":
        return cls(
            id=bot.id,
            name=bot.name,
            description=bot.description,
            icon=bot.icon,
            color=bot.color,
            model=bot.model,
            models=bot.models,
            systemPrompt=bot.system_prompt,
            capabilities=bot.capabilities,
            createdAt=bot.created_at.isoformat(),
            updatedAt=bot.updated_at.isoformat(),
        )

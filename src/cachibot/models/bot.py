"""
Pydantic models for Bot configuration.

Bot data synced from frontend to enable platform message processing.
"""

from datetime import datetime

from pydantic import BaseModel, Field


class Bot(BaseModel):
    """Bot configuration stored in backend."""

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    model: str
    system_prompt: str = Field(alias="systemPrompt")
    capabilities: dict = Field(default_factory=dict)
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    class Config:
        populate_by_name = True


class BotCreate(BaseModel):
    """Request body for creating/updating a bot."""

    id: str
    name: str
    description: str | None = None
    icon: str | None = None
    color: str | None = None
    model: str
    system_prompt: str = Field(alias="systemPrompt")
    capabilities: dict = Field(default_factory=dict)
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
    systemPrompt: str
    capabilities: dict
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
            systemPrompt=bot.system_prompt,
            capabilities=bot.capabilities,
            createdAt=bot.created_at.isoformat(),
            updatedAt=bot.updated_at.isoformat(),
        )

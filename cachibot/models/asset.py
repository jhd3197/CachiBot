"""Pydantic models for assets (file attachments)."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class Asset(BaseModel):
    """A file asset attached to a room or chat."""

    id: str
    owner_type: str  # 'room' or 'chat'
    owner_id: str
    name: str
    original_filename: str
    content_type: str
    size_bytes: int
    storage_path: str
    uploaded_by_user_id: str | None = None
    uploaded_by_bot_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AssetResponse(BaseModel):
    """Response model for an asset."""

    id: str
    ownerType: str
    ownerId: str
    name: str
    originalFilename: str
    contentType: str
    sizeBytes: int
    uploadedByUserId: str | None
    uploadedByBotId: str | None
    metadata: dict[str, Any]
    createdAt: str

    @classmethod
    def from_entity(cls, asset: Asset) -> "AssetResponse":
        return cls(
            id=asset.id,
            ownerType=asset.owner_type,
            ownerId=asset.owner_id,
            name=asset.name,
            originalFilename=asset.original_filename,
            contentType=asset.content_type,
            sizeBytes=asset.size_bytes,
            uploadedByUserId=asset.uploaded_by_user_id,
            uploadedByBotId=asset.uploaded_by_bot_id,
            metadata=asset.metadata,
            createdAt=asset.created_at.isoformat(),
        )

"""Assets API Routes -- file upload/download for rooms and chats."""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import FileResponse

from cachibot.api.auth import get_current_user
from cachibot.api.helpers import require_found
from cachibot.models.asset import Asset, AssetResponse
from cachibot.models.auth import User
from cachibot.storage.asset_repository import AssetRepository
from cachibot.storage.room_repository import RoomMemberRepository, RoomRepository

ASSETS_BASE = Path.home() / ".cachibot" / "assets"

room_asset_router = APIRouter(prefix="/api/rooms", tags=["room-assets"])
chat_asset_router = APIRouter(prefix="/api/bots", tags=["chat-assets"])

asset_repo = AssetRepository()
room_repo = RoomRepository()
member_repo = RoomMemberRepository()


def _ensure_dir(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


# =============================================================================
# ROOM ASSETS
# =============================================================================


@room_asset_router.get("/{room_id}/assets")
async def list_room_assets(
    room_id: str,
    user: User = Depends(get_current_user),
) -> list[AssetResponse]:
    """Get all assets for a room."""
    room = require_found(await room_repo.get_room(room_id), "Room")
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    assets = await asset_repo.get_by_owner("room", room_id)
    return [AssetResponse.from_entity(a) for a in assets]


@room_asset_router.post("/{room_id}/assets", status_code=201)
async def upload_room_asset(
    room_id: str,
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> AssetResponse:
    """Upload a file asset to a room."""
    room = require_found(await room_repo.get_room(room_id), "Room")
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    asset_id = str(uuid.uuid4())
    storage_dir = ASSETS_BASE / "room" / room_id
    storage_path = storage_dir / asset_id
    _ensure_dir(storage_path)

    content = await file.read()
    storage_path.write_bytes(content)

    asset = Asset(
        id=asset_id,
        owner_type="room",
        owner_id=room_id,
        name=file.filename or "unnamed",
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=str(storage_path),
        uploaded_by_user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    await asset_repo.create(asset)
    return AssetResponse.from_entity(asset)


@room_asset_router.get("/{room_id}/assets/{asset_id}")
async def get_room_asset(
    room_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> AssetResponse:
    """Get asset metadata."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    asset = await asset_repo.get(asset_id)
    if asset is None or asset.owner_type != "room" or asset.owner_id != room_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetResponse.from_entity(asset)


@room_asset_router.get("/{room_id}/assets/{asset_id}/download")
async def download_room_asset(
    room_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> FileResponse:
    """Download an asset file."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    asset = await asset_repo.get(asset_id)
    if asset is None or asset.owner_type != "room" or asset.owner_id != room_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    if not Path(asset.storage_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        asset.storage_path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


@room_asset_router.delete("/{room_id}/assets/{asset_id}", status_code=204)
async def delete_room_asset(
    room_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete an asset."""
    if not await member_repo.is_member(room_id, user.id):
        raise HTTPException(status_code=403, detail="Not a room member")

    storage_path = require_found(await asset_repo.delete(asset_id), "Asset")

    # Clean up file on disk
    try:
        Path(storage_path).unlink(missing_ok=True)
    except OSError:
        pass


# =============================================================================
# CHAT ASSETS
# =============================================================================


@chat_asset_router.get("/{bot_id}/chats/{chat_id}/assets")
async def list_chat_assets(
    bot_id: str,
    chat_id: str,
    user: User = Depends(get_current_user),
) -> list[AssetResponse]:
    """Get all assets for a chat."""
    assets = await asset_repo.get_by_owner("chat", chat_id)
    return [AssetResponse.from_entity(a) for a in assets]


@chat_asset_router.post("/{bot_id}/chats/{chat_id}/assets", status_code=201)
async def upload_chat_asset(
    bot_id: str,
    chat_id: str,
    file: UploadFile,
    user: User = Depends(get_current_user),
) -> AssetResponse:
    """Upload a file asset to a chat."""
    asset_id = str(uuid.uuid4())
    storage_dir = ASSETS_BASE / "chat" / chat_id
    storage_path = storage_dir / asset_id
    _ensure_dir(storage_path)

    content = await file.read()
    storage_path.write_bytes(content)

    asset = Asset(
        id=asset_id,
        owner_type="chat",
        owner_id=chat_id,
        name=file.filename or "unnamed",
        original_filename=file.filename or "unnamed",
        content_type=file.content_type or "application/octet-stream",
        size_bytes=len(content),
        storage_path=str(storage_path),
        uploaded_by_user_id=user.id,
        created_at=datetime.now(timezone.utc),
    )
    await asset_repo.create(asset)
    return AssetResponse.from_entity(asset)


@chat_asset_router.get("/{bot_id}/chats/{chat_id}/assets/{asset_id}")
async def get_chat_asset(
    bot_id: str,
    chat_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> AssetResponse:
    """Get asset metadata."""
    asset = await asset_repo.get(asset_id)
    if asset is None or asset.owner_type != "chat" or asset.owner_id != chat_id:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetResponse.from_entity(asset)


@chat_asset_router.get("/{bot_id}/chats/{chat_id}/assets/{asset_id}/download")
async def download_chat_asset(
    bot_id: str,
    chat_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> FileResponse:
    """Download an asset file."""
    asset = await asset_repo.get(asset_id)
    if asset is None or asset.owner_type != "chat" or asset.owner_id != chat_id:
        raise HTTPException(status_code=404, detail="Asset not found")

    if not Path(asset.storage_path).exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    return FileResponse(
        asset.storage_path,
        media_type=asset.content_type,
        filename=asset.original_filename,
    )


@chat_asset_router.delete("/{bot_id}/chats/{chat_id}/assets/{asset_id}", status_code=204)
async def delete_chat_asset(
    bot_id: str,
    chat_id: str,
    asset_id: str,
    user: User = Depends(get_current_user),
) -> None:
    """Delete an asset."""
    storage_path = require_found(await asset_repo.delete(asset_id), "Asset")

    try:
        Path(storage_path).unlink(missing_ok=True)
    except OSError:
        pass

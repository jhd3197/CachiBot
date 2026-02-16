"""
Connections API Routes

CRUD endpoints for managing bot platform connections.
"""

import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from cachibot.api.auth import require_bot_access
from cachibot.models.auth import User
from cachibot.models.connection import BotConnection, ConnectionPlatform, ConnectionStatus
from cachibot.services.adapters.registry import AdapterRegistry
from cachibot.services.platform_manager import get_platform_manager
from cachibot.storage.repository import ConnectionRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/bots/{bot_id}/connections", tags=["connections"])

# Repository instance
repo = ConnectionRepository()


# Request/Response models
class ConnectionCreate(BaseModel):
    """Request body for creating a connection."""

    platform: ConnectionPlatform
    name: str
    config: dict[str, str]  # e.g., {"token": "..."}


class ConnectionUpdate(BaseModel):
    """Request body for updating a connection."""

    name: str | None = None
    config: dict[str, str] | None = None


class ConnectionResponse(BaseModel):
    """Response model for a connection."""

    id: str
    bot_id: str
    platform: str
    name: str
    status: str
    message_count: int
    last_activity: str | None
    error: str | None
    created_at: str
    updated_at: str
    # Safe config values (excludes sensitive data like tokens)
    strip_markdown: bool = False
    # Custom platform config (safe values only — no api_key)
    custom_config: dict[str, str | bool] | None = None

    @classmethod
    def from_connection(cls, connection: BotConnection) -> "ConnectionResponse":
        # Extract safe config values
        strip_markdown = connection.config.get("strip_markdown", "false").lower() == "true"

        # Expose safe custom config (base_url + capability toggles, NOT api_key)
        custom_config: dict[str, str | bool] | None = None
        if connection.platform.value == "custom":
            capability_keys = [
                "send_messages",
                "typing_indicator",
                "read_receipts",
                "message_status",
            ]
            custom_config = {"base_url": connection.config.get("base_url", "")}
            for key in capability_keys:
                custom_config[key] = connection.config.get(key, "false").lower() == "true"

        return cls(
            id=connection.id,
            bot_id=connection.bot_id,
            platform=connection.platform.value,
            name=connection.name,
            status=connection.status.value,
            message_count=connection.message_count,
            last_activity=(
                connection.last_activity.isoformat() if connection.last_activity else None
            ),
            error=connection.error,
            created_at=connection.created_at.isoformat(),
            updated_at=connection.updated_at.isoformat(),
            strip_markdown=strip_markdown,
            custom_config=custom_config,
        )


@router.get("")
async def list_connections(
    bot_id: str,
    user: User = Depends(require_bot_access),
) -> list[ConnectionResponse]:
    """Get all connections for a bot."""
    connections = await repo.get_connections_by_bot(bot_id)
    return [ConnectionResponse.from_connection(c) for c in connections]


@router.post("", status_code=201)
async def create_connection(
    bot_id: str,
    body: ConnectionCreate,
    user: User = Depends(require_bot_access),
) -> ConnectionResponse:
    """Create a new connection for a bot."""
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Connection name is required")

    # Validate platform-specific config via the adapter registry
    adapter_cls = AdapterRegistry.get_adapter_class(body.platform.value)
    if not adapter_cls:
        raise HTTPException(status_code=400, detail=f"Unsupported platform: {body.platform.value}")
    errors = adapter_cls.validate_config(body.config)
    if errors:
        raise HTTPException(status_code=400, detail="; ".join(errors))

    now = datetime.utcnow()
    connection = BotConnection(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        platform=body.platform,
        name=body.name.strip(),
        status=ConnectionStatus.disconnected,
        config=body.config,
        message_count=0,
        last_activity=None,
        error=None,
        created_at=now,
        updated_at=now,
    )
    await repo.save_connection(connection)
    return ConnectionResponse.from_connection(connection)


@router.get("/{connection_id}")
async def get_connection(
    bot_id: str,
    connection_id: str,
    user: User = Depends(require_bot_access),
) -> ConnectionResponse:
    """Get a specific connection."""
    connection = await repo.get_connection(connection_id)
    if connection is None or connection.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ConnectionResponse.from_connection(connection)


@router.patch("/{connection_id}")
async def update_connection(
    bot_id: str,
    connection_id: str,
    body: ConnectionUpdate,
    user: User = Depends(require_bot_access),
) -> ConnectionResponse:
    """Update an existing connection."""
    connection = await repo.get_connection(connection_id)
    if connection is None or connection.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Connection name is required")
        connection.name = body.name.strip()

    if body.config is not None:
        # Merge config updates with existing config (preserves token if not provided)
        updated_config = {**connection.config, **body.config}
        connection.config = updated_config

    connection.updated_at = datetime.utcnow()
    await repo.update_connection(connection)
    return ConnectionResponse.from_connection(connection)


@router.delete("/{connection_id}", status_code=204)
async def delete_connection(
    bot_id: str,
    connection_id: str,
    user: User = Depends(require_bot_access),
) -> None:
    """Delete a connection."""
    connection = await repo.get_connection(connection_id)
    if connection is None or connection.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    # Disconnect if active
    manager = get_platform_manager()
    if manager.is_connected(connection_id):
        await manager.disconnect(connection_id)

    await repo.delete_connection(connection_id)


@router.post("/{connection_id}/connect")
async def connect_platform(
    bot_id: str,
    connection_id: str,
    user: User = Depends(require_bot_access),
) -> ConnectionResponse:
    """Start a platform connection."""
    connection = await repo.get_connection(connection_id)
    if connection is None or connection.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    manager = get_platform_manager()
    try:
        await manager.connect(connection_id)
        # Refresh connection from DB to get updated status
        connection = await repo.get_connection(connection_id)
        return ConnectionResponse.from_connection(connection)
    except Exception as e:
        logger.error(f"Failed to connect {connection_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to start connection")


@router.post("/{connection_id}/disconnect")
async def disconnect_platform(
    bot_id: str,
    connection_id: str,
    user: User = Depends(require_bot_access),
) -> ConnectionResponse:
    """Stop a platform connection."""
    connection = await repo.get_connection(connection_id)
    if connection is None or connection.bot_id != bot_id:
        raise HTTPException(status_code=404, detail="Connection not found")

    manager = get_platform_manager()
    await manager.disconnect(connection_id)

    # Refresh connection from DB to get updated status
    connection = await repo.get_connection(connection_id)
    return ConnectionResponse.from_connection(connection)

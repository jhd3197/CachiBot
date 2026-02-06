"""
Pydantic models for Platform Connections.

Includes models for per-bot platform connections (Telegram, Discord).
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel


class ConnectionPlatform(str, Enum):
    """Supported messaging platforms."""

    telegram = "telegram"
    discord = "discord"


class ConnectionStatus(str, Enum):
    """Connection state."""

    disconnected = "disconnected"
    connecting = "connecting"
    connected = "connected"
    error = "error"


class BotConnection(BaseModel):
    """A platform connection for a bot."""

    id: str  # UUID
    bot_id: str  # Which bot owns this connection
    platform: ConnectionPlatform
    name: str  # User-friendly name (e.g., "My Telegram Bot")
    status: ConnectionStatus = ConnectionStatus.disconnected
    config: dict[str, str]  # Platform-specific config (token, etc.) - stored encrypted
    message_count: int = 0
    last_activity: datetime | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime

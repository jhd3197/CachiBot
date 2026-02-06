"""
Pydantic models for Capabilities and Contacts.

Includes models for per-bot capability toggles and contact storage.
"""

from datetime import datetime

from pydantic import BaseModel


class BotCapabilities(BaseModel):
    """Per-bot capability toggles controlling tool access."""

    # Web search tools (web_search, web_fetch) - not implemented yet, but toggle ready
    webSearch: bool = False

    # Python code execution (python_execute tool) - default True for backwards compat
    codeExecution: bool = True

    # File operations (file_read, file_write, file_list, file_edit tools)
    fileOperations: bool = True

    # Contacts access in system prompt context
    contacts: bool = False

    # Platform connections (telegram_send, discord_send tools)
    connections: bool = False


class Contact(BaseModel):
    """A contact entry for a bot."""

    id: str  # UUID
    bot_id: str  # Which bot owns this contact
    name: str  # Contact name (required)
    details: str | None = None  # Freeform details (phone, email, notes, etc.)
    created_at: datetime
    updated_at: datetime

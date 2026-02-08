"""
Pydantic models for Capabilities and Contacts.

Includes models for per-bot capability toggles and contact storage.
"""

from datetime import datetime

from pydantic import BaseModel


class BotCapabilities(BaseModel):
    """Per-bot capability toggles controlling tool access."""

    # Python code execution (python_execute tool) - default True for backwards compat
    codeExecution: bool = True

    # File operations (file_read, file_write, file_list, file_edit tools)
    fileOperations: bool = True

    # Git operations (git_status, git_diff, git_log, git_commit, git_branch)
    gitOperations: bool = False

    # Shell access (shell_execute, shell_which)
    shellAccess: bool = False

    # Web access (web_fetch, web_search, http_request)
    webAccess: bool = False

    # Data operations (sqlite_query, sqlite_execute, zip/tar)
    dataOperations: bool = False

    # Contacts access in system prompt context
    contacts: bool = False

    # Platform connections (telegram_send, discord_send tools)
    connections: bool = False

    # Work management (work_create, work_list, work_update, todo_create, todo_list, todo_done)
    workManagement: bool = True


class Contact(BaseModel):
    """A contact entry for a bot."""

    id: str  # UUID
    bot_id: str  # Which bot owns this contact
    name: str  # Contact name (required)
    details: str | None = None  # Freeform details (phone, email, notes, etc.)
    created_at: datetime
    updated_at: datetime

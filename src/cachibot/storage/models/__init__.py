"""
CachiBot ORM Models

Re-exports all SQLAlchemy models and the Base class for convenient imports.
All 25 models covering 25 tables from the CachiBotV2 platform are defined here.

Website-only tables (not modeled here, remain in the website codebase):
- api_keys: API key management (FK to users.id via int PK in website)
- payments: Stripe payment tracking (FK to users.id)
- credit_transactions: Credit ledger (FK to users.id)
- usage_logs: LLM API call tracking (FK to users.id)
- provider_keys: Encrypted LLM provider credentials (no FK to platform tables)
- model_toggles: Per-model availability toggles (no FK to platform tables)
- platform_settings: Admin key-value settings (no FK to platform tables)
- tier_configs: Tier limit definitions (no FK to platform tables)

These website tables use integer PKs and FK to the website's integer user.id.
When both systems share a database, the website models should be updated to
reference the unified User model (String PK) defined here.
"""

from __future__ import annotations

from cachibot.storage.db import Base

# Automation system
from cachibot.storage.models.automations import (
    ExecutionDailySummary,
    ExecutionLog,
    ExecutionLogLine,
    Script,
    ScriptVersion,
    TimelineEvent,
)
from cachibot.storage.models.bot import Bot, BotOwnership
from cachibot.storage.models.chat import Chat
from cachibot.storage.models.connection import BotConnection
from cachibot.storage.models.contact import BotContact
from cachibot.storage.models.env_var import (
    BotEnvironment,
    BotSkillConfig,
    EnvAuditLog,
    PlatformEnvironment,
)
from cachibot.storage.models.group import BotGroupAccess, Group, GroupMember

# Custom instructions
from cachibot.storage.models.instruction import InstructionRecord, InstructionVersion
from cachibot.storage.models.job import Job
from cachibot.storage.models.knowledge import BotDocument, BotInstruction, BotNote, DocChunk
from cachibot.storage.models.message import BotMessage, Message
from cachibot.storage.models.platform_config import PlatformToolConfig
from cachibot.storage.models.room import Room, RoomBot, RoomMember, RoomMessage
from cachibot.storage.models.skill import BotSkill, Skill
from cachibot.storage.models.user import User
from cachibot.storage.models.work import Function, Schedule, Task, Todo, Work, WorkJob

__all__ = [
    # Base
    "Base",
    # User (unified)
    "User",
    # Messages
    "Message",
    "BotMessage",
    # Jobs
    "Job",
    # Bots
    "Bot",
    "BotOwnership",
    # Chats
    "Chat",
    # Knowledge
    "BotInstruction",
    "BotDocument",
    "DocChunk",
    "BotNote",
    # Contacts
    "BotContact",
    # Connections
    "BotConnection",
    # Environment variables
    "BotEnvironment",
    "PlatformEnvironment",
    "BotSkillConfig",
    "EnvAuditLog",
    # Platform tool config
    "PlatformToolConfig",
    # Skills
    "Skill",
    "BotSkill",
    # Work management
    "Function",
    "Schedule",
    "Work",
    "Task",
    "WorkJob",
    "Todo",
    # Groups & access
    "Group",
    "GroupMember",
    "BotGroupAccess",
    # Rooms
    "Room",
    "RoomMember",
    "RoomBot",
    "RoomMessage",
    # Automation system
    "Script",
    "ScriptVersion",
    "ExecutionLog",
    "ExecutionLogLine",
    "TimelineEvent",
    "ExecutionDailySummary",
    # Custom instructions
    "InstructionRecord",
    "InstructionVersion",
]

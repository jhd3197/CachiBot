"""
Cachibot Storage Layer

Multi-database storage using SQLAlchemy 2.0 async ORM.
Supports SQLite (default, zero-config) and PostgreSQL (via DATABASE_URL).
"""

from cachibot.storage.db import close_db, get_session, init_db
from cachibot.storage.repository import (
    BotRepository,
    ChatRepository,
    ConnectionRepository,
    ContactsRepository,
    JobRepository,
    KnowledgeRepository,
    MessageRepository,
    NotesRepository,
    SkillsRepository,
)
from cachibot.storage.room_repository import (
    RoomBotRepository,
    RoomMemberRepository,
    RoomMessageRepository,
    RoomRepository,
)
from cachibot.storage.user_repository import OwnershipRepository, UserRepository
from cachibot.storage.automations_repository import (
    ExecutionDailySummaryRepository,
    ExecutionLogLineRepository,
    ExecutionLogRepository,
    ScriptRepository,
    ScriptVersionRepository,
    TimelineEventRepository,
)
from cachibot.storage.work_repository import (
    FunctionRepository,
    ScheduleRepository,
    TaskRepository,
    TodoRepository,
    WorkJobRepository,
    WorkRepository,
)

__all__ = [
    # Database lifecycle
    "init_db",
    "close_db",
    "get_session",
    # Main repositories
    "MessageRepository",
    "JobRepository",
    "KnowledgeRepository",
    "NotesRepository",
    "ContactsRepository",
    "ConnectionRepository",
    "BotRepository",
    "ChatRepository",
    "SkillsRepository",
    # Work management repositories
    "FunctionRepository",
    "ScheduleRepository",
    "WorkRepository",
    "TaskRepository",
    "WorkJobRepository",
    "TodoRepository",
    # Room repositories
    "RoomRepository",
    "RoomMemberRepository",
    "RoomBotRepository",
    "RoomMessageRepository",
    # User repositories
    "UserRepository",
    "OwnershipRepository",
    # Automation repositories
    "ScriptRepository",
    "ScriptVersionRepository",
    "ExecutionLogRepository",
    "ExecutionLogLineRepository",
    "TimelineEventRepository",
    "ExecutionDailySummaryRepository",
]

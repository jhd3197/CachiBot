"""
Cachibot Storage Layer

SQLite-based storage for chat history, jobs, and work management.
"""

from cachibot.storage.database import close_db, get_db, init_db
from cachibot.storage.repository import ChatRepository, JobRepository
from cachibot.storage.work_repository import (
    FunctionRepository,
    ScheduleRepository,
    TaskRepository,
    TodoRepository,
    WorkJobRepository,
    WorkRepository,
)

__all__ = [
    # Database
    "init_db",
    "close_db",
    "get_db",
    # Legacy repositories
    "ChatRepository",
    "JobRepository",
    # Work management repositories
    "FunctionRepository",
    "ScheduleRepository",
    "WorkRepository",
    "TaskRepository",
    "WorkJobRepository",
    "TodoRepository",
]

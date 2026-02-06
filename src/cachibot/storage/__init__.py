"""
Cachibot Storage Layer

SQLite-based storage for chat history, jobs, and work management.
"""

from cachibot.storage.database import init_db, close_db, get_db
from cachibot.storage.repository import ChatRepository, JobRepository
from cachibot.storage.work_repository import (
    FunctionRepository,
    ScheduleRepository,
    WorkRepository,
    TaskRepository,
    WorkJobRepository,
    TodoRepository,
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

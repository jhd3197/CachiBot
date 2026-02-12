"""
Cachibot Pydantic Models

Request/response schemas for the API.
"""

from cachibot.models.chat import (
    ChatMessage,
    ChatRequest,
    ChatResponse,
    MessageRole,
)
from cachibot.models.config import ConfigResponse, ConfigUpdate
from cachibot.models.job import Job as LegacyJob
from cachibot.models.job import JobStatus as LegacyJobStatus
from cachibot.models.skill import (
    BotSkillActivation,
    BotSkillRequest,
    SkillDefinition,
    SkillInstallRequest,
    SkillResponse,
    SkillSource,
)
from cachibot.models.websocket import (
    ApprovalPayload,
    ErrorPayload,
    MessagePayload,
    ThinkingPayload,
    ToolEndPayload,
    ToolStartPayload,
    UsagePayload,
    WSMessage,
    WSMessageType,
)
from cachibot.models.work import (
    BotFunction,
    FailureAction,
    FunctionList,
    FunctionParameter,
    # Models
    FunctionStep,
    Job,
    JobList,
    JobLog,
    JobStatus,
    Priority,
    Schedule,
    ScheduleList,
    ScheduleType,
    Task,
    TaskList,
    TaskStatus,
    Todo,
    TodoList,
    TodoStatus,
    Work,
    # List responses
    WorkList,
    # Enums
    WorkStatus,
)

__all__ = [
    # Chat
    "ChatMessage",
    "ChatRequest",
    "ChatResponse",
    "MessageRole",
    # Legacy Job (for backwards compat)
    "LegacyJob",
    "LegacyJobStatus",
    # Config
    "ConfigResponse",
    "ConfigUpdate",
    # Skills
    "BotSkillActivation",
    "BotSkillRequest",
    "SkillDefinition",
    "SkillInstallRequest",
    "SkillResponse",
    "SkillSource",
    # WebSocket
    "WSMessage",
    "WSMessageType",
    "ThinkingPayload",
    "ToolStartPayload",
    "ToolEndPayload",
    "MessagePayload",
    "ApprovalPayload",
    "UsagePayload",
    "ErrorPayload",
    # Work Management - Enums
    "WorkStatus",
    "TaskStatus",
    "JobStatus",
    "TodoStatus",
    "Priority",
    "ScheduleType",
    "FailureAction",
    # Work Management - Models
    "FunctionStep",
    "FunctionParameter",
    "BotFunction",
    "Schedule",
    "Work",
    "Task",
    "Job",
    "JobLog",
    "Todo",
    # Work Management - Lists
    "WorkList",
    "TaskList",
    "JobList",
    "TodoList",
    "FunctionList",
    "ScheduleList",
]

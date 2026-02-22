"""Pydantic models for multi-agent rooms."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class RoomMemberRole(str, Enum):
    """Role of a user in a room."""

    CREATOR = "creator"
    MEMBER = "member"


class RoomSenderType(str, Enum):
    """Type of entity sending a message in a room."""

    USER = "user"
    BOT = "bot"
    SYSTEM = "system"


class RoomBotRole(str, Enum):
    """Role of a bot in a room."""

    DEFAULT = "default"
    LEAD = "lead"
    REVIEWER = "reviewer"
    OBSERVER = "observer"
    SPECIALIST = "specialist"


class RoomSettings(BaseModel):
    """Configurable room settings."""

    cooldown_seconds: float = 5.0
    auto_relevance: bool = True
    # parallel | sequential | chain | router | debate | waterfall | relay | consensus | interview
    response_mode: str = "parallel"

    # Debate mode settings
    debate_rounds: int = Field(default=2, ge=1, le=5)
    debate_positions: dict[str, str] = Field(default_factory=dict)  # bot_id -> "FOR"/"AGAINST"/etc.
    debate_judge_bot_id: str | None = None
    debate_judge_prompt: str = (
        "The following debate took place on the topic: {topic}\n\n"
        "{transcript}\n\n"
        "Provide a balanced summary and verdict."
    )

    # Router strategy settings
    routing_strategy: str = "llm"  # "llm" | "keyword" | "round_robin"
    bot_keywords: dict[str, list[str]] = Field(default_factory=dict)  # bot_id -> keywords

    # Waterfall settings
    waterfall_conditions: dict[str, str] = Field(default_factory=dict)  # bot_id -> condition type

    # Consensus mode settings
    consensus_synthesizer_bot_id: str | None = None
    consensus_show_individual: bool = False

    # Interview mode settings
    interview_bot_id: str | None = None
    interview_max_questions: int = Field(default=5, ge=1, le=20)
    interview_handoff_trigger: str = "auto"  # auto | manual | keyword

    # Auto-summary settings
    auto_summary_interval: int = 0  # 0 = disabled; N = every N messages
    auto_summary_bot_id: str | None = None
    auto_summary_auto_pin: bool = True

    # Room personality — injected into all bots' context
    system_prompt: str = ""

    # Room variables — key-value pairs accessible to all bots
    variables: dict[str, str] = Field(default_factory=dict)


class Room(BaseModel):
    """A collaborative room where multiple users and bots interact."""

    id: str
    title: str
    description: str | None = None
    creator_id: str
    max_bots: int = Field(default=4, ge=2, le=4)
    settings: RoomSettings = Field(default_factory=RoomSettings)
    created_at: datetime
    updated_at: datetime


class RoomMember(BaseModel):
    """A user membership in a room."""

    room_id: str
    user_id: str
    username: str = ""
    role: RoomMemberRole = RoomMemberRole.MEMBER
    joined_at: datetime


class RoomBot(BaseModel):
    """A bot assigned to a room."""

    room_id: str
    bot_id: str
    bot_name: str = ""
    role: str = "default"
    added_at: datetime


class RoomMessage(BaseModel):
    """A message in a room from any sender type."""

    id: str
    room_id: str
    sender_type: RoomSenderType
    sender_id: str
    sender_name: str
    content: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime


# =============================================================================
# REQUEST / RESPONSE SCHEMAS
# =============================================================================


class CreateRoomRequest(BaseModel):
    """Request to create a new room."""

    title: str = Field(min_length=1, max_length=100)
    description: str | None = None
    bot_ids: list[str] = Field(min_length=2, max_length=4)
    settings: RoomSettings = Field(default_factory=RoomSettings)


class UpdateRoomRequest(BaseModel):
    """Request to update room details."""

    title: str | None = None
    description: str | None = None
    settings: RoomSettings | None = None


class InviteMemberRequest(BaseModel):
    """Request to invite a user to a room."""

    username: str


class AddBotRequest(BaseModel):
    """Request to add a bot to a room."""

    bot_id: str


class UpdateBotRoleRequest(BaseModel):
    """Request to update a bot's role in a room."""

    role: str


class RoomMemberResponse(BaseModel):
    """Response model for a room member."""

    userId: str
    username: str
    role: str
    joinedAt: str

    @classmethod
    def from_member(cls, member: RoomMember) -> "RoomMemberResponse":
        return cls(
            userId=member.user_id,
            username=member.username,
            role=member.role.value,
            joinedAt=member.joined_at.isoformat(),
        )


class RoomBotResponse(BaseModel):
    """Response model for a room bot."""

    botId: str
    botName: str
    role: str = "default"
    addedAt: str

    @classmethod
    def from_room_bot(cls, room_bot: RoomBot) -> "RoomBotResponse":
        return cls(
            botId=room_bot.bot_id,
            botName=room_bot.bot_name,
            role=room_bot.role,
            addedAt=room_bot.added_at.isoformat(),
        )


class RoomResponse(BaseModel):
    """Response model for a room."""

    id: str
    title: str
    description: str | None
    creatorId: str
    maxBots: int
    settings: dict[str, Any]
    members: list[RoomMemberResponse]
    bots: list[RoomBotResponse]
    messageCount: int
    staleBotIds: list[str] = Field(default_factory=list)
    createdAt: str
    updatedAt: str

    @classmethod
    def from_room(
        cls,
        room: Room,
        members: list[RoomMember],
        bots: list[RoomBot],
        message_count: int = 0,
    ) -> "RoomResponse":
        # Detect stale bots: room_bot entries whose bot_name resolved to empty
        # (the LEFT JOIN in RoomBotRepository.get_bots didn't find a matching bot)
        stale = [b.bot_id for b in bots if not b.bot_name]

        return cls(
            id=room.id,
            title=room.title,
            description=room.description,
            creatorId=room.creator_id,
            maxBots=room.max_bots,
            settings=room.settings.model_dump(),
            members=[RoomMemberResponse.from_member(m) for m in members],
            bots=[RoomBotResponse.from_room_bot(b) for b in bots],
            messageCount=message_count,
            staleBotIds=stale,
            createdAt=room.created_at.isoformat(),
            updatedAt=room.updated_at.isoformat(),
        )


class RoomMessageResponse(BaseModel):
    """Response model for a room message."""

    id: str
    roomId: str
    senderType: str
    senderId: str
    senderName: str
    content: str
    metadata: dict[str, Any]
    toolCalls: list[dict[str, Any]] | None = None
    reactions: list["ReactionSummary"] = Field(default_factory=list)
    timestamp: str

    @classmethod
    def from_message(
        cls,
        msg: RoomMessage,
        reactions: list["ReactionSummary"] | None = None,
    ) -> "RoomMessageResponse":
        tool_calls = msg.metadata.get("toolCalls") if msg.metadata else None
        return cls(
            id=msg.id,
            roomId=msg.room_id,
            senderType=msg.sender_type.value,
            senderId=msg.sender_id,
            senderName=msg.sender_name,
            content=msg.content,
            metadata=msg.metadata,
            toolCalls=tool_calls,
            reactions=reactions or [],
            timestamp=msg.timestamp.isoformat(),
        )


# =============================================================================
# REACTIONS
# =============================================================================

# Fixed set of allowed emojis
ALLOWED_EMOJIS = {"👍", "👎", "❤️", "😂", "🤔", "🎉"}


class ReactionSummary(BaseModel):
    """Summary of reactions for a single emoji on a message."""

    emoji: str
    count: int
    userIds: list[str] = Field(default_factory=list)


class AddReactionRequest(BaseModel):
    """Request to add a reaction to a message."""

    emoji: str


# =============================================================================
# PINNED MESSAGES
# =============================================================================


class PinnedMessage(BaseModel):
    """A pinned message in a room."""

    id: str
    roomId: str
    messageId: str
    pinnedBy: str
    pinnedAt: str
    # Denormalized message fields for display
    senderName: str = ""
    content: str = ""
    timestamp: str = ""


# =============================================================================
# BOOKMARKS
# =============================================================================


class BookmarkedMessage(BaseModel):
    """A bookmarked message for a user."""

    id: str
    roomId: str
    messageId: str
    createdAt: str
    # Denormalized message fields for display
    senderName: str = ""
    content: str = ""
    timestamp: str = ""


# =============================================================================
# AUTOMATIONS
# =============================================================================

VALID_TRIGGER_TYPES = {"on_message", "on_keyword", "on_idle", "on_schedule"}
VALID_ACTION_TYPES = {"send_message", "summarize", "pin_message"}


class RoomAutomationResponse(BaseModel):
    """Response model for a room automation."""

    id: str
    roomId: str
    name: str
    enabled: bool
    triggerType: str
    triggerConfig: dict[str, Any]
    actionType: str
    actionConfig: dict[str, Any]
    createdBy: str
    triggerCount: int
    createdAt: str
    updatedAt: str


class CreateRoomAutomationRequest(BaseModel):
    """Request to create a room automation."""

    name: str = Field(min_length=1, max_length=100)
    trigger_type: str
    trigger_config: dict[str, Any] = Field(default_factory=dict)
    action_type: str
    action_config: dict[str, Any] = Field(default_factory=dict)


class UpdateRoomAutomationRequest(BaseModel):
    """Request to update a room automation."""

    name: str | None = None
    enabled: bool | None = None
    trigger_type: str | None = None
    trigger_config: dict[str, Any] | None = None
    action_type: str | None = None
    action_config: dict[str, Any] | None = None

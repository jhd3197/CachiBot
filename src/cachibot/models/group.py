"""Pydantic models for groups and bot access control."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class GroupRole(str, Enum):
    """Role within a group."""

    OWNER = "owner"
    MEMBER = "member"


class BotAccessLevel(str, Enum):
    """Access level for a bot shared with a group."""

    VIEWER = "viewer"
    OPERATOR = "operator"
    EDITOR = "editor"

    @property
    def rank(self) -> int:
        """Numeric rank for comparison (higher = more access)."""
        return {"viewer": 1, "operator": 2, "editor": 3}[self.value]

    def __ge__(self, other: "BotAccessLevel") -> bool:  # type: ignore[override]
        return self.rank >= other.rank

    def __gt__(self, other: "BotAccessLevel") -> bool:  # type: ignore[override]
        return self.rank > other.rank

    def __le__(self, other: "BotAccessLevel") -> bool:  # type: ignore[override]
        return self.rank <= other.rank

    def __lt__(self, other: "BotAccessLevel") -> bool:  # type: ignore[override]
        return self.rank < other.rank


# =============================================================================
# RESPONSE MODELS
# =============================================================================


class Group(BaseModel):
    """Group response model."""

    id: str = Field(description="Unique group ID")
    name: str = Field(description="Group name")
    description: str | None = Field(default=None, description="Group description")
    created_by: str = Field(description="User ID of group creator")
    created_at: datetime = Field(description="When group was created")
    updated_at: datetime = Field(description="When group was last updated")
    member_count: int = Field(default=0, description="Number of members")


class GroupMember(BaseModel):
    """Group member response model."""

    user_id: str = Field(description="User ID")
    username: str = Field(description="Username")
    email: str = Field(description="User email")
    role: GroupRole = Field(description="Role within group")
    joined_at: datetime = Field(description="When user joined")


class GroupWithMembers(Group):
    """Group with full member list."""

    members: list[GroupMember] = Field(default_factory=list, description="Group members")


class BotAccessRecord(BaseModel):
    """Bot-group access record."""

    id: str = Field(description="Access record ID")
    bot_id: str = Field(description="Bot ID")
    bot_name: str | None = Field(default=None, description="Bot name")
    group_id: str = Field(description="Group ID")
    group_name: str | None = Field(default=None, description="Group name")
    access_level: BotAccessLevel = Field(description="Access level")
    granted_by: str = Field(description="User ID who granted access")
    granted_at: datetime = Field(description="When access was granted")


# =============================================================================
# REQUEST MODELS
# =============================================================================


class CreateGroupRequest(BaseModel):
    """Request to create a group."""

    name: str = Field(description="Group name", min_length=1, max_length=100)
    description: str | None = Field(default=None, description="Group description", max_length=500)


class UpdateGroupRequest(BaseModel):
    """Request to update a group."""

    name: str | None = Field(default=None, description="New name", min_length=1, max_length=100)
    description: str | None = Field(default=None, description="New description", max_length=500)


class AddMemberRequest(BaseModel):
    """Request to add a member to a group."""

    user_id: str = Field(description="User ID to add")
    role: GroupRole = Field(default=GroupRole.MEMBER, description="Role to assign")


class ShareBotRequest(BaseModel):
    """Request to share a bot with a group."""

    group_id: str = Field(description="Group ID to share with")
    access_level: BotAccessLevel = Field(
        default=BotAccessLevel.VIEWER, description="Access level to grant"
    )


class UpdateAccessRequest(BaseModel):
    """Request to update bot access level for a group."""

    access_level: BotAccessLevel = Field(description="New access level")

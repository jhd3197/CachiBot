"""Authentication-related Pydantic models."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserRole(str, Enum):
    """User role in the system."""

    ADMIN = "admin"
    USER = "user"


class User(BaseModel):
    """User model."""

    id: str = Field(description="Unique user ID")
    email: str = Field(description="User email address")
    username: str = Field(description="Unique username")
    role: UserRole = Field(default=UserRole.USER, description="User role")
    is_active: bool = Field(default=True, description="Whether user is active")
    created_at: datetime = Field(description="When user was created")
    created_by: str | None = Field(default=None, description="Admin who created this user")
    last_login: datetime | None = Field(default=None, description="Last login timestamp")
    website_user_id: int | None = Field(default=None, description="Linked website user ID")
    tier: str = Field(default="free", description="User tier (free, pro, etc.)")
    credit_balance: float = Field(default=0.0, description="Available credits")
    is_verified: bool = Field(default=False, description="Whether email is verified")


class UserInDB(User):
    """User model with password hash (internal use only)."""

    password_hash: str = Field(description="Hashed password")


class LoginRequest(BaseModel):
    """Request to login."""

    identifier: str = Field(description="Email or username", min_length=1)
    password: str = Field(description="Password", min_length=1)


class LoginResponse(BaseModel):
    """Response from successful login."""

    access_token: str = Field(description="JWT access token")
    refresh_token: str = Field(description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")
    user: User = Field(description="Logged in user info")


class RefreshRequest(BaseModel):
    """Request to refresh access token."""

    refresh_token: str = Field(description="Refresh token")


class RefreshResponse(BaseModel):
    """Response from token refresh."""

    access_token: str = Field(description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")


class CreateUserRequest(BaseModel):
    """Request to create a new user (admin only)."""

    email: EmailStr = Field(description="User email address")
    username: str = Field(description="Unique username", min_length=3, max_length=32)
    password: str = Field(description="Password", min_length=8)
    role: UserRole = Field(default=UserRole.USER, description="User role")


class UpdateUserRequest(BaseModel):
    """Request to update a user (admin only)."""

    email: EmailStr | None = Field(default=None, description="New email address")
    username: str | None = Field(
        default=None, description="New username", min_length=3, max_length=32
    )
    role: UserRole | None = Field(default=None, description="New role")
    is_active: bool | None = Field(default=None, description="Set active status")


class ChangePasswordRequest(BaseModel):
    """Request to change own password."""

    current_password: str = Field(description="Current password", min_length=1)
    new_password: str = Field(description="New password", min_length=8)


class SetupRequest(BaseModel):
    """Request for initial admin setup (first user)."""

    email: EmailStr = Field(description="Admin email address")
    username: str = Field(description="Admin username", min_length=3, max_length=32)
    password: str = Field(description="Admin password", min_length=8)


class SetupStatusResponse(BaseModel):
    """Response for setup status check."""

    setup_required: bool = Field(description="Whether first-time setup is needed")


class UserListResponse(BaseModel):
    """Response with list of users."""

    users: list[User] = Field(default_factory=list, description="List of users")
    total: int = Field(default=0, description="Total user count")


class ExchangeTokenRequest(BaseModel):
    """Request to exchange a platform launch token for V2 native tokens."""

    token: str = Field(description="Platform launch token from website")


class AuthModeResponse(BaseModel):
    """Response indicating the platform's auth mode."""

    mode: str = Field(description="'selfhosted' or 'cloud'")
    login_url: str | None = Field(default=None, description="Website login URL (cloud mode)")


class BotOwnership(BaseModel):
    """Bot ownership tracking model."""

    id: str = Field(description="Unique ownership record ID")
    bot_id: str = Field(description="Bot ID")
    user_id: str = Field(description="Owner user ID")
    created_at: datetime = Field(description="When ownership was assigned")

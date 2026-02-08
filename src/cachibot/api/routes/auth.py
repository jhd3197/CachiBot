"""Authentication endpoints."""

import time
import uuid
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status

from cachibot.api.auth import get_admin_user, get_current_user
from cachibot.models.auth import (
    ChangePasswordRequest,
    CreateUserRequest,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    RefreshResponse,
    SetupRequest,
    SetupStatusResponse,
    UpdateUserRequest,
    User,
    UserInDB,
    UserListResponse,
    UserRole,
)
from cachibot.services.auth_service import get_auth_service
from cachibot.storage.user_repository import UserRepository

router = APIRouter(prefix="/auth")

# Simple in-memory rate limiter for auth endpoints
_rate_limit_store: dict[str, list[float]] = defaultdict(list)
RATE_LIMIT_WINDOW = 60  # seconds
RATE_LIMIT_MAX_REQUESTS = 5  # max attempts per window


async def rate_limit_auth(request: Request) -> None:
    """Rate limit authentication endpoints by client IP."""
    client_ip = request.client.host if request.client else "unknown"
    now = time.monotonic()

    # Prune old entries
    _rate_limit_store[client_ip] = [
        t for t in _rate_limit_store[client_ip] if now - t < RATE_LIMIT_WINDOW
    ]

    if len(_rate_limit_store[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please try again later.",
        )

    _rate_limit_store[client_ip].append(now)


@router.get("/setup-required", response_model=SetupStatusResponse)
async def check_setup_required() -> SetupStatusResponse:
    """Check if first-time setup is needed (no users exist)."""
    repo = UserRepository()
    count = await repo.get_user_count()
    return SetupStatusResponse(setup_required=count == 0)


@router.post("/setup", response_model=LoginResponse, dependencies=[Depends(rate_limit_auth)])
async def setup_initial_admin(request: SetupRequest) -> LoginResponse:
    """
    Create the initial admin user (first-time setup).

    This endpoint only works when no users exist in the system.
    """
    repo = UserRepository()

    # Check if setup is still needed
    count = await repo.get_user_count()
    if count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Setup already completed. Use login instead.",
        )

    # Validate unique constraints
    if await repo.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use",
        )

    if await repo.username_exists(request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create admin user
    auth_service = get_auth_service()
    now = datetime.utcnow()

    user = UserInDB(
        id=str(uuid.uuid4()),
        email=request.email.lower(),
        username=request.username.lower(),
        password_hash=auth_service.hash_password(request.password),
        role=UserRole.ADMIN,
        is_active=True,
        created_at=now,
        created_by=None,
        last_login=now,
    )

    await repo.create_user(user)

    # Generate tokens
    access_token = auth_service.create_access_token(user.id, user.role.value)
    refresh_token = auth_service.create_refresh_token(user.id)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            created_by=user.created_by,
            last_login=user.last_login,
        ),
    )


@router.post("/login", response_model=LoginResponse, dependencies=[Depends(rate_limit_auth)])
async def login(request: LoginRequest) -> LoginResponse:
    """
    Login with email or username and password.

    Returns access and refresh tokens on success.
    """
    repo = UserRepository()
    auth_service = get_auth_service()

    # Find user by email or username
    user = await repo.get_user_by_identifier(request.identifier)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Verify password
    if not auth_service.verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    # Update last login
    await repo.update_last_login(user.id)

    # Generate tokens
    access_token = auth_service.create_access_token(user.id, user.role.value)
    refresh_token = auth_service.create_refresh_token(user.id)

    return LoginResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        user=User(
            id=user.id,
            email=user.email,
            username=user.username,
            role=user.role,
            is_active=user.is_active,
            created_at=user.created_at,
            created_by=user.created_by,
            last_login=datetime.utcnow(),
        ),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(request: RefreshRequest) -> RefreshResponse:
    """
    Refresh the access token using a refresh token.

    Returns a new access token.
    """
    auth_service = get_auth_service()
    repo = UserRepository()

    # Verify refresh token
    payload = auth_service.verify_token(request.refresh_token, token_type="refresh")

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Get user to verify still active and get current role
    user = await repo.get_user_by_id(user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    # Generate new access token
    access_token = auth_service.create_access_token(user.id, user.role.value)

    return RefreshResponse(access_token=access_token)


@router.get("/me", response_model=User)
async def get_current_user_info(user: User = Depends(get_current_user)) -> User:
    """Get the current authenticated user's info."""
    return user


@router.post("/change-password")
async def change_password(
    request: ChangePasswordRequest,
    user: User = Depends(get_current_user),
) -> dict:
    """Change the current user's password."""
    repo = UserRepository()
    auth_service = get_auth_service()

    # Get user with password hash
    user_db = await repo.get_user_by_id(user.id)
    if user_db is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Verify current password
    if not auth_service.verify_password(request.current_password, user_db.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash and save new password
    new_hash = auth_service.hash_password(request.new_password)
    await repo.update_password(user.id, new_hash)

    return {"status": "password_changed"}


# ===== Admin-only endpoints =====


@router.get("/users", response_model=UserListResponse)
async def list_users(
    limit: int = 100,
    offset: int = 0,
    admin: User = Depends(get_admin_user),
) -> UserListResponse:
    """List all users (admin only)."""
    repo = UserRepository()
    users = await repo.get_all_users(limit=limit, offset=offset)
    total = await repo.get_user_count()

    return UserListResponse(users=users, total=total)


@router.post("/users", response_model=User)
async def create_user(
    request: CreateUserRequest,
    admin: User = Depends(get_admin_user),
) -> User:
    """Create a new user (admin only)."""
    repo = UserRepository()
    auth_service = get_auth_service()

    # Validate unique constraints
    if await repo.email_exists(request.email):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already in use",
        )

    if await repo.username_exists(request.username):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already taken",
        )

    # Create user
    now = datetime.utcnow()
    user = UserInDB(
        id=str(uuid.uuid4()),
        email=request.email.lower(),
        username=request.username.lower(),
        password_hash=auth_service.hash_password(request.password),
        role=request.role,
        is_active=True,
        created_at=now,
        created_by=admin.id,
        last_login=None,
    )

    await repo.create_user(user)

    return User(
        id=user.id,
        email=user.email,
        username=user.username,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        created_by=user.created_by,
        last_login=user.last_login,
    )


@router.put("/users/{user_id}", response_model=User)
async def update_user(
    user_id: str,
    request: UpdateUserRequest,
    admin: User = Depends(get_admin_user),
) -> User:
    """Update a user (admin only)."""
    repo = UserRepository()

    # Get existing user
    existing = await repo.get_user_by_id(user_id)
    if existing is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent demoting the last admin
    if existing.role == UserRole.ADMIN and request.role == UserRole.USER:
        # Count admins
        all_users = await repo.get_all_users(limit=1000)
        admin_count = sum(1 for u in all_users if u.role == UserRole.ADMIN)
        if admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot demote the last admin",
            )

    # Validate unique constraints
    if request.email and request.email.lower() != existing.email:
        if await repo.email_exists(request.email, exclude_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already in use",
            )

    if request.username and request.username.lower() != existing.username:
        if await repo.username_exists(request.username, exclude_user_id=user_id):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Username already taken",
            )

    # Update user
    await repo.update_user(
        user_id,
        email=request.email,
        username=request.username,
        role=request.role,
        is_active=request.is_active,
    )

    # Get updated user
    updated = await repo.get_user_by_id(user_id)
    if updated is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found after update",
        )

    return User(
        id=updated.id,
        email=updated.email,
        username=updated.username,
        role=updated.role,
        is_active=updated.is_active,
        created_at=updated.created_at,
        created_by=updated.created_by,
        last_login=updated.last_login,
    )


@router.delete("/users/{user_id}")
async def deactivate_user(
    user_id: str,
    admin: User = Depends(get_admin_user),
) -> dict:
    """Deactivate a user (admin only). Does not delete data."""
    repo = UserRepository()

    # Can't deactivate yourself
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot deactivate your own account",
        )

    # Get user
    user = await repo.get_user_by_id(user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    # Prevent deactivating the last admin
    if user.role == UserRole.ADMIN:
        all_users = await repo.get_all_users(limit=1000)
        active_admin_count = sum(
            1 for u in all_users if u.role == UserRole.ADMIN and u.is_active
        )
        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot deactivate the last active admin",
            )

    await repo.deactivate_user(user_id)

    return {"status": "deactivated"}

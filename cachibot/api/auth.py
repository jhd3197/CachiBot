"""
FastAPI Authentication Dependencies

Provides dependency functions for protecting routes.
In cloud mode, users exchange a short-lived launch token for V2-native
tokens via /auth/exchange. After that, all auth uses V2-native tokens only.
The website's main JWT secret is never shared with V2.

API keys (cb-* prefix) are resolved via SHA-256 hash lookup and coexist
with JWT tokens transparently.
"""

import asyncio
import hashlib
import logging
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cachibot.models.auth import User, UserInDB, UserRole
from cachibot.models.group import BotAccessLevel
from cachibot.services.auth_service import get_auth_service
from cachibot.storage.developer_repository import ApiKeyRepository
from cachibot.storage.group_repository import BotAccessRepository
from cachibot.storage.user_repository import OwnershipRepository, UserRepository

logger = logging.getLogger(__name__)

# HTTP Bearer token scheme
security = HTTPBearer(auto_error=False)


def _to_user(user_db: UserInDB) -> User:
    """Convert UserInDB to User (strips password_hash)."""
    return User(
        id=user_db.id,
        email=user_db.email,
        username=user_db.username,
        role=user_db.role,
        is_active=user_db.is_active,
        created_at=user_db.created_at,
        created_by=user_db.created_by,
        last_login=user_db.last_login,
        website_user_id=user_db.website_user_id,
        tier=user_db.tier,
        credit_balance=user_db.credit_balance,
        is_verified=user_db.is_verified,
    )


async def resolve_api_key(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> tuple[str, str]:
    """Resolve a cb-* API key to (bot_id, key_id).

    Hashes the bearer token with SHA-256 and looks up the key record.
    Checks revocation and expiration, then fires a background usage update.

    Raises:
        HTTPException 401 if credentials are missing, invalid, revoked, or expired.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = credentials.credentials
    if not token.startswith("cb-"):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key format",
            headers={"WWW-Authenticate": "Bearer"},
        )

    key_hash = hashlib.sha256(token.encode()).hexdigest()
    repo = ApiKeyRepository()
    key_record = await repo.get_key_by_hash(key_hash)

    if key_record is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if key_record.is_revoked:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if key_record.expires_at and key_record.expires_at < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key has expired",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Fire-and-forget usage tracking
    try:
        asyncio.get_running_loop().create_task(repo.record_usage(key_record.id))
    except RuntimeError:
        pass

    return (key_record.bot_id, key_record.id)


async def _resolve_token(token: str) -> User | None:
    """Resolve a V2-native bearer token to a User.

    Only verifies tokens signed with V2's own JWT secret.
    Website users must first exchange their launch token via /auth/exchange
    to get V2-native tokens.
    """
    auth = get_auth_service()

    payload = auth.verify_token(token, token_type="access")
    if not payload:
        return None

    user_id = payload.get("sub")
    if not user_id:
        return None

    repo = UserRepository()
    user_db = await repo.get_user_by_id(user_id)
    if user_db and user_db.is_active:
        return _to_user(user_db)

    return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User:
    """
    Dependency to get the current authenticated user.

    Supports both V2-native tokens and website tokens (cloud mode).
    Raises HTTPException 401 if not authenticated.
    """
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await _resolve_token(credentials.credentials)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


async def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> User | None:
    """
    Dependency to get the current user if authenticated, or None.

    Does not raise an error if not authenticated.
    """
    if credentials is None:
        return None

    try:
        return await get_current_user(credentials)
    except HTTPException:
        return None


async def get_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current user and verify they are an admin.

    Raises HTTPException 403 if not admin.
    """
    if user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user


async def get_manager_or_admin_user(
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to get the current user and verify they are a manager or admin.

    Raises HTTPException 403 if not manager or admin.
    """
    if user.role not in (UserRole.ADMIN, UserRole.MANAGER):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or admin access required",
        )
    return user


async def require_bot_access(
    bot_id: str,
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to verify user has access to a bot.

    Admins can access any bot. Regular users can access their own bots
    or bots shared with them via groups (any access level).

    Args:
        bot_id: The bot ID to check access for
        user: The current user (injected)

    Returns:
        The current user if access is granted

    Raises:
        HTTPException 403 if user doesn't have access
    """
    # Admins bypass ownership checks
    if user.role == UserRole.ADMIN:
        return user

    # Check ownership
    ownership_repo = OwnershipRepository()
    if await ownership_repo.user_owns_bot(user.id, bot_id):
        return user

    # Check group-based access
    access_repo = BotAccessRepository()
    level = await access_repo.get_user_bot_access_level(user.id, bot_id)
    if level is not None:
        return user

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You don't have access to this bot",
    )


def require_bot_access_level(min_level: BotAccessLevel) -> Callable[..., Any]:
    """Factory that returns a dependency checking the user has at least min_level access.

    Admin and bot owner always pass. Group members need effective level >= min_level.
    """

    async def _check(
        bot_id: str,
        user: User = Depends(get_current_user),
    ) -> User:
        # Admins bypass
        if user.role == UserRole.ADMIN:
            return user

        # Owner bypass
        ownership_repo = OwnershipRepository()
        if await ownership_repo.user_owns_bot(user.id, bot_id):
            return user

        # Check group-based access level
        access_repo = BotAccessRepository()
        level = await access_repo.get_user_bot_access_level(user.id, bot_id)
        if level is not None and level >= min_level:
            return user

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Requires at least {min_level.value} access to this bot",
        )

    return _check


def verify_token_from_query(token: str) -> dict[str, Any] | None:
    """
    Verify a V2-native JWT token from query parameter (for WebSocket).

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    auth_service = get_auth_service()
    return auth_service.verify_token(token, token_type="access")


async def get_user_from_token(token: str) -> User | None:
    """
    Get user from a JWT token (for WebSocket authentication).

    Supports both V2-native and website tokens (cloud mode).

    Args:
        token: JWT token string

    Returns:
        User if valid, None otherwise
    """
    return await _resolve_token(token)

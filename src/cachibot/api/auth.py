"""
FastAPI Authentication Dependencies

Provides dependency functions for protecting routes.
Supports dual-mode auth: V2-native tokens (selfhosted/cloud) and
website bearer tokens (cloud mode only).
"""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cachibot.models.auth import User, UserInDB, UserRole
from cachibot.services.auth_service import get_auth_service
from cachibot.storage.user_repository import OwnershipRepository, UserRepository

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


async def _resolve_token(token: str) -> User | None:
    """Try to resolve a bearer token to a User.

    1. Try V2 native token (has "type": "access" claim).
    2. In cloud mode, try website token (sub=email, no "type" claim).
    """
    auth = get_auth_service()
    repo = UserRepository()

    # 1. Try V2 native token
    payload = auth.verify_token(token, token_type="access")
    if payload:
        user_id = payload.get("sub")
        if user_id:
            user_db = await repo.get_user_by_id(user_id)
            if user_db and user_db.is_active:
                return _to_user(user_db)

    # 2. In cloud mode, try website token (sub=email, no "type" claim)
    if auth.is_cloud_mode:
        ws_payload = auth.verify_website_token(token)
        if ws_payload:
            email = ws_payload.get("sub")
            if email:
                user_db = await repo.get_user_by_email(email)
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


async def require_bot_access(
    bot_id: str,
    user: User = Depends(get_current_user),
) -> User:
    """
    Dependency to verify user has access to a bot.

    Admins can access any bot. Regular users can only access their own bots.

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

    # Check ownership for regular users
    ownership_repo = OwnershipRepository()
    if not await ownership_repo.user_owns_bot(user.id, bot_id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't have access to this bot",
        )

    return user


def verify_token_from_query(token: str) -> dict | None:
    """
    Verify a JWT token from query parameter (for WebSocket).

    Tries V2 native token first, then website token in cloud mode.

    Args:
        token: JWT token string

    Returns:
        Decoded payload if valid, None otherwise
    """
    auth_service = get_auth_service()

    # Try V2 native token
    payload = auth_service.verify_token(token, token_type="access")
    if payload:
        return payload

    # In cloud mode, try website token
    if auth_service.is_cloud_mode:
        return auth_service.verify_website_token(token)

    return None


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

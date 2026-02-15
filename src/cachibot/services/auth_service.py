"""
Authentication Service

Handles password hashing and JWT token management.
"""

import secrets
from datetime import datetime, timedelta
from typing import Any

import bcrypt
import jwt

from cachibot.config import AuthConfig, PlatformConfig


class AuthService:
    """Service for authentication operations."""

    def __init__(self, config: AuthConfig, platform_config: PlatformConfig | None = None):
        """Initialize auth service with config."""
        self.config = config
        self._platform_config = platform_config
        # Generate a random secret if not configured (for development only)
        self._jwt_secret = config.jwt_secret or secrets.token_hex(32)
        if not config.jwt_secret:
            import logging

            logging.getLogger(__name__).warning(
                "CACHIBOT_JWT_SECRET not set. Using random secret. "
                "Tokens will be invalidated on restart. "
                "Set CACHIBOT_JWT_SECRET in production."
            )

    @property
    def is_cloud_mode(self) -> bool:
        """Whether the platform is running in cloud mode."""
        return (
            self._platform_config is not None
            and self._platform_config.deploy_mode == "cloud"
        )

    @property
    def platform_config(self) -> PlatformConfig | None:
        """Access the platform configuration."""
        return self._platform_config

    # ===== Password Hashing =====

    def hash_password(self, password: str) -> str:
        """Hash a password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, password_hash: str) -> bool:
        """Verify a password against a hash."""
        try:
            return bcrypt.checkpw(
                password.encode("utf-8"),
                password_hash.encode("utf-8"),
            )
        except Exception:
            return False

    # ===== JWT Tokens =====

    def create_access_token(
        self,
        user_id: str,
        role: str,
        extra_claims: dict[str, Any] | None = None,
    ) -> str:
        """Create a JWT access token."""
        now = datetime.utcnow()
        expires = now + timedelta(minutes=self.config.access_token_expire_minutes)

        payload = {
            "sub": user_id,
            "role": role,
            "type": "access",
            "iat": now,
            "exp": expires,
        }

        if extra_claims:
            payload.update(extra_claims)

        return jwt.encode(
            payload,
            self._jwt_secret,
            algorithm=self.config.jwt_algorithm,
        )

    def create_refresh_token(self, user_id: str) -> str:
        """Create a JWT refresh token."""
        now = datetime.utcnow()
        expires = now + timedelta(days=self.config.refresh_token_expire_days)

        payload = {
            "sub": user_id,
            "type": "refresh",
            "iat": now,
            "exp": expires,
        }

        return jwt.encode(
            payload,
            self._jwt_secret,
            algorithm=self.config.jwt_algorithm,
        )

    def verify_token(self, token: str, token_type: str = "access") -> dict[str, Any] | None:
        """
        Verify and decode a JWT token.

        Args:
            token: The JWT token string
            token_type: Expected token type ("access" or "refresh")

        Returns:
            Decoded payload if valid, None if invalid
        """
        try:
            payload = jwt.decode(
                token,
                self._jwt_secret,
                algorithms=[self.config.jwt_algorithm],
            )

            # Verify token type
            if payload.get("type") != token_type:
                return None

            return payload

        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    def decode_token_unverified(self, token: str) -> dict[str, Any] | None:
        """
        Decode a token without verification (for inspection only).

        Returns:
            Decoded payload or None if malformed
        """
        try:
            return jwt.decode(
                token,
                options={"verify_signature": False},
            )
        except Exception:
            return None

    def get_token_expiry(self, token: str) -> datetime | None:
        """Get the expiry time of a token."""
        payload = self.decode_token_unverified(token)
        if payload and "exp" in payload:
            return datetime.utcfromtimestamp(payload["exp"])
        return None

    # ===== Platform Launch Tokens (cloud mode) =====

    def create_platform_launch_token(
        self,
        email: str,
        website_user_id: int,
        tier: str,
        credits: float,
        is_admin: bool,
    ) -> str:
        """Create a 60-second platform launch token (called by website)."""
        if not self._platform_config or not self._platform_config.website_jwt_secret:
            raise ValueError("Platform JWT secret not configured")

        now = datetime.utcnow()
        payload = {
            "sub": email,
            "website_user_id": website_user_id,
            "tier": tier,
            "credits": credits,
            "is_admin": is_admin,
            "type": "platform_launch",
            "iat": now,
            "exp": now + timedelta(seconds=60),
        }

        return jwt.encode(
            payload,
            self._platform_config.website_jwt_secret,
            algorithm="HS256",
        )

    def verify_platform_launch_token(self, token: str) -> dict[str, Any] | None:
        """Verify a platform launch token. Returns payload or None."""
        if not self._platform_config or not self._platform_config.website_jwt_secret:
            return None

        try:
            payload = jwt.decode(
                token,
                self._platform_config.website_jwt_secret,
                algorithms=["HS256"],
            )
            if payload.get("type") != "platform_launch":
                return None
            return payload
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None



# Global service instance (initialized on first use)
_auth_service: AuthService | None = None


def get_auth_service() -> AuthService:
    """Get the global auth service instance."""
    global _auth_service
    if _auth_service is None:
        from cachibot.config import Config

        config = Config.load()
        _auth_service = AuthService(config.auth, config.platform)
    return _auth_service


def reset_auth_service() -> None:
    """Reset the global auth service (for testing)."""
    global _auth_service
    _auth_service = None

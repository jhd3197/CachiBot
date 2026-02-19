"""Tests for authentication API endpoints.

Covers:
- Initial admin setup (first-time setup flow)
- Login with valid credentials (returns tokens)
- Login with wrong password (401)
- Access with valid token (GET /auth/me)
- Access with invalid/expired token (401)
- Access without token (401)
- Token refresh endpoint
- Rate limiting on login endpoint
- Admin user creation via POST /auth/users
"""

from datetime import datetime, timedelta

import jwt as pyjwt

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
import pytest

from cachibot.api.routes.auth import _rate_limit_store
from tests.conftest import create_test_user


@pytest.fixture(autouse=True)
def clear_rate_limit():
    """Clear the in-memory rate limiter between tests."""
    _rate_limit_store.clear()
    yield
    _rate_limit_store.clear()


# ---------------------------------------------------------------------------
# Setup / Signup
# ---------------------------------------------------------------------------


class TestSetup:
    """Test the initial admin setup flow (/auth/setup)."""

    async def test_setup_creates_admin_and_returns_tokens(self, api_client):
        """POST /auth/setup creates the first admin user and returns JWT tokens."""
        resp = await api_client.post(
            "/api/auth/setup",
            json={
                "email": "admin@setup.test",
                "username": "setupadmin",
                "password": "strongpass123",
            },
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["token_type"] == "bearer"
        assert data["user"]["role"] == "admin"
        assert data["user"]["email"] == "admin@setup.test"
        assert data["user"]["username"] == "setupadmin"

    async def test_setup_fails_if_users_exist(self, api_client, auth_service):
        """POST /auth/setup returns 400 when users already exist."""
        # Create a user first
        await create_test_user(
            auth_service,
            email="existing@test.com",
            username="existinguser",
        )

        resp = await api_client.post(
            "/api/auth/setup",
            json={
                "email": "second@test.com",
                "username": "secondadmin",
                "password": "password1234",
            },
        )
        assert resp.status_code == 400
        assert "already completed" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


class TestLogin:
    """Test the login endpoint (/auth/login)."""

    async def test_login_returns_tokens(self, api_client, auth_service):
        """POST /auth/login with valid credentials returns access + refresh tokens."""
        await create_test_user(
            auth_service,
            email="login@test.com",
            username="loginuser",
            password="correctpass1",
        )

        resp = await api_client.post(
            "/api/auth/login",
            json={"identifier": "login@test.com", "password": "correctpass1"},
        )
        assert resp.status_code == 200
        data = resp.json()

        assert "access_token" in data
        assert "refresh_token" in data
        assert data["user"]["email"] == "login@test.com"

    async def test_login_wrong_password(self, api_client, auth_service):
        """POST /auth/login with wrong password returns 401."""
        await create_test_user(
            auth_service,
            email="wrongpw@test.com",
            username="wrongpwuser",
            password="realpassword1",
        )

        resp = await api_client.post(
            "/api/auth/login",
            json={"identifier": "wrongpw@test.com", "password": "badpassword1"},
        )
        assert resp.status_code == 401
        assert "invalid credentials" in resp.json()["detail"].lower()

    async def test_login_nonexistent_user(self, api_client, auth_service):
        """POST /auth/login for a user that does not exist returns 401."""
        resp = await api_client.post(
            "/api/auth/login",
            json={"identifier": "nobody@test.com", "password": "irrelevant1"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token validation
# ---------------------------------------------------------------------------


class TestTokenAccess:
    """Test accessing protected endpoints with/without tokens."""

    async def test_valid_token_accesses_me(self, api_client, admin_user_with_token):
        """GET /auth/me with a valid token returns the user."""
        user, token = admin_user_with_token

        resp = await api_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == user.id
        assert data["email"] == user.email

    async def test_invalid_token_returns_401(self, api_client):
        """GET /auth/me with a garbage token returns 401."""
        resp = await api_client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer this.is.not.a.valid.jwt"},
        )
        assert resp.status_code == 401

    async def test_expired_token_returns_401(self, api_client, auth_service):
        """GET /auth/me with an expired token returns 401."""
        # Create a token that is already expired
        expired_payload = {
            "sub": "some-user-id",
            "role": "user",
            "type": "access",
            "iat": datetime.utcnow() - timedelta(hours=2),
            "exp": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = pyjwt.encode(
            expired_payload,
            auth_service._jwt_secret,
            algorithm="HS256",
        )

        resp = await api_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {expired_token}"},
        )
        assert resp.status_code == 401

    async def test_no_token_returns_401(self, api_client):
        """GET /auth/me without any Authorization header returns 401."""
        resp = await api_client.get("/api/auth/me")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Token refresh
# ---------------------------------------------------------------------------


class TestTokenRefresh:
    """Test the token refresh endpoint (/auth/refresh)."""

    async def test_refresh_returns_new_access_token(self, api_client, auth_service):
        """POST /auth/refresh with a valid refresh token returns a new access token."""
        user, _ = await create_test_user(
            auth_service,
            email="refresh@test.com",
            username="refreshuser",
            password="refreshpass1",
        )
        refresh_token = auth_service.create_refresh_token(user.id)

        resp = await api_client.post(
            "/api/auth/refresh",
            json={"refresh_token": refresh_token},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

        # The new access token should work
        me_resp = await api_client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        assert me_resp.status_code == 200

    async def test_refresh_with_invalid_token_returns_401(self, api_client):
        """POST /auth/refresh with an invalid token returns 401."""
        resp = await api_client.post(
            "/api/auth/refresh",
            json={"refresh_token": "invalid-refresh-token"},
        )
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    """Test rate limiting on auth endpoints."""

    async def test_rate_limit_blocks_after_max_attempts(self, api_client, auth_service):
        """Login endpoint returns 429 after too many attempts from same IP."""
        # Make 5 login attempts (the max allowed per window)
        for _ in range(5):
            await api_client.post(
                "/api/auth/login",
                json={"identifier": "nobody@test.com", "password": "wrong"},
            )

        # The 6th attempt should be rate-limited
        resp = await api_client.post(
            "/api/auth/login",
            json={"identifier": "nobody@test.com", "password": "wrong"},
        )
        assert resp.status_code == 429
        assert "too many" in resp.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Admin user creation
# ---------------------------------------------------------------------------


class TestAdminCreateUser:
    """Test admin-only user creation via POST /auth/users."""

    async def test_admin_creates_user(self, api_client, admin_user_with_token):
        """Admin can create a new user via POST /auth/users."""
        _, token = admin_user_with_token

        resp = await api_client.post(
            "/api/auth/users",
            json={
                "email": "newuser@test.com",
                "username": "newuser",
                "password": "newuserpass1",
                "role": "user",
            },
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "newuser@test.com"
        assert data["username"] == "newuser"
        assert data["role"] == "user"

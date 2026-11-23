"""Tests for per-bot execution log API endpoints.

Covers:
- GET /bots/{bot_id}/executions/stats returns run aggregates plus retentionDays
  (the same value the log retention service enforces)
- Stats rejects unknown periods with 422
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from cachibot.services.tier_limits import get_tier_limits


@pytest.fixture
async def executions_client(pg_db, auth_service):
    """Async HTTP client with the executions router mounted."""
    from fastapi import FastAPI

    from cachibot.api.routes import executions

    app = FastAPI()
    app.include_router(executions.router, tags=["executions"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestExecutionStats:
    """Test GET /bots/{bot_id}/executions/stats."""

    async def test_stats_includes_retention_days(self, executions_client, admin_user_with_token):
        """retentionDays matches the value the retention service uses."""
        _, token = admin_user_with_token
        bot_id = str(uuid.uuid4())

        resp = await executions_client.get(
            f"/api/bots/{bot_id}/executions/stats",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["retentionDays"] == get_tier_limits().log_retention_days
        assert "totalRuns" in data
        assert "errorCount" in data

    async def test_stats_rejects_unknown_period(self, executions_client, admin_user_with_token):
        """Period outside 24h/7d/30d is a 422."""
        _, token = admin_user_with_token
        bot_id = str(uuid.uuid4())

        resp = await executions_client.get(
            f"/api/bots/{bot_id}/executions/stats?period=1y",
            headers={"Authorization": f"Bearer {token}"},
        )

        assert resp.status_code == 422

    async def test_stats_requires_auth(self, executions_client):
        """Missing token is a 401."""
        bot_id = str(uuid.uuid4())

        resp = await executions_client.get(f"/api/bots/{bot_id}/executions/stats")

        assert resp.status_code == 401

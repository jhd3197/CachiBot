"""Tests for schedule next_run_at computation and the schedules API handlers.

Runs without PostgreSQL: the API handlers are exercised directly against an
in-memory fake ScheduleRepository, so the scheduler actually picks these
schedules up (next_run_at <= now) unlike the DB-gated tests in
test_scheduler.py.
"""

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException

from cachibot.api.routes import work
from cachibot.models.auth import User, UserRole
from cachibot.models.work import Schedule, ScheduleType
from cachibot.services.scheduler_service import compute_next_run


class _FakeScheduleRepo:
    """In-memory stand-in for ScheduleRepository (no database)."""

    def __init__(self) -> None:
        self._store: dict[str, Schedule] = {}

    async def save(self, schedule: Schedule) -> None:
        self._store[schedule.id] = schedule

    async def get(self, schedule_id: str) -> Schedule | None:
        return self._store.get(schedule_id)

    async def update(self, schedule: Schedule) -> None:
        self._store[schedule.id] = schedule


@pytest.fixture
def schedule_repo(monkeypatch):
    """Route handlers use this in-memory repository instead of the database."""
    fake = _FakeScheduleRepo()
    monkeypatch.setattr(work, "schedule_repo", fake)
    return fake


def _admin_user() -> User:
    return User(
        id="user-1",
        email="admin@test.com",
        username="admin",
        role=UserRole.ADMIN,
        created_at=datetime.now(timezone.utc),
    )


# ===========================================================================
# Next-run computation tests
# ===========================================================================


class TestComputeNextRun:
    """Tests for the compute_next_run helper used by the schedules API."""

    def test_once_returns_run_at(self):
        run_at = datetime.now(timezone.utc) + timedelta(hours=2)
        assert compute_next_run(ScheduleType.ONCE, run_at=run_at) == run_at

    def test_event_returns_none(self):
        assert compute_next_run(ScheduleType.EVENT) is None

    def test_interval_without_seconds_returns_none(self):
        assert compute_next_run(ScheduleType.INTERVAL) is None

    def test_interval_adds_seconds(self):
        before = datetime.now(timezone.utc)
        result = compute_next_run(ScheduleType.INTERVAL, interval_seconds=3600)
        assert result is not None
        assert 3500 < (result - before).total_seconds() < 3700

    def test_interval_uses_schedule_timezone(self):
        result = compute_next_run(
            ScheduleType.INTERVAL, interval_seconds=3600, timezone="America/New_York"
        )
        assert result is not None
        assert str(result.tzinfo) == "America/New_York"

    def test_cron_returns_future_occurrence(self):
        result = compute_next_run(ScheduleType.CRON, cron_expression="0 9 * * *")
        assert result is not None
        assert result > datetime.now(result.tzinfo)

    def test_cron_without_expression_returns_none(self):
        assert compute_next_run(ScheduleType.CRON) is None

    def test_cron_invalid_expression_raises(self):
        with pytest.raises(Exception):
            compute_next_run(ScheduleType.CRON, cron_expression="not a cron")

    def test_cron_uses_schedule_timezone(self):
        result = compute_next_run(
            ScheduleType.CRON, cron_expression="0 9 * * *", timezone="America/New_York"
        )
        assert result is not None
        assert str(result.tzinfo) == "America/New_York"
        assert result.hour == 9
        assert result.minute == 0

    def test_cron_invalid_timezone_falls_back_to_utc(self):
        result = compute_next_run(
            ScheduleType.CRON, cron_expression="0 9 * * *", timezone="Not/AZone"
        )
        assert result is not None
        assert str(result.tzinfo) == "UTC"


# ===========================================================================
# Schedules API next_run_at tests (handlers called directly, no DB)
# ===========================================================================


class TestScheduleApiNextRun:
    """create/update schedule handlers must set/recompute next_run_at."""

    async def test_create_schedule_sets_next_run_at(self, schedule_repo):
        resp = await work.create_schedule(
            "bot-1",
            work.CreateScheduleRequest(
                name="API Cron", scheduleType="cron", cronExpression="0 9 * * *"
            ),
            user=_admin_user(),
        )

        assert resp.nextRunAt is not None
        assert datetime.fromisoformat(resp.nextRunAt) > datetime.now(timezone.utc)
        stored = await schedule_repo.get(resp.id)
        assert stored is not None
        assert stored.next_run_at is not None

    async def test_create_schedule_event_has_no_next_run(self, schedule_repo):
        resp = await work.create_schedule(
            "bot-1",
            work.CreateScheduleRequest(name="API Event", scheduleType="event", eventTrigger="tick"),
            user=_admin_user(),
        )

        assert resp.nextRunAt is None

    async def test_create_schedule_invalid_cron_returns_422(self, schedule_repo):
        with pytest.raises(HTTPException) as exc_info:
            await work.create_schedule(
                "bot-1",
                work.CreateScheduleRequest(
                    name="Bad Cron", scheduleType="cron", cronExpression="not a cron"
                ),
                user=_admin_user(),
            )

        assert exc_info.value.status_code == 422

    async def test_update_schedule_recomputes_next_run_at(self, schedule_repo):
        run_at = datetime.now(timezone.utc) + timedelta(hours=1)
        created = await work.create_schedule(
            "bot-1",
            work.CreateScheduleRequest(
                name="API Once", scheduleType="once", runAt=run_at.isoformat()
            ),
            user=_admin_user(),
        )

        new_run_at = datetime.now(timezone.utc) + timedelta(hours=7)
        resp = await work.update_schedule(
            "bot-1",
            created.id,
            work.UpdateScheduleRequest(runAt=new_run_at.isoformat()),
            user=_admin_user(),
        )

        assert abs((datetime.fromisoformat(resp.nextRunAt) - new_run_at).total_seconds()) < 1

    async def test_update_schedule_invalid_cron_returns_422(self, schedule_repo):
        created = await work.create_schedule(
            "bot-1",
            work.CreateScheduleRequest(
                name="Cron To Fix", scheduleType="cron", cronExpression="0 9 * * *"
            ),
            user=_admin_user(),
        )
        before = (await schedule_repo.get(created.id)).next_run_at

        with pytest.raises(HTTPException) as exc_info:
            await work.update_schedule(
                "bot-1",
                created.id,
                work.UpdateScheduleRequest(cronExpression="not a cron"),
                user=_admin_user(),
            )

        assert exc_info.value.status_code == 422
        assert (await schedule_repo.get(created.id)).next_run_at == before

    async def test_update_non_trigger_field_keeps_next_run_at(self, schedule_repo):
        created = await work.create_schedule(
            "bot-1",
            work.CreateScheduleRequest(
                name="Cron Keep", scheduleType="cron", cronExpression="0 9 * * *"
            ),
            user=_admin_user(),
        )
        before = (await schedule_repo.get(created.id)).next_run_at

        resp = await work.update_schedule(
            "bot-1",
            created.id,
            work.UpdateScheduleRequest(name="Renamed"),
            user=_admin_user(),
        )

        assert resp.name == "Renamed"
        assert (await schedule_repo.get(created.id)).next_run_at == before

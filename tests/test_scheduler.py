"""Tests for the scheduler system: repositories, service, WebSocket messages, and LLM tools."""

import json
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from cachibot.models.websocket import WSMessage, WSMessageType
from cachibot.models.work import Schedule, ScheduleType, Todo, TodoStatus
from cachibot.services.scheduler_service import SchedulerService
from cachibot.storage.work_repository import ScheduleRepository, TodoRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
async def _db(pg_db):
    """Use PostgreSQL test database for all scheduler tests."""
    yield


def _make_schedule(
    *,
    schedule_type: ScheduleType = ScheduleType.ONCE,
    enabled: bool = True,
    next_run_at: datetime | None = None,
    interval_seconds: int | None = None,
    cron_expression: str | None = None,
    run_count: int = 0,
    bot_id: str = "bot-1",
) -> Schedule:
    now = datetime.now(timezone.utc)
    return Schedule(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        name="Test Schedule",
        description="A test schedule",
        function_id=None,
        function_params={"message": "hello", "chat_id": "chat-1"},
        schedule_type=schedule_type,
        cron_expression=cron_expression,
        interval_seconds=interval_seconds,
        run_at=next_run_at if schedule_type == ScheduleType.ONCE else None,
        timezone="UTC",
        enabled=enabled,
        max_concurrent=1,
        catch_up=False,
        created_at=now,
        updated_at=now,
        next_run_at=next_run_at,
        last_run_at=None,
        run_count=run_count,
    )


def _make_todo(
    *,
    status: TodoStatus = TodoStatus.OPEN,
    remind_at: datetime | None = None,
    bot_id: str = "bot-1",
) -> Todo:
    now = datetime.now(timezone.utc)
    return Todo(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        chat_id="chat-1",
        title="Test Todo",
        notes="some notes",
        status=status,
        priority="normal",
        created_at=now,
        remind_at=remind_at,
        tags=[],
    )


# ===========================================================================
# Repository Tests
# ===========================================================================


class TestScheduleRepository:
    """Tests for ScheduleRepository CRUD operations."""

    async def test_schedule_save_and_get(self):
        repo = ScheduleRepository()
        sched = _make_schedule(next_run_at=datetime.now(timezone.utc) + timedelta(hours=1))
        await repo.save(sched)

        loaded = await repo.get(sched.id)
        assert loaded is not None
        assert loaded.id == sched.id
        assert loaded.name == sched.name
        assert loaded.bot_id == sched.bot_id
        assert loaded.schedule_type == sched.schedule_type
        assert loaded.enabled == sched.enabled
        assert loaded.run_count == sched.run_count

    async def test_get_due_schedules_returns_overdue(self):
        repo = ScheduleRepository()
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        sched = _make_schedule(next_run_at=past, enabled=True)
        await repo.save(sched)

        due = await repo.get_due_schedules()
        ids = [s.id for s in due]
        assert sched.id in ids

    async def test_get_due_schedules_ignores_future(self):
        repo = ScheduleRepository()
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        sched = _make_schedule(next_run_at=future, enabled=True)
        await repo.save(sched)

        due = await repo.get_due_schedules()
        ids = [s.id for s in due]
        assert sched.id not in ids

    async def test_get_due_schedules_ignores_disabled(self):
        repo = ScheduleRepository()
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        sched = _make_schedule(next_run_at=past, enabled=False)
        await repo.save(sched)

        due = await repo.get_due_schedules()
        ids = [s.id for s in due]
        assert sched.id not in ids

    async def test_record_run_increments_count(self):
        repo = ScheduleRepository()
        sched = _make_schedule(
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            run_count=0,
        )
        await repo.save(sched)

        await repo.record_run(sched.id)
        updated = await repo.get(sched.id)
        assert updated.run_count == 1
        assert updated.last_run_at is not None

    async def test_update_next_run(self):
        repo = ScheduleRepository()
        sched = _make_schedule(next_run_at=datetime.now(timezone.utc))
        await repo.save(sched)

        new_time = datetime.now(timezone.utc) + timedelta(hours=2)
        await repo.update_next_run(sched.id, new_time)
        updated = await repo.get(sched.id)
        # Compare with ~1 second tolerance (isoformat round-trip)
        assert abs((updated.next_run_at - new_time).total_seconds()) < 1

    async def test_toggle_enabled(self):
        repo = ScheduleRepository()
        sched = _make_schedule(enabled=True, next_run_at=datetime.now(timezone.utc))
        await repo.save(sched)

        await repo.toggle_enabled(sched.id, False)
        updated = await repo.get(sched.id)
        assert updated.enabled is False

    async def test_schedule_delete(self):
        repo = ScheduleRepository()
        sched = _make_schedule(next_run_at=datetime.now(timezone.utc))
        await repo.save(sched)

        deleted = await repo.delete(sched.id)
        assert deleted is True
        assert await repo.get(sched.id) is None


# ===========================================================================
# Todo Reminder Repository Tests
# ===========================================================================


class TestTodoRepository:
    """Tests for TodoRepository reminder queries."""

    async def test_get_due_reminders_returns_overdue(self):
        repo = TodoRepository()
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        todo = _make_todo(remind_at=past, status=TodoStatus.OPEN)
        await repo.save(todo)

        due = await repo.get_due_reminders()
        ids = [t.id for t in due]
        assert todo.id in ids

    async def test_get_due_reminders_ignores_done(self):
        repo = TodoRepository()
        past = datetime.now(timezone.utc) - timedelta(minutes=5)
        todo = _make_todo(remind_at=past, status=TodoStatus.DONE)
        await repo.save(todo)

        due = await repo.get_due_reminders()
        ids = [t.id for t in due]
        assert todo.id not in ids


# ===========================================================================
# Scheduler Service Tests
# ===========================================================================


class TestSchedulerService:
    """Tests for SchedulerService._fire_schedule behaviour."""

    async def test_fire_schedule_once(self):
        repo = ScheduleRepository()
        sched = _make_schedule(
            schedule_type=ScheduleType.ONCE,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        await repo.save(sched)

        svc = SchedulerService()
        with patch.object(svc, "_deliver_message", new_callable=AsyncMock):
            await svc._fire_schedule(sched)

        updated = await repo.get(sched.id)
        assert updated.enabled is False
        assert updated.next_run_at is None

    async def test_fire_schedule_interval(self):
        repo = ScheduleRepository()
        sched = _make_schedule(
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=3600,
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        await repo.save(sched)

        svc = SchedulerService()
        with patch.object(svc, "_deliver_message", new_callable=AsyncMock):
            before = datetime.now(timezone.utc)
            await svc._fire_schedule(sched)

        updated = await repo.get(sched.id)
        assert updated.next_run_at is not None
        # next_run_at should be roughly 1 hour from now
        delta = (updated.next_run_at - before).total_seconds()
        assert 3500 < delta < 3700

    async def test_fire_schedule_cron(self):
        repo = ScheduleRepository()
        sched = _make_schedule(
            schedule_type=ScheduleType.CRON,
            cron_expression="0 9 * * *",
            next_run_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        await repo.save(sched)

        svc = SchedulerService()
        with patch.object(svc, "_deliver_message", new_callable=AsyncMock):
            await svc._fire_schedule(sched)

        updated = await repo.get(sched.id)
        assert updated.next_run_at is not None
        # Next run should be in the future
        assert updated.next_run_at > datetime.now(timezone.utc)


# ===========================================================================
# WebSocket Message Tests
# ===========================================================================


class TestWSMessage:
    """Tests for WSMessage.scheduled_notification factory."""

    def test_scheduled_notification_message(self):
        msg = WSMessage.scheduled_notification(
            bot_id="bot-1",
            chat_id="chat-1",
            content="Hello from scheduler",
        )
        assert msg.type == WSMessageType.SCHEDULED_NOTIFICATION
        assert msg.payload["botId"] == "bot-1"
        assert msg.payload["chatId"] == "chat-1"
        assert msg.payload["content"] == "Hello from scheduler"

    def test_scheduled_notification_without_chat_id(self):
        msg = WSMessage.scheduled_notification(
            bot_id="bot-1",
            chat_id=None,
            content="No chat",
        )
        assert msg.type == WSMessageType.SCHEDULED_NOTIFICATION
        assert "chatId" not in msg.payload
        assert msg.payload["botId"] == "bot-1"
        assert msg.payload["content"] == "No chat"


# ===========================================================================
# LLM Tool (Plugin Skill) Tests
# ===========================================================================


class TestScheduleTools:
    """Tests for the schedule_create / schedule_list / schedule_delete LLM tools."""

    def _build_plugin(self, bot_id: str = "bot-1", chat_id: str = "chat-1"):
        from unittest.mock import MagicMock

        from cachibot.plugins.base import PluginContext
        from cachibot.plugins.work_management import WorkManagementPlugin

        ctx = MagicMock(spec=PluginContext)
        ctx.bot_id = bot_id
        ctx.chat_id = chat_id
        ctx.config = MagicMock()
        ctx.sandbox = MagicMock()
        plugin = WorkManagementPlugin(ctx)
        return plugin

    async def test_schedule_create_once(self):
        plugin = self._build_plugin()
        fn = plugin.skills["schedule_create"].fn

        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = await fn(name="Once Test", message="hello", run_at=run_at)
        data = json.loads(result)
        assert data["type"] == "once"
        assert data["enabled"] is True
        assert data["id"]

        # Verify persisted
        repo = ScheduleRepository()
        sched = await repo.get(data["id"])
        assert sched is not None
        assert sched.schedule_type == ScheduleType.ONCE

    async def test_schedule_create_interval(self):
        plugin = self._build_plugin()
        fn = plugin.skills["schedule_create"].fn

        result = await fn(name="Interval Test", message="ping", interval_seconds=3600)
        data = json.loads(result)
        assert data["type"] == "interval"
        assert data["enabled"] is True

        repo = ScheduleRepository()
        sched = await repo.get(data["id"])
        assert sched is not None
        assert sched.interval_seconds == 3600

    async def test_schedule_create_cron(self):
        plugin = self._build_plugin()
        fn = plugin.skills["schedule_create"].fn

        result = await fn(
            name="Cron Test", message="daily", cron_expression="0 9 * * *"
        )
        data = json.loads(result)
        assert data["type"] == "cron"
        assert data["enabled"] is True

        repo = ScheduleRepository()
        sched = await repo.get(data["id"])
        assert sched is not None
        assert sched.cron_expression == "0 9 * * *"

    async def test_schedule_list(self):
        plugin = self._build_plugin()
        create_fn = plugin.skills["schedule_create"].fn
        list_fn = plugin.skills["schedule_list"].fn

        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        await create_fn(name="Sched A", message="a", run_at=run_at)
        await create_fn(name="Sched B", message="b", interval_seconds=3600)

        result = await list_fn()
        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) >= 2
        names = {s["name"] for s in data}
        assert "Sched A" in names
        assert "Sched B" in names

    async def test_schedule_delete_tool(self):
        plugin = self._build_plugin()
        create_fn = plugin.skills["schedule_create"].fn
        delete_fn = plugin.skills["schedule_delete"].fn

        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        result = await create_fn(name="To Delete", message="bye", run_at=run_at)
        schedule_id = json.loads(result)["id"]

        delete_result = await delete_fn(schedule_id=schedule_id)
        assert "deleted" in delete_result.lower()

        repo = ScheduleRepository()
        assert await repo.get(schedule_id) is None

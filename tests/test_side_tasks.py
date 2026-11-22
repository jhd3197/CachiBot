"""Tests for side tasks: service (queue, stop, resume), API and git requirement.

Runs entirely on SQLite in a tmp dir — no PostgreSQL needed. The agent run
is mocked; git tests use a real git repo in a tmp dir.
"""

import asyncio
import subprocess
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.chat_model import Chat
from cachibot.models.group import BotAccessLevel
from cachibot.models.side_task import SideTask, SideTaskStatus
from cachibot.services.side_task_service import (
    MAX_RUNNING_PER_PARENT,
    SideTaskService,
    SideTaskStartError,
)
from cachibot.storage.db import Base
from cachibot.storage.group_repository import BotAccessRepository, GroupRepository
from cachibot.storage.repository import BotRepository, ChatRepository
from cachibot.storage.side_task_repository import SideTaskRepository
from cachibot.storage.user_repository import OwnershipRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite database in a tmp dir, patched into the shared session maker."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/test.db", echo=False)
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import cachibot.storage.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_mod.engine
    original_session_maker = db_mod.async_session_maker
    db_mod.engine = engine
    db_mod.async_session_maker = session_maker

    yield session_maker

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()
    db_mod.engine = original_engine
    db_mod.async_session_maker = original_session_maker


class FakeTurn:
    """Mock agent run: records calls, can block on a gate or raise."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.gate: asyncio.Event | None = None
        self.error: Exception | None = None

    async def __call__(self, side_task: SideTask) -> None:
        self.calls.append(side_task.id)
        if self.gate is not None:
            await self.gate.wait()
        if self.error is not None:
            raise self.error


@pytest.fixture
def service(sqlite_db, monkeypatch):
    """Fresh SideTaskService with a mocked agent turn and broadcast."""
    svc = SideTaskService()
    fake = FakeTurn()
    broadcasts: list[dict] = []

    async def fake_broadcast(side_task: SideTask) -> None:
        broadcasts.append(side_task.model_dump(mode="json", by_alias=True))

    monkeypatch.setattr(svc, "_execute_turn", fake)
    monkeypatch.setattr(svc, "_broadcast", fake_broadcast)

    async def fake_git_check() -> None:
        return None

    monkeypatch.setattr(svc, "_ensure_git_workspace", fake_git_check)
    monkeypatch.setattr("cachibot.services.side_task_service._side_task_service", svc)
    return SimpleNamespace(svc=svc, fake=fake, broadcasts=broadcasts)


async def wait_for(predicate, timeout: float = 5.0) -> None:
    """Poll (awaiting async predicates) until true or time out."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        result = predicate()
        if asyncio.iscoroutine(result):
            result = await result
        if result:
            return
        await asyncio.sleep(0.02)
    raise AssertionError("Timed out waiting for condition")


async def status_is(side_task_id: str, status: SideTaskStatus) -> bool:
    latest = await SideTaskRepository().get(side_task_id)
    return latest is not None and latest.status == status


# ---------------------------------------------------------------------------
# Seed helpers
# ---------------------------------------------------------------------------


async def make_bot(owner_user_id: str | None = None) -> str:
    """Create a bot (optionally owned by a user). Returns bot id."""
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await BotRepository().upsert_bot(
        Bot(
            id=bot_id,
            name="Test Bot",
            model="test/model",
            systemPrompt="You are a test bot.",
            createdAt=now,
            updatedAt=now,
        )
    )
    if owner_user_id:
        await OwnershipRepository().assign_bot_owner(
            BotOwnership(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                user_id=owner_user_id,
                created_at=now,
            )
        )
    return bot_id


async def make_chat(bot_id: str, parent_chat_id: str | None = None, title: str = "Chat") -> Chat:
    """Create a chat row. Returns the Chat entity."""
    now = datetime.now(timezone.utc)
    chat = Chat(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        title=title,
        parent_chat_id=parent_chat_id,
        created_at=now,
        updated_at=now,
    )
    await ChatRepository().create_chat(chat)
    return chat


def git_init(path: Path) -> None:
    """Initialize a git repo in a tmp dir."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


# ---------------------------------------------------------------------------
# Service tests: start, queue limit, FIFO promotion
# ---------------------------------------------------------------------------


class TestStartAndQueue:
    async def test_start_creates_chat_record_and_work(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        svc: SideTaskService = service.svc

        st = await svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Update the changelog")

        assert st.status == SideTaskStatus.RUNNING
        assert st.started_at is not None
        assert st.work_id is not None

        # The side task's own chat is nested under the parent
        chat = await ChatRepository().get_chat(st.chat_id)
        assert chat is not None
        assert chat.parent_chat_id == parent.id
        assert chat.title == "Update the changelog"

        # A Work row links the side task (for Runs)
        work = await svc._work_repo.get(st.work_id)
        assert work is not None
        assert work.chat_id == st.chat_id

        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

    async def test_title_derived_from_prompt(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        long_prompt = "Update the changelog for the last release and check it twice. " * 3

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt=long_prompt)

        first_line = long_prompt.strip().splitlines()[0]
        assert st.title == first_line[:59].rstrip() + "…"

    async def test_start_missing_parent_fails(self, service):
        bot_id = await make_bot()
        with pytest.raises(SideTaskStartError, match="not found"):
            await service.svc.start(parent_chat_id=str(uuid.uuid4()), bot_id=bot_id, prompt="Do it")

    async def test_start_on_side_task_chat_fails(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        side = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="First")
        await wait_for(lambda: status_is(side.id, SideTaskStatus.DONE))

        with pytest.raises(SideTaskStartError, match="one level deep"):
            await service.svc.start(parent_chat_id=side.chat_id, bot_id=bot_id, prompt="Nested")

    async def test_limit_four_running_per_parent_and_fifo(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        svc: SideTaskService = service.svc
        service.fake.gate = asyncio.Event()  # keep turns blocked

        started = []
        for i in range(MAX_RUNNING_PER_PARENT + 2):
            st = await svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt=f"Task {i}")
            started.append(st)

        running = [st for st in started if st.status == SideTaskStatus.RUNNING]
        waiting = [st for st in started if st.status == SideTaskStatus.WAITING_FOR_SLOT]
        assert len(running) == MAX_RUNNING_PER_PARENT
        assert len(waiting) == 2

        # Free all slots: the waiting tasks promote in FIFO order
        service.fake.gate.set()

        async def all_done() -> bool:
            for st in started:
                if not await status_is(st.id, SideTaskStatus.DONE):
                    return False
            return True

        await wait_for(all_done)

        # FIFO: the 5th was promoted (got its slot) before the 6th
        repo = SideTaskRepository()
        fourth = await repo.get(started[4].id)
        fifth = await repo.get(started[5].id)
        assert fourth.started_at is not None and fifth.started_at is not None
        assert fourth.started_at <= fifth.started_at

    async def test_limit_is_per_parent(self, service):
        bot_id = await make_bot()
        parent_a = await make_chat(bot_id)
        parent_b = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()

        for _ in range(MAX_RUNNING_PER_PARENT):
            await service.svc.start(parent_chat_id=parent_a.id, bot_id=bot_id, prompt="A")
        st_b = await service.svc.start(parent_chat_id=parent_b.id, bot_id=bot_id, prompt="B")

        assert st_b.status == SideTaskStatus.RUNNING


# ---------------------------------------------------------------------------
# Service tests: stop, cascade, failure, needs_you / resume
# ---------------------------------------------------------------------------


class TestStopAndNeedsYou:
    async def test_stop_running_task(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: len(service.fake.calls) == 1)

        stopped = await service.svc.stop(st.id)
        assert stopped is not None
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))
        latest = await SideTaskRepository().get(st.id)
        assert latest.status == SideTaskStatus.STOPPED
        assert latest.finished_at is not None

    async def test_stop_waiting_task_keeps_it_from_running(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()

        tasks = [
            await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt=f"T{i}")
            for i in range(MAX_RUNNING_PER_PARENT + 1)
        ]
        waiting = tasks[-1]
        assert waiting.status == SideTaskStatus.WAITING_FOR_SLOT

        await service.svc.stop(waiting.id)
        await wait_for(lambda: status_is(waiting.id, SideTaskStatus.STOPPED))

        # Free the running ones — the stopped one must not be promoted
        service.fake.gate.set()
        await wait_for(lambda: len(service.fake.calls) == MAX_RUNNING_PER_PARENT)
        await asyncio.sleep(0.1)
        latest = await SideTaskRepository().get(waiting.id)
        assert latest.status == SideTaskStatus.STOPPED

    async def test_stop_all_for_parent_cascades(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        other_parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()

        mine = [
            await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt=f"M{i}")
            for i in range(3)
        ]
        theirs = await service.svc.start(
            parent_chat_id=other_parent.id, bot_id=bot_id, prompt="Other"
        )

        count = await service.svc.stop_all_for_parent(parent.id)
        assert count == 3

        for st in mine:
            await wait_for(lambda sid=st.id: status_is(sid, SideTaskStatus.STOPPED))
        # The other parent's side task keeps running
        assert not await status_is(theirs.id, SideTaskStatus.STOPPED)

    async def test_failure_marks_failed_and_records_error(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.error = RuntimeError("boom")

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.FAILED))

        latest = await SideTaskRepository().get(st.id)
        assert latest.status == SideTaskStatus.FAILED
        assert latest.error == "boom"
        assert latest.finished_at is not None

    async def test_mark_needs_you_and_resume(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: len(service.fake.calls) == 1)

        await service.svc.mark_needs_you(st.id, "Which version number?")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.NEEDS_YOU))
        latest = await SideTaskRepository().get(st.id)
        assert latest.needs_you_reason == "Which version number?"

        # Resume: re-runs the turn and finishes
        service.fake.gate.set()
        resumed = await service.svc.resume(st.id)
        assert resumed is not None and resumed.status == SideTaskStatus.RUNNING
        await wait_for(lambda: len(service.fake.calls) == 2)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        latest = await SideTaskRepository().get(st.id)
        assert latest.needs_you_reason is None
        assert latest.status == SideTaskStatus.DONE

    async def test_broadcast_on_every_state_change(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        statuses = [b["status"] for b in service.broadcasts if b["id"] == st.id]
        assert "running" in statuses
        assert "done" in statuses
        # Payloads are camelCase with the full record
        payload = service.broadcasts[-1]
        assert payload["parentChatId"] == parent.id
        assert payload["chatId"] == st.chat_id


# ---------------------------------------------------------------------------
# Service tests: restart resume
# ---------------------------------------------------------------------------


class TestRestartResume:
    async def _seed(self, bot_id: str, parent_chat_id: str, status: SideTaskStatus) -> SideTask:
        now = datetime.now(timezone.utc)
        st = SideTask(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            parent_chat_id=parent_chat_id,
            chat_id=str(uuid.uuid4()),
            title=f"Task {uuid.uuid4().hex[:6]}",
            prompt="Do something",
            status=status,
            started_at=now if status == SideTaskStatus.RUNNING else None,
        )
        await make_chat(bot_id, parent_chat_id=parent_chat_id, title=st.title)
        await SideTaskRepository().save(st)
        return st

    async def test_restart_resumes_running_and_keeps_limit(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        repo = SideTaskRepository()
        service.fake.gate = asyncio.Event()  # keep resumed turns blocked

        # 5 running for one parent: only 4 resume, the 5th goes back to waiting
        running = [
            await self._seed(bot_id, parent.id, SideTaskStatus.RUNNING)
            for _ in range(MAX_RUNNING_PER_PARENT + 1)
        ]
        # A waiting one stays queued until a slot frees
        waiting = await self._seed(bot_id, parent.id, SideTaskStatus.WAITING_FOR_SLOT)
        # A needs_you one is untouched
        needs_you = await self._seed(bot_id, parent.id, SideTaskStatus.NEEDS_YOU)
        needs_you.needs_you_reason = "question"
        await repo.update(needs_you)

        await service.svc.resume_on_startup()

        # Exactly the 4 oldest running turns are resumed
        await wait_for(lambda: len(service.fake.calls) == MAX_RUNNING_PER_PARENT)
        assert set(service.fake.calls) == {st.id for st in running[:MAX_RUNNING_PER_PARENT]}
        assert waiting.id not in service.fake.calls
        assert needs_you.id not in service.fake.calls

        latest = await repo.get(running[-1].id)
        assert latest.status == SideTaskStatus.WAITING_FOR_SLOT
        latest_ny = await repo.get(needs_you.id)
        assert latest_ny.status == SideTaskStatus.NEEDS_YOU

        # Free the slots: the demoted one reclaims its slot first (FIFO),
        # then the one that was waiting
        service.fake.gate.set()

        async def both_done() -> bool:
            return await status_is(running[-1].id, SideTaskStatus.DONE) and await status_is(
                waiting.id, SideTaskStatus.DONE
            )

        await wait_for(both_done)

        # Promotion order (started_at), not call order, is the FIFO guarantee
        demoted = await repo.get(running[-1].id)
        queued = await repo.get(waiting.id)
        assert demoted.started_at is not None and queued.started_at is not None
        assert demoted.started_at <= queued.started_at

    async def test_restart_resumes_multiple_parents(self, service):
        bot_id = await make_bot()
        parent_a = await make_chat(bot_id)
        parent_b = await make_chat(bot_id)

        a1 = await self._seed(bot_id, parent_a.id, SideTaskStatus.RUNNING)
        b1 = await self._seed(bot_id, parent_b.id, SideTaskStatus.RUNNING)

        await service.svc.resume_on_startup()

        await wait_for(lambda: len(service.fake.calls) == 2)
        assert set(service.fake.calls) == {a1.id, b1.id}


# ---------------------------------------------------------------------------
# Git requirement
# ---------------------------------------------------------------------------


class TestGitRequired:
    def _use_real_git_check(self, service, monkeypatch) -> None:
        """Remove the no-op stub so the real git workspace check runs."""
        monkeypatch.delattr(service.svc, "_ensure_git_workspace", raising=False)

    async def test_start_fails_without_git_repo(self, service, tmp_path, monkeypatch):
        self._use_real_git_check(service, monkeypatch)
        monkeypatch.setattr(
            "cachibot.config.Config.load",
            lambda *a, **k: SimpleNamespace(workspace_path=tmp_path),
        )
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        with pytest.raises(SideTaskStartError, match="git repository"):
            await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")

    async def test_start_succeeds_in_git_repo(self, service, tmp_path, monkeypatch):
        self._use_real_git_check(service, monkeypatch)
        monkeypatch.setattr(
            "cachibot.config.Config.load",
            lambda *a, **k: SimpleNamespace(workspace_path=tmp_path),
        )
        git_init(tmp_path)
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        assert st.status == SideTaskStatus.RUNNING


# ---------------------------------------------------------------------------
# API tests
# ---------------------------------------------------------------------------


@pytest.fixture
async def st_client(sqlite_db, auth_service, service):
    """HTTP client wired to an app with only the side task routes."""
    from fastapi import FastAPI

    from cachibot.api.routes import side_tasks

    app = FastAPI()
    app.include_router(side_tasks.router, tags=["side-tasks"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


class TestSideTaskApi:
    async def test_requires_auth(self, st_client):
        bot_id = await make_bot()
        resp = await st_client.get(f"/api/bots/{bot_id}/side-tasks")
        assert resp.status_code == 401

    async def test_viewer_can_list_but_not_start(self, st_client, auth_service):
        from tests.conftest import create_test_user

        owner, _ = await create_test_user(auth_service, email="owner@test.com", username="owner")
        viewer, _ = await create_test_user(
            auth_service, email="viewer@test.com", username="viewer1"
        )
        viewer_token = auth_service.create_access_token(viewer.id, viewer.role.value)
        bot_id = await make_bot(owner.id)
        parent = await make_chat(bot_id)

        # Share the bot with the viewer's group at viewer level
        group = await GroupRepository().create_group("Viewers", created_by=owner.id)
        await GroupRepository().add_member(group.id, viewer.id)
        await BotAccessRepository().share_bot(
            bot_id, group.id, BotAccessLevel.VIEWER, granted_by=owner.id
        )

        headers = {"Authorization": f"Bearer {viewer_token}"}
        resp = await st_client.get(f"/api/bots/{bot_id}/side-tasks", headers=headers)
        assert resp.status_code == 200
        assert resp.json() == []

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Do it"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_start_stop_flow(self, st_client, auth_service, service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="o@test.com", username="o")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        headers = {"Authorization": f"Bearer {token}"}

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Update the changelog"},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "running"
        assert data["title"] == "Update the changelog"
        assert data["parentChatId"] == parent.id
        assert data["chatId"] != parent.id
        assert data["startedBy"] == "user"
        assert data["workId"] is not None

        # The side task chat is nested under the parent
        chat = await ChatRepository().get_chat(data["chatId"])
        assert chat.parent_chat_id == parent.id

        # List (with and without parent filter)
        resp = await st_client.get(f"/api/bots/{bot_id}/side-tasks", headers=headers)
        assert len(resp.json()) == 1
        other_parent = await make_chat(bot_id)
        await st_client.post(
            f"/api/bots/{bot_id}/chats/{other_parent.id}/side-tasks",
            json={"prompt": "Other", "title": "Other task"},
            headers=headers,
        )
        resp = await st_client.get(
            f"/api/bots/{bot_id}/side-tasks",
            params={"parent_chat_id": parent.id},
            headers=headers,
        )
        assert len(resp.json()) == 1

        # Get one
        resp = await st_client.get(f"/api/bots/{bot_id}/side-tasks/{data['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["id"] == data["id"]

        # Stop after the turn finished
        await wait_for(lambda: status_is(data["id"], SideTaskStatus.DONE))
        resp = await st_client.post(
            f"/api/bots/{bot_id}/side-tasks/{data['id']}/stop", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "done"

    async def test_stop_running_via_api(self, st_client, auth_service, service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="s@test.com", username="s")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        headers = {"Authorization": f"Bearer {token}"}
        service.fake.gate = asyncio.Event()

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Long task"},
            headers=headers,
        )
        side_task_id = resp.json()["id"]
        await wait_for(lambda: len(service.fake.calls) == 1)

        resp = await st_client.post(
            f"/api/bots/{bot_id}/side-tasks/{side_task_id}/stop", headers=headers
        )
        assert resp.status_code == 200
        await wait_for(lambda: status_is(side_task_id, SideTaskStatus.STOPPED))

    async def test_start_validation(self, st_client, auth_service, service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="v@test.com", username="v")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        headers = {"Authorization": f"Bearer {token}"}

        # Empty prompt -> 422
        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": ""},
            headers=headers,
        )
        assert resp.status_code == 422

        # Unknown chat -> 400
        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{uuid.uuid4()}/side-tasks",
            json={"prompt": "Do it"},
            headers=headers,
        )
        assert resp.status_code == 400

        # Side tasks are one level deep -> 400
        side = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="First")
        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{side.chat_id}/side-tasks",
            json={"prompt": "Nested"},
            headers=headers,
        )
        assert resp.status_code == 400

    async def test_start_requires_git_workspace(
        self, st_client, auth_service, service, tmp_path, monkeypatch
    ):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="g@test.com", username="g")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)

        monkeypatch.delattr(service.svc, "_ensure_git_workspace", raising=False)
        monkeypatch.setattr(
            "cachibot.config.Config.load",
            lambda *a, **k: SimpleNamespace(workspace_path=tmp_path),
        )

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Do it"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 400
        assert "git" in resp.json()["detail"]

    async def test_get_unknown_returns_404(self, st_client, auth_service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="n@test.com", username="n")
        token = auth_service.create_access_token(user.id, UserRole.USER.value)
        bot_id = await make_bot(user.id)

        resp = await st_client.get(
            f"/api/bots/{bot_id}/side-tasks/{uuid.uuid4()}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# WebSocket scoping: side-task events only reach users with bot access
# ---------------------------------------------------------------------------


class FakeWebSocket:
    """Records sent messages like a real WebSocket."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def accept(self) -> None:
        pass

    async def send_json(self, data: dict) -> None:
        self.sent.append(data)


class StubManager:
    """Records scoped broadcasts; backs pending_approval dicts."""

    def __init__(self) -> None:
        self.pending_approvals: dict = {}
        self.approval_results: dict = {}
        self.scoped: list[tuple] = []

    async def broadcast_to_bot(self, message, bot_id: str) -> None:
        self.scoped.append((message, bot_id))


@pytest.fixture
async def scoped_actors(sqlite_db, auth_service):
    """Owner, group viewer, stranger and admin around one bot."""
    from tests.conftest import create_test_user

    owner, _ = await create_test_user(auth_service, email="so@test.com", username="so")
    viewer, _ = await create_test_user(auth_service, email="sv@test.com", username="sv")
    stranger, _ = await create_test_user(auth_service, email="ss@test.com", username="ss")
    admin, _ = await create_test_user(
        auth_service, email="sa@test.com", username="sa", role=UserRole.ADMIN
    )
    bot_id = await make_bot(owner.id)
    group = await GroupRepository().create_group("Scoped", created_by=owner.id)
    await GroupRepository().add_member(group.id, viewer.id)
    await BotAccessRepository().share_bot(
        bot_id, group.id, BotAccessLevel.VIEWER, granted_by=owner.id
    )
    return SimpleNamespace(
        users={"owner": owner, "viewer": viewer, "stranger": stranger, "admin": admin},
        bot_id=bot_id,
    )


class TestScopedBroadcast:
    async def test_broadcast_to_bot_scopes_by_access(self, scoped_actors):
        from cachibot.api.websocket import ConnectionManager
        from cachibot.models.websocket import WSMessage

        manager = ConnectionManager()
        sockets: dict[str, FakeWebSocket] = {}
        for name, user in scoped_actors.users.items():
            ws = FakeWebSocket()
            await manager.connect(ws, name, user=user)
            sockets[name] = ws

        msg = WSMessage.side_task_update({"id": "st1", "title": "Secret title"})
        await manager.broadcast_to_bot(msg, scoped_actors.bot_id)

        # Owner, group viewer and admin receive it; the stranger does not
        assert len(sockets["owner"].sent) == 1
        assert len(sockets["viewer"].sent) == 1
        assert len(sockets["admin"].sent) == 1
        assert sockets["stranger"].sent == []

        # Unscoped broadcast still reaches everyone (existing behavior)
        await manager.broadcast(WSMessage.error("x"))
        assert len(sockets["owner"].sent) == 2
        assert len(sockets["viewer"].sent) == 2
        assert len(sockets["admin"].sent) == 2
        assert len(sockets["stranger"].sent) == 1  # only the unscoped one

    async def test_disconnect_stops_scoped_delivery(self, scoped_actors):
        from cachibot.api.websocket import ConnectionManager
        from cachibot.models.websocket import WSMessage

        manager = ConnectionManager()
        ws = FakeWebSocket()
        await manager.connect(ws, "owner", user=scoped_actors.users["owner"])
        manager.disconnect("owner")

        await manager.broadcast_to_bot(WSMessage.side_task_update({}), scoped_actors.bot_id)
        assert ws.sent == []

    async def test_service_broadcast_uses_scoped_send(self, monkeypatch):
        import cachibot.services.side_task_service as stm

        stub = StubManager()
        monkeypatch.setattr("cachibot.api.websocket.manager", stub)

        svc = stm.SideTaskService()
        side_task = SideTask(
            id="st-1",
            bot_id="bot-1",
            parent_chat_id="chat-1",
            chat_id="chat-2",
            title="Secret",
            prompt="Do the secret thing",
        )
        await svc._broadcast(side_task)

        assert len(stub.scoped) == 1
        message, bot_id = stub.scoped[0]
        assert bot_id == "bot-1"
        assert message.type.value == "side_task_update"
        assert message.payload["title"] == "Secret"

    async def test_side_task_approval_uses_scoped_send(self, monkeypatch):
        import cachibot.services.side_task_service as stm

        monkeypatch.setattr(stm, "_APPROVAL_TIMEOUT_SECONDS", 0.1)
        stub = StubManager()
        monkeypatch.setattr("cachibot.api.websocket.manager", stub)

        svc = stm.SideTaskService()
        config = SimpleNamespace(agent=SimpleNamespace(approve_actions=False))
        handler = svc._make_approval_handler(config, "bot-9")

        # Nobody answers: falls back to the agent's approval policy
        result = await handler("file_write", "Write a file", {"path": "x.py"})
        assert result is True

        assert len(stub.scoped) == 1
        message, bot_id = stub.scoped[0]
        assert bot_id == "bot-9"
        assert message.type.value == "approval_needed"
        # Pending request is cleaned up after the timeout
        assert stub.pending_approvals == {}
        assert stub.approval_results == {}


# ---------------------------------------------------------------------------
# Resume must not duplicate the prompt in the side chat
# ---------------------------------------------------------------------------


class _FakeConversation:
    def __init__(self) -> None:
        self.seeded: list[tuple[str, str]] = []

    def add_context(self, role: str, content: str) -> None:
        self.seeded.append((role, content))


class _FakeAgent:
    def __init__(self) -> None:
        self.conversation = _FakeConversation()
        self.run_messages: list[str] = []

    async def run(self, message: str, images: object = None) -> SimpleNamespace:
        self.run_messages.append(message)
        return SimpleNamespace(output_text="All done")


@pytest.fixture
def fake_agent_factory(monkeypatch):
    """Route build_bot_agent to a fake agent and return it."""
    agent = _FakeAgent()

    async def fake_build(config, **kwargs) -> _FakeAgent:
        return agent

    monkeypatch.setattr("cachibot.services.agent_factory.build_bot_agent", fake_build)
    monkeypatch.setattr("cachibot.config.Config.load", lambda *a, **k: SimpleNamespace())
    return agent


async def _seed_side_task(sqlite_db, prompt: str) -> tuple[SideTask, Chat]:
    bot_id = await make_bot()
    parent = await make_chat(bot_id)
    chat = await make_chat(bot_id, parent_chat_id=parent.id, title="Side")
    st = SideTask(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        parent_chat_id=parent.id,
        chat_id=chat.id,
        title="Side",
        prompt=prompt,
        status=SideTaskStatus.RUNNING,
    )
    await SideTaskRepository().save(st)
    return st, chat


async def _persist_user_message(st: SideTask, content: str) -> None:
    from cachibot.models.knowledge import BotMessage
    from cachibot.storage.repository import KnowledgeRepository

    await KnowledgeRepository().save_bot_message(
        BotMessage(
            id=str(uuid.uuid4()),
            bot_id=st.bot_id,
            chat_id=st.chat_id,
            role="user",
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
    )


async def _prompt_copies(st: SideTask) -> int:
    from cachibot.storage.repository import KnowledgeRepository

    messages = await KnowledgeRepository().get_bot_messages(st.bot_id, st.chat_id, limit=100)
    return sum(1 for m in messages if m.role == "user" and m.content == st.prompt)


class TestResumePromptPersistence:
    async def test_fresh_turn_persists_prompt_once(self, sqlite_db, fake_agent_factory):
        st, _chat = await _seed_side_task(sqlite_db, "Fix the bug")
        svc = SideTaskService()

        await svc._execute_turn(st)

        assert await _prompt_copies(st) == 1

    async def test_resume_mid_turn_keeps_single_prompt(self, sqlite_db, fake_agent_factory):
        """Interrupted before the assistant replied: chat already ends with the prompt."""
        st, _chat = await _seed_side_task(sqlite_db, "Fix the bug")
        await _persist_user_message(st, "Fix the bug")
        svc = SideTaskService()

        await svc._execute_turn(st)

        assert await _prompt_copies(st) == 1

    async def test_resume_after_needs_you_keeps_single_prompt(self, sqlite_db, fake_agent_factory):
        """Resumed with a user answer in the chat: prompt is the first message."""
        st, _chat = await _seed_side_task(sqlite_db, "Fix the bug")
        await _persist_user_message(st, "Fix the bug")
        await _persist_user_message(st, "Use version 2.0")
        svc = SideTaskService()

        await svc._execute_turn(st)

        assert await _prompt_copies(st) == 1
        # The answer is seeded and the run continues the conversation
        assert ("user", "Use version 2.0") in fake_agent_factory.conversation.seeded
        assert fake_agent_factory.run_messages[0].startswith("Continue this side task")

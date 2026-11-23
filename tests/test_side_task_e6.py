"""Tests for side-task follow-ups (E6): replies inside the side chat, the
diff endpoint, execution-log rows in Runs, and the done-callback regression.

Runs entirely on SQLite in a tmp dir — no PostgreSQL needed. The agent turn
is mocked; git runs for real against repos in tmp dirs, so nothing here can
touch the developer's checkout (the autouse ``hermetic_side_task_git``
conftest fixture refuses side-task git ops outside the system temp dir).
"""

import asyncio
import shutil
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
from cachibot.config import Config
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.chat_model import Chat
from cachibot.models.group import BotAccessLevel
from cachibot.models.side_task import SideTask, SideTaskStatus
from cachibot.services.side_task_service import (
    MAX_RUNNING_PER_PARENT,
    SideTaskReplyError,
    SideTaskService,
    SideTaskStartError,
)
from cachibot.storage.db import Base
from cachibot.storage.group_repository import BotAccessRepository, GroupRepository
from cachibot.storage.repository import BotRepository, ChatRepository, KnowledgeRepository
from cachibot.storage.side_task_repository import SideTaskRepository
from cachibot.storage.user_repository import OwnershipRepository

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite database in a tmp dir, patched into the shared session maker."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_conn, _record) -> None:  # pragma: no cover - plumbing
        dbapi_conn.execute("PRAGMA journal_mode=WAL")
        dbapi_conn.execute("PRAGMA synchronous=NORMAL")

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
    """Mock agent run: records calls, can block on a gate."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.gate: asyncio.Event | None = None

    async def __call__(self, side_task: SideTask) -> None:
        self.calls.append(side_task.id)
        if self.gate is not None:
            await self.gate.wait()


@pytest.fixture
async def service(sqlite_db, monkeypatch, tmp_path):
    """Fresh SideTaskService with a mocked turn, broadcast and git check.

    The workspace is a real git repo in a tmp dir; teardown cancels and
    awaits in-flight turns so none outlive the test's database/loop.
    """
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

    workspace = tmp_path / "workspace"
    workspace.mkdir()
    git_init(workspace)
    git(workspace, "commit", "--allow-empty", "-m", "init")

    def fake_config_load(*args, **kwargs) -> Config:
        config = Config()
        config.workspace_path = workspace
        return config

    monkeypatch.setattr("cachibot.config.Config.load", fake_config_load)
    monkeypatch.setattr(
        "cachibot.services.side_task_worktrees.worktrees_base_dir",
        lambda: tmp_path / "worktrees",
    )
    yield SimpleNamespace(svc=svc, fake=fake, broadcasts=broadcasts, workspace=workspace)

    await svc.shutdown()


@pytest.fixture
async def e6_client(sqlite_db, auth_service, service):
    """HTTP client with the side-task and executions routers mounted."""
    from fastapi import FastAPI

    from cachibot.api.routes import executions, side_tasks

    app = FastAPI()
    app.include_router(side_tasks.router, tags=["side-tasks"])
    app.include_router(executions.router, tags=["executions"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


async def wait_for(predicate, timeout: float = 30.0) -> None:
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


async def parent_side_task_replies(bot_id: str, parent_chat_id: str) -> list:
    """The parent chat's persisted side-task thread replies."""
    return [
        m
        for m in await KnowledgeRepository().get_bot_messages(bot_id, parent_chat_id, limit=100)
        if (m.metadata or {}).get("kind") == "side_task_reply"
    ]


async def make_bot(owner_user_id: str | None = None) -> str:
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
    now = datetime.now(timezone.utc)
    chat = Chat(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        title=title,
        platform=None,
        platform_chat_id=None,
        pinned=False,
        archived=False,
        parent_chat_id=parent_chat_id,
        created_at=now,
        updated_at=now,
    )
    await ChatRepository().create_chat(chat)
    return chat


def git_init(path: Path) -> None:
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [
            "git",
            "-c",
            "user.name=Tester",
            "-c",
            "user.email=tester@localhost",
            "-C",
            str(repo),
            *args,
        ],
        capture_output=True,
        text=True,
        check=check,
    )


def commit_file(repo: Path, name: str, content: str, message: str | None = None) -> str:
    (repo / name).write_text(content)
    git(repo, "add", name)
    git(repo, "commit", "-m", message or f"change {name}")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


async def _worktree_of(side_task_id: str) -> Path:
    latest = await SideTaskRepository().get(side_task_id)
    assert latest is not None and latest.worktree_path
    return Path(latest.worktree_path)


async def _start_gated(service, bot_id: str, parent: Chat, title: str = "Task") -> SideTask:
    service.fake.gate = asyncio.Event()
    st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt=title, title=title)
    await wait_for(lambda: st.id in service.fake.calls)
    return st


async def _operator_headers(auth_service, email: str = "op@test.com", username: str = "op"):
    from tests.conftest import create_test_user

    user, _ = await create_test_user(auth_service, email=email, username=username)
    token = auth_service.create_access_token(user.id, UserRole.USER.value)
    bot_id = await make_bot(user.id)
    parent = await make_chat(bot_id)
    return {"Authorization": f"Bearer {token}"}, bot_id, parent


# ---------------------------------------------------------------------------
# Replies: continue in the worktree, re-merge only new changes
# ---------------------------------------------------------------------------


class TestReplyContinuation:
    async def test_reply_merges_only_new_changes_and_updates_reply_in_place(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        async def turn_one(st: SideTask) -> None:
            Path(st.worktree_path, "side.txt").write_text("first round\n")

        async def turn_two(st: SideTask) -> None:
            Path(st.worktree_path, "side2.txt").write_text("second round\n")

        turns = [turn_one, turn_two]

        async def router(st: SideTask) -> None:
            await turns.pop(0)(st)

        service.svc._execute_turn = router
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Round one", title="Round one"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        first = await SideTaskRepository().get(st.id)
        assert {f["path"] for f in first.merged_files} == {"side.txt"}
        assert not Path(first.worktree_path).exists()  # cleaned up after the merge

        # The settle persists the status BEFORE posting the parent-chat
        # reply, so on slow runners the reply lands a few awaits later:
        # wait for the exact outcome — exactly one reply, stamped on the
        # record — instead of reading right after the status flip.
        async def one_stamped_reply() -> bool:
            record = await SideTaskRepository().get(st.id)
            if record is None or not record.reply_message_id:
                return False
            return len(await parent_side_task_replies(bot_id, parent.id)) == 1

        await wait_for(one_stamped_reply)
        reply_id = (await SideTaskRepository().get(st.id)).reply_message_id

        # Reply inside the side task: it lands in the side chat, the task
        # runs again and only the NEW file comes back
        updated = await service.svc.reply(st.id, "Also add side2.txt")
        assert updated is not None and updated.status == SideTaskStatus.RUNNING
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))

        side_msgs = await KnowledgeRepository().get_bot_messages(bot_id, st.chat_id, limit=50)
        assert any(m.role == "user" and m.content == "Also add side2.txt" for m in side_msgs)

        # The continued turn branched from the first merge commit, so its
        # base is that merge — and only the new file is reported
        latest = await SideTaskRepository().get(st.id)
        assert {f["path"] for f in latest.merged_files} == {"side2.txt"}
        assert (service.workspace / "side.txt").read_text() == "first round\n"
        assert (service.workspace / "side2.txt").read_text() == "second round\n"
        assert latest.base_commit == first.merged_commit
        assert latest.base_commit != first.base_commit
        assert git(service.workspace, "rev-parse", "HEAD").stdout.strip() == latest.merged_commit

        # Same parent-chat reply, updated in place for the second merge —
        # again wait until the message actually reflects the second
        # bring-in before asserting on it.
        async def reply_shows_second_merge() -> bool:
            record = await SideTaskRepository().get(st.id)
            replies = await parent_side_task_replies(bot_id, parent.id)
            if record is None or len(replies) != 1:
                return False
            msg = replies[0]
            return (
                msg.id == record.reply_message_id
                and msg.metadata.get("status") == "merged"
                and {f["path"] for f in msg.metadata.get("mergedFiles", [])} == {"side2.txt"}
            )

        await wait_for(reply_shows_second_merge)
        replies_after = await parent_side_task_replies(bot_id, parent.id)
        assert len(replies_after) == 1
        assert replies_after[0].id == reply_id

    async def test_reply_on_done_recreates_worktree_from_current_parent_head(self, service):
        """A `done` task merged nothing: its worktree/branch are gone, so a
        reply starts a fresh branch from the parent's current HEAD."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="No changes", title="No changes"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))
        done = await SideTaskRepository().get(st.id)
        assert not Path(done.worktree_path).exists()
        assert git(service.workspace, "branch", "--list", "side/*").stdout == ""

        # The parent moves on before the reply lands
        commit_file(service.workspace, "other.txt", "unrelated\n", "unrelated work")

        async def turn_two(s: SideTask) -> None:
            Path(s.worktree_path, "fresh.txt").write_text("fresh work\n")

        service.svc._execute_turn = turn_two
        service.fake.gate = asyncio.Event()  # keep the continued turn blocked
        updated = await service.svc.reply(st.id, "Now do something")
        assert updated is not None and updated.status == SideTaskStatus.RUNNING

        latest = await SideTaskRepository().get(st.id)
        wt = Path(latest.worktree_path)
        assert wt.is_dir()
        # Fresh branch from the CURRENT HEAD: the unrelated file is there,
        # and the base is the new parent tip (so only new work merges)
        assert (wt / "other.txt").read_text() == "unrelated\n"
        assert latest.base_commit == git(service.workspace, "rev-parse", "HEAD").stdout.strip()

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        latest = await SideTaskRepository().get(st.id)
        assert {f["path"] for f in latest.merged_files} == {"fresh.txt"}
        assert (service.workspace / "fresh.txt").read_text() == "fresh work\n"

    async def test_reply_on_needs_you_keeps_existing_worktree(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await _start_gated(service, bot_id, parent, "Question task")
        wt = await _worktree_of(st.id)
        (wt / "draft.txt").write_text("uncommitted\n")

        await service.svc.mark_needs_you(st.id, "Which version should the entry use?")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.NEEDS_YOU))

        updated = await service.svc.reply(st.id, "v0.10.0 please")
        assert updated is not None and updated.status == SideTaskStatus.RUNNING

        latest = await SideTaskRepository().get(st.id)
        assert latest.worktree_path == str(wt)  # same worktree, work intact
        assert (wt / "draft.txt").read_text() == "uncommitted\n"
        assert latest.needs_you_reason is None

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        latest = await SideTaskRepository().get(st.id)
        assert {f["path"] for f in latest.merged_files} == {"draft.txt"}

    async def test_reply_on_stopped_reuses_branch_when_worktree_dir_gone(self, service):
        """Worktree dir deleted by hand, branch alive: the reply recreates
        the checkout from the branch and continues on it."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await _start_gated(service, bot_id, parent, "Survivor")
        wt = await _worktree_of(st.id)
        (wt / "committed.txt").write_text("committed work\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-m", "wip")
        tip = git(wt, "rev-parse", "HEAD").stdout.strip()

        await service.svc.stop(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))
        shutil.rmtree(wt)
        assert not wt.exists()

        updated = await service.svc.reply(st.id, "Keep going")
        assert updated is not None
        latest = await SideTaskRepository().get(st.id)
        assert Path(latest.worktree_path).is_dir()
        # Recreated from the branch: the committed work is still there
        assert git(Path(latest.worktree_path), "rev-parse", "HEAD").stdout.strip() == tip
        assert latest.branch == updated.branch

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        latest = await SideTaskRepository().get(st.id)
        assert {f["path"] for f in latest.merged_files} == {"committed.txt"}
        assert (service.workspace / "committed.txt").read_text() == "committed work\n"

    async def test_reply_rejected_while_running_or_waiting(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await _start_gated(service, bot_id, parent, "Busy")

        with pytest.raises(SideTaskReplyError, match="still working"):
            await service.svc.reply(st.id, "hello?")

        # Fill the remaining slots; a queued side task rejects replies too
        waiting = None
        for i in range(MAX_RUNNING_PER_PARENT):
            other = await service.svc.start(
                parent_chat_id=parent.id, bot_id=bot_id, prompt=f"T{i}", title=f"T{i}"
            )
            if other.status == SideTaskStatus.WAITING_FOR_SLOT:
                waiting = other
        assert waiting is not None
        with pytest.raises(SideTaskReplyError, match="still working"):
            await service.svc.reply(waiting.id, "now?")

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))
        await wait_for(lambda: status_is(waiting.id, SideTaskStatus.DONE))

    async def test_reply_rejected_on_merge_conflict(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        gate = asyncio.Event()

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "file.txt").write_text("side version\n")
            await gate.wait()

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Docs", title="Docs"
        )

        async def side_file_written() -> bool:
            wt = await SideTaskRepository().get(st.id)
            return bool(wt and wt.worktree_path and (Path(wt.worktree_path) / "file.txt").exists())

        await wait_for(side_file_written)
        # The parent rewrites the same file: the automatic merge will conflict
        commit_file(service.workspace, "file.txt", "parent version\n", "parent change")
        gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.NEEDS_YOU))
        latest = await SideTaskRepository().get(st.id)
        assert latest.needs_you_reason == "merge_conflict"

        with pytest.raises(SideTaskReplyError, match="merge conflict"):
            await service.svc.reply(st.id, "use mine")

    async def test_reply_respects_four_per_parent_limit(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()  # one gate for all four turns
        running = [
            await service.svc.start(
                parent_chat_id=parent.id, bot_id=bot_id, prompt=f"R{i}", title=f"R{i}"
            )
            for i in range(MAX_RUNNING_PER_PARENT)
        ]
        await wait_for(lambda: len(service.fake.calls) == MAX_RUNNING_PER_PARENT)
        stopped = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Idle", title="Idle"
        )
        await wait_for(lambda: status_is(stopped.id, SideTaskStatus.WAITING_FOR_SLOT))
        await service.svc.stop(stopped.id)
        await wait_for(lambda: status_is(stopped.id, SideTaskStatus.STOPPED))

        # All four slots are taken: the replied task waits for one
        updated = await service.svc.reply(stopped.id, "Wake up")
        assert updated is not None and updated.status == SideTaskStatus.WAITING_FOR_SLOT

        # Stopping one of the four promotes the replied task FIFO
        await service.svc.stop(running[0].id)
        await wait_for(lambda: status_is(stopped.id, SideTaskStatus.RUNNING))
        await wait_for(lambda: stopped.id in service.fake.calls)

        service.fake.gate.set()
        for st in running[1:] + [stopped]:
            await wait_for(lambda sid=st.id: status_is(sid, SideTaskStatus.DONE))

    async def test_reply_requires_git_workspace(self, service, tmp_path, monkeypatch):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Task", title="Task"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        monkeypatch.setattr(
            "cachibot.config.Config.load",
            lambda *a, **k: SimpleNamespace(workspace_path=tmp_path / "not-a-repo"),
        )
        with pytest.raises(SideTaskStartError, match="git"):
            await service.svc.reply(st.id, "Anyone there?")


# ---------------------------------------------------------------------------
# Reply API
# ---------------------------------------------------------------------------


class TestReplyApi:
    async def test_reply_flow_via_api(self, e6_client, auth_service, service):
        headers, bot_id, parent = await _operator_headers(auth_service)
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Task", title="Task"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        resp = await e6_client.post(
            f"/api/bots/{bot_id}/side-tasks/{st.id}/messages",
            json={"content": "One more thing"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["status"] in ("running", "waiting_for_slot")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        # The reply is persisted in the side chat
        side_task = await SideTaskRepository().get(st.id)
        msgs = await KnowledgeRepository().get_bot_messages(bot_id, side_task.chat_id, limit=50)
        assert any(m.role == "user" and m.content == "One more thing" for m in msgs)

    async def test_viewer_cannot_reply(self, e6_client, auth_service, service):
        from tests.conftest import create_test_user

        owner, _ = await create_test_user(auth_service, email="own2@test.com", username="own2")
        viewer, _ = await create_test_user(auth_service, email="view2@test.com", username="view2")
        viewer_token = auth_service.create_access_token(viewer.id, viewer.role.value)
        bot_id = await make_bot(owner.id)
        await make_chat(bot_id)
        group = await GroupRepository().create_group("Viewers", created_by=owner.id)
        await GroupRepository().add_member(group.id, viewer.id)
        await BotAccessRepository().share_bot(
            bot_id, group.id, BotAccessLevel.VIEWER, granted_by=owner.id
        )
        headers = {"Authorization": f"Bearer {viewer_token}"}

        resp = await e6_client.post(
            f"/api/bots/{bot_id}/side-tasks/{uuid.uuid4()}/messages",
            json={"content": "hi"},
            headers=headers,
        )
        assert resp.status_code == 403

    async def test_reply_unknown_returns_404(self, e6_client, auth_service, service):
        headers, bot_id, _parent = await _operator_headers(auth_service)
        resp = await e6_client.post(
            f"/api/bots/{bot_id}/side-tasks/{uuid.uuid4()}/messages",
            json={"content": "hi"},
            headers=headers,
        )
        assert resp.status_code == 404

    async def test_reply_running_returns_409(self, e6_client, auth_service, service):
        headers, bot_id, parent = await _operator_headers(auth_service)
        st = await _start_gated(service, bot_id, parent, "Busy")
        resp = await e6_client.post(
            f"/api/bots/{bot_id}/side-tasks/{st.id}/messages",
            json={"content": "hi"},
            headers=headers,
        )
        assert resp.status_code == 409
        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

    async def test_reply_requires_content(self, e6_client, auth_service, service):
        headers, bot_id, parent = await _operator_headers(auth_service)
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Task", title="Task"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))
        resp = await e6_client.post(
            f"/api/bots/{bot_id}/side-tasks/{st.id}/messages",
            json={"content": ""},
            headers=headers,
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


class TestDiff:
    async def test_diff_unmerged_includes_uncommitted_and_untracked(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")
        st = await _start_gated(service, bot_id, parent, "Working")

        wt = await _worktree_of(st.id)
        (wt / "file.txt").write_text("base\nchanged\n")  # modified, uncommitted
        (wt / "brand_new.txt").write_text("untracked\n")  # never staged

        diff = await service.svc.diff(st.id)
        assert diff is not None
        by_path = {f.path: f for f in diff.files}
        assert by_path["file.txt"].status == "modified"
        assert by_path["file.txt"].additions == 1
        assert by_path["brand_new.txt"].status == "added"
        assert "changed" in diff.diff
        assert "untracked" in diff.diff
        assert diff.base and diff.head is None  # worktree diff
        assert not diff.truncated

    async def test_diff_merged_shows_only_the_latest_range(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        async def turn_one(st: SideTask) -> None:
            Path(st.worktree_path, "one.txt").write_text("one\n")

        async def turn_two(st: SideTask) -> None:
            Path(st.worktree_path, "two.txt").write_text("two\n")

        turns = [turn_one, turn_two]

        async def router(st: SideTask) -> None:
            await turns.pop(0)(st)

        service.svc._execute_turn = router
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Rounds", title="Rounds"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        await service.svc.reply(st.id, "again")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))

        latest = await SideTaskRepository().get(st.id)
        diff = await service.svc.diff(st.id)
        assert diff is not None
        assert {f.path for f in diff.files} == {"two.txt"}
        assert "two.txt" in diff.diff
        assert "one.txt" not in diff.diff
        assert diff.base == latest.base_commit
        assert diff.head == latest.merged_commit

    async def test_diff_with_worktree_gone_uses_branch_range(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await _start_gated(service, bot_id, parent, "Committed work")
        wt = await _worktree_of(st.id)
        (wt / "wip.txt").write_text("wip\n")
        git(wt, "add", "-A")
        git(wt, "commit", "-m", "wip")

        await service.svc.stop(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))
        shutil.rmtree(wt)

        diff = await service.svc.diff(st.id)
        assert diff is not None
        assert {f.path for f in diff.files} == {"wip.txt"}
        assert "wip" in diff.diff

    async def test_diff_truncates_huge_changes(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "big.txt", "seed\n", "add big")
        st = await _start_gated(service, bot_id, parent, "Huge")

        wt = await _worktree_of(st.id)
        (wt / "big.txt").write_text("".join(f"line {i}\n" for i in range(60000)))

        diff = await service.svc.diff(st.id)
        assert diff is not None
        assert diff.truncated
        assert len(diff.diff.encode()) <= 512 * 1024 + 64

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))

    async def test_diff_flags_binary_files(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await _start_gated(service, bot_id, parent, "Binary")

        wt = await _worktree_of(st.id)
        (wt / "blob.bin").write_bytes(b"\x00\x01\x02\x03")

        diff = await service.svc.diff(st.id)
        assert diff is not None
        by_path = {f.path: f for f in diff.files}
        assert by_path["blob.bin"].binary
        assert by_path["blob.bin"].additions is None
        assert by_path["blob.bin"].deletions is None

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))

    async def test_diff_empty_when_nothing_to_show(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Nothing", title="Nothing"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))
        diff = await service.svc.diff(st.id)
        assert diff is not None
        assert diff.files == []
        assert diff.diff == ""

    async def test_diff_endpoint(self, e6_client, auth_service, service):
        from tests.conftest import create_test_user

        owner, _ = await create_test_user(auth_service, email="own3@test.com", username="own3")
        viewer, _ = await create_test_user(auth_service, email="view3@test.com", username="view3")
        viewer_token = auth_service.create_access_token(viewer.id, viewer.role.value)
        bot_id = await make_bot(owner.id)
        parent = await make_chat(bot_id)
        group = await GroupRepository().create_group("Viewers", created_by=owner.id)
        await GroupRepository().add_member(group.id, viewer.id)
        await BotAccessRepository().share_bot(
            bot_id, group.id, BotAccessLevel.VIEWER, granted_by=owner.id
        )

        commit_file(service.workspace, "file.txt", "base\n", "add file")
        st = await _start_gated(service, bot_id, parent, "Endpoint task")
        wt = await _worktree_of(st.id)
        (wt / "file.txt").write_text("base\nendpoint\n")

        # Viewers can read the diff (it is read-only)
        resp = await e6_client.get(
            f"/api/bots/{bot_id}/side-tasks/{st.id}/diff",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["sideTaskId"] == st.id
        assert data["status"] == "running"
        assert {f["path"] for f in data["files"]} == {"file.txt"}
        assert data["files"][0]["additions"] == 1
        assert "endpoint" in data["diff"]
        assert data["truncated"] is False

        resp = await e6_client.get(
            f"/api/bots/{bot_id}/side-tasks/{uuid.uuid4()}/diff",
            headers={"Authorization": f"Bearer {viewer_token}"},
        )
        assert resp.status_code == 404

        service.fake.gate.set()
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))


# ---------------------------------------------------------------------------
# Execution logs (Runs)
# ---------------------------------------------------------------------------


class TestExecutions:
    async def _side_task_rows(self, e6_client, headers, bot_id) -> list[dict]:
        resp = await e6_client.get(
            f"/api/bots/{bot_id}/executions?trigger=side_task", headers=headers
        )
        assert resp.status_code == 200
        return resp.json()

    async def test_turns_write_execution_rows_with_side_task_trigger(
        self, e6_client, auth_service, service
    ):
        headers, bot_id, parent = await _operator_headers(auth_service)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        state = {"n": 0}

        async def turn(st: SideTask) -> None:
            state["n"] += 1
            Path(st.worktree_path, f"notes{state['n']}.txt").write_text("notes\n")

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Notes", title="Notes"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        # A reply runs a second turn: a second row
        await service.svc.reply(st.id, "More notes")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.MERGED))
        latest = await SideTaskRepository().get(st.id)

        # Both rows settle shortly after the side task does — poll the API
        async def two_success_rows() -> bool:
            rows = await self._side_task_rows(e6_client, headers, bot_id)
            return len(rows) == 2 and all(r["status"] == "success" for r in rows)

        await wait_for(two_success_rows)
        rows = await self._side_task_rows(e6_client, headers, bot_id)
        for row in rows:
            assert row["trigger"] == "side_task"
            assert row["executionType"] == "side_task"
            assert row["sourceType"] == "side_task"
            assert row["sourceId"] == st.id
            assert row["sourceName"] == "Notes"
            assert row["chatId"] == parent.id  # grouped under the parent chat
            assert row["sideTaskId"] == st.id
            assert row["sideTaskChatId"] == st.chat_id
            assert row["workId"] == latest.work_id
            assert row["startedAt"] and row["finishedAt"] and row["durationMs"] is not None

        # Unfiltered listing returns them too
        resp = await e6_client.get(f"/api/bots/{bot_id}/executions", headers=headers)
        assert len(resp.json()) == 2

        # Key step lines are retrievable per row
        row = rows[0]
        resp = await e6_client.get(
            f"/api/bots/{bot_id}/executions/{row['id']}/lines", headers=headers
        )
        assert resp.status_code == 200
        lines = resp.json()
        contents = [line["content"] for line in lines]
        assert any("Worktree ready" in c for c in contents)
        assert any("Turn finished" in c for c in contents)
        assert any("Merged back" in c for c in contents)

    async def test_stopped_turn_marks_cancelled_row(self, e6_client, auth_service, service):
        headers, bot_id, parent = await _operator_headers(auth_service)
        st = await _start_gated(service, bot_id, parent, "Stop me")
        await service.svc.stop(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))

        async def cancelled_row() -> bool:
            rows = await self._side_task_rows(e6_client, headers, bot_id)
            return len(rows) == 1 and rows[0]["status"] == "cancelled"

        await wait_for(cancelled_row)
        rows = await self._side_task_rows(e6_client, headers, bot_id)
        assert rows[0]["output"] == "Stopped"

    async def test_failed_turn_marks_error_row(self, e6_client, auth_service, service):
        headers, bot_id, parent = await _operator_headers(auth_service)

        async def boom(st: SideTask) -> None:
            raise RuntimeError("provider exploded")

        service.svc._execute_turn = boom
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Boom", title="Boom"
        )
        await wait_for(lambda: status_is(st.id, SideTaskStatus.FAILED))

        async def error_row() -> bool:
            rows = await self._side_task_rows(e6_client, headers, bot_id)
            return len(rows) == 1 and rows[0]["status"] == "error"

        await wait_for(error_row)
        rows = await self._side_task_rows(e6_client, headers, bot_id)
        assert "provider exploded" in rows[0]["output"]

        resp = await e6_client.get(
            f"/api/bots/{bot_id}/executions/{rows[0]['id']}/lines", headers=headers
        )
        assert any("Failed" in line["content"] for line in resp.json())


# ---------------------------------------------------------------------------
# Regression: the done-callback must not evict a freshly launched turn
# ---------------------------------------------------------------------------


class TestDoneCallbackEviction:
    async def test_cancelled_turn_done_callback_keeps_newer_handle(self, service):
        """needs_you cancels turn A; resume() launches turn B before A's
        done-callback runs. Without the identity check, A's callback pops
        B's handle and Stop loses the running turn (direct-transition
        fallback while it keeps working)."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()
        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: st.id in service.fake.calls)

        await service.svc.mark_needs_you(st.id, "Which one?")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.NEEDS_YOU))

        resumed = await service.svc.resume(st.id)
        assert resumed is not None and resumed.status == SideTaskStatus.RUNNING
        second_handle = service.svc._running.get(st.id)
        assert second_handle is not None

        # A's done callback fires here — it must not evict the new handle
        await asyncio.sleep(0.1)
        assert service.svc._running.get(st.id) is second_handle

        # Stop reaches the live turn through its handle and settles it
        await service.svc.stop(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))
        await wait_for(lambda: second_handle.done())
        assert service.svc._running.get(st.id) is None

    async def test_done_callback_pops_only_its_own_handle(self, service):
        """Deterministic version of the race: an old turn completing after a
        new one was stored must not remove the new handle."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.gate = asyncio.Event()
        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Task")
        await wait_for(lambda: st.id in service.fake.calls)
        old_handle = service.svc._running[st.id]

        started = asyncio.Event()
        release = asyncio.Event()

        async def slow_turn(_st: SideTask) -> None:
            started.set()
            await release.wait()

        # The old turn is cancelled but stays alive in its cleanup window;
        # a new turn is stored meanwhile.
        old_handle.cancel()
        service.svc._execute_turn = slow_turn
        service.svc._running[st.id] = asyncio.ensure_future(slow_turn(st))
        new_handle = service.svc._running[st.id]
        await started.wait()

        # Now let the old done-callback run: the new handle must survive
        try:
            await old_handle
        except asyncio.CancelledError:
            pass
        await asyncio.sleep(0)
        assert service.svc._running.get(st.id) is new_handle

        release.set()
        await wait_for(lambda: new_handle.done())
        service.svc._running.pop(st.id, None)

"""E5 tests: side-task thread replies in the parent chat.

Covers source_message_id storage/validation/fallback, the one-reply-per-side-
task contract (created on the first qualifying transition, updated in place
after), the helper-group reply, and the scoped ``message_update`` broadcast.
Also migration 015 up/down on SQLite through real alembic.

Runs entirely on SQLite in a tmp dir — no PostgreSQL needed. The agent run
is mocked; the workspace is a real git repo in a tmp dir.
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
from cachibot.config import Config
from cachibot.models.auth import BotOwnership, UserRole
from cachibot.models.bot import Bot
from cachibot.models.chat_model import Chat
from cachibot.models.group import BotAccessLevel
from cachibot.models.knowledge import BotMessage
from cachibot.models.side_task import (
    SideTask,
    SideTaskKind,
    SideTaskStartedBy,
    SideTaskStatus,
)
from cachibot.services.side_task_service import SideTaskService, SideTaskStartError
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
async def service(sqlite_db, monkeypatch, tmp_path):
    """Fresh SideTaskService with a mocked agent turn and broadcast.

    The workspace is a real git repo in a tmp dir so worktree creation and
    the automatic merge back run for real. Teardown cancels any turn still
    running (a test that stops early must not leak tasks into the next
    test's loop) and waits for the cancellations to settle.
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

    # No turn may outlive the test's database/loop: cancel and await whatever
    # is still in flight (the conftest guard also keeps every git mutation
    # inside the system temp dir).
    await svc.shutdown()


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


async def save_user_message(bot_id: str, chat_id: str, content: str) -> BotMessage:
    """Persist a user message in a chat; returns it (usable as a source)."""
    message = BotMessage(
        id=str(uuid.uuid4()),
        bot_id=bot_id,
        chat_id=chat_id,
        role="user",
        content=content,
        timestamp=datetime.now(timezone.utc),
    )
    await KnowledgeRepository().save_bot_message(message)
    return message


def git_init(path: Path) -> None:
    """Initialize a git repo in a tmp dir."""
    subprocess.run(["git", "init"], cwd=path, check=True, capture_output=True)


def git(repo: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run git in a tmp repo with a test identity."""
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
    """Write and commit a file in a tmp repo. Returns the new commit sha."""
    (repo / name).write_text(content)
    git(repo, "add", name)
    git(repo, "commit", "-m", message or f"change {name}")
    return git(repo, "rev-parse", "HEAD").stdout.strip()


async def parent_messages(bot_id: str, parent_chat_id: str) -> list[BotMessage]:
    """Everything persisted in the parent chat."""
    return await KnowledgeRepository().get_bot_messages(bot_id, parent_chat_id, limit=100)


async def parent_replies(bot_id: str, parent_chat_id: str) -> list[BotMessage]:
    """Side-task reply messages persisted in the parent chat."""
    return [
        m
        for m in await parent_messages(bot_id, parent_chat_id)
        if m.metadata.get("kind") in ("side_task_reply", "side_task_group_reply")
    ]


async def reply_has_status(bot_id: str, parent_chat_id: str, status: str) -> bool:
    """The one reply exists and reflects `status` (the reply sync runs right
    after the record update in the same transition, so poll the reply
    itself — reading the record's status can win the race)."""
    replies = await parent_replies(bot_id, parent_chat_id)
    return len(replies) == 1 and replies[0].metadata.get("status") == status


async def side_chat_say(bot_id: str, chat_id: str, content: str, role: str = "assistant") -> None:
    """Append a message to a side task's own chat."""
    await KnowledgeRepository().save_bot_message(
        BotMessage(
            id=str(uuid.uuid4()),
            bot_id=bot_id,
            chat_id=chat_id,
            role=role,
            content=content,
            timestamp=datetime.now(timezone.utc),
        )
    )


# ---------------------------------------------------------------------------
# source_message_id: stored, validated, and the documented fallback
# ---------------------------------------------------------------------------


class TestSourceMessage:
    async def test_explicit_source_message_is_stored(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        source = await save_user_message(bot_id, parent.id, "Do the changelog on the side")

        st = await service.svc.start(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            prompt="Update the changelog",
            source_message_id=source.id,
        )
        assert st.source_message_id == source.id

        # The settle reply quotes exactly that message
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "done"))
        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].reply_to_id == source.id

    async def test_source_message_must_belong_to_parent_chat(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        other = await make_chat(bot_id)
        foreign = await save_user_message(bot_id, other.id, "other chat message")

        with pytest.raises(SideTaskStartError):
            await service.svc.start(
                parent_chat_id=parent.id,
                bot_id=bot_id,
                prompt="Nope",
                source_message_id=foreign.id,
            )

    async def test_unknown_source_message_rejected(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        with pytest.raises(SideTaskStartError):
            await service.svc.start(
                parent_chat_id=parent.id,
                bot_id=bot_id,
                prompt="Nope",
                source_message_id=str(uuid.uuid4()),
            )

    async def test_omitted_source_falls_back_to_latest_user_message(self, service):
        """Bot tools / the composer have no message reference: the latest
        user message in the parent chat is the one the turn is answering."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        await save_user_message(bot_id, parent.id, "First")
        latest = await save_user_message(bot_id, parent.id, "Latest")

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Side work")
        assert st.source_message_id == latest.id
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

    async def test_no_user_message_leaves_source_empty(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Side work")
        assert st.source_message_id is None

        await wait_for(lambda: reply_has_status(bot_id, parent.id, "done"))
        replies = await parent_replies(bot_id, parent.id)
        assert replies[0].reply_to_id is None  # nothing real to quote — no fake quote


# ---------------------------------------------------------------------------
# One reply per side task, updated in place
# ---------------------------------------------------------------------------


class TestSingleReply:
    async def test_merged_side_task_reply_carries_summary_and_merge(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        source = await save_user_message(bot_id, parent.id, "Rename the env vars")

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "config.py").write_text("NEW_NAME=1\n")
            await side_chat_say(bot_id, st.chat_id, "Renamed OLD_NAME to NEW_NAME in config.py.")

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            prompt="Rename the env vars",
            source_message_id=source.id,
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "merged"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        reply = replies[0]
        assert reply.role == "assistant"
        assert reply.metadata["kind"] == "side_task_reply"
        assert reply.metadata["sideTaskId"] == st.id
        assert reply.metadata["status"] == "merged"
        assert reply.metadata["replyTo"] == source.id
        assert reply.reply_to_id == source.id
        assert reply.metadata["chatId"] == st.chat_id
        # Summary: the side chat's last assistant message
        assert "Renamed OLD_NAME" in reply.content
        # Merge details for the card
        assert {f["path"] for f in reply.metadata["mergedFiles"]} == {"config.py"}
        assert reply.metadata["mergedCommit"]

        # The record points at the one reply message
        latest = await SideTaskRepository().get(st.id)
        assert latest.reply_message_id == reply.id

    async def test_exactly_one_reply_across_repeated_syncs(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Quiet task")
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "done"))

        # A later transition touching the same record must not duplicate
        latest = await SideTaskRepository().get(st.id)
        await service.svc._sync_single_reply(latest)
        await service.svc._sync_single_reply(latest)

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1

    async def test_failed_side_task_reply_carries_error(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.error = RuntimeError("agent blew up")

        await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Will fail")
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "failed"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].metadata["status"] == "failed"
        assert "agent blew up" in replies[0].metadata["error"]

    async def test_needs_you_reply_then_discard_updates_in_place(self, service):
        """The amber needs-you reply must not linger after a resolution."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        gate = asyncio.Event()

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "file.txt").write_text("side version\n")
            await gate.wait()

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Conflicting change"
        )

        async def side_file_written() -> bool:
            latest = await SideTaskRepository().get(st.id)
            wt = Path(latest.worktree_path) if latest.worktree_path else None
            return wt is not None and (wt / "file.txt").exists()

        await wait_for(side_file_written)
        commit_file(service.workspace, "file.txt", "parent version\n", "parent change")
        gate.set()
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "needs_you"))

        replies = await parent_replies(bot_id, parent.id)
        amber = replies[0]
        assert amber.metadata["status"] == "needs_you"
        assert amber.metadata["needsYouReason"] == "merge_conflict"
        assert amber.metadata["conflictFiles"] == ["file.txt"]
        amber_id = amber.id

        discarded = await service.svc.discard(st.id)
        assert discarded.status == SideTaskStatus.STOPPED

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1  # updated in place, not a second message
        assert replies[0].id == amber_id
        assert replies[0].metadata["status"] == "stopped"
        assert "needsYouReason" not in replies[0].metadata

    async def test_needs_you_then_retry_merge_updates_in_place(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        gate = asyncio.Event()

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "file.txt").write_text("side version\n")
            await gate.wait()

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Conflicting change"
        )

        async def side_file_written() -> bool:
            latest = await SideTaskRepository().get(st.id)
            wt = Path(latest.worktree_path) if latest.worktree_path else None
            return wt is not None and (wt / "file.txt").exists()

        await wait_for(side_file_written)
        commit_file(service.workspace, "file.txt", "parent version\n", "parent change")
        gate.set()
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "needs_you"))

        replies = await parent_replies(bot_id, parent.id)
        amber_id = replies[0].id

        latest = await SideTaskRepository().get(st.id)
        Path(latest.worktree_path, "file.txt").write_text("parent version\n")
        merged = await service.svc.retry_merge(st.id)
        assert merged.status == SideTaskStatus.MERGED

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].id == amber_id
        assert replies[0].metadata["status"] == "merged"
        assert "needsYouReason" not in replies[0].metadata
        assert "conflictFiles" not in replies[0].metadata
        assert replies[0].metadata["mergedCommit"]

    async def test_resume_rewrites_stale_needs_you_reply(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        # The turn stays blocked until the test stops the side task, so the
        # RUNNING state after resume is deterministic.
        gate = asyncio.Event()
        started: list[str] = []

        async def turn(st: SideTask) -> None:
            started.append(st.id)
            await gate.wait()

        service.svc._execute_turn = turn
        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="Needs a human"
        )
        await wait_for(lambda: len(started) == 1)
        await service.svc.mark_needs_you(st.id, "which version number?")
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "needs_you"))

        replies = await parent_replies(bot_id, parent.id)
        reply_id = replies[0].id

        await service.svc.resume(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.RUNNING))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].id == reply_id
        assert replies[0].metadata["status"] == "running"

        # Clean up the still-blocked turn
        gate.set()
        await service.svc.stop(st.id)
        await wait_for(lambda: status_is(st.id, SideTaskStatus.STOPPED))

    async def test_no_duplicate_with_old_system_note(self, service):
        """Bot-started or user-started: exactly one parent message, and it is
        the reply — the old E3 system note is gone."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        await service.svc.start(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            prompt="Bot-started side task",
            started_by=SideTaskStartedBy.BOT,
            kind=SideTaskKind.SIDE,
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "done"))

        messages = await parent_messages(bot_id, parent.id)
        assert len(messages) == 1
        assert messages[0].role == "assistant"
        assert messages[0].metadata["kind"] == "side_task_reply"
        assert all(m.role != "system" for m in messages)


# ---------------------------------------------------------------------------
# Helper groups: one reply, updated in place
# ---------------------------------------------------------------------------


class TestGroupReply:
    async def test_group_reply_created_once_and_updated_in_place(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        source = await save_user_message(bot_id, parent.id, "Test every Python version")

        gate = asyncio.Event()

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, f"{st.title.replace(' ', '_')}.txt").write_text("ok\n")
            if st.title == "Python 3.11":
                await side_chat_say(bot_id, st.chat_id, "12 passed on Python 3.11.")
            if st.title == "Python 3.12":
                await gate.wait()

        service.svc._execute_turn = turn
        group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[
                {"title": "Python 3.11", "prompt": "Test on 3.11"},
                {"title": "Python 3.12", "prompt": "Test on 3.12"},
            ],
            group_title="Test on Python 3.11–3.13",
            source_message_id=source.id,
        )

        async def reply_done_is_one() -> bool:
            replies = await parent_replies(bot_id, parent.id)
            return len(replies) == 1 and replies[0].metadata.get("done") == 1

        await wait_for(reply_done_is_one)

        replies = await parent_replies(bot_id, parent.id)
        reply = replies[0]
        reply_id = reply.id
        assert reply.metadata["kind"] == "side_task_group_reply"
        assert reply.metadata["groupId"] == group_id
        assert reply.reply_to_id == source.id
        assert reply.metadata["total"] == 2
        assert reply.metadata["done"] == 1
        assert reply.metadata["running"] == 1
        assert {i["title"] for i in reply.metadata["items"]} == {"Python 3.11", "Python 3.12"}
        assert all(i["chatId"] for i in reply.metadata["items"])

        # Second helper settles: same message, counts refresh
        gate.set()
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "settled"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].id == reply_id
        assert replies[0].metadata["status"] == "settled"
        assert replies[0].metadata["done"] == 2
        assert "all 2 done" in replies[0].content

        # Every helper record points at the one group reply
        for h in helpers:
            latest = await SideTaskRepository().get(h.id)
            assert latest.reply_message_id == reply_id

    async def test_group_reply_counts_failed_and_waiting(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.error = RuntimeError("nope")

        _group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[
                {"title": "One", "prompt": "First"},
                {"title": "Two", "prompt": "Second"},
                {"title": "Three", "prompt": "Third"},
                {"title": "Four", "prompt": "Fourth"},
                {"title": "Five", "prompt": "Fifth"},
            ],
            group_title="Matrix",
        )
        # 4 run, 1 waits for a slot; every runner fails and the waiter is
        # promoted and fails too — the group reply must settle as failed 5/5.
        for h in helpers:
            await wait_for(lambda h=h: status_is(h.id, SideTaskStatus.FAILED))

        async def reply_failed_is_five() -> bool:
            replies = await parent_replies(bot_id, parent.id)
            return len(replies) == 1 and replies[0].metadata.get("failed") == 5

        await wait_for(reply_failed_is_five)

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].metadata["status"] == "failed"


# ---------------------------------------------------------------------------
# Scoped message_update broadcast
# ---------------------------------------------------------------------------


class StubManager:
    """Records scoped broadcasts (same shape as ConnectionManager)."""

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

    owner, _ = await create_test_user(auth_service, email="ro@test.com", username="ro")
    viewer, _ = await create_test_user(auth_service, email="rv@test.com", username="rv")
    stranger, _ = await create_test_user(auth_service, email="rs@test.com", username="rs")
    admin, _ = await create_test_user(
        auth_service, email="ra@test.com", username="ra", role=UserRole.ADMIN
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


class TestMessageUpdateScoping:
    async def test_reply_create_and_update_broadcast_scoped(self, service, monkeypatch):
        """Both the create and the in-place update go through the scoped
        bot broadcast (same access rule as side_task_update)."""
        stub = StubManager()
        monkeypatch.setattr("cachibot.api.websocket.manager", stub)

        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(parent_chat_id=parent.id, bot_id=bot_id, prompt="Scoped task")
        await wait_for(lambda: status_is(st.id, SideTaskStatus.DONE))

        pairs = [(m, b) for m, b in stub.scoped if m.type.value == "message_update"]
        assert len(pairs) == 1
        message, bid = pairs[0]
        assert bid == bot_id
        assert message.payload["chatId"] == parent.id
        assert message.payload["message"]["metadata"]["kind"] == "side_task_reply"
        assert message.payload["message"]["id"]

        # An in-place update broadcasts again with the same message id
        latest = await SideTaskRepository().get(st.id)
        await service.svc._sync_single_reply(latest)
        pairs = [(m, b) for m, b in stub.scoped if m.type.value == "message_update"]
        assert len(pairs) == 2
        assert all(b == bot_id for _, b in pairs)
        assert pairs[-1][0].payload["message"]["id"] == pairs[0][0].payload["message"]["id"]

    async def test_message_update_only_reaches_users_with_bot_access(
        self, scoped_actors, monkeypatch
    ):
        from cachibot.api.websocket import ConnectionManager

        class FakeWebSocket:
            def __init__(self) -> None:
                self.sent: list[dict] = []

            async def accept(self) -> None:
                pass

            async def send_json(self, data: dict) -> None:
                self.sent.append(data)

        manager = ConnectionManager()
        sockets: dict[str, FakeWebSocket] = {}
        for name, user in scoped_actors.users.items():
            ws = FakeWebSocket()
            await manager.connect(ws, name, user=user)
            sockets[name] = ws

        from cachibot.models.websocket import WSMessage

        msg = WSMessage.message_update(
            "chat-1",
            {
                "id": "m-1",
                "chatId": "chat-1",
                "role": "assistant",
                "content": "Side task done",
                "timestamp": "2026-11-22T00:00:00+00:00",
                "metadata": {"kind": "side_task_reply"},
                "replyToId": None,
            },
        )
        await manager.broadcast_to_bot(msg, scoped_actors.bot_id)

        assert len(sockets["owner"].sent) == 1
        assert len(sockets["viewer"].sent) == 1
        assert len(sockets["admin"].sent) == 1
        assert sockets["stranger"].sent == []


# ---------------------------------------------------------------------------
# Migration 015 up/down on SQLite through real alembic
# ---------------------------------------------------------------------------


class TestMigration015:
    def test_upgrade_adds_and_downgrade_drops_columns(self, tmp_path, monkeypatch):
        """015 adds source_message_id/reply_message_id; down removes them.

        Runs 015 alone through real alembic on SQLite: the DB is stamped at
        014 with a minimal side_tasks table (the earlier chain is
        Postgres-only — 001 creates the vector extension — so it is not
        SQLite-runnable from scratch). Sync test: alembic drives its own
        event loop."""
        from alembic import command
        from alembic.config import Config as AlembicConfig
        from sqlalchemy import create_engine, inspect, text

        db_path = tmp_path / "alembic.db"
        sync_url = f"sqlite:///{db_path}"
        engine = create_engine(sync_url)
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE side_tasks (id VARCHAR PRIMARY KEY)"))
        engine.dispose()

        # Hermetic: alembic's env resolves the URL from this env var first
        # (otherwise it falls back to the developer's real config), so point
        # it at the tmp DB and make sure nothing ambient leaks in.
        monkeypatch.setenv("CACHIBOT_DATABASE_URL", f"sqlite+aiosqlite:///{db_path}")
        monkeypatch.delenv("DATABASE_URL", raising=False)

        cfg = AlembicConfig(str(Path(__file__).resolve().parent.parent / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", f"sqlite+aiosqlite:///{db_path}")

        command.stamp(cfg, "014")
        command.upgrade(cfg, "015")

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            columns = {c["name"] for c in inspect(conn).get_columns("side_tasks")}
        engine.dispose()
        assert "source_message_id" in columns
        assert "reply_message_id" in columns

        command.downgrade(cfg, "014")

        engine = create_engine(sync_url)
        with engine.connect() as conn:
            columns = {c["name"] for c in inspect(conn).get_columns("side_tasks")}
        engine.dispose()
        assert "source_message_id" not in columns
        assert "reply_message_id" not in columns


# ---------------------------------------------------------------------------
# API: sourceMessageId accepted, validated, returned
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


class TestSourceMessageApi:
    async def test_start_returns_source_message_id(self, st_client, auth_service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="s1@test.com", username="s1")
        token = auth_service.create_access_token(user.id, user.role.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        source = await save_user_message(bot_id, parent.id, "On the side, please")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Do it", "sourceMessageId": source.id},
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["sourceMessageId"] == source.id
        assert data["replyMessageId"] is None

        await wait_for(lambda: status_is(data["id"], SideTaskStatus.DONE))

        # The reply exists and is exposed on the record
        resp = await st_client.get(f"/api/bots/{bot_id}/side-tasks/{data['id']}", headers=headers)
        assert resp.status_code == 200
        assert resp.json()["replyMessageId"]

    async def test_start_with_foreign_source_message_rejected(self, st_client, auth_service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="s2@test.com", username="s2")
        token = auth_service.create_access_token(user.id, user.role.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        other = await make_chat(bot_id)
        foreign = await save_user_message(bot_id, other.id, "elsewhere")
        headers = {"Authorization": f"Bearer {token}"}

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={"prompt": "Do it", "sourceMessageId": foreign.id},
            headers=headers,
        )
        assert resp.status_code == 400

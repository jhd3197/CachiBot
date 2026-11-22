"""E3 tests: bot-started side tasks and helpers.

Covers the side_task_start / start_helpers tools, helper groups (summary
endpoint + counts), the one-level rule (tools hidden in side chats and
rejected by the service) and the parent-chat thread replies on finish.

Runs entirely on SQLite in a tmp dir — no PostgreSQL needed. The agent run
is mocked; the workspace is a real git repo in a tmp dir.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukuy import PythonSandbox

import cachibot.storage.db as db_mod
from cachibot.config import Config
from cachibot.models.knowledge import BotMessage
from cachibot.models.side_task import (
    SideTask,
    SideTaskKind,
    SideTaskStartedBy,
    SideTaskStatus,
)
from cachibot.plugins.base import PluginContext
from cachibot.plugins.side_tasks import SIDE_TASK_TOOL_NAMES, SideTaskToolsPlugin
from cachibot.services.side_task_service import (
    MAX_RUNNING_PER_PARENT,
    SideTaskService,
    SideTaskStartError,
)
from cachibot.storage.db import Base
from cachibot.storage.repository import ChatRepository, KnowledgeRepository
from cachibot.storage.side_task_repository import SideTaskRepository
from tests.test_side_tasks import (  # noqa: F401  (re-exported helpers)
    FakeTurn,
    commit_file,
    git,
    git_init,
    make_bot,
    make_chat,
    status_is,
    wait_for,
)

# ---------------------------------------------------------------------------
# Fixtures (same shape as tests/test_side_tasks.py)
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


@pytest.fixture
async def service(sqlite_db, monkeypatch, tmp_path):
    """Fresh SideTaskService with a mocked agent turn and broadcast.

    The workspace is a real git repo in a tmp dir and worktrees live under
    tmp_path too, so E2's worktree creation and automatic merge back run
    for real without touching the developer's repository. Teardown cancels
    and awaits in-flight turns (none may outlive the test's database/loop).
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
async def st_client(sqlite_db, auth_service, service):
    """HTTP client wired to an app with only the side task routes."""
    from fastapi import FastAPI

    from cachibot.api.routes import side_tasks

    app = FastAPI()
    app.include_router(side_tasks.router, tags=["side-tasks"])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def make_plugin(bot_id: str, chat_id: str | None) -> SideTaskToolsPlugin:
    """A SideTaskToolsPlugin bound to a bot/chat, like the agent registry does."""
    return SideTaskToolsPlugin(
        PluginContext(config=Config(), sandbox=PythonSandbox(), bot_id=bot_id, chat_id=chat_id)
    )


# ---------------------------------------------------------------------------
# Tool registration: only offered in a main chat
# ---------------------------------------------------------------------------


class TestToolRegistration:
    def test_registry_includes_tools_when_work_management_enabled(self):
        from cachibot.services.plugin_manager import build_registry

        registry = build_registry(
            PluginContext(config=Config(), sandbox=PythonSandbox()),
            capabilities={"workManagement": True},
        )
        assert "side_task_start" in registry.names
        assert "start_helpers" in registry.names

    def test_registry_excludes_tools_without_work_management(self):
        from cachibot.services.plugin_manager import build_registry

        registry = build_registry(
            PluginContext(config=Config(), sandbox=PythonSandbox()),
            capabilities={"fileOperations": True},
        )
        assert "side_task_start" not in registry.names
        assert "start_helpers" not in registry.names

    def test_agent_in_main_chat_keeps_tools(self):
        from cachibot.agent import CachibotAgent

        config = Config()
        config.agent.model = "openai/gpt-4o-mini"
        agent = CachibotAgent(
            config=config,
            capabilities={"workManagement": True},
            bot_id="b1",
            chat_id="c1",
        )
        assert "side_task_start" in agent.registry.names
        assert "start_helpers" in agent.registry.names
        assert "work_create" in agent.registry.names

    def test_agent_with_exclusions_hides_only_side_task_tools(self):
        from cachibot.agent import CachibotAgent

        config = Config()
        config.agent.model = "openai/gpt-4o-mini"
        agent = CachibotAgent(
            config=config,
            capabilities={"workManagement": True},
            bot_id="b1",
            chat_id="c1",
            excluded_tools=set(SIDE_TASK_TOOL_NAMES),
        )
        assert "side_task_start" not in agent.registry.names
        assert "start_helpers" not in agent.registry.names
        # Other tools from the same capability are untouched
        assert "work_create" in agent.registry.names
        assert "todo_create" in agent.registry.names

    async def test_exclusions_resolved_per_chat(self, sqlite_db):
        from cachibot.services.agent_factory import side_task_tool_exclusions

        bot_id = await make_bot()
        main = await make_chat(bot_id)
        side = await make_chat(bot_id, parent_chat_id=main.id)

        assert await side_task_tool_exclusions(main.id) == set()
        assert await side_task_tool_exclusions(side.id) == set(SIDE_TASK_TOOL_NAMES)
        assert await side_task_tool_exclusions(str(uuid.uuid4())) == set()
        assert await side_task_tool_exclusions(None) == set()

    async def test_build_bot_agent_hides_tools_in_side_chat(self, sqlite_db):
        """End to end: the agent built for a side chat has no side task tools."""
        from cachibot.services.agent_factory import build_bot_agent

        bot_id = await make_bot()
        main = await make_chat(bot_id)
        side = await make_chat(bot_id, parent_chat_id=main.id)

        config = Config()
        config.agent.model = "openai/gpt-4o-mini"

        main_agent = await build_bot_agent(
            config, bot_id=bot_id, chat_id=main.id, capabilities={"workManagement": True}
        )
        assert "side_task_start" in main_agent.registry.names
        assert "start_helpers" in main_agent.registry.names

        side_agent = await build_bot_agent(
            config, bot_id=bot_id, chat_id=side.id, capabilities={"workManagement": True}
        )
        assert "side_task_start" not in side_agent.registry.names
        assert "start_helpers" not in side_agent.registry.names


# ---------------------------------------------------------------------------
# side_task_start tool
# ---------------------------------------------------------------------------


class TestSideTaskStartTool:
    async def test_creates_bot_started_side_task(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)

        result = await plugin._skills_map["side_task_start"].fn(
            prompt="Update the changelog", title="Changelog"
        )
        data = json.loads(result)

        assert data["status"] == "running"
        assert data["title"] == "Changelog"

        record = await SideTaskRepository().get(data["id"])
        assert record is not None
        assert record.started_by == SideTaskStartedBy.BOT
        assert record.kind == SideTaskKind.SIDE
        assert record.parent_chat_id == parent.id
        assert record.group_id is None

        await wait_for(lambda: status_is(record.id, SideTaskStatus.DONE))

    async def test_title_derived_when_omitted(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)

        result = await plugin._skills_map["side_task_start"].fn(prompt="Fix the flaky test")
        data = json.loads(result)
        assert data["title"] == "Fix the flaky test"

        latest = await SideTaskRepository().get(data["id"])
        await wait_for(lambda: status_is(latest.id, SideTaskStatus.DONE))

    async def test_start_from_side_chat_returns_error(self, service):
        """The service enforces one level even if a tool call gets through."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        first = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="First", title="First"
        )
        await wait_for(lambda: status_is(first.id, SideTaskStatus.DONE))

        side_chat = await ChatRepository().get_chat(first.chat_id)
        plugin = make_plugin(bot_id, side_chat.id)
        result = await plugin._skills_map["side_task_start"].fn(prompt="Nested")
        assert result.startswith("Error:")
        assert "one level deep" in result

    async def test_requires_chat_context(self, service):
        plugin = make_plugin(None, None)
        result = await plugin._skills_map["side_task_start"].fn(prompt="Do it")
        assert result.startswith("Error:")


# ---------------------------------------------------------------------------
# start_helpers tool + group summary
# ---------------------------------------------------------------------------


class TestStartHelpersTool:
    async def test_creates_one_helper_per_item_in_one_group(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)

        result = await plugin._skills_map["start_helpers"].fn(
            items=[
                {"title": "Python 3.11", "prompt": "Run the tests on Python 3.11"},
                {"title": "Python 3.12", "prompt": "Run the tests on Python 3.12"},
                {"prompt": "Run the tests on Python 3.13"},
            ],
            group_title="Test on 3.11-3.13",
        )
        data = json.loads(result)

        assert data["group_title"] == "Test on 3.11-3.13"
        assert len(data["helpers"]) == 3
        group_id = data["group_id"]

        records = await SideTaskRepository().get_by_group(group_id)
        assert len(records) == 3
        for record, helper in zip(records, data["helpers"], strict=True):
            assert record.id == helper["id"]
            assert record.kind == SideTaskKind.HELPER
            assert record.started_by == SideTaskStartedBy.BOT
            assert record.group_id == group_id
            assert record.group_title == "Test on 3.11-3.13"
            assert record.parent_chat_id == parent.id
        # The item without a title got one derived from its prompt
        assert records[2].title == "Run the tests on Python 3.13"

        for record in records:
            await wait_for(lambda sid=record.id: status_is(sid, SideTaskStatus.DONE))

    async def test_limit_four_applies_to_helpers(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)
        service.fake.gate = asyncio.Event()  # keep the turns blocked

        items = [{"title": f"H{i}", "prompt": f"Helper {i}"} for i in range(6)]
        result = await plugin._skills_map["start_helpers"].fn(items=items, group_title="Six")
        data = json.loads(result)

        statuses = [h["status"] for h in data["helpers"]]
        assert statuses.count("running") == MAX_RUNNING_PER_PARENT
        assert statuses.count("waiting_for_slot") == 2

        # Group summary reflects the queue in real time
        summary = await service.svc.group_summary(data["group_id"])
        assert summary.total == 6
        assert summary.running == MAX_RUNNING_PER_PARENT
        assert summary.waiting == 2
        assert summary.done == 0

        service.fake.gate.set()
        for helper in data["helpers"]:
            await wait_for(lambda sid=helper["id"]: status_is(sid, SideTaskStatus.DONE))

    async def test_validates_items(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)

        result = await plugin._skills_map["start_helpers"].fn(items=[])
        assert "At least one helper" in result

        result = await plugin._skills_map["start_helpers"].fn(items=[{"title": "No prompt"}])
        assert "needs a prompt" in result

    async def test_start_helpers_from_side_chat_returns_error(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        first = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="First", title="First"
        )
        await wait_for(lambda: status_is(first.id, SideTaskStatus.DONE))

        side_chat = await ChatRepository().get_chat(first.chat_id)
        plugin = make_plugin(bot_id, side_chat.id)
        result = await plugin._skills_map["start_helpers"].fn(items=[{"prompt": "Nested"}])
        assert result.startswith("Error:")
        assert "one level deep" in result

    async def test_service_rejects_helpers_from_side_chat(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        first = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="First", title="First"
        )
        await wait_for(lambda: status_is(first.id, SideTaskStatus.DONE))

        with pytest.raises(SideTaskStartError, match="one level deep"):
            await service.svc.start_helpers(
                parent_chat_id=first.chat_id,
                bot_id=bot_id,
                items=[{"prompt": "Nested"}],
            )


# ---------------------------------------------------------------------------
# Group summary counts (service)
# ---------------------------------------------------------------------------


class TestGroupSummary:
    async def test_counts_all_buckets(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        group_id = str(uuid.uuid4())

        async def seed(status: SideTaskStatus, title: str, **kwargs) -> SideTask:
            chat = await make_chat(bot_id, parent_chat_id=parent.id, title=title)
            record = SideTask(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                parent_chat_id=parent.id,
                chat_id=chat.id,
                title=title,
                prompt=f"Do {title}",
                kind=SideTaskKind.HELPER,
                started_by=SideTaskStartedBy.BOT,
                group_id=group_id,
                group_title="Test matrix",
                status=status,
                **kwargs,
            )
            await SideTaskRepository().save(record)
            return record

        await seed(SideTaskStatus.WAITING_FOR_SLOT, "waiting")
        await seed(SideTaskStatus.RUNNING, "running", started_at=datetime.now(timezone.utc))
        await seed(SideTaskStatus.NEEDS_YOU, "needs-you")
        await seed(SideTaskStatus.DONE, "done")
        await seed(SideTaskStatus.MERGED, "merged")
        await seed(SideTaskStatus.FAILED, "failed")
        stopped = await seed(SideTaskStatus.STOPPED, "stopped")

        summary = await service.svc.group_summary(group_id)
        assert summary is not None
        assert summary.group_id == group_id
        assert summary.title == "Test matrix"
        assert summary.total == 7
        assert summary.waiting == 1
        assert summary.running == 1
        assert summary.needs_you == 1
        assert summary.done == 2  # done + merged both count as done
        assert summary.failed == 1
        # Stopped helpers stay out of the buckets but remain visible
        assert stopped.id in {st.id for st in summary.items}
        assert len(summary.items) == 7

    async def test_unknown_group_returns_none(self, service):
        assert await service.svc.group_summary(str(uuid.uuid4())) is None

    async def test_group_is_scoped_to_its_own_records(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        plugin = make_plugin(bot_id, parent.id)

        result = await plugin._skills_map["start_helpers"].fn(
            items=[{"title": "Only", "prompt": "Solo helper"}], group_title="Solo"
        )
        group_id = json.loads(result)["group_id"]

        summary = await service.svc.group_summary(group_id)
        assert summary.total == 1
        assert summary.title == "Solo"
        await wait_for(lambda: status_is(summary.items[0].id, SideTaskStatus.DONE))


# ---------------------------------------------------------------------------
# Group summary API
# ---------------------------------------------------------------------------


class TestGroupSummaryApi:
    async def _auth_client(self, st_client, auth_service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="op@test.com", username="op")
        token = auth_service.create_access_token(user.id, user.role.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        headers = {"Authorization": f"Bearer {token}"}
        return headers, bot_id, parent

    async def test_group_endpoint_returns_counts(self, st_client, auth_service, service):
        headers, bot_id, parent = await self._auth_client(st_client, auth_service)
        plugin = make_plugin(bot_id, parent.id)
        service.fake.gate = asyncio.Event()

        result = await plugin._skills_map["start_helpers"].fn(
            items=[{"title": f"H{i}", "prompt": f"Helper {i}"} for i in range(5)],
            group_title="Five helpers",
        )
        data = json.loads(result)

        resp = await st_client.get(
            f"/api/bots/{bot_id}/side-task-groups/{data['group_id']}", headers=headers
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["groupId"] == data["group_id"]
        assert body["title"] == "Five helpers"
        assert body["total"] == 5
        assert body["running"] == MAX_RUNNING_PER_PARENT
        assert body["waiting"] == 1
        assert body["done"] == 0
        assert body["needsYou"] == 0
        assert body["failed"] == 0
        assert len(body["items"]) == 5
        # Items carry the full record (camelCase) for the group card
        assert body["items"][0]["kind"] == "helper"
        assert body["items"][0]["startedBy"] == "bot"
        assert body["items"][0]["groupId"] == data["group_id"]
        assert body["items"][0]["groupTitle"] == "Five helpers"

        # Let everything settle so nothing outlives the test
        service.fake.gate.set()
        for helper in data["helpers"]:
            await wait_for(lambda sid=helper["id"]: status_is(sid, SideTaskStatus.DONE))

    async def test_group_endpoint_404_for_unknown_group(self, st_client, auth_service, service):
        headers, bot_id, _parent = await self._auth_client(st_client, auth_service)
        resp = await st_client.get(
            f"/api/bots/{bot_id}/side-task-groups/{uuid.uuid4()}", headers=headers
        )
        assert resp.status_code == 404

    async def test_group_endpoint_requires_access(self, st_client, auth_service, service):
        bot_id = await make_bot()
        resp = await st_client.get(f"/api/bots/{bot_id}/side-task-groups/{uuid.uuid4()}")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Parent chat thread replies when a bot-started helper settles
# ---------------------------------------------------------------------------


async def parent_replies(bot_id: str, parent_chat_id: str) -> list:
    """Side-task reply messages persisted in the parent chat (E5)."""
    messages = await KnowledgeRepository().get_bot_messages(bot_id, parent_chat_id, limit=100)
    return [
        m
        for m in messages
        if m.metadata.get("kind") in ("side_task_reply", "side_task_group_reply")
    ]


async def reply_has_status(bot_id: str, parent_chat_id: str, status: str) -> bool:
    """The one reply exists and reflects `status` (it is synced right after
    the record update in the same transition — poll the reply itself)."""
    replies = await parent_replies(bot_id, parent_chat_id)
    return len(replies) == 1 and replies[0].metadata.get("status") == status


class TestParentChatNote:
    async def test_merged_helper_writes_group_reply_in_parent_chat(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "result.txt").write_text("ok\n")

        service.svc._execute_turn = turn
        group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[{"title": "Python 3.11", "prompt": "Test on 3.11"}],
            group_title="Test matrix",
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "settled"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        reply = replies[0]
        assert reply.role == "assistant"
        assert reply.metadata["kind"] == "side_task_group_reply"
        assert reply.metadata["groupId"] == group_id
        assert reply.metadata["status"] == "settled"
        assert reply.metadata["total"] == 1
        assert reply.metadata["done"] == 1
        assert "all 1 done" in reply.content
        # The merge details stay on the record (the card/chat), not in the reply
        latest = await SideTaskRepository().get(helpers[0].id)
        assert {f["path"] for f in latest.merged_files} == {"result.txt"}
        assert group_id == latest.group_id
        assert latest.reply_message_id == reply.id

    async def test_done_helper_updates_group_reply_in_place(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        _group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[{"title": "No changes", "prompt": "Nothing to do"}],
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "settled"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1  # created at start, updated in place — never two
        assert "No changes" in replies[0].content or "all 1 done" in replies[0].content
        assert replies[0].metadata["status"] == "settled"

    async def test_failed_helper_marks_group_reply(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        service.fake.error = RuntimeError("boom")

        _group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[{"title": "Broken", "prompt": "Will fail"}],
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "failed"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].metadata["status"] == "failed"
        assert replies[0].metadata["failed"] == 1

    async def test_needs_you_helper_marks_group_reply(self, service):
        """A bot-started helper that hits a merge conflict tells its parent."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        commit_file(service.workspace, "file.txt", "base\n", "add file")

        gate = asyncio.Event()

        async def turn(st: SideTask) -> None:
            Path(st.worktree_path, "file.txt").write_text("side version\n")
            await gate.wait()

        service.svc._execute_turn = turn
        group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[{"title": "Docs update", "prompt": "Update the docs"}],
            group_title="Docs",
        )
        st = helpers[0]

        async def side_file_written() -> bool:
            latest = await SideTaskRepository().get(st.id)
            wt = Path(latest.worktree_path) if latest.worktree_path else None
            return wt is not None and (wt / "file.txt").exists()

        await wait_for(side_file_written)
        commit_file(service.workspace, "file.txt", "parent version\n", "parent change")
        gate.set()
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "needs_you"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].metadata["status"] == "needs_you"
        assert replies[0].metadata["needsYou"] == 1

        # Resolve in the worktree and retry: same message updated, still one
        latest = await SideTaskRepository().get(st.id)
        Path(latest.worktree_path, "file.txt").write_text("parent version\n")
        merged = await service.svc.retry_merge(st.id)
        assert merged.status == SideTaskStatus.MERGED

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].id == latest.reply_message_id
        assert replies[0].metadata["status"] == "settled"
        assert replies[0].metadata["done"] == 1

    async def test_user_started_side_task_writes_single_reply(self, service):
        """User-started side tasks reply too — parity with bot-started ones."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        st = await service.svc.start(
            parent_chat_id=parent.id, bot_id=bot_id, prompt="User task", title="User task"
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "done"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].metadata["kind"] == "side_task_reply"
        assert replies[0].metadata["sideTaskId"] == st.id
        assert replies[0].metadata["status"] == "done"

    async def test_reply_goes_to_parent_not_side_chat(self, service):
        bot_id = await make_bot()
        parent = await make_chat(bot_id)

        _group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[{"title": "Solo", "prompt": "Work"}],
        )
        await wait_for(lambda: reply_has_status(bot_id, parent.id, "settled"))

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        side_messages = await KnowledgeRepository().get_bot_messages(
            bot_id, helpers[0].chat_id, limit=100
        )
        assert all(
            m.metadata.get("kind") not in ("side_task_reply", "side_task_group_reply")
            for m in side_messages
        )

    async def test_helpers_group_shares_one_source_message(self, service):
        """Every helper of a group answers the same parent-chat message."""
        bot_id = await make_bot()
        parent = await make_chat(bot_id)
        repo = KnowledgeRepository()
        await repo.save_bot_message(
            BotMessage(
                id=str(uuid.uuid4()),
                bot_id=bot_id,
                chat_id=parent.id,
                role="user",
                content="Check every Python version",
                timestamp=datetime.now(timezone.utc),
            )
        )

        _group_id, helpers = await service.svc.start_helpers(
            parent_chat_id=parent.id,
            bot_id=bot_id,
            items=[
                {"title": "Py 3.11", "prompt": "Test 3.11"},
                {"title": "Py 3.12", "prompt": "Test 3.12"},
            ],
        )
        assert helpers[0].source_message_id is not None
        assert all(h.source_message_id == helpers[0].source_message_id for h in helpers)

        replies = await parent_replies(bot_id, parent.id)
        assert len(replies) == 1
        assert replies[0].reply_to_id == helpers[0].source_message_id


# ---------------------------------------------------------------------------
# Full flow through the HTTP API (bot-started)
# ---------------------------------------------------------------------------


class TestBotStartedViaApi:
    async def test_api_start_with_kind_helper_and_group_title(self, st_client, auth_service):
        from tests.conftest import create_test_user

        user, _ = await create_test_user(auth_service, email="h@test.com", username="h")
        token = auth_service.create_access_token(user.id, user.role.value)
        bot_id = await make_bot(user.id)
        parent = await make_chat(bot_id)
        headers = {"Authorization": f"Bearer {token}"}
        group_id = str(uuid.uuid4())

        resp = await st_client.post(
            f"/api/bots/{bot_id}/chats/{parent.id}/side-tasks",
            json={
                "prompt": "Run the tests",
                "title": "Python 3.11",
                "kind": "helper",
                "startedBy": "bot",
                "groupId": group_id,
                "groupTitle": "Test matrix",
            },
            headers=headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["kind"] == "helper"
        assert data["startedBy"] == "bot"
        assert data["groupId"] == group_id
        assert data["groupTitle"] == "Test matrix"

        await wait_for(lambda: status_is(data["id"], SideTaskStatus.DONE))

        # The group endpoint sees it
        resp = await st_client.get(
            f"/api/bots/{bot_id}/side-task-groups/{group_id}", headers=headers
        )
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test matrix"
        assert resp.json()["total"] == 1
        assert resp.json()["done"] == 1

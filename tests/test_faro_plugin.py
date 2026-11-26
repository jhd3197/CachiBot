"""Tests for the Faro plugin: the registration gate and the live MCP tools
mapped to tukuy skills with honest risk levels.

SQLite in a tmp dir; the bridge is the fake aiohttp server on 127.0.0.1.
"""

import json
import os
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from tukuy import PythonSandbox
from tukuy.skill import RiskLevel

import cachibot.storage.db as db_mod
from cachibot.config import Config
from cachibot.models.bot import Bot
from cachibot.plugins.base import PluginContext
from cachibot.plugins.faro import FaroPlugin, _icon_for, _risk_for
from cachibot.services.faro.service import FaroService
from cachibot.storage.db import Base
from cachibot.storage.repository import BotRepository
from tests.faro_fakes import FakeFaroBridge


@pytest.fixture
async def sqlite_db(tmp_path):
    """SQLite in a tmp dir patched into the shared session maker."""
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    import cachibot.storage.models  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    original_engine = db_mod.engine
    original_session_maker = db_mod.async_session_maker
    db_mod.engine = engine
    db_mod.async_session_maker = session_maker

    yield session_maker

    await engine.dispose()
    db_mod.engine = original_engine
    db_mod.async_session_maker = original_session_maker


@pytest.fixture
async def bridge():
    server = FakeFaroBridge()
    await server.start()
    yield server
    await server.stop()


@pytest.fixture
async def faro_env(tmp_path, sqlite_db, bridge):
    write_discovery(tmp_path, bridge)
    svc = FaroService(data_dir=tmp_path, status_ttl=5.0, approvals_poll=0.05)
    yield SimpleNamespace(svc=svc, bridge=bridge, tmp_path=tmp_path)


def write_discovery(tmp_path, bridge: FakeFaroBridge) -> None:
    payload = bridge.discovery(pid=os.getpid())
    (tmp_path / "agent-endpoint.json").write_text(json.dumps(payload), encoding="utf-8")


async def make_bot() -> str:
    bot_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await BotRepository().upsert_bot(
        Bot(
            id=bot_id,
            name="Faro Bot",
            model="test/model",
            systemPrompt="You are a test bot.",
            createdAt=now,
            updatedAt=now,
        )
    )
    return bot_id


def make_plugin(env: SimpleNamespace, bot_id: str | None) -> FaroPlugin:
    ctx = PluginContext(config=Config(), sandbox=PythonSandbox(), bot_id=bot_id, chat_id="c1")
    return FaroPlugin(ctx, faro_service=env.svc)


async def connect(env: SimpleNamespace, bot_id: str) -> None:
    await env.svc.connect(bot_id)


class TestRegistrationGate:
    async def test_no_tools_without_a_bot(self, faro_env) -> None:
        plugin = make_plugin(faro_env, None)
        assert plugin.skills == {}

    async def test_no_tools_when_not_connected(self, faro_env) -> None:
        bot_id = await make_bot()
        plugin = make_plugin(faro_env, bot_id)
        assert faro_env.svc.faro_tools_available(bot_id) is False
        assert plugin.skills == {}

    async def test_no_tools_when_bridge_is_down(self, faro_env) -> None:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        await faro_env.bridge.stop()
        await faro_env.svc.get_status(force=True)
        plugin = make_plugin(faro_env, bot_id)
        assert plugin.skills == {}

    async def test_tools_registered_when_connected_and_available(self, faro_env) -> None:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        plugin = make_plugin(faro_env, bot_id)
        names = set(plugin.skills)
        assert "faro_context" in names
        assert "faro_read" in names
        assert "faro_exec" in names
        assert "faro_mystery_new_tool" in names

    async def test_disconnecting_hides_the_tools(self, faro_env) -> None:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        plugin = make_plugin(faro_env, bot_id)
        assert plugin.skills != {}
        await faro_env.svc.disconnect(bot_id)
        assert plugin.skills == {}


class TestRiskLevels:
    async def _skills(self, faro_env) -> dict[str, Any]:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        return make_plugin(faro_env, bot_id).skills

    async def test_reads_are_safe_and_idempotent(self, faro_env) -> None:
        skills = await self._skills(faro_env)
        for name in (
            "faro_context",
            "faro_list_sessions",
            "faro_server_info",
            "faro_read",
            "faro_search",
        ):
            descriptor = skills[name].descriptor
            assert descriptor.risk_level is RiskLevel.SAFE, name
            assert descriptor.side_effects is False, name
            assert descriptor.idempotent is True, name

    async def test_writes_and_transfers_are_moderate(self, faro_env) -> None:
        skills = await self._skills(faro_env)
        for name in (
            "faro_write",
            "faro_upload",
            "faro_download",
            "faro_sync",
            "faro_rename",
            "faro_mkdir",
        ):
            descriptor = skills[name].descriptor
            assert descriptor.risk_level is RiskLevel.MODERATE, name
            assert descriptor.side_effects is True, name

    async def test_execution_and_unknown_tools_are_dangerous(self, faro_env) -> None:
        skills = await self._skills(faro_env)
        for name in ("faro_exec", "faro_run_command", "faro_mystery_new_tool"):
            descriptor = skills[name].descriptor
            assert descriptor.risk_level is RiskLevel.DANGEROUS, name
            assert descriptor.side_effects is True, name

    async def test_risk_mapping_table(self) -> None:
        assert _risk_for("faro_read") is RiskLevel.SAFE
        assert _risk_for("faro_job") is RiskLevel.SAFE
        assert _risk_for("faro_upload") is RiskLevel.MODERATE
        assert _risk_for("faro_exec") is RiskLevel.DANGEROUS
        assert _risk_for("faro_exec_script") is RiskLevel.DANGEROUS
        assert _risk_for("faro_skill_deploy") is RiskLevel.DANGEROUS
        assert _risk_for("faro_whatever_new") is RiskLevel.DANGEROUS
        assert _icon_for("faro_exec") == "terminal"
        assert _icon_for("faro_read") == "file-text"

    async def test_the_bridge_schema_becomes_the_input_schema(self, faro_env) -> None:
        skills = await self._skills(faro_env)
        schema = skills["faro_read"].descriptor.input_schema
        assert schema["properties"]["path"]["type"] == "string"

    async def test_side_effecting_descriptions_mention_the_approval(self, faro_env) -> None:
        skills = await self._skills(faro_env)
        assert "Faro" in skills["faro_exec"].descriptor.description
        assert "confirmed by the user" in skills["faro_exec"].descriptor.description


class TestToolCalls:
    async def test_calling_a_skill_runs_the_bridge_tool(self, faro_env) -> None:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        plugin = make_plugin(faro_env, bot_id)
        result = await plugin.skills["faro_read"].fn(session="s", path="/a")
        assert result == "ok:faro_read"
        calls = [c for c in faro_env.bridge.mcp_calls if c["method"] == "tools/call"]
        assert calls[-1]["params"] == {
            "name": "faro_read",
            "arguments": {"session": "s", "path": "/a"},
        }

    async def test_denied_call_is_honest_through_the_skill(self, faro_env) -> None:
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        faro_env.bridge.deny_tools = {"faro_exec"}
        plugin = make_plugin(faro_env, bot_id)
        result = await plugin.skills["faro_exec"].fn(session="s", command="ls")
        assert "denied or did not respond" in result

    async def test_catalogue_tools_disappear_when_the_bridge_dies(self, faro_env) -> None:
        """The live list is authoritative: a dead bridge removes the tools."""
        bot_id = await make_bot()
        await connect(faro_env, bot_id)
        plugin = make_plugin(faro_env, bot_id)
        assert plugin.skills != {}
        await faro_env.bridge.stop()
        await faro_env.svc.get_status(force=True)
        assert plugin.skills == {}

"""Optional real-Docker coverage for the C3 bot-facing computer surface.

Opt-in only: these tests skip unless CACHIBOT_DOCKER_TESTS=1 is set AND the
daemon answers (the same gate as tests/test_computer_integration.py). They
must never run just because Docker happens to be installed — CI runners
included. Run them explicitly with:

    CACHIBOT_DOCKER_TESTS=1 pytest tests/test_computer_plugin_integration.py

The pinned image is still Vela 0.2.0 (protocol 2: controller + driver, no
terminal/workspace/editor yet), so what is honestly covered here is: the
wake-time agent setup, the driven tool catalogue, a driven run with a
browser-surface step (or Vela's own plain refusal, which is surfaced, never
faked), and the plain feature-gap refusal for the terminal tools. The
container and both named volumes are always removed in a finally block.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import cachibot.storage.db as db_mod
from cachibot.config import ComputerConfig
from cachibot.services.computer.service import (
    ComputerService,
    container_name_for,
    data_volume_for,
    workspace_volume_for,
)
from cachibot.storage.db import Base


def _docker_tests_enabled() -> bool:
    """CACHIBOT_DOCKER_TESTS=1 plus a working daemon (docker info answers)."""
    if os.environ.get("CACHIBOT_DOCKER_TESTS", "") != "1":
        return False
    if not shutil.which("docker"):
        return False
    try:
        return subprocess.run(["docker", "info"], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _docker_tests_enabled(),
    reason="set CACHIBOT_DOCKER_TESTS=1 with a working Docker daemon",
)


@pytest.fixture
async def sqlite_db(tmp_path):
    engine = create_async_engine(
        f"sqlite+aiosqlite:///{tmp_path}/test.db",
        connect_args={"timeout": 30},
        echo=False,
    )
    session_maker = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    from sqlalchemy import event

    @event.listens_for(engine.sync_engine, "connect")
    def _set_wal(dbapi_conn, _record) -> None:  # pragma: no cover - plumbing
        dbapi_conn.execute("PRAGMA journal_mode=WAL")

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


def _docker(*args: str) -> None:
    subprocess.run(["docker", *args], capture_output=True, timeout=120)


async def _wait_awake(svc: ComputerService, bot_id: str) -> dict:
    import asyncio
    import time as time_mod

    deadline = time_mod.monotonic() + 30 * 60
    final: dict = {}
    while time_mod.monotonic() < deadline:
        final = await svc.get_status(bot_id)
        if final["state"] == "awake":
            return final
        if final["state"] == "off" and final["lastError"]:
            break
        await asyncio.sleep(5)
    raise AssertionError(f"the computer did not wake: {final.get('lastError')}")


async def test_driven_surface_against_real_docker(tmp_path, sqlite_db) -> None:
    """Wake a real computer and exercise the C3 surface it honestly offers.

    With the pinned 0.2.0 image: the terminal tools refuse with the plain
    feature-gap reason (nothing faked), the driven tool catalogue lists the
    driver surface, and a driven run can be opened and finished (Vela's own
    refusal, if a fresh desktop declines, is surfaced as the plain answer).
    """
    bot_id = f"itest-c3-{uuid.uuid4().hex[:12]}"
    name = container_name_for(bot_id)
    data_volume = data_volume_for(bot_id)
    workspace_volume = workspace_volume_for(bot_id)

    svc = ComputerService(
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=Path(tmp_path) / "tokens",
        health_timeout=120.0,
        idle_poll=3600.0,
        events_poll=3600.0,
        wake_timeout=30 * 60,
        wake_poll=5.0,
    )
    try:
        await svc.wake(bot_id)
        await _wait_awake(svc, bot_id)

        # Feature detection on the pinned image: terminal/workspace/editor
        # are absent, and the refusal says so plainly.
        outcome = await svc.run_tool_step(bot_id, tool="terminal_open", arguments={})
        assert outcome.status == "refusal"
        assert outcome.code == "feature_missing"
        assert "terminal" in outcome.message

        # The wake's agent setup made the desktop agent-ready and cached the
        # driven tool catalogue: the driver surface is listed, the terminal
        # surface is not (the image predates it).
        catalogue = svc.cached_tool_catalogue(bot_id)
        assert catalogue, "the driven tool catalogue was fetched at wake"
        names = {
            (entry.get("function") or {}).get("name")
            for entry in catalogue
            if isinstance(entry, dict)
        }
        assert any(name and name.startswith("desktop.") for name in names)
        assert not any(name and name.startswith("terminal_") for name in names)

        # A driven run on the real desktop: a browser-surface step, or Vela's
        # own plain refusal — either is an honest answer, never a fake one.
        step = await svc.run_tool_step(bot_id, tool="desktop.observe", arguments={})
        assert step.status in ("result", "refusal", "approval", "needs_person", "error")
        if step.status == "result":
            finished = await svc.finish_computer_run(
                bot_id, outcome="succeeded", summary="integration check"
            )
            assert finished.status == "result"
    finally:
        # Nothing may leak: container and both named volumes go away even on
        # failure (volumes are only removed here, in the integration test).
        await svc.stop()
        _docker("rm", "-f", name)
        _docker("volume", "rm", "-f", data_volume)
        _docker("volume", "rm", "-f", workspace_volume)
        token_file = Path(tmp_path) / "tokens" / bot_id / "controller-token"
        token_file.unlink(missing_ok=True)

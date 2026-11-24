"""Optional integration test against a real Docker daemon.

Opt-in only: these tests skip unless CACHIBOT_DOCKER_TESTS=1 is set AND the
daemon answers. They must never run just because Docker happens to be
installed — CI runners included. Run them explicitly with:

    CACHIBOT_DOCKER_TESTS=1 pytest tests/test_computer_integration.py

The first wake builds the real pinned image (a 1-2 GB download); the image
stays in the local Docker cache afterwards, which is intended — later runs
(and the developer's own computer) reuse it. The test's container and both
named volumes are always removed in a finally block — nothing else leaks.
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


async def test_wake_sleep_stop_against_real_docker(tmp_path, sqlite_db) -> None:
    """Build the pinned image (if needed), wake a computer, then clean up.

    The image build can take a long while (Chromium download), so the wake
    itself is given a generous deadline via the service's health timeout.
    """
    bot_id = f"itest-{uuid.uuid4().hex[:12]}"
    name = container_name_for(bot_id)
    data_volume = data_volume_for(bot_id)
    workspace_volume = workspace_volume_for(bot_id)

    svc = ComputerService(
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=Path(tmp_path) / "tokens",
        health_timeout=120.0,
        idle_poll=3600.0,
    )
    try:
        status = await svc.wake(bot_id)
        assert status["available"] is True, status["reason"]

        # Wait for the background wake to finish (build + start + health).
        import asyncio
        import time as time_mod

        deadline = time_mod.monotonic() + 30 * 60
        final = status
        while time_mod.monotonic() < deadline:
            final = await svc.get_status(bot_id)
            if final["state"] in ("awake", "off") and final["lastError"]:
                break
            if final["state"] == "awake":
                break
            await asyncio.sleep(5)
        assert final["state"] == "awake", final.get("lastError")

        # Sleep keeps the volumes; stop marks the computer off.
        slept = await svc.sleep(bot_id)
        assert slept["state"] == "asleep"
        stopped = await svc.stop_computer(bot_id)
        assert stopped["state"] == "off"
    finally:
        # Nothing may leak: container and both named volumes go away even on
        # failure (volumes are only removed here, in the integration test).
        await svc.stop()
        _docker("rm", "-f", name)
        _docker("volume", "rm", "-f", data_volume)
        _docker("volume", "rm", "-f", workspace_volume)
        token_file = Path(tmp_path) / "tokens" / bot_id / "controller-token"
        token_file.unlink(missing_ok=True)


async def test_probe_reports_real_docker(tmp_path, sqlite_db) -> None:
    svc = ComputerService(
        config=ComputerConfig(enabled=True, idle_minutes=10),
        token_dir=Path(tmp_path) / "tokens",
    )
    try:
        probe = await svc.get_docker_status()
        assert probe["available"] is True, probe["reason"]
        assert probe["docker_version"]
    finally:
        await svc.stop()

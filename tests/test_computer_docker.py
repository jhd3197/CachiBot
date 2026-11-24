"""Tests for the Docker probe, CLI discovery, image build and token files.

All Docker access is faked (``tests.computer_fakes.FakeDockerRunner``): no
daemon, no network, no containers. Discovery tests exercise Windows/macOS
path lookup through injected ``which``/``isfile`` callables.
"""

import asyncio
import os
import sys
from pathlib import Path

import httpx
import pytest
from httpx import MockTransport

import cachibot.services.computer.probe as probe_mod
from cachibot.services.computer.build import (
    COMPUTER_IMAGE_TAG,
    VELA_BUILD_CONTEXT,
    VELA_VERSION,
    BuildManager,
    ImageBuildError,
)
from cachibot.services.computer.probe import DockerProbe, find_docker_cli
from cachibot.services.computer.runner import CommandResult, DockerCommandTimeoutError
from cachibot.services.computer.tokens import TokenManager
from cachibot.services.computer.vela_client import VelaClient, VelaClientError
from tests.computer_fakes import FakeClock, FakeDockerRunner, docker_version_json

# ---------------------------------------------------------------------------
# CLI discovery
# ---------------------------------------------------------------------------


class TestCliDiscovery:
    def test_path_wins_everywhere(self) -> None:
        cli = find_docker_cli(
            candidates=[Path("/Applications/Docker.app/Contents/Resources/bin/docker")],
            which=lambda name: "/usr/bin/docker" if name == "docker" else None,
            isfile=lambda path: True,
        )
        assert cli == "/usr/bin/docker"

    def test_no_cli_anywhere(self) -> None:
        cli = find_docker_cli(
            candidates=[Path("/usr/bin/docker")],
            which=lambda name: None,
            isfile=lambda path: False,
        )
        assert cli is None

    def test_windows_docker_desktop_path(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(probe_mod.platform, "system", lambda: "Windows")
        monkeypatch.setenv("ProgramFiles", r"C:\Program Files")
        candidates = probe_mod.default_cli_candidates()
        # Built the same way the production code builds it (Path is
        # platform-specific; this test runs on POSIX CI too).
        expected = (
            Path(os.environ["ProgramFiles"])
            / "Docker"
            / "Docker"
            / "resources"
            / "bin"
            / "docker.exe"
        )
        assert candidates == [expected]
        cli = find_docker_cli(
            candidates=candidates,
            which=lambda name: None,
            isfile=lambda path: path == candidates[0],
        )
        assert cli == str(candidates[0])

    def test_macos_docker_desktop_paths(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(probe_mod.platform, "system", lambda: "Darwin")
        candidates = probe_mod.default_cli_candidates()
        assert candidates == [
            Path("/Applications/Docker.app/Contents/Resources/bin/docker"),
            Path("/usr/local/bin/docker"),
            Path("/opt/homebrew/bin/docker"),
        ]
        cli = find_docker_cli(
            candidates=candidates,
            which=lambda name: None,
            isfile=lambda path: path == Path("/opt/homebrew/bin/docker"),
        )
        assert cli == "/opt/homebrew/bin/docker"


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------


def make_probe(runner: FakeDockerRunner, clock: FakeClock | None = None) -> DockerProbe:
    return DockerProbe(
        runner,
        cli_resolver=lambda: runner.cli,
        clock=(clock or FakeClock()).monotonic,
        cache_seconds=15.0,
    )


class TestProbe:
    async def test_no_cli(self) -> None:
        probe = DockerProbe(FakeDockerRunner(), cli_resolver=lambda: None)
        result = await probe.probe()
        assert not result.available
        assert "docker CLI" in (result.reason or "")

    async def test_daemon_down(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "version",
            result=CommandResult(
                [],
                1,
                "",
                "Cannot connect to the Docker daemon at unix:///var/run/docker.sock. "
                "Is the docker daemon running?",
            ),
        )
        result = await make_probe(runner).probe()
        assert not result.available
        assert "daemon" in (result.reason or "").lower()

    async def test_permission_denied(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "version",
            result=CommandResult(
                [], 1, "", "permission denied while trying to connect to the Docker daemon socket"
            ),
        )
        result = await make_probe(runner).probe()
        assert not result.available
        assert "permission denied" in (result.reason or "")

    async def test_ok(self) -> None:
        runner = FakeDockerRunner()
        runner.when("version", result=CommandResult([], 0, docker_version_json(), ""))
        result = await make_probe(runner).probe()
        assert result.available
        assert result.reason is None
        assert result.docker_version == "27.3.1"
        assert result.server_os == "linux"
        assert result.arch == "x86_64"

    async def test_server_missing_in_output(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "version", result=CommandResult([], 0, docker_version_json(with_server=False), "")
        )
        result = await make_probe(runner).probe()
        assert not result.available
        assert "not reachable" in (result.reason or "")

    async def test_timeout(self) -> None:
        runner = FakeDockerRunner()
        runner.when("version", result=DockerCommandTimeoutError("slow"))
        result = await make_probe(runner).probe()
        assert not result.available
        assert "in time" in (result.reason or "")

    async def test_result_cached_then_forced(self) -> None:
        runner = FakeDockerRunner()
        runner.when("version", result=CommandResult([], 0, docker_version_json(), ""))
        clock = FakeClock()
        probe = make_probe(runner, clock)
        await probe.probe()
        await probe.probe()
        assert len(runner.calls_for("version")) == 1
        clock.advance(seconds=20)
        await probe.probe()
        assert len(runner.calls_for("version")) == 2
        await probe.probe(force=True)
        assert len(runner.calls_for("version")) == 3


# ---------------------------------------------------------------------------
# Image build
# ---------------------------------------------------------------------------


BUILD_LINES = [
    "#1 [internal] load build definition from Dockerfile",
    "#1 DONE 0.1s",
    "#5 [2/7] RUN pip install vela",
    "#5 0.234 Collecting vela",
    "#5 DONE 2.0s",
    "#9 [7/7] HEALTHCHECK /api/health",
    "#9 DONE 30.0s",
]


def make_build_manager(runner: FakeDockerRunner, on_progress=None) -> BuildManager:
    return BuildManager(
        runner,
        cli_resolver=lambda: runner.cli,
        on_progress=on_progress,
        timeout=60.0,
    )


class TestBuildManager:
    async def test_build_argv_is_pinned(self) -> None:
        manager = make_build_manager(FakeDockerRunner())
        assert manager.build_argv("docker") == [
            "docker",
            "build",
            "--target",
            "computer",
            "--build-arg",
            f"VELA_VERSION={VELA_VERSION}",
            "--progress",
            "plain",
            "-t",
            COMPUTER_IMAGE_TAG,
            VELA_BUILD_CONTEXT,
        ]

    async def test_skips_build_when_image_exists(self) -> None:
        runner = FakeDockerRunner()
        runner.when("image", "inspect", COMPUTER_IMAGE_TAG, result=CommandResult([], 0, "[]", ""))
        manager = make_build_manager(runner)
        await manager.ensure_image()
        assert runner.calls_for("build") == []

    async def test_builds_and_parses_progress_when_missing(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "image", "inspect", COMPUTER_IMAGE_TAG, result=CommandResult([], 1, "", "No such image")
        )
        runner.when("build", result=BUILD_LINES)
        progress = []
        manager = make_build_manager(runner, on_progress=progress.append)
        await manager.ensure_image()
        assert len(runner.calls_for("build")) == 1
        assert manager.progress.status == "idle"
        building = [p for p in progress if p.status == "building"]
        assert building, "expected building progress events"
        by_line = {p.line: p for p in building}
        assert by_line["#5 [2/7] RUN pip install vela"].step == 2
        assert by_line["#9 [7/7] HEALTHCHECK /api/health"].total == 7
        # After the [7/7] marker the total stays 7; the trailing "#9 DONE"
        # line carries no marker, so its step clamps to the known total.
        last = building[-1]
        assert (last.step, last.total) == (7, 7)

    async def test_single_flight_concurrent_builds(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "image", "inspect", COMPUTER_IMAGE_TAG, result=CommandResult([], 1, "", "No such image")
        )
        gate = asyncio.Event()

        async def scripted_build():
            await gate.wait()
            return BUILD_LINES

        runner.when("build", result=scripted_build)
        manager = make_build_manager(runner)
        first = asyncio.create_task(manager.ensure_image())
        await asyncio.sleep(0.05)  # let the first build start and block on the gate
        second = asyncio.create_task(manager.ensure_image())
        gate.set()
        await asyncio.gather(first, second)
        assert len(runner.calls_for("build")) == 1

    async def test_failed_build_reports_error_and_retries_later(self) -> None:
        runner = FakeDockerRunner()
        runner.when(
            "image", "inspect", COMPUTER_IMAGE_TAG, result=CommandResult([], 1, "", "No such image")
        )
        progress = []
        attempts = {"count": 0}

        def flaky_build() -> CommandResult | list[str]:
            attempts["count"] += 1
            if attempts["count"] == 1:
                return CommandResult([], 1, "#1 [1/2] RUN broken\nboom: something exploded", "")
            return BUILD_LINES

        runner.when("build", result=flaky_build)
        manager = make_build_manager(runner, on_progress=progress.append)

        with pytest.raises(ImageBuildError) as excinfo:
            await manager.ensure_image()
        assert "boom" in str(excinfo.value)
        assert "boom" in manager.progress.error  # type: ignore[operator]
        assert manager.progress.status == "failed"

        # A later wake retries and succeeds.
        await manager.ensure_image()
        assert attempts["count"] == 2
        assert manager.progress.status == "idle"
        assert any(p.status == "failed" for p in progress)


# ---------------------------------------------------------------------------
# Controller tokens
# ---------------------------------------------------------------------------


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes are not enforced on Windows")
class TestTokenFilePosix:
    async def test_file_contents_and_permissions(self, tmp_path: Path) -> None:
        manager = TokenManager(tmp_path / "computers")
        bot_id = "b0t-1234-uuid"
        token = manager.ensure_token(bot_id)
        assert token == manager.ensure_token(bot_id), "token must be stable per bot"

        token_file = manager.token_path(bot_id)
        assert token_file.read_text(encoding="utf-8").strip() == token
        assert len(token) >= 32
        assert token_file.stat().st_mode & 0o777 == 0o644

        directory = token_file.parent
        assert directory.stat().st_mode & 0o777 == 0o700
        # The per-bot directories live inside the computers base dir.
        assert (tmp_path / "computers").stat().st_mode & 0o777 == 0o700

    async def test_rejects_path_traversal(self, tmp_path: Path) -> None:
        manager = TokenManager(tmp_path / "computers")
        with pytest.raises(ValueError):
            manager.ensure_token("../escape")


class TestTokenFileAnyPlatform:
    async def test_stable_and_urlsafe(self, tmp_path: Path) -> None:
        manager = TokenManager(tmp_path / "computers")
        token = manager.ensure_token("b0t-uuid")
        assert token == manager.ensure_token("b0t-uuid")
        assert token.isalnum() or "-" in token or "_" in token


# ---------------------------------------------------------------------------
# Vela client (httpx MockTransport — no network)
# ---------------------------------------------------------------------------


class TestVelaClient:
    def _client(self, handler) -> VelaClient:
        return VelaClient(
            "http://127.0.0.1:9",
            token="t" * 40,
            transport=MockTransport(handler),
        )

    async def test_health_open_endpoint(self) -> None:
        def handler(request):
            assert request.url.path == "/api/health"
            assert "authorization" not in request.headers
            return httpx.Response(200, json={"ok": True})

        assert await self._client(handler).health() is True

    async def test_health_false_on_error_status(self) -> None:
        assert await self._client(lambda request: httpx.Response(500)).health() is False

    async def test_health_false_on_connection_error(self) -> None:
        def handler(request):
            raise httpx.ConnectError("refused")

        assert await self._client(handler).health() is False

    async def test_controller_info_sends_bearer(self) -> None:
        seen = {}

        def handler(request):
            seen["path"] = request.url.path
            seen["auth"] = request.headers.get("authorization")
            return httpx.Response(
                200,
                json={"mode": "controller", "version": "0.2.0", "protocol": 2},
            )

        info = await self._client(handler).controller_info()
        assert info["protocol"] == 2
        assert seen == {"path": "/api/controller", "auth": "Bearer " + "t" * 40}

    async def test_controller_rejected_token(self) -> None:
        with pytest.raises(VelaClientError, match="rejected"):
            await self._client(lambda request: httpx.Response(401)).controller_info()

    async def test_controller_other_error(self) -> None:
        with pytest.raises(VelaClientError, match="500"):
            await self._client(lambda request: httpx.Response(500)).controller_info()

    async def test_controller_invalid_json(self) -> None:
        with pytest.raises(VelaClientError, match="JSON"):
            await self._client(lambda request: httpx.Response(200, text="nope")).controller_info()

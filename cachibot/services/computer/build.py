"""Pinned Vela computer image: build once, locally, on first use.

The image is built from the pinned Vela release's git repo through a remote
build context — no checkout needed. Nothing is pulled from a registry.
Builds are single-flight: the first caller starts the build and concurrent
callers await the same task, so a bot's wake never kicks off two builds. A
failed build records its error (with a log tail) and lets the next wake
retry from scratch.
"""

from __future__ import annotations

import asyncio
import logging
import re
from collections import deque
from collections.abc import Callable

from cachibot.models.computer import BuildProgress
from cachibot.services.computer.runner import DockerRunner

logger = logging.getLogger(__name__)

#: Pinned Vela release (the first release with the controller mode and the
#: ``computer`` image target). Bumping this is the only way the image changes.
VELA_VERSION = "0.2.0"
COMPUTER_IMAGE_TAG = f"cachibot-vela-computer:{VELA_VERSION}"
VELA_BUILD_CONTEXT = f"https://github.com/jhd3197/Vela.git#v{VELA_VERSION}"

BUILD_LOG_TAIL_LINES = 30
DEFAULT_BUILD_TIMEOUT_SECONDS = 1800.0  # local builds are slow; still bounded

_PROGRESS_RE = re.compile(r"^#(\d+)\s+(?:\[(\d+)/(\d+)\]\s*)?(.*)$")


class ImageBuildError(Exception):
    """The image build failed; carries a short log tail for the UI."""

    def __init__(self, message: str, log_tail: str = "") -> None:
        super().__init__(message)
        self.log_tail = log_tail


def _one_line(text: str, limit: int = 300) -> str:
    return " ".join(text.split())[:limit]


class BuildManager:
    """Ensure the pinned computer image exists, building it once if needed."""

    def __init__(
        self,
        runner: DockerRunner,
        *,
        cli_resolver: Callable[[], str | None],
        on_progress: Callable[[BuildProgress], None] | None = None,
        image_tag: str = COMPUTER_IMAGE_TAG,
        vela_version: str = VELA_VERSION,
        build_context: str = VELA_BUILD_CONTEXT,
        timeout: float = DEFAULT_BUILD_TIMEOUT_SECONDS,
    ) -> None:
        self._runner = runner
        self._cli_resolver = cli_resolver
        self._on_progress = on_progress
        self._image_tag = image_tag
        self._vela_version = vela_version
        self._build_context = build_context
        self._timeout = timeout
        self._task: asyncio.Task[None] | None = None
        self._start_lock = asyncio.Lock()
        self.progress = BuildProgress(status="idle")

    def _emit(self, progress: BuildProgress) -> None:
        self.progress = progress
        if self._on_progress is not None:
            try:
                self._on_progress(progress)
            except Exception:  # noqa: BLE001 - progress callbacks must not break builds
                logger.debug("build progress callback raised", exc_info=True)

    async def image_exists(self) -> bool:
        """True when the pinned tag already exists locally."""
        cli = self._cli_resolver()
        if not cli:
            raise ImageBuildError("docker CLI not found", "")
        result = await self._runner.run([cli, "image", "inspect", self._image_tag], timeout=30.0)
        return result.returncode == 0

    async def ensure_image(self) -> None:
        """Build the image if missing; concurrent callers share one build.

        Raises :class:`ImageBuildError` when the build fails; a later call
        starts a fresh build (single-flight per attempt, retry on the next).
        """
        if await self.image_exists():
            return
        async with self._start_lock:
            if await self.image_exists():
                return  # another caller built it while we waited for the lock
            if self._task is None or self._task.done():
                self._task = asyncio.create_task(self._build())
            task = self._task
        # Shield so one caller cancelling its wake never kills the shared build.
        await asyncio.shield(task)

    async def _build(self) -> None:
        cli = self._cli_resolver()
        if not cli:
            raise ImageBuildError("docker CLI not found", "")

        tail: deque[str] = deque(maxlen=BUILD_LOG_TAIL_LINES)
        latest = BuildProgress(status="building", line="starting build")
        self._emit(latest)

        def on_line(line: str) -> None:
            tail.append(line)
            match = _PROGRESS_RE.match(line.strip())
            if match:
                stream_id = int(match.group(1))
                step = int(match.group(2)) if match.group(2) else stream_id
                total = int(match.group(3)) if match.group(3) else None
                if total is not None:
                    latest.total = total
                latest.step = step
                if latest.total is not None and latest.step > latest.total:
                    latest.step = latest.total
            latest.line = line
            self._emit(BuildProgress(**latest.model_dump()))

        argv = self.build_argv(cli)
        try:
            result = await self._runner.run(argv, timeout=self._timeout, on_line=on_line)
        except Exception as exc:  # noqa: BLE001 - timeouts etc. surface as build errors
            log_tail = "\n".join(tail)
            self._emit(BuildProgress(status="failed", error=_one_line(str(exc)), line=latest.line))
            raise ImageBuildError(f"image build failed: {_one_line(str(exc))}", log_tail) from exc

        if result.returncode != 0:
            log_tail = "\n".join(tail) or result.stderr
            message = f"image build failed (exit {result.returncode}): {_one_line(log_tail)}"
            self._emit(BuildProgress(status="failed", error=_one_line(message), line=latest.line))
            raise ImageBuildError(message, log_tail)

        self._emit(BuildProgress(status="idle"))

    def build_argv(self, cli: str) -> list[str]:
        """The exact docker build invocation (kept separate for tests)."""
        return [
            cli,
            "build",
            "--target",
            "computer",
            "--build-arg",
            f"VELA_VERSION={self._vela_version}",
            "--progress",
            "plain",
            "-t",
            self._image_tag,
            self._build_context,
        ]

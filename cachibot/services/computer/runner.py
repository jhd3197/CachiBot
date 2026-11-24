"""Docker CLI runner: the single choke point for all Docker access.

Everything Docker goes through :class:`DockerRunner` so tests can swap in a
fake that records argv and returns scripted output — no Docker daemon, no
network, no containers in tests. The real implementation is a thin async
subprocess wrapper; it never uses ``shell=True`` (argument lists only).
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass
class CommandResult:
    """Finished process: what ran, its exit code and captured output."""

    argv: list[str]
    returncode: int
    stdout: str
    stderr: str = ""


@runtime_checkable
class DockerRunner(Protocol):
    """Run one Docker CLI invocation.

    ``on_line`` (when given) is called for every output line as it arrives,
    letting callers stream long-running commands (image builds) instead of
    waiting for completion. Implementations must not mutate ``argv``.
    """

    async def run(
        self,
        argv: list[str],
        timeout: float | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> CommandResult:
        """Run ``argv`` and wait for it to finish."""
        ...


class DockerCLINotFoundError(Exception):
    """Raised when the docker CLI cannot be located anywhere."""


class DockerCommandTimeoutError(Exception):
    """Raised when a Docker CLI invocation exceeded its timeout."""


@dataclass
class SubprocessDockerRunner:
    """Async subprocess implementation of :class:`DockerRunner`."""

    max_line_length: int = 100_000

    async def run(
        self,
        argv: list[str],
        timeout: float | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> CommandResult:
        """Run ``argv`` without a shell, capturing stdout/stderr.

        With ``on_line``, stdout and stderr are drained concurrently and each
        line is reported as it arrives (build output streams this way); the
        final :class:`CommandResult` still holds the full captured text.
        """
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            limit=self.max_line_length,
        )

        async def _read(pipe: asyncio.StreamReader, sink: list[str]) -> None:
            while True:
                raw = await pipe.readline()
                if not raw:
                    return
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                sink.append(line)
                if on_line is not None:
                    on_line(line)

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        tasks = [
            asyncio.create_task(_read(proc.stdout, stdout_lines)),  # type: ignore[arg-type]
            asyncio.create_task(_read(proc.stderr, stderr_lines)),  # type: ignore[arg-type]
        ]
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
            await asyncio.gather(*tasks)
        except (TimeoutError, asyncio.TimeoutError):
            proc.kill()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise DockerCommandTimeoutError(f"docker command timed out after {timeout}s: {argv[0]}")
        finally:
            for task in tasks:
                task.cancel()

        return CommandResult(
            argv=list(argv),
            returncode=proc.returncode or 0,
            stdout="\n".join(stdout_lines),
            stderr="\n".join(stderr_lines),
        )

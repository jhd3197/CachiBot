"""Shared fakes for the computer tests: no Docker, no network, no containers.

``FakeDockerRunner`` records every argv and replays scripted responses (or
streams scripted build lines through ``on_line``); ``FakeVelaClient`` stands
in for the Vela controller endpoints. Tests for the token file run against a
tmp dir, never the real data dir.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from cachibot.services.computer.runner import CommandResult


class FakeDockerRunner:
    """Scripted :class:`DockerRunner`: first matching predicate wins.

    A response may be:
      - a ``CommandResult`` (replayed as-is; stdout lines go to ``on_line``),
      - a list of strings (streamed line by line, exit code 0),
      - an exception instance (raised),
      - a zero-arg callable returning any of the above (evaluated per call,
        so tests can script state changes over time).
    """

    def __init__(self, cli: str = "/usr/bin/docker") -> None:
        self.cli = cli
        self.calls: list[list[str]] = []
        self._responses: list[
            tuple[
                Callable[[list[str]], bool],
                CommandResult | Iterable[str] | Exception | Callable[[], Any],
            ]
        ] = []
        self.default = CommandResult([], 0, "", "")

    def when(
        self,
        *argv_prefix: str,
        result: CommandResult | Iterable[str] | Exception | Callable[[], Any] | None = None,
    ) -> None:
        """Script the response for invocations whose args (after the program
        name) start with ``argv_prefix``."""

        def pred(argv: list[str]) -> bool:
            return list(argv[1 : 1 + len(argv_prefix)]) == list(argv_prefix)

        if result is None:
            result = CommandResult([], 0, "", "")
        self._responses.insert(0, (pred, result))

    def calls_for(self, *argv_prefix: str) -> list[list[str]]:
        """Recorded invocations whose args (after the program name) start with
        ``argv_prefix``."""
        return [
            call for call in self.calls if list(call[1 : 1 + len(argv_prefix)]) == list(argv_prefix)
        ]

    async def run(
        self,
        argv: list[str],
        timeout: float | None = None,
        on_line: Callable[[str], None] | None = None,
    ) -> CommandResult:
        self.calls.append(list(argv))
        response: Any = self.default
        for pred, scripted in self._responses:
            if pred(argv):
                response = scripted
                break
        if callable(response):
            response = response()
        if asyncio.iscoroutine(response):
            response = await response
        if isinstance(response, Exception):
            raise response
        if isinstance(response, CommandResult):
            if on_line is not None:
                for line in response.stdout.splitlines():
                    on_line(line)
            return CommandResult(list(argv), response.returncode, response.stdout, response.stderr)
        lines = list(response)
        if on_line is not None:
            for line in lines:
                on_line(line)
        return CommandResult(list(argv), 0, "\n".join(lines), "")


class FakeVelaClient:
    """Scripted Vela controller client (health + controller_info)."""

    def __init__(
        self,
        *,
        health: bool = True,
        info: dict[str, Any] | None = None,
        info_error: Exception | None = None,
    ) -> None:
        self.health_result = health
        self.info = (
            info
            if info is not None
            else {
                "mode": "controller",
                "version": "0.2.0",
                "protocol": 2,
                "features": {"controller": True, "driver": True},
            }
        )
        self.info_error = info_error
        self.health_calls = 0

    async def health(self) -> bool:
        self.health_calls += 1
        return self.health_result

    async def controller_info(self) -> dict[str, Any]:
        if self.info_error is not None:
            raise self.info_error
        return self.info


class FakeClock:
    """Controllable wall clock + monotonic clock (idle-sleep tests)."""

    def __init__(self, start: datetime | None = None) -> None:
        self._dt = start or datetime(2026, 11, 23, 12, 0, 0, tzinfo=timezone.utc)
        self._mono = 0.0

    def now(self) -> datetime:
        return self._dt

    def monotonic(self) -> float:
        return self._mono

    def advance(self, *, minutes: float = 0.0, seconds: float = 0.0) -> None:
        self._dt += timedelta(minutes=minutes, seconds=seconds)
        self._mono += minutes * 60.0 + seconds


def docker_version_json(
    *,
    server_version: str = "27.3.1",
    os_name: str = "linux",
    arch: str = "x86_64",
    client_version: str = "27.3.1",
    with_server: bool = True,
) -> str:
    """A ``docker version --format '{{json .}}'`` payload."""
    data: dict[str, Any] = {"Client": {"Version": client_version}}
    if with_server:
        data["Server"] = {"Version": server_version, "Os": os_name, "Arch": arch}
    import json

    return json.dumps(data)


def ps_line(
    *,
    bot_id: str,
    names: str,
    state: str,
    image: str = "cachibot-vela-computer:0.2.0",
) -> str:
    """One ``docker ps -a --format '{{json .}}'`` line for a managed container."""
    import json

    return json.dumps(
        {
            "ID": "abcdef123456",
            "Names": names,
            "Image": image,
            "Labels": f"cachibot.bot_id={bot_id},cachibot.managed=1",
            "State": state,
            "Status": state,
        }
    )

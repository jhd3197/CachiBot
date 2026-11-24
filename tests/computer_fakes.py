"""Shared fakes for the computer tests: no Docker, no network, no containers.

``FakeDockerRunner`` records every argv and replays scripted responses (or
streams scripted build lines through ``on_line``); ``FakeVelaClient`` stands
in for the Vela controller endpoints (C1 discovery, the C2 live surface —
desktops, views, frames, heartbeats, take-over/input/release, events,
approvals and task control — and the C3 driven-run surface: the tool
catalogue, driven runs/steps, the task list, and the policy + enable-agent
setup a fresh desktop needs). Tests for the token file run against a tmp
dir, never the real data dir.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone
from typing import Any

from cachibot.services.computer.runner import CommandResult
from cachibot.services.computer.vela_client import VelaClientError, VelaFrameResult


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
    """Scripted Vela controller client (C1 discovery + the C2 live surface).

    Defaults describe one desktop (``desk-1``) with one web window
    (``view-1``) whose frame digest is ``digest-1``; the full-desktop frame
    exists only when ``info`` advertises ``features.desktopFrame`` (the
    desktop-frame opt-in; set an info dict that carries it to switch it on).
    Every call is recorded.
    """

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
                "version": "0.3.0",
                "protocol": 5,
                "features": {"controller": True, "driver": True},
            }
        )
        self.info_error = info_error
        self.health_calls = 0
        self.close_calls = 0
        # Desktops
        self.desktops: list[dict[str, Any]] = [
            {"id": "desk-1", "name": "Bot computer", "kind": "personal"}
        ]
        self.default_desktop_id: str | None = "desk-1"
        self.create_calls: list[str] = []
        # Views / viewer
        self.views_payload: dict[str, Any] = {
            "views": [
                {
                    "id": "view-1",
                    "kind": "web",
                    "title": "Example",
                    "url": "https://example.com/",
                    "appId": None,
                    "agentViewable": True,
                }
            ],
            "layout": {"selectedView": "view-1"},
        }
        self.views_error: Exception | None = None
        self.viewer_status_payload: dict[str, Any] = {
            "desktopId": "desk-1",
            "kind": "personal",
            "control": None,
            "task": None,
            "watchers": {"count": 0, "kinds": {}},
            "activity": None,
        }
        self.heartbeats: list[dict[str, Any]] = []
        # Frames
        self.frame_meta: dict[str, Any] = {
            "viewId": "view-1",
            "desktopId": "desk-1",
            "digest": "digest-1",
            "width": 1280,
            "height": 800,
            "capturedAt": 1.0,
        }
        self.frame_meta_error: Exception | None = None
        self.frame_bytes_map: dict[tuple[str, str], bytes] = {("view-1", "digest-1"): b"png-1"}
        self.frame_bytes_calls: list[tuple[str, str, str]] = []
        self.desktop_frame_body = b"desktop-png-1"
        self.desktop_frame_etag = '"desktop-digest-1"'
        self.desktop_frame_revision = "7"
        self.desktop_frame_calls: list[str | None] = []
        # Take-over / input / hand back
        self.takeover_calls: list[dict[str, Any]] = []
        self.takeover_error: Exception | None = None
        self.input_calls: list[dict[str, Any]] = []
        self.input_error: Exception | None = None
        self.release_calls: list[tuple[str, str]] = []
        self.release_error: Exception | None = None
        # Events / needs-you answers
        self.events_handler: Callable[[int, int], dict[str, Any]] | None = None
        self.events_calls: list[int] = []
        self.resolve_approval_calls: list[tuple[str, str, str]] = []
        self.control_task_calls: list[tuple[str, str, str]] = []
        # C3: driven runs + agent setup. The desktop starts "personal"; the
        # policy starts empty, so enable_agent refuses until a policy with an
        # approved app or site is saved — exactly like the real Vela.
        self.policy: dict[str, Any] = {
            "revision": 0,
            "apps": [],
            "sites": [],
            "approvals": "ask",
            "actionScopes": [],
            "budget": None,
            "rememberSessions": False,
        }
        self.put_policy_calls: list[dict[str, Any]] = []
        self.enable_agent_calls: list[str] = []
        self.driven_runs: list[dict[str, Any]] = []
        self.create_run_calls: list[dict[str, Any]] = []
        self.create_run_error: Exception | None = None
        self.step_calls: list[dict[str, Any]] = []
        self.step_handler: Callable[[str, dict[str, Any], str], dict[str, Any]] | None = None
        self.step_read_handler: Callable[[str], dict[str, Any]] | None = None
        self.step_read_calls: list[str] = []
        self.finish_calls: list[dict[str, Any]] = []
        self.cancel_calls: list[str] = []
        self.tasks_payload: dict[str, Any] | None = None
        self.driven_tools: list[dict[str, Any]] | None = None

    # -- C1 ----------------------------------------------------------------

    async def health(self) -> bool:
        self.health_calls += 1
        return self.health_result

    async def controller_info(self) -> dict[str, Any]:
        if self.info_error is not None:
            raise self.info_error
        return self.info

    async def aclose(self) -> None:
        self.close_calls += 1

    # -- Desktops ------------------------------------------------------------

    async def list_desktops(self) -> dict[str, Any]:
        return {"desktops": list(self.desktops), "defaultId": self.default_desktop_id}

    async def create_desktop(self, name: str) -> dict[str, Any]:
        self.create_calls.append(name)
        desktop = {"id": f"desk-{len(self.desktops) + 1}", "name": name, "kind": "personal"}
        self.desktops.append(desktop)
        if self.default_desktop_id is None:
            self.default_desktop_id = desktop["id"]
        return desktop

    async def views(self, desktop_id: str) -> dict[str, Any]:
        if self.views_error is not None:
            raise self.views_error
        return self.views_payload

    # -- Viewer --------------------------------------------------------------

    async def viewer_status(self, desktop_id: str) -> dict[str, Any]:
        return self.viewer_status_payload

    async def viewer_heartbeat(
        self,
        desktop_id: str,
        viewer_id: str,
        *,
        kind: str | None = None,
        view_id: str | None = None,
    ) -> dict[str, Any]:
        self.heartbeats.append(
            {"desktopId": desktop_id, "viewerId": viewer_id, "kind": kind, "viewId": view_id}
        )
        return {
            "watching": True,
            "expiresInSeconds": 20,
            "watchers": {"count": len(self.heartbeats), "kinds": {"person": len(self.heartbeats)}},
        }

    async def view_frame(self, desktop_id: str, view_id: str) -> dict[str, Any]:
        if self.frame_meta_error is not None:
            raise self.frame_meta_error
        return dict(self.frame_meta)

    async def view_frame_bytes(self, desktop_id: str, view_id: str, digest: str) -> bytes:
        self.frame_bytes_calls.append((desktop_id, view_id, digest))
        body = self.frame_bytes_map.get((view_id, digest))
        if body is None:
            raise VelaClientError("view frame bytes: HTTP 404", status_code=404)
        return body

    async def desktop_frame(self, desktop_id: str, etag: str | None = None) -> VelaFrameResult:
        self.desktop_frame_calls.append(etag)
        features = self.info.get("features") or {}
        if not features.get("desktopFrame"):
            raise VelaClientError("desktop frame: HTTP 404", status_code=404)
        if etag and etag == self.desktop_frame_etag:
            return VelaFrameResult(status=304, etag=self.desktop_frame_etag)
        return VelaFrameResult(
            status=200,
            body=self.desktop_frame_body,
            etag=self.desktop_frame_etag,
            revision=self.desktop_frame_revision,
        )

    # -- Take-over / input / hand back ----------------------------------------

    async def takeover(self, desktop_id: str, view_id: str | None = None) -> dict[str, Any]:
        self.takeover_calls.append({"desktopId": desktop_id, "viewId": view_id})
        if self.takeover_error is not None:
            raise self.takeover_error
        return {
            "leaseId": f"lease-{len(self.takeover_calls)}",
            "desktopId": desktop_id,
            "viewId": view_id,
            "holder": "abcd1234",
            "controlEpoch": 3,
            "expiresAt": 999999999.0,
            "task": None,
        }

    async def send_input(
        self, desktop_id: str, lease_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.input_calls.append({"desktopId": desktop_id, "leaseId": lease_id, "payload": payload})
        if self.input_error is not None:
            raise self.input_error
        return {"ok": True, "after": None}

    async def release(self, desktop_id: str, lease_id: str) -> dict[str, Any]:
        self.release_calls.append((desktop_id, lease_id))
        if self.release_error is not None:
            raise self.release_error
        return {"released": True, "task": None, "note": "The task is still paused."}

    # -- Events / needs-you answers -------------------------------------------

    async def events(self, desktop_id: str, *, after: int = 0, limit: int = 200) -> dict[str, Any]:
        self.events_calls.append(after)
        if self.events_handler is not None:
            return self.events_handler(after, limit)
        return {"events": [], "cursor": after, "latest": after, "gap": False}

    async def resolve_approval(
        self, desktop_id: str, request_id: str, decision: str
    ) -> dict[str, Any]:
        self.resolve_approval_calls.append((desktop_id, request_id, decision))
        return {"ok": True}

    async def control_task(self, desktop_id: str, run_id: str, action: str) -> dict[str, Any]:
        self.control_task_calls.append((desktop_id, run_id, action))
        return {"ok": True}

    # -- C3: driven runs + agent setup ----------------------------------------

    def _features(self) -> dict[str, Any]:
        return self.info.get("features") or {}

    def _desktop_kind(self, desktop_id: str) -> str:
        for desktop in self.desktops:
            if desktop.get("id") == desktop_id:
                return str(desktop.get("kind") or "personal")
        return "personal"

    async def list_driven_tools(self, desktop_id: str) -> dict[str, Any]:
        if self._desktop_kind(desktop_id) != "agent":
            raise VelaClientError(
                "list driven tools: HTTP 409 — This desktop is not running an agent.",
                status_code=409,
                detail="This desktop is not running an agent.",
            )
        if self.driven_tools is not None:
            return {"tools": list(self.driven_tools)}
        return {"tools": default_driven_tools(self._features())}

    async def create_driven_run(
        self,
        desktop_id: str,
        *,
        title: str,
        instruction: str | None = None,
        client_request_id: str | None = None,
    ) -> dict[str, Any]:
        self.create_run_calls.append(
            {
                "desktopId": desktop_id,
                "title": title,
                "instruction": instruction,
                "clientRequestId": client_request_id,
            }
        )
        if self.create_run_error is not None:
            raise self.create_run_error
        if self._desktop_kind(desktop_id) != "agent":
            raise VelaClientError(
                "create driven run: HTTP 409 — This desktop is not running an agent.",
                status_code=409,
                detail="This desktop is not running an agent.",
            )
        if client_request_id:
            for run in self.driven_runs:
                if run.get("clientRequestId") == client_request_id:
                    return dict(run)
        active = next((r for r in self.driven_runs if r["state"] not in TERMINAL_RUN_STATES), None)
        if active is not None:
            raise VelaClientError(
                "create driven run: HTTP 409 — This desktop is already carrying a task.",
                status_code=409,
                detail="This desktop is already carrying a task.",
            )
        run = {
            "id": f"run-{len(self.driven_runs) + 1}",
            "kind": "driven",
            "state": "running",
            "title": title,
            "clientRequestId": client_request_id,
        }
        self.driven_runs.append(run)
        return dict(run)

    async def driven_step(
        self,
        desktop_id: str,
        run_id: str,
        *,
        tool: str,
        arguments: dict[str, Any],
        client_step_id: str,
    ) -> dict[str, Any]:
        self.step_calls.append(
            {
                "desktopId": desktop_id,
                "runId": run_id,
                "tool": tool,
                "arguments": arguments,
                "clientStepId": client_step_id,
            }
        )
        if self.step_handler is not None:
            return self.step_handler(tool, arguments, client_step_id)
        return {
            "result": {"tool": tool, "arguments": arguments},
            "budget": {"steps": len(self.step_calls)},
        }

    async def get_driven_step(
        self, desktop_id: str, run_id: str, client_step_id: str
    ) -> dict[str, Any]:
        self.step_read_calls.append(client_step_id)
        if self.step_read_handler is not None:
            return self.step_read_handler(client_step_id)
        raise VelaClientError(
            "read driven step: HTTP 404 — There is no step by that id on this task.",
            status_code=404,
            detail="There is no step by that id on this task.",
        )

    async def finish_driven_run(
        self, desktop_id: str, run_id: str, *, outcome: str, summary: str
    ) -> dict[str, Any]:
        self.finish_calls.append(
            {"desktopId": desktop_id, "runId": run_id, "outcome": outcome, "summary": summary}
        )
        for run in self.driven_runs:
            if run["id"] == run_id:
                run["state"] = outcome if outcome in ("succeeded", "failed") else "succeeded"
                run["summary"] = summary
                return dict(run)
        raise VelaClientError(
            "finish driven run: HTTP 404 — no such run", status_code=404, detail="no such run"
        )

    async def cancel_driven_run(self, desktop_id: str, run_id: str) -> dict[str, Any]:
        self.cancel_calls.append(run_id)
        for run in self.driven_runs:
            if run["id"] == run_id:
                run["state"] = "cancelled"
                return dict(run)
        raise VelaClientError(
            "cancel driven run: HTTP 404 — no such run", status_code=404, detail="no such run"
        )

    async def list_tasks(self, desktop_id: str) -> dict[str, Any]:
        if self.tasks_payload is not None:
            return self.tasks_payload
        return {"tasks": [dict(run) for run in self.driven_runs]}

    async def get_policy(self, desktop_id: str) -> dict[str, Any]:
        return dict(self.policy)

    async def put_policy(
        self, desktop_id: str, document: dict[str, Any], revision: int
    ) -> dict[str, Any]:
        if revision != self.policy.get("revision"):
            raise VelaClientError(
                "save policy: HTTP 409 — the policy changed",
                status_code=409,
                detail="the policy changed",
            )
        self.put_policy_calls.append({"desktopId": desktop_id, "document": document})
        self.policy = {
            **self.policy,
            **document,
            "revision": int(self.policy.get("revision") or 0) + 1,
        }
        return dict(self.policy)

    async def enable_agent(self, desktop_id: str) -> dict[str, Any]:
        self.enable_agent_calls.append(desktop_id)
        if not (self.policy.get("apps") or self.policy.get("sites")):
            raise VelaClientError(
                "enable agent: HTTP 422 — choose what this desktop may use first",
                status_code=422,
                detail="Choose what this desktop may use before turning on its agent.",
            )
        for desktop in self.desktops:
            if desktop.get("id") == desktop_id:
                desktop["kind"] = "agent"
        return {"desktop": {"id": desktop_id, "kind": "agent"}, "views": []}


#: Run states Vela considers ended (a driven run in any other state is active).
TERMINAL_RUN_STATES = ("succeeded", "failed", "cancelled", "interrupted", "outcome_unknown")


def controller_info(**features: bool) -> dict[str, Any]:
    """A /api/controller document advertising exactly the given features."""
    return {
        "mode": "controller",
        "version": "0.3.0",
        "protocol": 5,
        "features": {"controller": True, "driver": True, **features},
    }


def _tool(name: str, description: str, properties: dict[str, Any] | None = None) -> dict[str, Any]:
    """One catalogue entry, in the shape Vela's driven-runs/tools answers."""
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": properties or {},
                "additionalProperties": False,
            },
        },
    }


def default_driven_tools(features: dict[str, Any]) -> list[dict[str, Any]]:
    """The catalogue a Vela with these features would offer (per the controller
    docs): browser/desktop tools with ``driver``, the terminal five with
    ``terminal``, the workspace three + editor with ``workspace``/``editor``."""
    tools: list[dict[str, Any]] = []
    if features.get("driver"):
        tools += [
            _tool("desktop.observe", "Look at a view and get its current controls and text."),
            _tool(
                "desktop.open_site",
                "Open a website in this desktop's browser.",
                {"url": {"type": "string"}},
            ),
            _tool(
                "desktop.click",
                "Click a control from the last observation.",
                {"viewId": {"type": "string"}, "control": {"type": "string"}},
            ),
            _tool(
                "desktop.type",
                "Type text into a control from the last observation.",
                {
                    "viewId": {"type": "string"},
                    "control": {"type": "string"},
                    "text": {"type": "string"},
                },
            ),
            _tool(
                "desktop.key",
                "Press one named key.",
                {"viewId": {"type": "string"}, "key": {"type": "string"}},
            ),
            _tool(
                "desktop.scroll",
                "Scroll a view.",
                {"viewId": {"type": "string"}, "dx": {"type": "number"}, "dy": {"type": "number"}},
            ),
            _tool(
                "desktop.wait",
                "Wait for the page to settle.",
                {"viewId": {"type": "string"}, "milliseconds": {"type": "number"}},
            ),
            _tool(
                "desktop.attach_file",
                "Attach a workspace file to an upload control.",
                {
                    "viewId": {"type": "string"},
                    "control": {"type": "string"},
                    "path": {"type": "string"},
                },
            ),
            _tool(
                "desktop.needs_person",
                "Ask for a person (a sign-in, a challenge).",
                {"reason": {"type": "string"}, "detail": {"type": "string"}},
            ),
        ]
    if features.get("terminal"):
        tools += [
            _tool(
                "terminal_open",
                "Open a terminal: a shell on a pseudo-terminal, rooted at the workspace.",
                {"title": {"type": "string"}, "cwd": {"type": "string"}},
            ),
            _tool(
                "terminal_run",
                "Run one command line in a terminal.",
                {
                    "terminalId": {"type": "string"},
                    "command": {"type": "string"},
                    "timeoutSeconds": {"type": "number"},
                    "waitFor": {"type": "string", "enum": ["exit", "output", "none"]},
                },
            ),
            _tool(
                "terminal_read",
                "Read a terminal's output since a cursor.",
                {"terminalId": {"type": "string"}, "sinceCursor": {"type": "number"}},
            ),
            _tool(
                "terminal_write",
                "Type text or send one named key to a terminal.",
                {
                    "terminalId": {"type": "string"},
                    "text": {"type": "string"},
                    "keys": {"type": "string"},
                },
            ),
            _tool(
                "terminal_close",
                "Close a terminal, killing its shell and everything it started.",
                {"terminalId": {"type": "string"}},
            ),
        ]
    if features.get("workspace"):
        tools += [
            _tool(
                "workspace_list",
                "List the entries at a workspace folder.",
                {"path": {"type": "string"}},
            ),
            _tool(
                "workspace_read",
                "Read a UTF-8 text file from the workspace.",
                {
                    "path": {"type": "string"},
                    "offset": {"type": "number"},
                    "limit": {"type": "number"},
                },
            ),
            _tool(
                "workspace_write",
                "Replace a workspace file atomically.",
                {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                    "expectedRevision": {"type": "string"},
                },
            ),
        ]
    if features.get("editor"):
        tools += [
            _tool(
                "editor_open",
                "Open a plain-text editor window for a workspace file.",
                {"path": {"type": "string"}},
            )
        ]
    return tools


def events_page(
    events: list[dict[str, Any]],
) -> Callable[[int, int], dict[str, Any]]:
    """An ``events_handler`` that pages a fixed event list by cursor."""

    def handler(after: int, limit: int) -> dict[str, Any]:
        page = [event for event in events if event["sequence"] > after][:limit]
        latest = events[-1]["sequence"] if events else after
        return {
            "events": page,
            "cursor": page[-1]["sequence"] if page else after,
            "latest": latest,
            "gap": False,
        }

    return handler


def make_event(
    sequence: int,
    kind: str,
    payload: dict[str, Any],
    *,
    run_id: str | None = None,
    created_at: str = "2026-11-24T12:00:00+00:00",
) -> dict[str, Any]:
    """One Vela event record, in the stream's shape."""
    return {
        "desktopId": "desk-1",
        "sequence": sequence,
        "runId": run_id,
        "kind": kind,
        "payload": payload,
        "createdAt": created_at,
    }


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
    status: str | None = None,
    image: str = "cachibot-vela-computer:0.3.0",
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
            "Status": status if status is not None else state,
        }
    )

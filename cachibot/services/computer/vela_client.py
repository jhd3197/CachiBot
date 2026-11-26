"""Async client for a Vela computer's controller endpoints.

C1 used ``GET /api/health`` and ``GET /api/controller``. C2 adds the live
surface, all under the controller token and all with timeouts:

- desktops: list and create (the bot's desktop is picked, or ensured once),
- viewer read (control lease, task, watchers, activity line),
- per-window frames (metadata + bytes; a text frame for terminals/editors),
- the opt-in full-desktop frame (ETag/If-None-Match → 304 passthrough),
- viewer heartbeats (what keeps Vela's watcher count right),
- take-over (control lease), person input and hand back (release),
- the events stream, polled with a numbered cursor (bounded pages),
- approval answers and task control (the needs-you responses).

C3 adds the driven-run surface the bot's own tools use, plus the one-time
agent setup a fresh desktop needs before Vela accepts driven runs:

- the driven tool catalogue (the same names/schemas Vela's own loop offers),
- create/step/read/finish/cancel for driven runs (steps wait up to
  ``DRIVEN_STEP_TIMEOUT`` — a terminal command can hold one for 30s),
- the task list (to adopt the active run after a controller restart),
- the desktop policy read/save and ``enable-agent``.

The token only ever travels in the ``Authorization`` header; errors carry
status codes and Vela's own detail sentences, never request internals.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

import httpx

DEFAULT_TIMEOUT = 5.0
#: Frame calls wait on a shared capture; input waits on the browser worker
#: (Vela's own command timeout is 20s, so the client waits a little longer).
FRAME_TIMEOUT = 15.0
INPUT_TIMEOUT = 25.0
#: A driven step can wait on a terminal command (Vela caps a terminal_run
#: wait at 30s), so the step call waits well past the default timeout.
DRIVEN_STEP_TIMEOUT = 60.0


class VelaClientError(Exception):
    """The computer did not answer as expected.

    ``status_code`` is Vela's HTTP status when there was an answer (None for
    transport failures); ``detail`` is Vela's plain-language sentence when it
    sent one.
    """

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        detail: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


@dataclass
class VelaFrameResult:
    """One answer from the full-desktop frame route.

    ``status`` is 200 (``body`` holds the PNG) or 304 (not modified — the
    caller's ETag is still current). ``etag`` is the quoted ETag Vela sent;
    ``revision`` is the ``X-Vela-Frame-Revision`` counter when present.
    """

    status: int
    body: bytes | None = None
    etag: str | None = None
    revision: str | None = None


@runtime_checkable
class VelaComputerClient(Protocol):
    """What the ComputerService needs from a Vela client (fakes implement this)."""

    async def health(self) -> bool:
        """True when /api/health answers 200."""
        ...

    async def controller_info(self) -> dict[str, Any]:
        """GET /api/controller with the bearer token; raises on any failure."""
        ...

    async def list_desktops(self) -> dict[str, Any]:
        """GET /api/desktops → {"desktops": [...], "defaultId": ...}."""
        ...

    async def create_desktop(self, name: str) -> dict[str, Any]:
        """POST /api/desktops → the created desktop."""
        ...

    async def views(self, desktop_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/views → {"views": [...], "layout": {...}}."""
        ...

    async def viewer_status(self, desktop_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/viewer → lease, task, watchers, activity."""
        ...

    async def viewer_heartbeat(
        self,
        desktop_id: str,
        viewer_id: str,
        *,
        kind: str | None = None,
        view_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/desktops/{id}/viewer/heartbeat (protocol >= 5)."""
        ...

    async def view_frame(self, desktop_id: str, view_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/views/{viewId}/frame → frame metadata.

        Browser windows answer with capture metadata (digest, width, height,
        capturedAt); terminals and editors answer with a text frame.
        """
        ...

    async def view_frame_bytes(self, desktop_id: str, view_id: str, digest: str) -> bytes:
        """GET /api/desktops/{id}/views/{viewId}/frame/{digest} → PNG bytes."""
        ...

    async def desktop_frame(self, desktop_id: str, etag: str | None = None) -> VelaFrameResult:
        """GET /api/desktops/{id}/frame, passing If-None-Match through.

        Only exists when the container opted in (VELA_CONTROLLER_DESKTOP_FRAME=1)
        and the token is the controller's; anywhere else it answers 404.
        """
        ...

    async def takeover(self, desktop_id: str, view_id: str | None = None) -> dict[str, Any]:
        """POST /api/desktops/{id}/takeover → the lease plus the task state."""
        ...

    async def send_input(
        self, desktop_id: str, lease_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        """POST /api/desktops/{id}/takeover/{leaseId}/input."""
        ...

    async def release(self, desktop_id: str, lease_id: str) -> dict[str, Any]:
        """DELETE /api/desktops/{id}/takeover/{leaseId} (hand back)."""
        ...

    async def events(self, desktop_id: str, *, after: int = 0, limit: int = 200) -> dict[str, Any]:
        """GET /api/desktops/{id}/events?after=&limit= → one bounded page."""
        ...

    async def resolve_approval(
        self, desktop_id: str, request_id: str, decision: str
    ) -> dict[str, Any]:
        """POST /api/desktops/{id}/approvals/{requestId} {"decision": ...}."""
        ...

    async def control_task(self, desktop_id: str, run_id: str, action: str) -> dict[str, Any]:
        """POST /api/desktops/{id}/tasks/{runId}/control {"action": ...}."""
        ...

    # -- C3: driven runs (the bot drives the desktop one tool call at a time) --

    async def list_driven_tools(self, desktop_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/driven-runs/tools → {"tools": [...]}."""
        ...

    async def create_driven_run(
        self,
        desktop_id: str,
        *,
        title: str,
        instruction: str | None = None,
        client_request_id: str | None = None,
    ) -> dict[str, Any]:
        """POST /api/desktops/{id}/driven-runs → the run {id, kind, state}."""
        ...

    async def driven_step(
        self,
        desktop_id: str,
        run_id: str,
        *,
        tool: str,
        arguments: dict[str, Any],
        client_step_id: str,
    ) -> dict[str, Any]:
        """POST .../driven-runs/{runId}/steps → result | refusal | approval |
        needsPerson, plus the run's budget."""
        ...

    async def get_driven_step(
        self, desktop_id: str, run_id: str, client_step_id: str
    ) -> dict[str, Any]:
        """GET .../driven-runs/{runId}/steps/{clientStepId} — the settling read
        after an approval is answered."""
        ...

    async def finish_driven_run(
        self, desktop_id: str, run_id: str, *, outcome: str, summary: str
    ) -> dict[str, Any]:
        """POST .../driven-runs/{runId}/finish {"outcome", "summary"}."""
        ...

    async def cancel_driven_run(self, desktop_id: str, run_id: str) -> dict[str, Any]:
        """POST .../driven-runs/{runId}/cancel (kills the terminals the run
        started; an ordinary finish leaves them)."""
        ...

    async def list_tasks(self, desktop_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/tasks → the run records (used to adopt the
        active driven run after a controller restart)."""
        ...

    async def get_policy(self, desktop_id: str) -> dict[str, Any]:
        """GET /api/desktops/{id}/policy → the desktop's policy document."""
        ...

    async def put_policy(
        self, desktop_id: str, document: dict[str, Any], revision: int
    ) -> dict[str, Any]:
        """PUT /api/desktops/{id}/policy {"revision", ...document}."""
        ...

    async def enable_agent(self, desktop_id: str) -> dict[str, Any]:
        """POST /api/desktops/{id}/enable-agent (needs a non-empty policy)."""
        ...


class VelaClient:
    """httpx-based client pointed at one container's loopback port."""

    def __init__(
        self,
        base_url: str,
        token: str,
        timeout: float = DEFAULT_TIMEOUT,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client = httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport)
        self._token = token

    # ------------------------------------------------------------------
    # Plumbing
    # ------------------------------------------------------------------

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}"}

    @staticmethod
    def _detail(response: httpx.Response) -> str | None:
        """Vela's plain-language sentence, when the body carries one."""
        try:
            data = response.json()
        except ValueError:
            return None
        if isinstance(data, dict):
            detail = data.get("detail")
            if isinstance(detail, str) and detail:
                return detail
        return None

    def _raise_for(self, response: httpx.Response, what: str) -> None:
        if response.status_code == 200:
            return
        detail = self._detail(response)
        if response.status_code in (401, 403):
            raise VelaClientError(
                f"{what}: controller rejected the token",
                status_code=response.status_code,
                detail=detail,
            )
        raise VelaClientError(
            f"{what}: HTTP {response.status_code}" + (f" — {detail}" if detail else ""),
            status_code=response.status_code,
            detail=detail,
        )

    async def _get(self, path: str, *, what: str, timeout: float | None = None) -> dict[str, Any]:
        try:
            response = await self._client.get(
                path, headers=self._headers(), timeout=timeout or DEFAULT_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise VelaClientError(f"{what}: {exc}") from exc
        self._raise_for(response, what)
        try:
            data = response.json()
        except ValueError as exc:
            raise VelaClientError(f"{what}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise VelaClientError(f"{what}: unexpected payload")
        return data

    async def _send(
        self,
        method: str,
        path: str,
        *,
        what: str,
        payload: dict[str, Any] | None = None,
        timeout: float | None = None,
        ok_statuses: tuple[int, ...] = (200,),
    ) -> dict[str, Any]:
        try:
            response = await self._client.request(
                method,
                path,
                headers=self._headers(),
                json=payload,
                timeout=timeout or DEFAULT_TIMEOUT,
            )
        except httpx.HTTPError as exc:
            raise VelaClientError(f"{what}: {exc}") from exc
        if response.status_code not in ok_statuses:
            self._raise_for(response, what)
        if not response.content:
            return {}
        try:
            data = response.json()
        except ValueError as exc:
            raise VelaClientError(f"{what}: invalid JSON") from exc
        if not isinstance(data, dict):
            raise VelaClientError(f"{what}: unexpected payload")
        return data

    # ------------------------------------------------------------------
    # C1: health + discovery
    # ------------------------------------------------------------------

    async def health(self) -> bool:
        """True when /api/health answers 200 (it is open — no token)."""
        try:
            response = await self._client.get("/api/health")
        except httpx.HTTPError:
            return False
        return response.status_code == 200

    async def controller_info(self) -> dict[str, Any]:
        """Return /api/controller's JSON, raising :class:`VelaClientError` otherwise."""
        return await self._get("/api/controller", what="controller check")

    # ------------------------------------------------------------------
    # Desktops
    # ------------------------------------------------------------------

    async def list_desktops(self) -> dict[str, Any]:
        return await self._get("/api/desktops", what="list desktops")

    async def create_desktop(self, name: str) -> dict[str, Any]:
        return await self._send(
            "POST",
            "/api/desktops",
            what="create desktop",
            payload={"name": name},
            ok_statuses=(200, 201),
        )

    async def views(self, desktop_id: str) -> dict[str, Any]:
        return await self._get(f"/api/desktops/{desktop_id}/views", what="list views")

    # ------------------------------------------------------------------
    # Viewer: status, heartbeats, frames
    # ------------------------------------------------------------------

    async def viewer_status(self, desktop_id: str) -> dict[str, Any]:
        return await self._get(f"/api/desktops/{desktop_id}/viewer", what="viewer status")

    async def viewer_heartbeat(
        self,
        desktop_id: str,
        viewer_id: str,
        *,
        kind: str | None = None,
        view_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"viewerId": viewer_id}
        if kind is not None:
            payload["kind"] = kind
        if view_id is not None:
            payload["viewId"] = view_id
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/viewer/heartbeat",
            what="viewer heartbeat",
            payload=payload,
        )

    async def view_frame(self, desktop_id: str, view_id: str) -> dict[str, Any]:
        return await self._get(
            f"/api/desktops/{desktop_id}/views/{view_id}/frame",
            what="view frame",
            timeout=FRAME_TIMEOUT,
        )

    async def view_frame_bytes(self, desktop_id: str, view_id: str, digest: str) -> bytes:
        path = f"/api/desktops/{desktop_id}/views/{view_id}/frame/{digest}"
        try:
            response = await self._client.get(path, headers=self._headers(), timeout=FRAME_TIMEOUT)
        except httpx.HTTPError as exc:
            raise VelaClientError(f"view frame bytes: {exc}") from exc
        self._raise_for(response, "view frame bytes")
        return response.content

    async def desktop_frame(self, desktop_id: str, etag: str | None = None) -> VelaFrameResult:
        headers = self._headers()
        if etag:
            headers["If-None-Match"] = etag
        try:
            response = await self._client.get(
                f"/api/desktops/{desktop_id}/frame", headers=headers, timeout=FRAME_TIMEOUT
            )
        except httpx.HTTPError as exc:
            raise VelaClientError(f"desktop frame: {exc}") from exc
        if response.status_code == 304:
            return VelaFrameResult(status=304, etag=response.headers.get("ETag") or etag)
        self._raise_for(response, "desktop frame")
        return VelaFrameResult(
            status=200,
            body=response.content,
            etag=response.headers.get("ETag"),
            revision=response.headers.get("X-Vela-Frame-Revision"),
        )

    # ------------------------------------------------------------------
    # Take-over, input, hand back
    # ------------------------------------------------------------------

    async def takeover(self, desktop_id: str, view_id: str | None = None) -> dict[str, Any]:
        payload = {"viewId": view_id} if view_id else None
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/takeover",
            what="take over",
            payload=payload,
            timeout=INPUT_TIMEOUT,
            ok_statuses=(200, 201),
        )

    async def send_input(
        self, desktop_id: str, lease_id: str, payload: dict[str, Any]
    ) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/takeover/{lease_id}/input",
            what="send input",
            payload=payload,
            timeout=INPUT_TIMEOUT,
        )

    async def release(self, desktop_id: str, lease_id: str) -> dict[str, Any]:
        return await self._send(
            "DELETE",
            f"/api/desktops/{desktop_id}/takeover/{lease_id}",
            what="hand back",
        )

    # ------------------------------------------------------------------
    # Events + needs-you answers
    # ------------------------------------------------------------------

    async def events(self, desktop_id: str, *, after: int = 0, limit: int = 200) -> dict[str, Any]:
        return await self._get(
            f"/api/desktops/{desktop_id}/events?after={int(after)}&limit={int(limit)}",
            what="desktop events",
        )

    async def resolve_approval(
        self, desktop_id: str, request_id: str, decision: str
    ) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/approvals/{request_id}",
            what="resolve approval",
            payload={"decision": decision},
        )

    async def control_task(self, desktop_id: str, run_id: str, action: str) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/tasks/{run_id}/control",
            what="control task",
            payload={"action": action},
        )

    # ------------------------------------------------------------------
    # C3: driven runs, agent setup
    # ------------------------------------------------------------------

    async def list_driven_tools(self, desktop_id: str) -> dict[str, Any]:
        return await self._get(
            f"/api/desktops/{desktop_id}/driven-runs/tools", what="list driven tools"
        )

    async def create_driven_run(
        self,
        desktop_id: str,
        *,
        title: str,
        instruction: str | None = None,
        client_request_id: str | None = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"title": title}
        if instruction is not None:
            payload["instruction"] = instruction
        if client_request_id is not None:
            payload["clientRequestId"] = client_request_id
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/driven-runs",
            what="create driven run",
            payload=payload,
            ok_statuses=(200, 201),
        )

    async def driven_step(
        self,
        desktop_id: str,
        run_id: str,
        *,
        tool: str,
        arguments: dict[str, Any],
        client_step_id: str,
    ) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/driven-runs/{run_id}/steps",
            what="driven step",
            payload={"tool": tool, "arguments": arguments, "clientStepId": client_step_id},
            timeout=DRIVEN_STEP_TIMEOUT,
        )

    async def get_driven_step(
        self, desktop_id: str, run_id: str, client_step_id: str
    ) -> dict[str, Any]:
        return await self._get(
            f"/api/desktops/{desktop_id}/driven-runs/{run_id}/steps/{client_step_id}",
            what="read driven step",
        )

    async def finish_driven_run(
        self, desktop_id: str, run_id: str, *, outcome: str, summary: str
    ) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/driven-runs/{run_id}/finish",
            what="finish driven run",
            payload={"outcome": outcome, "summary": summary},
        )

    async def cancel_driven_run(self, desktop_id: str, run_id: str) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/driven-runs/{run_id}/cancel",
            what="cancel driven run",
        )

    async def list_tasks(self, desktop_id: str) -> dict[str, Any]:
        return await self._get(f"/api/desktops/{desktop_id}/tasks", what="list tasks")

    async def get_policy(self, desktop_id: str) -> dict[str, Any]:
        return await self._get(f"/api/desktops/{desktop_id}/policy", what="get policy")

    async def put_policy(
        self, desktop_id: str, document: dict[str, Any], revision: int
    ) -> dict[str, Any]:
        return await self._send(
            "PUT",
            f"/api/desktops/{desktop_id}/policy",
            what="save policy",
            payload={"revision": revision, **document},
        )

    async def enable_agent(self, desktop_id: str) -> dict[str, Any]:
        return await self._send(
            "POST",
            f"/api/desktops/{desktop_id}/enable-agent",
            what="enable agent",
            timeout=INPUT_TIMEOUT,
        )

    async def aclose(self) -> None:
        """Close the underlying connection pool."""
        await self._client.aclose()

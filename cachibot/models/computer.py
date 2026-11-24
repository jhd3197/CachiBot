"""Bot computer models: one Vela container per bot, managed by CachiBot.

Domain models shared by the ComputerService, the REST API and the
``computer_update`` WebSocket events. Nothing here talks to Docker or Vela —
the service layer owns all of that.
"""

import math
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class ComputerState(str, Enum):
    """Lifecycle of a bot's computer.

    ``needs_you`` is set while Vela reports a needs-person pause or a waiting
    approval (C2); it clears when the person answers, takes over or hands
    back. ``asleep`` also covers the C5 recovery: a computer whose container
    died or was removed while it should be awake goes to asleep with a real
    lastError — volumes kept, never auto-woken, woken again by the user.
    """

    UNAVAILABLE = "unavailable"
    OFF = "off"
    BUILDING = "building"
    STARTING = "starting"
    AWAKE = "awake"
    ASLEEP = "asleep"
    NEEDS_YOU = "needs_you"


#: States that mean "no container is (or should be) running right now".
INACTIVE_STATES = (
    ComputerState.UNAVAILABLE,
    ComputerState.OFF,
    ComputerState.ASLEEP,
)

#: States that mean "a container should exist and be running right now" — the
#: states the dead-container sweep checks (C5). A computer found in one of
#: these states without a running container is not pretended awake: it goes to
#: asleep with a real lastError and the user wakes it again.
ACTIVE_STATES = (
    ComputerState.AWAKE,
    ComputerState.STARTING,
    ComputerState.NEEDS_YOU,
)


class BuildProgress(BaseModel):
    """Progress of the (global, single-flight) Vela image build.

    ``step``/``total`` come from buildkit's plain progress lines (``#5 [2/7]``);
    either may be ``None`` when the current line carries no step marker.
    """

    status: str = Field(description='"building", "idle" or "failed"')
    step: int | None = Field(default=None, description="Current build step")
    total: int | None = Field(default=None, description="Total build steps, when known")
    line: str = Field(default="", description="Most recent build output line")
    error: str | None = Field(default=None, description="Failure summary when status is failed")


class ComputerRecord(BaseModel):
    """Persisted per-bot computer row (the ``bot_computers`` table)."""

    bot_id: str = Field(description="Bot that owns this computer (primary key)")
    state: ComputerState = Field(default=ComputerState.OFF)
    container_name: str | None = Field(default=None)
    host_port: int | None = Field(
        default=None, description="Published 127.0.0.1 port of the container"
    )
    image_tag: str = Field(description="Pinned Vela computer image tag")
    vela_version: str = Field(description="Pinned Vela release")
    last_active_at: datetime | None = Field(default=None, description="Last wake/touch activity")
    last_error: str | None = Field(default=None, description="Last failure, one line, user-facing")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class DockerProbeResult(BaseModel):
    """Result of probing the local Docker installation."""

    available: bool = Field(description="Docker CLI found and daemon answering")
    reason: str | None = Field(default=None, description="Plain-language reason when unavailable")
    docker_version: str | None = Field(default=None, description="Daemon (or client) version")
    server_os: str | None = Field(default=None)
    arch: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# C2: live preview, watchers, take-over and needs-you
# ---------------------------------------------------------------------------


class ComputerActivity(BaseModel):
    """The desktop's one-line "what it is doing", derived by Vela from the
    step that is actually running (never invented)."""

    text: str
    at: float = Field(description="When the line was set (unix seconds)")
    viewId: str | None = None


class ComputerDriver(BaseModel):
    """Who is driving the computer right now (a person holding the take-over)."""

    userId: str
    name: str
    since: str = Field(description="ISO timestamp of when the take-over began")


class BotComputerStatus(BaseModel):
    """What the UI gets for one bot's computer (camelCase, like other routes).

    Never carries the controller token or the host port — users reach the
    computer only through CachiBot's proxy (C2+). The live fields (activity,
    windows, watchers, driver, needs-you, preview revision) are filled from
    the service's runtime state; they are empty while the computer is not
    awake.
    """

    available: bool
    reason: str | None
    state: str
    build: BuildProgress | None
    velaVersion: str
    lastActiveAt: str | None
    lastError: str | None
    activity: ComputerActivity | None = None
    windowsCount: int = 0
    watchers: int = 0
    driver: ComputerDriver | None = None
    needsYou: str | None = None
    previewRevision: str | None = None


class ComputerWindow(BaseModel):
    """One open window on the bot's desktop (a Vela view), as the UI lists it."""

    id: str
    kind: str = Field(description="Vela view kind: app, web, terminal, editor, ...")
    title: str
    app: str = Field(description="App id, site host, or the kind when there is nothing truer")
    url: str | None = None


class ComputerViewsResponse(BaseModel):
    """GET .../computer/views: the open windows plus the activity line."""

    windows: list[ComputerWindow]
    activity: ComputerActivity | None


class ComputerWatchResponse(BaseModel):
    """POST .../computer/watch: the watcher is counted; heartbeats expire."""

    watching: bool = True
    watchers: int = Field(description="Live watchers CachiBot counts for this bot")
    expiresInSeconds: int = Field(description="How long one heartbeat keeps the watcher live")


#: Bounds for person input, mirroring Vela's own checks so a bad call is a
#: 422 here rather than a worker refusal there.
MAX_POINT_COORDINATE = 10000.0
MAX_SCROLL_PIXELS = 4000.0
MAX_INPUT_KEY_LENGTH = 32
MAX_INPUT_TEXT_LENGTH = 4000


class ComputerInputRequest(BaseModel):
    """One piece of person input, proxied to Vela under the caller's lease.

    Kinds: ``click`` (button left/right/middle — a right click is the
    long-press), ``scroll`` (wheel deltas, as a touch-drag sends them),
    ``type`` (text the person chose; Vela's "text" kind) and ``key`` (one
    named key). ``frameAt`` is when the picture the input was decided from
    was taken; Vela refuses input aimed at a stale frame.
    """

    kind: Literal["click", "scroll", "type", "key"]
    viewId: str | None = Field(default=None, max_length=64)
    point: dict[str, float] | None = None
    button: Literal["left", "right", "middle"] | None = None
    clickCount: int | None = Field(default=None, ge=1, le=2)
    dx: float | None = None
    dy: float | None = None
    key: str | None = Field(default=None, max_length=MAX_INPUT_KEY_LENGTH)
    text: str | None = Field(default=None, max_length=MAX_INPUT_TEXT_LENGTH)
    frameAt: float | None = None

    @model_validator(mode="after")
    def _check_kind_fields(self) -> "ComputerInputRequest":
        if self.kind == "click":
            if self.point is None:
                raise ValueError("a click needs a point")
            x, y = self.point.get("x"), self.point.get("y")
            if x is None or y is None:
                raise ValueError("a click needs a numeric point")
            for value in (x, y):
                if not math.isfinite(value) or not 0 <= value <= MAX_POINT_COORDINATE:
                    raise ValueError("the point is outside the computer's screen")
        elif self.kind == "scroll":
            dx, dy = self.dx or 0.0, self.dy or 0.0
            if not (math.isfinite(dx) and math.isfinite(dy)):
                raise ValueError("a scroll moves by numbers of pixels")
            if abs(dx) > MAX_SCROLL_PIXELS or abs(dy) > MAX_SCROLL_PIXELS:
                raise ValueError(
                    f"a single scroll may move at most {int(MAX_SCROLL_PIXELS)} pixels"
                )
            if dx == 0 and dy == 0:
                raise ValueError("a scroll needs a direction")
        elif self.kind == "type":
            if not self.text:
                raise ValueError("typing needs text")
        elif self.kind == "key":
            if not self.key or not self.key.strip():
                raise ValueError("a key press needs a key name")
        return self

    def to_vela_payload(self, view_id: str) -> dict[str, Any]:
        """Map onto Vela's takeover-input vocabulary ("type" is Vela's "text")."""
        payload: dict[str, Any] = {"viewId": view_id}
        if self.kind == "click":
            payload["kind"] = "click"
            payload["point"] = {"x": self.point["x"], "y": self.point["y"]} if self.point else {}
            if self.button:
                payload["button"] = self.button
            if self.clickCount:
                payload["clickCount"] = self.clickCount
        elif self.kind == "scroll":
            payload["kind"] = "scroll"
            payload["dx"] = self.dx or 0.0
            payload["dy"] = self.dy or 0.0
        elif self.kind == "type":
            payload["kind"] = "text"
            payload["text"] = self.text or ""
        else:  # key
            payload["kind"] = "key"
            payload["key"] = (self.key or "").strip()
        if self.frameAt is not None:
            payload["frameAt"] = self.frameAt
        return payload


class ComputerNeedsYouRespond(BaseModel):
    """POST .../computer/needs-you/respond: answer a needs-you.

    ``takeover`` hands the desktop to the responding person (the run stays
    paused, as Vela's take-over always leaves it). ``skip`` is the documented
    closest refusal: denying the approval when an approval is waiting, and —
    because Vela has no "skip this step" for a needs-person pause — stopping
    the run.
    """

    action: Literal["takeover", "skip"]


# ---------------------------------------------------------------------------
# C4: workspace files on the computer (Files sheet "Open on computer")
# ---------------------------------------------------------------------------


def workspace_relative_path(path: str) -> str:
    """Normalize a UI-supplied path to a workspace-relative one.

    Accepts ``bakery/index.html``, ``/workspace/bakery/index.html`` and
    ``./bakery/index.html``; rejects anything that escapes the workspace
    (``..`` segments or a naked ``..``) with a ValueError the route maps to
    a 422, mirroring the bot-side file tools.
    """
    p = path.strip()
    if p.startswith("/workspace/"):
        p = p[len("/workspace/") :]
    elif p.startswith("/"):
        p = p[1:]
    if p.startswith("./"):
        p = p[2:]
    if p in ("", "."):
        return ""
    if ".." in p.split("/"):
        raise ValueError("the path is outside the workspace")
    return p


class ComputerWorkspaceEntry(BaseModel):
    """One entry (file or folder) in the bot's /workspace, as Vela lists it."""

    name: str
    path: str = Field(description="Workspace-relative path")
    kind: str = Field(description='"file" or "folder"')
    size: int | None = None
    modified: str | None = None


class ComputerWorkspaceResponse(BaseModel):
    """GET .../computer/workspace: the entries at one workspace folder."""

    path: str = Field(description="The folder that was listed (workspace-relative)")
    entries: list[ComputerWorkspaceEntry]


class ComputerEditorOpenRequest(BaseModel):
    """POST .../computer/editor/open: open a workspace file in the computer's
    editor so a person can watch or edit along (design 10 "Open on computer").

    The path is stored normalized to a workspace-relative one; anything that
    escapes the workspace is a 422, mirroring the bot-side file tools.
    """

    path: str = Field(min_length=1, max_length=512)

    @field_validator("path")
    @classmethod
    def _workspace_only(cls, value: str) -> str:
        try:
            return workspace_relative_path(value)
        except ValueError as exc:
            raise ValueError(str(exc)) from exc


class ComputerEditorOpenResponse(BaseModel):
    """The editor window was opened on the computer's desktop."""

    ok: bool = True

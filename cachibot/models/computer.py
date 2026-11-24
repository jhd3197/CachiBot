"""Bot computer models: one Vela container per bot, managed by CachiBot.

Domain models shared by the ComputerService, the REST API and the
``computer_update`` WebSocket events. Nothing here talks to Docker or Vela —
the service layer owns all of that.
"""

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


class ComputerState(str, Enum):
    """Lifecycle of a bot's computer.

    C1 uses everything except ``needs_you`` (that lands with the C2
    needs-you mapping); the value stays in the enum so the schema is final.
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


class BotComputerStatus(BaseModel):
    """What the UI gets for one bot's computer (camelCase, like other routes).

    Never carries the controller token or the host port — users reach the
    computer only through CachiBot's proxy (C2+).
    """

    available: bool
    reason: str | None
    state: str
    build: BuildProgress | None
    velaVersion: str
    lastActiveAt: str | None
    lastError: str | None

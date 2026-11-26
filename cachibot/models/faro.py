"""Faro Agent Bridge models: the local Faro bridge and per-bot connections.

Domain models shared by the FaroService, the REST API and the
``faro_update`` WebSocket events. Nothing here talks to Faro — the service
layer owns all of that. No model ever carries the bridge token or any other
Faro credential.
"""

from pydantic import BaseModel, Field


class FaroBridgeStatus(BaseModel):
    """Result of detecting the local Faro Agent Bridge.

    ``available`` is True only when the discovery file named a live localhost
    endpoint whose ``GET /health`` answered ``name == "faro-agent-bridge"``.
    ``supportsApprovals`` is False on older Faro builds (their ``GET
    /approvals`` answers 404): the tools still work, there is just no
    approvals line.
    """

    available: bool = Field(description="The bridge was found and answered /health")
    reason: str | None = Field(default=None, description="Plain-language reason when unavailable")
    version: str | None = Field(
        default=None, description="The bridge (Faro) version, when available"
    )
    supportsApprovals: bool = Field(
        default=False, description="This build offers GET /approvals (pending approvals)"
    )


class FaroApproval(BaseModel):
    """One approval Faro is waiting for, as ``GET /approvals`` lists it.

    ``summary`` is the command summary Faro shows its own user; it can carry
    sensitive text, so payloads carrying these are only delivered to users
    who can see the bot (same scoping as ``computer_update``).
    """

    requestId: str = Field(description="The id POST /approvals/deny takes")
    sessionId: str | None = Field(default=None)
    sessionName: str | None = Field(default=None)
    kind: str | None = Field(default=None, description="The approval kind (exec, upload, ...)")
    summary: str | None = Field(
        default=None, description="What Faro is asking about (may be sensitive)"
    )


class BotFaroStatus(BaseModel):
    """What the UI gets for one bot's Faro connection (camelCase).

    Never carries the bridge token, the endpoint URL or the pid — users do
    not need them, and the token must not leave the discovery file.
    """

    connected: bool = Field(description="This bot is connected to the Faro bridge")
    available: bool = Field(description="The bridge is currently running")
    reason: str | None = Field(default=None, description="Plain-language reason when unavailable")
    version: str | None = Field(
        default=None, description="The bridge (Faro) version, when available"
    )
    supportsApprovals: bool = Field(
        default=False, description="This build offers GET /approvals (pending approvals)"
    )
    callInFlight: bool = Field(
        default=False, description="One of this bot's faro tools is running right now"
    )
    pendingApprovals: list[FaroApproval] = Field(
        default_factory=list, description="Approvals Faro is waiting on during the current call"
    )


class FaroDenyApprovalResponse(BaseModel):
    """POST .../faro/approvals/{request_id}/deny — the denial reached Faro."""

    denied: bool = Field(description="True when Faro accepted the denial")

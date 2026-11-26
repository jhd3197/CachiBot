"""FaroService: the local Faro Agent Bridge, detected and used per bot.

Faro (a desktop SFTP/SSH/S3 client) can run an Agent Bridge: a localhost
HTTP server with a per-launch bearer token that lends the user's
already-authenticated sessions to a local agent. While the bridge is on,
Faro writes a discovery file ``agent-endpoint.json`` (``{url, port, token,
pid, version}``, mode 0600) into its data dir — ``FARO_DATA_DIR`` when set,
else ``<OS data dir>/com.juandenis.faro``.

This service:

- **Detects** the bridge: reads the discovery file, accepts only
  127.0.0.1/localhost URLs, checks the pid when one is recorded, and
  confirms ``GET /health`` answers ``name == "faro-agent-bridge"``. The
  answer (available/version/whether ``GET /approvals`` exists) is cached
  for a few seconds — the *status*, never the token. When CachiBot runs
  where it cannot see the file (Docker, a remote server) the integration
  is simply unavailable and every surface hides.
- **Never stores the token.** The discovery file is re-read for every
  connection/call; on a 401 or connection error it is re-read once and the
  call retried once. No log line, error, API response or WS payload ever
  carries the token, and tool arguments (which may hold secrets) are never
  logged — only the tool name and its outcome.
- **Per-bot opt-in**: a non-secret boolean per bot (``bot_faro_connections``)
  set by the connect/disconnect routes. The bot's faro tools are registered
  only when the bot is connected *and* the bridge is available.
- **Approvals line**: while one of the bot's faro calls is in flight, the
  pending approvals are polled from ``GET /approvals`` and published over
  ``faro_update`` WS events (scoped to users who can see the bot — approval
  summaries can carry sensitive text). There is deliberately no approve
  path: approving only ever happens in Faro. CachiBot can only deny.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from cachibot.models.faro import FaroApproval, FaroBridgeStatus
from cachibot.services.faro.client import FaroClient, FaroClientError
from cachibot.storage.faro_repository import FaroRepository

logger = logging.getLogger(__name__)

BRIDGE_NAME = "faro-agent-bridge"
DISCOVERY_FILE = "agent-endpoint.json"

#: How long a detection answer is reused before re-checking (the status TTL —
#: the token is never cached at all).
STATUS_TTL_SECONDS = 5.0
#: How long one bot's tools/list answer is cached.
TOOLS_TTL_SECONDS = 60.0
#: How often pending approvals are polled while a call is in flight.
APPROVALS_POLL_SECONDS = 2.0
#: Tool-result text cap, mirroring the computer plugin's bound.
MAX_RESULT_CHARS = 6000
#: Text Faro sends when the human denied or let the approval time out.
DENIED_MARKER = "the user denied or did not respond"

#: A ``faro_update`` broadcast: (payload, bot_id).
BroadcastFn = Callable[[dict[str, Any], str], Awaitable[None]]
#: Builds a client for an endpoint + token (fakes in tests).
ClientFactory = Callable[[str, str], FaroClient]


class FaroRequestError(Exception):
    """A Faro request that cannot be served, with an HTTP status.

    The routes translate this into the response; ``detail`` is a plain
    sentence for the user (never a token, never the endpoint, never tool
    arguments).
    """

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.detail = detail


@dataclass
class FaroEndpoint:
    """One freshly-read discovery file: where the bridge is and today's token."""

    url: str
    token: str
    pid: int | None
    version: str | None


def default_faro_data_dir() -> Path:
    """Faro's data dir: ``FARO_DATA_DIR``, else the OS default."""
    env = os.environ.get("FARO_DATA_DIR")
    if env:
        return Path(env)
    if sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    elif os.name == "nt":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    else:
        base = Path(os.environ.get("XDG_DATA_HOME", str(Path.home() / ".local" / "share")))
    return base / "com.juandenis.faro"


def _is_local_url(url: str) -> bool:
    """Only 127.0.0.1/localhost are ever accepted from the discovery file."""
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = parsed.hostname
    return host in ("127.0.0.1", "localhost")


def _pid_alive(pid: Any) -> bool | None:
    """Whether the recorded pid is alive; None when there is nothing to check."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except OSError:
        # No permission to signal it (or a platform quirk): not proof of death.
        return True
    return True


class FaroService:
    """Detects the local Faro bridge and runs per-bot connections over it."""

    def __init__(
        self,
        *,
        repo: FaroRepository | None = None,
        data_dir: Path | None = None,
        monotonic: Callable[[], float] = time.monotonic,
        broadcast: BroadcastFn | None = None,
        client_factory: ClientFactory | None = None,
        status_ttl: float = STATUS_TTL_SECONDS,
        tools_ttl: float = TOOLS_TTL_SECONDS,
        approvals_poll: float = APPROVALS_POLL_SECONDS,
    ) -> None:
        self._repo = repo or FaroRepository()
        self._data_dir = data_dir
        self._monotonic = monotonic
        self._broadcast_fn = broadcast
        self._client_factory = client_factory or (lambda url, token: FaroClient(url, token))
        self._status_ttl = status_ttl
        self._tools_ttl = tools_ttl
        self._approvals_poll = approvals_poll
        self._started = False
        # Detection cache: the status only, never the token.
        self._status: FaroBridgeStatus | None = None
        self._status_at = 0.0
        # Per-bot connection flags, mirrored from the DB so the synchronous
        # plugin gate (skills registration) can read them. Loaded by start()
        # and kept fresh by every connect/disconnect/status path.
        self._connected: dict[str, bool] = {}
        # Per-bot tools/list cache: bot_id -> (timestamp, tools).
        self._tools_cache: dict[str, tuple[float, list[dict[str, Any]]]] = {}
        # Live call state: bots with a faro call in flight and the approvals
        # Faro is waiting on for them (both die with the call).
        self._in_flight: set[str] = set()
        self._pending: dict[str, list[FaroApproval]] = {}

    # ------------------------------------------------------------------
    # Lifecycle (owned by the app lifespan)
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Warm the per-bot connection mirror and the first detection.

        Idempotent. Nothing loops here: detection is on demand (TTL-cached)
        and approvals are only polled while a bot's call is in flight.
        """
        if self._started:
            return
        self._started = True
        try:
            for bot_id in await self._repo.list_connected():
                self._connected[bot_id] = True
        except Exception:
            logger.debug("could not load Faro connections", exc_info=True)
        try:
            await self.get_status(force=True)
        except Exception:
            logger.debug("initial Faro detection failed", exc_info=True)
        # Warm the tool catalogue for connected bots so the (synchronous)
        # skill registration sees it on the first run after a restart.
        for bot_id in list(self._connected):
            try:
                if self.faro_tools_available(bot_id):
                    await self.list_tools(bot_id)
            except Exception:
                logger.debug("could not warm the Faro tool list for bot %s", bot_id, exc_info=True)

    async def stop(self) -> None:
        """Drop live call bookkeeping (in-flight HTTP calls die with the app)."""
        self._started = False
        self._in_flight.clear()
        self._pending.clear()

    # ------------------------------------------------------------------
    # Detection
    # ------------------------------------------------------------------

    def _discovery_path(self) -> Path:
        base = self._data_dir if self._data_dir is not None else default_faro_data_dir()
        return base / DISCOVERY_FILE

    def _read_endpoint(self) -> FaroEndpoint | None:
        """Read the discovery file now. None (logged at debug) when unusable."""
        path = self._discovery_path()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return None
        except (ValueError, OSError) as exc:
            logger.debug("could not read the Faro discovery file: %s", exc.__class__.__name__)
            return None
        if not isinstance(raw, dict):
            return None
        url = raw.get("url")
        token = raw.get("token")
        if not isinstance(url, str) or not isinstance(token, str) or not token:
            return None
        if not _is_local_url(url):
            logger.debug("the Faro discovery file named a non-localhost URL; ignoring it")
            return None
        pid = raw.get("pid")
        version = raw.get("version")
        return FaroEndpoint(
            url=url.rstrip("/"),
            token=token,
            pid=pid if isinstance(pid, int) and not isinstance(pid, bool) else None,
            version=version if isinstance(version, str) else None,
        )

    async def _detect(self) -> FaroBridgeStatus:
        """The full truth right now: file → pid → /health → /approvals probe."""
        endpoint = self._read_endpoint()
        if endpoint is None:
            env_hint = (
                "the Faro Agent Bridge was not found on this machine — "
                "open Faro and turn on the Agent Bridge"
            )
            return FaroBridgeStatus(available=False, reason=env_hint)
        alive = _pid_alive(endpoint.pid)
        if alive is False:
            return FaroBridgeStatus(
                available=False,
                reason="Faro's Agent Bridge is not running (its process has exited) — "
                "open Faro and turn the Agent Bridge on again",
            )
        client = self._client_for(endpoint)
        try:
            health = await client.health()
        except FaroClientError as exc:
            return FaroBridgeStatus(
                available=False, reason=f"the Faro bridge did not answer ({exc.detail})"
            )
        finally:
            await client.aclose()
        if health.get("name") != BRIDGE_NAME:
            return FaroBridgeStatus(
                available=False,
                reason="the local endpoint answered, but it is not Faro's Agent Bridge",
            )
        version = endpoint.version or health.get("version")
        supports = await self._probe_approvals(endpoint)
        return FaroBridgeStatus(
            available=True,
            reason=None,
            version=version if isinstance(version, str) else None,
            supportsApprovals=supports,
        )

    async def _probe_approvals(self, endpoint: FaroEndpoint) -> bool:
        """Whether this build offers GET /approvals (older builds answer 404)."""
        client = self._client_for(endpoint)
        try:
            await client.list_approvals()
            return True
        except FaroClientError as exc:
            if exc.code != "not_found":
                logger.debug("could not probe the Faro approvals route: %s", exc.code)
            return False
        finally:
            await client.aclose()

    async def get_status(self, *, force: bool = False) -> FaroBridgeStatus:
        """The bridge status, TTL-cached; ``force`` re-detects on the spot.

        Every async surface refreshes this, so the synchronous plugin gate
        (``faro_tools_available``) reads the freshest known answer — the same
        last-known-answer pattern the computer service's probe uses.
        """
        now = self._monotonic()
        if not force and self._status is not None and now - self._status_at < self._status_ttl:
            return self._status
        status = await self._detect()
        self._status = status
        self._status_at = now
        return status

    # ------------------------------------------------------------------
    # Per-bot connection (the persisted opt-in flag)
    # ------------------------------------------------------------------

    def sync_connected(self, bot_id: str) -> bool:
        """The mirrored connection flag (the plugin's synchronous gate reads this)."""
        return self._connected.get(bot_id, False)

    def faro_tools_available(self, bot_id: str) -> bool:
        """Synchronous registration gate: connected AND last-known-available.

        True only when the bot opted in and the most recent detection found
        the bridge. Every async path re-detects; each tool call re-checks
        with a fresh detection before acting.
        """
        if not self._connected.get(bot_id, False):
            return False
        status = self._status
        return status is not None and status.available

    async def refresh_bot(self, bot_id: str) -> bool:
        """Re-read the bot's flag from the DB into the mirror. Returns it."""
        connected = await self._repo.is_connected(bot_id)
        self._connected[bot_id] = connected
        return connected

    async def connect(self, bot_id: str) -> dict[str, Any]:
        """Enable the bot's Faro connection. Requires a running bridge."""
        status = await self.get_status(force=True)
        if not status.available:
            reason = status.reason or "Faro is not running"
            raise FaroRequestError(409, f"Faro is not connected: {reason}")
        await self._repo.set_connected(bot_id, True)
        self._connected[bot_id] = True
        try:
            await self.list_tools(bot_id)
        except FaroRequestError:
            pass  # the connection stands; the catalogue loads on the next use
        await self._broadcast(bot_id)
        return self._bot_payload(bot_id)

    async def disconnect(self, bot_id: str) -> dict[str, Any]:
        """Disable the bot's Faro connection (always allowed)."""
        await self._repo.set_connected(bot_id, False)
        self._connected[bot_id] = False
        self._pending.pop(bot_id, None)
        self._tools_cache.pop(bot_id, None)
        await self._broadcast(bot_id)
        return self._bot_payload(bot_id)

    async def get_bot_status(self, bot_id: str) -> dict[str, Any]:
        """The full per-bot payload (what GET /api/bots/{id}/faro returns)."""
        await self.refresh_bot(bot_id)
        await self.get_status()
        return self._bot_payload(bot_id)

    # ------------------------------------------------------------------
    # Bot tools: the live MCP catalogue and one call
    # ------------------------------------------------------------------

    def cached_tools(self, bot_id: str) -> list[dict[str, Any]] | None:
        """The last tools/list answer for the bot, or None while unknown.

        None until the first successful fetch (connect, start-up warmup or a
        call): the plugin then registers no faro skills, the same way the
        computer plugin waits for its catalogue.
        """
        cached = self._tools_cache.get(bot_id)
        return list(cached[1]) if cached is not None else None

    async def list_tools(self, bot_id: str) -> list[dict[str, Any]]:
        """The bridge's tools/list, cached briefly per bot.

        Raises FaroRequestError when the bot is not connected or the bridge
        is gone.
        """
        await self._require_usable(bot_id)
        cached = self._tools_cache.get(bot_id)
        now = self._monotonic()
        if cached is not None and now - cached[0] < self._tools_ttl:
            return cached[1]

        async def _listing(client: FaroClient) -> list[dict[str, Any]]:
            await client.initialize()
            return await client.list_tools()

        tools: list[dict[str, Any]] = await self._run(_listing)
        self._tools_cache[bot_id] = (now, tools)
        return tools

    async def call_tool(self, bot_id: str, tool: str, arguments: dict[str, Any]) -> str:
        """One faro tool call for the bot: the model-facing text, honest always.

        While the call is in flight the pending approvals are polled and
        published over ``faro_update``; the moment the call ends (answer,
        denial, timeout or a dead bridge) the approvals line is cleared.
        Only the tool name and its outcome are ever logged — never its
        arguments, which may carry secrets.
        """
        try:
            await self._require_usable(bot_id)
        except FaroRequestError as exc:
            return f"Error: {exc.detail}"
        status = await self.get_status()

        stop_polling = asyncio.Event()
        poller: asyncio.Task[None] | None = None
        if status.supportsApprovals:
            poller = asyncio.create_task(self._poll_approvals(bot_id, stop_polling))
        self._in_flight.add(bot_id)
        await self._broadcast(bot_id)
        logger.info("faro tool call started: %s (bot %s)", tool, bot_id)
        try:
            result = await self._run(
                lambda client: _initialize_then_call(client, tool, dict(arguments))
            )
        except FaroRequestError as exc:
            return f"Error: {exc.detail}"
        except FaroClientError as exc:
            outcome = _honest_call_error(exc)
            logger.info("faro tool call ended: %s (bot %s) — %s", tool, bot_id, exc.code)
            return outcome
        except Exception as exc:
            logger.exception("faro tool call failed: %s (bot %s)", tool, bot_id)
            return f"Error: the Faro call failed ({' '.join(str(exc).split())[:200]})"
        finally:
            self._in_flight.discard(bot_id)
            stop_polling.set()
            if poller is not None:
                await asyncio.gather(poller, return_exceptions=True)
            self._set_pending(bot_id, [])
            await self._broadcast(bot_id)
        logger.info("faro tool call ended: %s (bot %s) — ok", tool, bot_id)
        return _format_call_result(result)

    async def _require_usable(self, bot_id: str) -> None:
        if not await self.refresh_bot(bot_id):
            raise FaroRequestError(409, "Faro is not connected for this bot")
        status = await self.get_status()
        if not status.available:
            reason = status.reason or "Faro is not running"
            raise FaroRequestError(503, f"the Faro bridge is not available: {reason}")

    # ------------------------------------------------------------------
    # Approvals: polled, published, deny-only
    # ------------------------------------------------------------------

    async def deny_approval(self, bot_id: str, request_id: str) -> None:
        """Deny one pending approval in Faro (the only answer CachiBot has).

        There is deliberately no approve path anywhere: approving only ever
        happens in Faro's own UI.
        """
        if not await self.refresh_bot(bot_id):
            raise FaroRequestError(409, "Faro is not connected for this bot")
        status = await self.get_status()
        if not status.available:
            raise FaroRequestError(503, "the Faro bridge is not available right now")
        try:
            await self._run(lambda client: client.deny_approval(request_id))
        except FaroClientError as exc:
            raise _map_client_error(exc, "deny the approval") from exc
        # Settle the line promptly instead of waiting for the next poll.
        try:
            approvals = await self._run(lambda client: client.list_approvals())
            self._set_pending(bot_id, [_approval_from_raw(a) for a in approvals])
        except FaroClientError:
            logger.debug("could not refresh approvals after the denial", exc_info=True)
        await self._broadcast(bot_id)

    async def _poll_approvals(self, bot_id: str, stop: asyncio.Event) -> None:
        """Poll GET /approvals while the bot's call runs; publish changes."""
        while not stop.is_set():
            try:
                approvals = await self._run(lambda client: client.list_approvals())
                changed = self._set_pending(bot_id, [_approval_from_raw(a) for a in approvals])
                if changed:
                    await self._broadcast(bot_id)
            except Exception:
                logger.debug("faro approvals poll failed for bot %s", bot_id, exc_info=True)
            try:
                await asyncio.wait_for(stop.wait(), timeout=self._approvals_poll)
            except asyncio.TimeoutError:
                continue

    def _set_pending(self, bot_id: str, approvals: list[FaroApproval]) -> bool:
        """Store the pending approvals; True when the list actually changed."""
        current = self._pending.get(bot_id, [])
        if [a.model_dump() for a in current] == [a.model_dump() for a in approvals]:
            return False
        if approvals:
            self._pending[bot_id] = approvals
        else:
            self._pending.pop(bot_id, None)
        return True

    # ------------------------------------------------------------------
    # Internals: retry-with-reread, payload, broadcast
    # ------------------------------------------------------------------

    def _client_for(self, endpoint: FaroEndpoint) -> FaroClient:
        return self._client_factory(endpoint.url, endpoint.token)

    async def _run(self, operation: Callable[[FaroClient], Awaitable[Any]]) -> Any:
        """Run ``operation(client)`` against a freshly-read endpoint.

        The discovery file (and therefore the token, which changes on every
        Faro launch) is re-read for every call; on a 401 or a connection
        error it is re-read once and the call retried exactly once.
        """
        last: FaroClientError | None = None
        for attempt in range(2):
            endpoint = self._read_endpoint()
            if endpoint is None:
                raise FaroRequestError(503, "the Faro bridge is not available on this machine")
            client = self._client_for(endpoint)
            try:
                return await operation(client)
            except FaroClientError as exc:
                last = exc
                retryable = exc.code in ("unauthorized", "connection_error")
                if attempt == 1 or not retryable:
                    raise
                logger.debug("faro call failed (%s); re-reading the discovery file", exc.code)
            finally:
                await client.aclose()
        # Unreachable: the second failure raised above.
        raise FaroRequestError(503, last.detail if last else "the Faro bridge failed")

    def _bot_payload(self, bot_id: str) -> dict[str, Any]:
        status = self._status or FaroBridgeStatus(available=False, reason=None)
        return {
            "botId": bot_id,
            "connected": self._connected.get(bot_id, False),
            "available": status.available,
            "reason": status.reason,
            "version": status.version,
            "supportsApprovals": status.supportsApprovals,
            "callInFlight": bot_id in self._in_flight,
            "pendingApprovals": [
                approval.model_dump() for approval in self._pending.get(bot_id, [])
            ],
        }

    async def _broadcast(self, bot_id: str) -> None:
        """Send a ``faro_update`` to every socket that can see the bot."""
        payload = self._bot_payload(bot_id)
        try:
            if self._broadcast_fn is not None:
                await self._broadcast_fn(payload, bot_id)
                return
            from cachibot.api.websocket import get_ws_manager
            from cachibot.models.websocket import WSMessage

            await get_ws_manager().broadcast_to_bot(WSMessage.faro_update(payload), bot_id)
        except Exception:
            logger.debug("could not broadcast faro update", exc_info=True)


def _approval_from_raw(raw: dict[str, Any]) -> FaroApproval:
    """One raw /approvals entry → the model. ``command`` is the summary."""
    summary = raw.get("summary")
    if not isinstance(summary, str) or not summary:
        summary = raw.get("command")
    session_name = raw.get("sessionName")
    if not isinstance(session_name, str) or not session_name:
        session_name = raw.get("session")
    return FaroApproval(
        requestId=str(raw.get("requestId") or ""),
        sessionId=str(raw["sessionId"]) if raw.get("sessionId") is not None else None,
        sessionName=session_name if isinstance(session_name, str) else None,
        kind=str(raw["kind"]) if raw.get("kind") is not None else None,
        summary=summary if isinstance(summary, str) else None,
    )


def _format_call_result(result: dict[str, Any]) -> str:
    """The standard MCP tools/call shape → the text the model sees."""
    content = result.get("content")
    texts: list[str] = []
    if isinstance(content, list):
        for item in content:
            if (
                isinstance(item, dict)
                and item.get("type") == "text"
                and isinstance(item.get("text"), str)
            ):
                texts.append(item["text"])
    text = "\n".join(texts).strip() or "(the call returned no text)"
    if len(text) > MAX_RESULT_CHARS:
        text = text[:MAX_RESULT_CHARS] + "\n... (truncated)"
    if result.get("isError"):
        if DENIED_MARKER in text.lower():
            return (
                "The user denied or did not respond to the approval in Faro — "
                "nothing was done. Adjust the plan or ask the user about it."
            )
        return f"Faro refused: {text}"
    return text


def _honest_call_error(exc: FaroClientError) -> str:
    """A failed call → the model-facing truth (no internals, no token)."""
    if exc.code == "denied":
        detail = exc.detail.lower()
        if DENIED_MARKER in detail:
            return (
                "The user denied or did not respond to the approval in Faro — "
                "nothing was done. Adjust the plan or ask the user about it."
            )
        return f"Refused: {exc.detail}"
    if exc.code == "unauthorized":
        return "Error: the Faro bridge rejected the connection — the bridge may have restarted"
    if exc.code == "connection_error":
        return "Error: the Faro bridge went away mid-call — nothing more was done"
    return f"Error: {exc.detail}"


def _map_client_error(exc: FaroClientError, what: str) -> FaroRequestError:
    if exc.code == "not_found":
        return FaroRequestError(404, exc.detail or f"could not {what}")
    if exc.code == "bad_request":
        return FaroRequestError(400, exc.detail or f"could not {what}")
    if exc.code == "connection_error":
        return FaroRequestError(503, f"the Faro bridge is not answering (could not {what})")
    return FaroRequestError(503, exc.detail or f"could not {what}")


async def _initialize_then_call(
    client: FaroClient, tool: str, arguments: dict[str, Any]
) -> dict[str, Any]:
    """One connection: the MCP handshake, then the call itself."""
    await client.initialize()
    return await client.call_tool(tool, arguments)


_faro_service: FaroService | None = None


def get_faro_service() -> FaroService:
    """Process-wide FaroService singleton (constructed lazily)."""
    global _faro_service
    if _faro_service is None:
        _faro_service = FaroService()
    return _faro_service

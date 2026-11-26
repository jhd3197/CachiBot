"""A small MCP Streamable-HTTP client for Faro's Agent Bridge.

CachiBot has no MCP dependency, so this is a focused JSON-RPC 2.0 client
over aiohttp speaking exactly the surface Faro's bridge exposes: POST /mcp
with ``initialize``, ``notifications/initialized``, ``ping``, ``tools/list``
and ``tools/call``. The bridge is stateless and answers plain JSON (no SSE).

Honest errors throughout: transport failures, HTTP statuses and JSON-RPC
error objects each surface as a :class:`FaroClientError` whose ``code`` is
one of ``connection_error``, ``unauthorized``, ``denied``, ``not_found``,
``bad_request`` or ``rpc_error``. The token travels only in the
``Authorization`` header and is never part of any message.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

#: Cap for any single response body read from the bridge. Results are bounded
#: before they ever reach the model or a log line.
MAX_RESPONSE_BYTES = 1_000_000

HEALTH_TIMEOUT = 3.0
DEFAULT_TIMEOUT = 15.0
#: tools/call blocks on the human's approve/deny in Faro (Faro's own timeout
#: is 120 s), so the call waits well past it before giving up.
CALL_TIMEOUT = 140.0
APPROVALS_TIMEOUT = 10.0
DENY_TIMEOUT = 15.0

PROTOCOL_VERSION = "2025-03-26"
CLIENT_NAME = "cachibot"
CLIENT_VERSION = "1"


class FaroClientError(Exception):
    """The bridge did not answer as expected.

    ``code`` is a machine-checkable category (see module docstring);
    ``detail`` is a plain-language sentence safe to show and log (never a
    token, never the tool's arguments).
    """

    def __init__(self, code: str, detail: str, *, status: int | None = None) -> None:
        super().__init__(detail)
        self.code = code
        self.detail = detail
        self.status = status


class FaroClient:
    """One-shot JSON-RPC client for one bridge endpoint + token.

    The service builds a fresh client from the freshly-read discovery file
    for every operation; nothing here caches a token.
    """

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        session: aiohttp.ClientSession | None = None,
        owns_session: bool = False,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._token = token
        self._session = session
        self._owns_session = owns_session or session is None
        self._next_id = 0

    async def aclose(self) -> None:
        if self._owns_session and self._session is not None:
            await self._session.close()
        self._session = None

    # ------------------------------------------------------------------
    # Raw HTTP surface
    # ------------------------------------------------------------------

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        json_body: Any = None,
        timeout: float,
    ) -> tuple[int, bytes]:
        """One HTTP request with a bounded body read; raises FaroClientError."""
        session = await self._ensure_session()

        async def _do() -> tuple[int, bytes]:
            async with session.request(
                method,
                f"{self._base_url}{path}",
                headers=self._headers(),
                json=json_body,
            ) as resp:
                return resp.status, await _read_bounded(resp, MAX_RESPONSE_BYTES)

        try:
            return await asyncio.wait_for(_do(), timeout=timeout)
        except FaroClientError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as exc:
            raise FaroClientError(
                "connection_error",
                f"could not reach the Faro bridge ({exc.__class__.__name__})",
            ) from exc

    # ------------------------------------------------------------------
    # Bridge REST surface
    # ------------------------------------------------------------------

    async def health(self) -> dict[str, Any]:
        """GET /health → {ok, name, version}; raises on any failure."""
        status, body = await self._request("GET", "/health", timeout=HEALTH_TIMEOUT)
        if status != 200:
            raise FaroClientError(
                "rpc_error", f"the bridge answered {status} to the health check", status=status
            )
        data = _decode_json(body)
        if not isinstance(data, dict):
            raise FaroClientError("rpc_error", "the bridge's health answer was not understood")
        return data

    async def list_approvals(self) -> list[dict[str, Any]]:
        """GET /approvals → the pending approvals list.

        Older Faro builds answer 404: that is reported as ``not_found`` so
        the caller can mark approvals as unsupported (the tools still work).
        """
        status, body = await self._request("GET", "/approvals", timeout=APPROVALS_TIMEOUT)
        if status == 404:
            raise FaroClientError("not_found", "this Faro build cannot list approvals", status=404)
        if status != 200:
            raise FaroClientError(
                "rpc_error", f"the bridge answered {status} when asked for approvals", status=status
            )
        data = _decode_json(body)
        approvals = data.get("approvals") if isinstance(data, dict) else None
        if not isinstance(approvals, list):
            raise FaroClientError("rpc_error", "the approvals answer was not understood")
        return [item for item in approvals if isinstance(item, dict)]

    async def deny_approval(self, request_id: str) -> None:
        """POST /approvals/deny {"requestId"}; 404/400 are honest errors."""
        status, body = await self._request(
            "POST",
            "/approvals/deny",
            json_body={"requestId": request_id},
            timeout=DENY_TIMEOUT,
        )
        if status == 200:
            return
        if status == 404:
            raise FaroClientError("not_found", "that approval is no longer pending", status=404)
        if status == 400:
            detail = _detail_from_body(body) or "the bridge refused the denial"
            raise FaroClientError("bad_request", detail, status=400)
        raise FaroClientError(
            "rpc_error", f"the bridge answered {status} to the denial", status=status
        )

    # ------------------------------------------------------------------
    # MCP JSON-RPC surface
    # ------------------------------------------------------------------

    def _rpc(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        self._next_id += 1
        message: dict[str, Any] = {"jsonrpc": "2.0", "id": self._next_id, "method": method}
        if params is not None:
            message["params"] = params
        return message

    async def _post_rpc(
        self,
        method: str,
        params: dict[str, Any] | None = None,
        *,
        timeout: float,
        notification: bool = False,
    ) -> dict[str, Any] | None:
        """POST one JSON-RPC message to /mcp and unpack the answer.

        Notifications (no id) expect 202 with an empty body. Requests expect
        a JSON-RPC response carrying ``result``; an ``error`` object, an
        unexpected HTTP status or a non-JSON body is a plain FaroClientError.
        """
        message = self._rpc(method, params)
        if notification:
            message.pop("id", None)
        status, body = await self._request("POST", "/mcp", json_body=message, timeout=timeout)
        if notification:
            if status in (200, 202):
                return None
            raise FaroClientError(
                "rpc_error", f"the bridge answered {status} to a notification", status=status
            )
        if status == 401:
            raise FaroClientError("unauthorized", "the bridge rejected the token", status=401)
        if status == 403:
            detail = _detail_from_body(body) or "the bridge refused the call"
            raise FaroClientError("denied", detail, status=403)
        if status != 200:
            status_detail = _detail_from_body(body)
            raise FaroClientError(
                "rpc_error",
                status_detail or f"the bridge answered {status}",
                status=status,
            )
        data = _decode_json(body)
        if not isinstance(data, dict):
            raise FaroClientError(
                "rpc_error", "the bridge answered with something that is not JSON-RPC"
            )
        if "error" in data and data["error"] is not None:
            error = data["error"] if isinstance(data["error"], dict) else {}
            detail = str(error.get("message") or "the bridge reported an error")
            raise FaroClientError("rpc_error", detail, status=status)
        result = data.get("result")
        if not isinstance(result, dict):
            raise FaroClientError("rpc_error", "the bridge's answer had no result")
        return result

    async def initialize(self) -> None:
        """The MCP handshake: initialize, then the initialized notification."""
        await self._post_rpc(
            "initialize",
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": CLIENT_NAME, "version": CLIENT_VERSION},
            },
            timeout=DEFAULT_TIMEOUT,
        )
        await self._post_rpc(
            "notifications/initialized", notification=True, timeout=DEFAULT_TIMEOUT
        )

    async def ping(self) -> dict[str, Any] | None:
        return await self._post_rpc("ping", timeout=DEFAULT_TIMEOUT)

    async def list_tools(self) -> list[dict[str, Any]]:
        result = await self._post_rpc("tools/list", timeout=DEFAULT_TIMEOUT)
        tools = (result or {}).get("tools")
        if not isinstance(tools, list):
            raise FaroClientError("rpc_error", "the tools/list answer was not understood")
        return [tool for tool in tools if isinstance(tool, dict)]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """One tools/call; blocks on the human's answer in Faro (long timeout).

        The standard MCP shape comes back: ``content`` (a list whose items
        carry ``text``) and ``isError``. ``arguments`` may hold secrets — it
        is sent to the bridge and never logged or repeated in errors.
        """
        result = await self._post_rpc(
            "tools/call",
            {"name": name, "arguments": arguments},
            timeout=CALL_TIMEOUT,
        )
        if result is None:  # tools/call is a request; a missing result is a bug
            raise FaroClientError("rpc_error", "the bridge's call answer had no result")
        return result


async def _read_bounded(resp: aiohttp.ClientResponse, cap: int) -> bytes:
    """Read at most ``cap`` bytes; a larger body is an honest error."""
    chunks: list[bytes] = []
    total = 0
    async for chunk in resp.content.iter_chunked(8192):
        total += len(chunk)
        if total > cap:
            raise FaroClientError("rpc_error", "the bridge's answer was larger than expected")
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_json(body: bytes) -> Any:
    try:
        return json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError) as exc:
        raise FaroClientError(
            "rpc_error", "the bridge answered with something that is not JSON"
        ) from exc


def _detail_from_body(body: bytes) -> str | None:
    """A plain detail string from an error body, if it carries one.

    Accepts a JSON object with ``detail``/``message``/``error`` (what the
    bridge usually sends) and a plain-text body (what some of its refusals
    send). Never returns internals beyond that one sentence.
    """
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except (ValueError, UnicodeDecodeError):
        text = body.decode("utf-8", errors="replace").strip()
        return " ".join(text.split())[:300] if text else None
    if not isinstance(data, dict):
        return None
    for key in ("detail", "message", "error"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return " ".join(value.split())[:300]
    return None

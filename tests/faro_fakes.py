"""Fake Faro Agent Bridge for tests: a real aiohttp server on 127.0.0.1.

Implements the bridge surface the client speaks — GET /health, POST /mcp
(initialize, notifications/initialized, ping, tools/list, tools/call),
GET /approvals and POST /approvals/deny — with a bearer token, scripted
blocking/denied/erroring calls, and a record of everything it received so
tests can assert exactly what CachiBot sent (and that no approval was ever
posted).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from aiohttp import web

DENIED_TEXT = "the user denied or did not respond to the request"

DEFAULT_TOOLS: list[dict[str, Any]] = [
    {
        "name": "faro_context",
        "description": "Summarize the current Faro context.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_list_sessions",
        "description": "List the configured sessions.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_server_info",
        "description": "Show information about one server.",
        "inputSchema": {
            "type": "object",
            "properties": {"session": {"type": "string"}},
            "required": ["session"],
        },
    },
    {
        "name": "faro_read",
        "description": "Read a remote file.",
        "inputSchema": {
            "type": "object",
            "properties": {"session": {"type": "string"}, "path": {"type": "string"}},
            "required": ["session", "path"],
        },
    },
    {
        "name": "faro_search",
        "description": "Search remote files.",
        "inputSchema": {"type": "object", "properties": {"query": {"type": "string"}}},
    },
    {
        "name": "faro_exec",
        "description": "Run one command on a session.",
        "inputSchema": {
            "type": "object",
            "properties": {"session": {"type": "string"}, "command": {"type": "string"}},
            "required": ["session", "command"],
        },
    },
    {
        "name": "faro_write",
        "description": "Write a remote file.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_upload",
        "description": "Upload a file.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_download",
        "description": "Download a file.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_sync",
        "description": "Sync a folder.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_delete",
        "description": "Delete a remote file.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_rename",
        "description": "Rename a remote file.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_mkdir",
        "description": "Create a remote folder.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_run_command",
        "description": "Run a saved command.",
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "faro_mystery_new_tool",
        "description": "A tool this build added that CachiBot does not know.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


class FakeFaroBridge:
    """A scriptable Faro bridge bound to an ephemeral 127.0.0.1 port."""

    def __init__(
        self,
        *,
        token: str = "faro-test-token-1",
        name: str = "faro-agent-bridge",
        version: str = "1.2.3",
        supports_approvals: bool = True,
        tools: list[dict[str, Any]] | None = None,
    ) -> None:
        self.token = token
        self.name = name
        self.version = version
        self.supports_approvals = supports_approvals
        self.tools = list(DEFAULT_TOOLS if tools is None else tools)
        # Scripting + recording.
        self.mcp_calls: list[dict[str, Any]] = []
        self.deny_calls: list[str] = []
        self.get_paths: list[str] = []
        self.post_paths: list[str] = []
        self.blocked_tools: set[str] = set()
        self.release = asyncio.Event()
        self.error_tools: set[str] = set()
        self.deny_tools: set[str] = set()
        self.huge_tools: set[str] = set()
        self.reject_next_mcp = False
        self.mcp_override: Any = None
        self.pending_approvals: list[dict[str, Any]] = []
        self.block_timeout = 30.0
        self._runner: web.AppRunner | None = None
        self.port: int | None = None

    # ------------------------------------------------------------------
    # Server plumbing
    # ------------------------------------------------------------------

    async def start(self) -> None:
        app = web.Application()
        app.router.add_get("/health", self._health)
        app.router.add_get("/approvals", self._approvals)
        app.router.add_post("/approvals/deny", self._deny)
        app.router.add_post("/mcp", self._mcp)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        site = web.TCPSite(self._runner, "127.0.0.1", 0)
        await site.start()
        self.port = self._runner.addresses[0][1]  # type: ignore[index]

    async def stop(self) -> None:
        if self._runner is not None:
            await self._runner.cleanup()
            self._runner = None

    @property
    def url(self) -> str:
        assert self.port is not None
        return f"http://127.0.0.1:{self.port}"

    def discovery(self, *, token: str | None = None, pid: int | None = None) -> dict[str, Any]:
        """The discovery-file payload pointing at this server."""
        return {
            "url": self.url,
            "port": self.port,
            "token": self.token if token is None else token,
            "pid": pid,
            "version": self.version,
        }

    def authorized(self, request: web.Request) -> bool:
        return request.headers.get("Authorization") == f"Bearer {self.token}"

    # ------------------------------------------------------------------
    # Handlers
    # ------------------------------------------------------------------

    async def _health(self, request: web.Request) -> web.Response:
        self.get_paths.append("/health")
        if not self.authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response({"ok": True, "name": self.name, "version": self.version})

    async def _approvals(self, request: web.Request) -> web.Response:
        self.get_paths.append("/approvals")
        if not self.authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        if not self.supports_approvals:
            return web.json_response({"error": "not found"}, status=404)
        return web.json_response({"approvals": list(self.pending_approvals)})

    async def _deny(self, request: web.Request) -> web.Response:
        self.post_paths.append("/approvals/deny")
        if not self.authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            body = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "bad json"}, status=400)
        request_id = body.get("requestId") if isinstance(body, dict) else None
        if not isinstance(request_id, str) or not request_id:
            return web.json_response({"error": "requestId required"}, status=400)
        for approval in list(self.pending_approvals):
            if approval.get("requestId") == request_id:
                self.pending_approvals.remove(approval)
                self.deny_calls.append(request_id)
                return web.json_response({"denied": True})
        return web.json_response({"error": "no such approval"}, status=404)

    async def _mcp(self, request: web.Request) -> web.Response:
        self.post_paths.append("/mcp")
        if self.mcp_override is not None:
            return await self.mcp_override(request)
        if self.reject_next_mcp:
            # One scripted 401 (Faro relaunched mid-use), then back to normal.
            self.reject_next_mcp = False
            return web.json_response({"error": "unauthorized"}, status=401)
        if not self.authorized(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        try:
            message = await request.json()
        except json.JSONDecodeError:
            return web.json_response({"error": "bad json"}, status=400)
        if not isinstance(message, dict):
            return web.json_response({"error": "bad message"}, status=400)
        method = message.get("method")
        is_notification = "id" not in message
        if not is_notification:
            self.mcp_calls.append({"method": method, "params": message.get("params")})

        if method == "initialize":
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {"tools": {}},
                        "serverInfo": {"name": "faro-agent-bridge", "version": self.version},
                    },
                }
            )
        if is_notification:
            # notifications/initialized and friends: 202 with an empty body.
            return web.Response(status=202)
        if method == "ping":
            return web.json_response({"jsonrpc": "2.0", "id": message.get("id"), "result": {}})
        if method == "tools/list":
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {"tools": list(self.tools)},
                }
            )
        if method == "tools/call":
            params = message.get("params") or {}
            name = params.get("name") if isinstance(params, dict) else None
            if name in self.blocked_tools:
                # Blocks like the real bridge (it waits on the human). The
                # test releases the event; the approvals route keeps working
                # while this handler waits.
                try:
                    await asyncio.wait_for(self.release.wait(), timeout=self.block_timeout)
                except asyncio.TimeoutError:
                    return web.json_response(
                        {
                            "jsonrpc": "2.0",
                            "id": message.get("id"),
                            "result": {
                                "content": [{"type": "text", "text": "the approval timed out"}],
                                "isError": True,
                            },
                        }
                    )
            if name in self.deny_tools:
                return web.Response(text=DENIED_TEXT, status=403)
            if name in self.error_tools:
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": "the remote failed"}],
                            "isError": True,
                        },
                    }
                )
            if name in self.huge_tools:
                # Over the model-facing result cap, well under the transport cap.
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": message.get("id"),
                        "result": {
                            "content": [{"type": "text", "text": "x" * 100_000}],
                            "isError": False,
                        },
                    }
                )
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": message.get("id"),
                    "result": {
                        "content": [{"type": "text", "text": f"ok:{name}"}],
                        "isError": False,
                    },
                }
            )
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": message.get("id"),
                "error": {"code": -32601, "message": f"unknown method {method}"},
            }
        )

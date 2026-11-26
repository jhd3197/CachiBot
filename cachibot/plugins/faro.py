"""
Faro plugin — the bot's own bridge into Faro (SFTP/SSH/S3 sessions).

Faro's Agent Bridge is a localhost server that lends the user's
already-authenticated sessions to a local agent. This plugin exposes the
bridge's live MCP tools to the bot, registered ONLY when the bot has Faro
connected and the bridge is currently available — otherwise the model sees
no faro tools at all.

The tools come from the bridge's own ``tools/list`` (cached briefly per
bot), exposed under their own names (already ``faro_``-prefixed), with the
JSON schema converted into a tukuy Skill the same way the computer
plugin builds catalogue skills. Risk levels are set honestly per tool so
CachiBot's own approval policy applies exactly as for any other tool:

- reads (faro_context, faro_list_sessions, faro_server_info, list, read,
  search, tail, info, glob, read_batch, history, job) are SAFE,
- writes/transfers (write, upload, download, sync, rename, mkdir, ...) are
  MODERATE,
- execution (exec, exec_script, run_command, skill runs) — and anything
  unknown — are DANGEROUS, the strongest level tukuy has.

Every side-effecting call is approved by the user in Faro's own UI; the
MCP call blocks on that answer. There is no approval path here at all —
CachiBot can only watch the pending approvals and offer Deny.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext, skill_of

if TYPE_CHECKING:
    from cachibot.services.faro.service import FaroService

logger = logging.getLogger(__name__)

#: Read-only tools: no side effects, safe to call freely.
_SAFE_TOOLS = frozenset(
    {
        "faro_context",
        "faro_list_sessions",
        "faro_server_info",
        "faro_list",
        "faro_read",
        "faro_search",
        "faro_tail",
        "faro_info",
        "faro_glob",
        "faro_read_batch",
        "faro_history",
        "faro_job",
    }
)

#: File-changing tools that Faro would ask about, but reversible in nature.
_MODERATE_TOOLS = frozenset(
    {
        "faro_write",
        "faro_upload",
        "faro_download",
        "faro_sync",
        "faro_rename",
        "faro_mkdir",
        "faro_move",
        "faro_chmod",
        "faro_touch",
        "faro_symlink",
        "faro_truncate",
    }
)

#: Everything else — faro_exec, faro_exec_script, faro_run_command, skill
#: runs, and any tool this build adds that we do not know — is DANGEROUS,
#: the strongest level tukuy has (arbitrary remote execution, or unknown).


def _risk_for(name: str) -> RiskLevel:
    if name in _SAFE_TOOLS:
        return RiskLevel.SAFE
    if name in _MODERATE_TOOLS:
        return RiskLevel.MODERATE
    return RiskLevel.DANGEROUS


def _icon_for(name: str) -> str:
    core = name.removeprefix("faro_")
    if core in ("exec", "exec_script", "run_command") or "exec" in core or "command" in core:
        return "terminal"
    if core in ("upload", "download", "sync"):
        return "arrow-up-down"
    if "list" in core or core == "glob":
        return "folder-open"
    if "read" in core or core in ("tail", "history", "job", "info", "context"):
        return "file-text"
    if core in ("search",):
        return "search"
    return "server"


class FaroPlugin(CachibotPlugin):
    """Provides the live faro_* tools while the bot's Faro bridge is usable."""

    def __init__(self, ctx: PluginContext, faro_service: FaroService | None = None) -> None:
        super().__init__("faro", ctx)
        self._faro = faro_service

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="faro",
            display_name="Faro",
            icon="server",
            group="Core",
        )

    def _service(self) -> FaroService:
        if self._faro is None:
            # Imported lazily: the service needs aiohttp (server extra),
            # which the slim CLI install does not have.
            from cachibot.services.faro.service import get_faro_service

            self._faro = get_faro_service()
        return self._faro

    def _usable(self) -> bool:
        return self.ctx.bot_id is not None and self._service().faro_tools_available(
            self.ctx.bot_id or ""
        )

    async def _run_tool(self, tool: str, arguments: dict[str, Any]) -> str:
        return await self._service().call_tool(self.ctx.bot_id or "", tool, arguments)

    @property
    def skills(self) -> dict[str, Skill]:
        if not self._usable():
            return {}
        tools = self._service().cached_tools(self.ctx.bot_id or "")
        skills: dict[str, Skill] = {}
        for entry in tools or []:
            name = str(entry.get("name") or "")
            if not name:
                continue
            skills[name] = self._mcp_skill(name, entry)
        return skills

    # ------------------------------------------------------------------
    # One skill per live MCP tool
    # ------------------------------------------------------------------

    def _mcp_skill(self, name: str, entry: dict[str, Any]) -> Skill:
        description = str(
            entry.get("description")
            or f"Run the Faro tool {name} against the user's Faro sessions."
        )
        # Approval note: side-effecting calls are confirmed by the user in
        # Faro before they run — the call waits for that answer.
        if _risk_for(name) is not RiskLevel.SAFE and "approv" not in description.lower():
            description = (
                f"{description.rstrip('.')}. Any change is confirmed by the user in "
                "Faro before it runs."
            )
        schema = entry.get("inputSchema")
        if not isinstance(schema, dict) or "properties" not in schema:
            schema = {"type": "object", "properties": {}}
        risk = _risk_for(name)
        safe = risk is RiskLevel.SAFE

        @skill(
            name=name,
            description=description,
            category="faro",
            tags=["faro"],
            side_effects=not safe,
            idempotent=safe,
            display_name=name.removeprefix("faro_").replace("_", " ").title(),
            icon=_icon_for(name),
            risk_level=risk,
            input_schema=schema,
        )
        async def faro_tool(**kwargs: Any) -> str:
            return await self._run_tool(name, dict(kwargs))

        return skill_of(faro_tool)

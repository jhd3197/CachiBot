"""
Computer plugin — the bot's own computer (a per-bot Vela container).

Tools for the terminal, the workspace files, the editor and the
browser/desktop, all driven one step at a time through the ComputerService
(never raw HTTP to Vela from here). The plugin's tools are registered only
when the computer feature is usable (enabled + Docker available); when it
is off the model does not see them at all.

While the computer is asleep only the documented stable tools are listed
(terminal, workspace, editor — their names do not drift); the
browser/desktop tools appear from Vela's live tool catalogue once the
computer is awake, so their names and schemas never drift from what Vela
actually accepts. Ending work is not a driven step: ``computer_finish``
goes to Vela's finish route.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from tukuy.manifest import PluginManifest
from tukuy.skill import RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext, skill_of
from cachibot.services.computer.service import (
    ComputerService,
    ComputerStepOutcome,
    get_computer_service,
)

logger = logging.getLogger(__name__)

#: Vela tool names whose skills are always hand-registered (documented,
#: stable); catalogue entries for these are skipped so the hand-written
#: snake_case schemas stay the one consistent surface.
_STABLE_VELA_TOOLS = frozenset(
    {
        "terminal_open",
        "terminal_run",
        "terminal_read",
        "terminal_write",
        "terminal_close",
        "workspace_list",
        "workspace_read",
        "workspace_write",
        "editor_open",
    }
)

#: Tool-result text is capped so a huge answer never floods the context.
_MAX_RESULT_CHARS = 6000


def _computer_tool_name(vela_name: str) -> str:
    """The registry name for a Vela tool (dots are not valid in tool names)."""
    return "computer_" + re.sub(r"[^a-zA-Z0-9_-]", "_", vela_name)


def _format_result(result: Any) -> str:
    if result is None:
        return "done"
    if isinstance(result, str):
        return result[:_MAX_RESULT_CHARS]
    text = json.dumps(result, indent=2, default=str)
    if len(text) > _MAX_RESULT_CHARS:
        text = text[:_MAX_RESULT_CHARS] + "\n... (truncated)"
    return text


def format_outcome(outcome: ComputerStepOutcome) -> str:
    """What the model sees for one computer step — honest in every branch."""
    if outcome.status == "result":
        return _format_result(outcome.result)
    if outcome.status == "refusal":
        return f"Refused: {outcome.message}"
    if outcome.status in ("approval", "needs_person"):
        return outcome.message
    return f"Error: {outcome.message}"


class ComputerPlugin(CachibotPlugin):
    """Provides the computer_* tools while the bot's computer is usable."""

    def __init__(self, ctx: PluginContext, computer_service: ComputerService | None = None) -> None:
        super().__init__("computer", ctx)
        self._computer = computer_service

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="computer",
            display_name="Computer",
            icon="monitor",
            group="Core",
        )

    def _service(self) -> ComputerService:
        if self._computer is None:
            self._computer = get_computer_service()
        return self._computer

    def _usable(self) -> bool:
        return self.ctx.bot_id is not None and self._service().computer_tools_available()

    async def _run_step(self, tool: str, arguments: dict[str, Any]) -> str:
        outcome = await self._service().run_tool_step(
            self.ctx.bot_id or "",
            tool=tool,
            arguments=arguments,
            chat_id=self.ctx.chat_id,
            run_title="CachiBot work",
        )
        return format_outcome(outcome)

    @property
    def skills(self) -> dict[str, Skill]:
        if not self._usable():
            return {}
        skills = self._stable_skills()
        catalogue = self._service().cached_tool_catalogue(self.ctx.bot_id or "")
        for entry in catalogue or []:
            fn_def = entry.get("function") or {}
            vela_name = str(fn_def.get("name") or "")
            if not vela_name or vela_name in _STABLE_VELA_TOOLS:
                continue
            name = _computer_tool_name(vela_name)
            if name in skills:
                continue
            skills[name] = self._catalogue_skill(name, vela_name, fn_def)
        return skills

    # ------------------------------------------------------------------
    # Stable tools (terminal, workspace, editor, finish)
    # ------------------------------------------------------------------

    def _stable_skills(self) -> dict[str, Skill]:
        run = self._run_step

        @skill(
            name="computer_terminal_open",
            description=(
                "Open a terminal on the bot's computer: a shell rooted at its "
                "/workspace (PATH includes /workspace/.local, so tools the bot "
                "installed there are found). Returns the terminalId the other "
                "terminal tools take."
            ),
            category="computer",
            tags=["computer", "terminal"],
            side_effects=True,
            display_name="Open Computer Terminal",
            icon="terminal",
            risk_level=RiskLevel.MODERATE,
        )
        async def computer_terminal_open(title: str = "", cwd: str = "") -> str:
            """Open a terminal on the bot's computer.

            Args:
                title: Optional window title.
                cwd: Optional working directory inside /workspace (created if missing).
            """
            arguments: dict[str, Any] = {}
            if title:
                arguments["title"] = title
            if cwd:
                arguments["cwd"] = cwd
            return await run("terminal_open", arguments)

        @skill(
            name="computer_terminal_run",
            description=(
                "Run one command line in a terminal on the bot's computer. "
                "wait_for='exit' (default) waits for the command to finish and "
                "returns its exit code; 'output' returns as soon as anything "
                "new appears; 'none' returns at once and the command keeps "
                "running — use that (or 'output' with a short timeout) for a "
                "dev server. timeout_seconds is capped at 30 by the computer."
            ),
            category="computer",
            tags=["computer", "terminal"],
            side_effects=True,
            display_name="Run in Computer Terminal",
            icon="terminal",
            risk_level=RiskLevel.MODERATE,
        )
        async def computer_terminal_run(
            terminal_id: str,
            command: str,
            timeout_seconds: int = 30,
            wait_for: str = "exit",
        ) -> str:
            """Run one command line in a computer terminal.

            Args:
                terminal_id: From computer_terminal_open.
                command: One command line (at most 4000 bytes).
                timeout_seconds: How long to wait (the computer caps it at 30).
                wait_for: 'exit', 'output' or 'none'.
            """
            return await run(
                "terminal_run",
                {
                    "terminalId": terminal_id,
                    "command": command,
                    "timeoutSeconds": timeout_seconds,
                    "waitFor": wait_for,
                },
            )

        @skill(
            name="computer_terminal_read",
            description=(
                "Read a computer terminal's output since a cursor (0 = "
                "everything kept). Returns the new cursor to ask from next."
            ),
            category="computer",
            tags=["computer", "terminal"],
            idempotent=True,
            display_name="Read Computer Terminal",
            icon="terminal",
            risk_level=RiskLevel.SAFE,
        )
        async def computer_terminal_read(terminal_id: str, since_cursor: int = 0) -> str:
            """Read a computer terminal's output.

            Args:
                terminal_id: From computer_terminal_open.
                since_cursor: The cursor from the previous read (0 for everything).
            """
            return await run(
                "terminal_read", {"terminalId": terminal_id, "sinceCursor": since_cursor}
            )

        @skill(
            name="computer_terminal_write",
            description=(
                "Type text into a computer terminal, or send one named key "
                "(ctrl-c, ctrl-d, ctrl-z, ctrl-l, enter, tab, escape, "
                "backspace, up, down, left, right). ctrl-c stops what is running."
            ),
            category="computer",
            tags=["computer", "terminal"],
            side_effects=True,
            display_name="Write to Computer Terminal",
            icon="terminal",
            risk_level=RiskLevel.MODERATE,
        )
        async def computer_terminal_write(terminal_id: str, text: str = "", keys: str = "") -> str:
            """Type text or send one named key to a computer terminal.

            Args:
                terminal_id: From computer_terminal_open.
                text: Text to type (ignored when keys is given).
                keys: One named key, e.g. 'ctrl-c' or 'enter'.
            """
            arguments: dict[str, Any] = {"terminalId": terminal_id}
            if keys:
                arguments["keys"] = keys
            else:
                arguments["text"] = text
            return await run("terminal_write", arguments)

        @skill(
            name="computer_terminal_close",
            description=(
                "Close a computer terminal, killing its shell and everything "
                "it started. Leave a dev server's terminal open instead."
            ),
            category="computer",
            tags=["computer", "terminal"],
            side_effects=True,
            display_name="Close Computer Terminal",
            icon="terminal",
            risk_level=RiskLevel.MODERATE,
        )
        async def computer_terminal_close(terminal_id: str) -> str:
            """Close a computer terminal.

            Args:
                terminal_id: From computer_terminal_open.
            """
            return await run("terminal_close", {"terminalId": terminal_id})

        @skill(
            name="computer_workspace_list",
            description=(
                "List the entries at a folder in the bot's computer workspace "
                "(/workspace), folders first. Paths are workspace-relative."
            ),
            category="computer",
            tags=["computer", "files"],
            idempotent=True,
            display_name="List Computer Files",
            icon="folder-open",
            risk_level=RiskLevel.SAFE,
        )
        async def computer_workspace_list(path: str = "") -> str:
            """List a folder in the bot's computer workspace.

            Args:
                path: Workspace-relative folder (empty for the root).
            """
            return await run("workspace_list", {"path": path} if path else {})

        @skill(
            name="computer_workspace_read",
            description=(
                "Read a UTF-8 text file from the bot's computer workspace, "
                "with its revision (for conflict-safe writes). Long files come "
                "back cut; use offset/limit to slice."
            ),
            category="computer",
            tags=["computer", "files"],
            idempotent=True,
            display_name="Read Computer File",
            icon="file-text",
            risk_level=RiskLevel.SAFE,
        )
        async def computer_workspace_read(path: str, offset: int = 0, limit: int = 0) -> str:
            """Read a text file from the bot's computer workspace.

            Args:
                path: Workspace-relative file path.
                offset: Character offset to start from.
                limit: Maximum characters to read (0 = the computer's cap).
            """
            arguments: dict[str, Any] = {"path": path}
            if offset:
                arguments["offset"] = offset
            if limit:
                arguments["limit"] = limit
            return await run("workspace_read", arguments)

        @skill(
            name="computer_workspace_write",
            description=(
                "Replace a file in the bot's computer workspace atomically. "
                "Pass expected_revision from a previous read so a concurrent "
                "edit is refused as a conflict instead of overwritten."
            ),
            category="computer",
            tags=["computer", "files"],
            side_effects=True,
            display_name="Write Computer File",
            icon="file-pen",
            risk_level=RiskLevel.MODERATE,
        )
        async def computer_workspace_write(
            path: str, content: str, expected_revision: str = ""
        ) -> str:
            """Write a file in the bot's computer workspace.

            Args:
                path: Workspace-relative file path (its folder must exist).
                content: The file's whole new text.
                expected_revision: The revision from a previous read, when overwriting.
            """
            arguments: dict[str, Any] = {"path": path, "content": content}
            if expected_revision:
                arguments["expectedRevision"] = expected_revision
            return await run("workspace_write", arguments)

        @skill(
            name="computer_editor_open",
            description=(
                "Open a plain-text editor window for a file in the bot's "
                "computer workspace, so a person can watch or edit along."
            ),
            category="computer",
            tags=["computer", "files", "editor"],
            side_effects=True,
            display_name="Open in Computer Editor",
            icon="file-edit",
            risk_level=RiskLevel.SAFE,
        )
        async def computer_editor_open(path: str) -> str:
            """Open a file in the bot's computer editor.

            Args:
                path: Workspace-relative file path.
            """
            return await run("editor_open", {"path": path})

        @skill(
            name="computer_finish",
            description=(
                "End the current work session on the bot's computer when the "
                "work is done. An ordinary finish leaves terminals (and any "
                "dev servers) running. Use this instead of leaving sessions open."
            ),
            category="computer",
            tags=["computer"],
            side_effects=True,
            display_name="Finish Computer Work",
            icon="check",
            risk_level=RiskLevel.SAFE,
        )
        async def computer_finish(summary: str, outcome: str = "succeeded") -> str:
            """Finish the current computer work session.

            Args:
                summary: What happened, in a sentence.
                outcome: 'succeeded' or 'failed'.
            """
            step = await self._service().finish_computer_run(
                self.ctx.bot_id or "",
                outcome=outcome,
                summary=summary,
                chat_id=self.ctx.chat_id,
            )
            return format_outcome(step)

        return {
            "computer_terminal_open": skill_of(computer_terminal_open),
            "computer_terminal_run": skill_of(computer_terminal_run),
            "computer_terminal_read": skill_of(computer_terminal_read),
            "computer_terminal_write": skill_of(computer_terminal_write),
            "computer_terminal_close": skill_of(computer_terminal_close),
            "computer_workspace_list": skill_of(computer_workspace_list),
            "computer_workspace_read": skill_of(computer_workspace_read),
            "computer_workspace_write": skill_of(computer_workspace_write),
            "computer_editor_open": skill_of(computer_editor_open),
            "computer_finish": skill_of(computer_finish),
        }

    # ------------------------------------------------------------------
    # Catalogue tools (browser/desktop), registered from Vela's live list
    # ------------------------------------------------------------------

    def _catalogue_skill(self, name: str, vela_name: str, fn_def: dict[str, Any]) -> Skill:
        description = str(fn_def.get("description") or f"Drive the bot's computer: {vela_name}")
        schema = fn_def.get("parameters")
        if not isinstance(schema, dict) or "properties" not in schema:
            schema = {"type": "object", "properties": {}}

        @skill(
            name=name,
            description=description,
            category="computer",
            tags=["computer", "browser"],
            side_effects=True,
            display_name=vela_name.replace(".", " ").replace("_", " ").title(),
            icon="monitor",
            risk_level=RiskLevel.MODERATE,
            input_schema=schema,
        )
        async def catalogue_tool(**kwargs: Any) -> str:
            return await self._run_step(vela_name, dict(kwargs))

        return skill_of(catalogue_tool)

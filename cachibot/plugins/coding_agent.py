"""
Coding agent plugin — spawn external AI coding CLIs as autonomous tools.

Supports Claude Code, OpenAI Codex, and Gemini CLI. Each runs as a subprocess
in the bot's workspace directory with configurable timeout and turn limits.
"""

import asyncio
import logging
import platform
import shutil
import subprocess
import threading
from collections.abc import Callable
from enum import Enum
from pathlib import Path

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)


class CodingCLI(str, Enum):
    """Supported coding agent CLIs."""

    CLAUDE = "claude"
    CODEX = "codex"
    GEMINI = "gemini"


# CLI invocation specs: binary name and argument builder
_CLI_SPECS: dict[CodingCLI, dict[str, str | Callable[..., list[str]]]] = {
    CodingCLI.CLAUDE: {
        "binary": "claude",
        "build_args": lambda task, max_turns: [
            "--print",
            task,
            "--output-format",
            "text",
            "--max-turns",
            str(max_turns),
            "--allowedTools",
            "Edit,Write,Read,Bash,Glob,Grep",
        ],
    },
    CodingCLI.CODEX: {
        "binary": "codex",
        "build_args": lambda task, max_turns: [
            "--approval-mode",
            "full-auto",
            "--quiet",
            task,
        ],
    },
    CodingCLI.GEMINI: {
        "binary": "gemini",
        "build_args": lambda task, max_turns: [
            "-y",
            task,
        ],
    },
}


def _resolve_binary(name: str) -> str | None:
    """Find a CLI binary, preferring .cmd/.ps1/.bat on Windows.

    On Windows, npm-installed CLIs produce an extensionless stub file alongside
    the real ``.cmd`` wrapper.  ``shutil.which()`` may find the stub first, but
    it isn't a valid Win32 executable.  We therefore check ``.cmd`` *before*
    falling back to the bare name so the correct wrapper is always used.
    """
    if platform.system() == "Windows":
        for ext in (".cmd", ".ps1", ".bat"):
            path = shutil.which(name + ext)
            if path:
                return path
    path = shutil.which(name)
    if path:
        return path
    return None


async def _run_coding_cli(
    cli: CodingCLI,
    task: str,
    cwd: str | Path,
    *,
    timeout: int = 600,
    max_turns: int = 25,
    max_output: int = 50000,
    binary_override: str = "",
    on_output: Callable[[str], None] | None = None,
) -> str:
    """Spawn a coding CLI subprocess and return its output.

    Args:
        cli: Which coding agent to use.
        task: The coding task description.
        cwd: Working directory (bot workspace).
        timeout: Max seconds before killing the process.
        max_turns: Max agent turns (passed to CLIs that support it).
        max_output: Truncate output beyond this many characters.
        binary_override: Custom binary path (skips PATH lookup if set).
        on_output: Optional callback invoked with each line of stdout for live streaming.

    Returns:
        The agent's stdout output, or an error message.
    """
    spec = _CLI_SPECS[cli]
    binary_name = binary_override or str(spec["binary"])

    binary = binary_override or _resolve_binary(binary_name)
    if not binary:
        return f"Error: '{binary_name}' is not installed or not on PATH."

    # Ensure cwd is a resolved string path and exists
    cwd_str = str(Path(cwd).resolve())
    if not Path(cwd_str).is_dir():
        return f"Error: Working directory does not exist: {cwd_str}"

    build_args: Callable[..., list[str]] = spec["build_args"]  # type: ignore[assignment]
    args = build_args(task, max_turns)

    logger.info("Spawning %s: %s %s (cwd=%s)", cli.value, binary, args, cwd_str)

    # Use subprocess.Popen in a thread — asyncio.create_subprocess_exec raises
    # NotImplementedError on Windows with SelectorEventLoop (uvicorn default).
    # Stream stdout line-by-line so callers can relay live output.
    def _run_sync() -> tuple[int, str]:
        try:
            proc = subprocess.Popen(
                [binary, *args],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=cwd_str,
            )
        except OSError as exc:
            logger.error("Failed to spawn %s: %s", binary, exc, exc_info=True)
            return -1, f"Error: Failed to start '{binary}': {exc}"

        # Watchdog thread to enforce the timeout.
        # cancelled is set when the process finishes normally to prevent the
        # watchdog from killing it. killed is set by the watchdog to signal
        # that it timed out.
        cancelled = threading.Event()
        killed = threading.Event()

        def _watchdog() -> None:
            if not cancelled.wait(timeout):
                killed.set()
                try:
                    proc.kill()
                except OSError:
                    pass

        timer = threading.Thread(target=_watchdog, daemon=True)
        timer.start()

        chunks: list[str] = []
        try:
            assert proc.stdout is not None  # noqa: S101
            for raw_line in proc.stdout:
                text = raw_line.decode(errors="replace")
                chunks.append(text)
                if on_output:
                    on_output(text)
        except Exception:
            pass

        proc.wait()
        cancelled.set()  # Stop watchdog

        if killed.is_set():
            return -1, f"Error: {binary} timed out after {timeout}s."

        return proc.returncode or 0, "".join(chunks).strip()

    try:
        returncode, output = await asyncio.to_thread(_run_sync)
    except Exception as exc:
        logger.error("Unexpected error running %s: %s", binary, exc, exc_info=True)
        return f"Error: Could not run '{binary}' ({type(exc).__name__}): {exc}"

    if len(output) > max_output:
        output = output[:max_output] + f"\n\n... (truncated at {max_output} chars)"

    if returncode == -1:
        # Error message already formatted by _run_sync
        return output

    if returncode != 0:
        logger.warning("%s exited with code %d", binary, returncode)
        return f"{binary} exited with code {returncode}:\n{output}"

    return output or f"{binary} completed successfully (no output)."


class CodingAgentPlugin(CachibotPlugin):
    """Provides the coding_agent tool for spawning external AI coding CLIs."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("coding_agent", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="coding_agent",
            display_name="Coding Agents",
            icon="terminal-square",
            group="Developer Tools",
            requires=PluginRequirements(filesystem=True, network=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(  # type: ignore[untyped-decorator]
            name="coding_agent",
            description=(
                "Spawn an external AI coding agent to autonomously complete a "
                "development task. The agent runs in the workspace directory and "
                "can read, write, and execute code. "
                "Supported agents: claude (Claude Code), codex (OpenAI Codex), "
                "gemini (Gemini CLI). Defaults to claude."
            ),
            category="developer",
            tags=["claude-code", "codex", "gemini", "coding", "agent"],
            side_effects=True,
            requires_filesystem=True,
            display_name="Coding Agent",
            icon="terminal-square",
            risk_level=RiskLevel.DANGEROUS,
            config_params=[
                ConfigParam(
                    name="defaultAgent",
                    display_name="Default Agent",
                    type="select",
                    default="claude",
                    options=["claude", "codex", "gemini"],
                ),
                ConfigParam(
                    name="timeoutSeconds",
                    display_name="Timeout",
                    type="number",
                    default=600,
                    min=10,
                    max=86400,
                    step=10,
                    unit="seconds",
                ),
                ConfigParam(
                    name="maxTurns",
                    display_name="Max Turns",
                    type="number",
                    default=25,
                    min=5,
                    max=100,
                    step=5,
                ),
                ConfigParam(
                    name="maxOutputLength",
                    display_name="Max Output Length",
                    type="number",
                    default=50000,
                    min=5000,
                    max=200000,
                    step=5000,
                    unit="chars",
                ),
            ],
        )
        async def coding_agent(task: str, agent: str = "") -> str:
            """Spawn a coding agent to autonomously complete a development task.

            Args:
                task: Description of the coding task to complete.
                agent: Which coding agent to use — "claude", "codex", or "gemini".
                       Defaults to the configured default agent.

            Returns:
                The agent's output after completing (or failing) the task.
            """
            cfg = ctx.tool_configs.get("coding_agent", {})
            ca_config = ctx.config.coding_agents

            # Resolve agent: explicit arg > tool config > global config
            resolved_agent = agent or cfg.get("defaultAgent", "") or ca_config.default_agent

            try:
                cli = CodingCLI(resolved_agent)
            except ValueError:
                available = ", ".join(c.value for c in CodingCLI)
                return f"Unknown agent '{resolved_agent}'. Available: {available}"

            timeout = cfg.get("timeoutSeconds", ca_config.timeout_seconds)
            max_turns = cfg.get("maxTurns", ca_config.max_turns)
            max_output = cfg.get("maxOutputLength", ca_config.max_output_length)

            # Resolve binary path: config path > auto-detect
            path_map = {
                CodingCLI.CLAUDE: ca_config.claude_path,
                CodingCLI.CODEX: ca_config.codex_path,
                CodingCLI.GEMINI: ca_config.gemini_path,
            }
            binary_override = path_map.get(cli, "")

            # Build a sync on_output callback that schedules async WS sends
            _on_output: Callable[[str], None] | None = None
            if ctx.on_tool_output:
                # Get current tool_call_id from Prompture's ContextVar
                from prompture.integrations.tukuy_bridge import current_tool_call_id

                tool_id = current_tool_call_id.get()
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None

                if loop and tool_id:
                    _ctx_on_tool_output = ctx.on_tool_output

                    def _on_output(text: str) -> None:
                        loop.call_soon_threadsafe(  # type: ignore[union-attr]
                            asyncio.ensure_future,
                            _ctx_on_tool_output(tool_id, text),  # type: ignore[arg-type]
                        )

            try:
                return await _run_coding_cli(
                    cli=cli,
                    task=task,
                    cwd=ctx.config.workspace_path,
                    timeout=timeout,
                    max_turns=max_turns,
                    max_output=max_output,
                    binary_override=binary_override,
                    on_output=_on_output,
                )
            except Exception as exc:
                logger.error(
                    "coding_agent(%s) failed: %s", cli.value, exc, exc_info=True
                )
                return f"Error running {cli.value} ({type(exc).__name__}): {exc}"

        return {"coding_agent": coding_agent.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

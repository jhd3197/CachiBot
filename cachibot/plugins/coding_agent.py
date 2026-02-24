"""
Coding agent plugin — spawn external AI coding CLIs as autonomous tools.

Supports Claude Code, OpenAI Codex, and Gemini CLI. Each runs as a subprocess
in the bot's workspace directory with configurable timeout and turn limits.
"""

import asyncio
import shutil
from collections.abc import Callable
from enum import Enum

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


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


async def _run_coding_cli(
    cli: CodingCLI,
    task: str,
    cwd: str,
    *,
    timeout: int = 300,
    max_turns: int = 25,
    max_output: int = 50000,
    binary_override: str = "",
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

    Returns:
        The agent's stdout output, or an error message.
    """
    spec = _CLI_SPECS[cli]
    binary = binary_override or str(spec["binary"])

    if not shutil.which(binary):
        return f"Error: '{binary}' is not installed or not on PATH."

    build_args: Callable[..., list[str]] = spec["build_args"]  # type: ignore[assignment]
    args = build_args(task, max_turns)

    proc = await asyncio.create_subprocess_exec(
        binary,
        *args,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
        cwd=cwd,
    )

    try:
        stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        return f"Error: {binary} timed out after {timeout}s."

    output = stdout.decode(errors="replace").strip() if stdout else ""

    if len(output) > max_output:
        output = output[:max_output] + f"\n\n... (truncated at {max_output} chars)"

    if proc.returncode != 0:
        return f"{binary} exited with code {proc.returncode}:\n{output}"

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
                    default=300,
                    min=30,
                    max=600,
                    step=30,
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

            return await _run_coding_cli(
                cli=cli,
                task=task,
                cwd=ctx.config.workspace_path,
                timeout=timeout,
                max_turns=max_turns,
                max_output=max_output,
                binary_override=binary_override,
            )

        return {"coding_agent": coding_agent.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

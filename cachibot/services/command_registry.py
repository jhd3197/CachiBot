"""
Unified Command Registry — discovery and routing for /prefix:command patterns.

Discovers user-level skills, per-bot instructions, and CLI passthrough stubs.
Parses /prefix:command args patterns and resolves them to CommandDescriptors.
"""

import logging
import re
import shutil
import time
from dataclasses import dataclass, field

from cachibot.services.skills import get_skills_service

logger = logging.getLogger(__name__)

# Regex: /prefix:name optional-args
_COMMAND_PATTERN = re.compile(r"^/(\w+):(\S+)\s*(.*)$", re.DOTALL)

# Cache TTL in seconds
_CACHE_TTL = 60


@dataclass
class CommandDescriptor:
    """Describes a resolved command and how to execute it."""

    prefix: str  # "skill", "bot", "gsd", "codex", "gemini"
    name: str  # "my-skill", "progress", etc.
    display_name: str
    description: str
    source: str  # "user_skill", "bot_instruction", "cli"
    execution_mode: str  # "native" or "passthrough"
    instructions: str | None = None  # SKILL.md content (native mode)
    cli_binary: str | None = None  # "claude", "codex", "gemini" (passthrough)
    tags: list[str] = field(default_factory=list)
    icon: str | None = None


@dataclass
class ParsedCommand:
    """Result of parsing a /prefix:command args message."""

    prefix: str
    name: str
    args: str


# GSD subcommands that map to /gsd:X via Claude Code CLI
_GSD_COMMANDS: list[dict[str, str]] = [
    {"name": "progress", "description": "Check project progress and next action"},
    {"name": "plan-phase", "description": "Create detailed phase plan"},
    {"name": "execute-phase", "description": "Execute all plans in a phase"},
    {"name": "new-project", "description": "Initialize a new project"},
    {"name": "new-milestone", "description": "Start a new milestone cycle"},
    {"name": "debug", "description": "Systematic debugging session"},
    {"name": "help", "description": "Show GSD commands and usage"},
    {"name": "quick", "description": "Execute a quick task with GSD guarantees"},
    {"name": "verify-work", "description": "Validate built features through UAT"},
    {"name": "resume-work", "description": "Resume work from previous session"},
    {"name": "settings", "description": "Configure GSD workflow toggles"},
]


class CommandRegistry:
    """Discovers and routes /prefix:command patterns."""

    def __init__(self) -> None:
        self._cache: list[CommandDescriptor] | None = None
        self._cache_ts: float = 0
        self._bot_cache: dict[str, list[CommandDescriptor]] = {}
        self._bot_cache_ts: dict[str, float] = {}

    def parse_command(self, message: str) -> ParsedCommand | None:
        """Parse a /prefix:command args message.

        Returns None if the message doesn't match the pattern.
        """
        m = _COMMAND_PATTERN.match(message.strip())
        if not m:
            return None
        return ParsedCommand(
            prefix=m.group(1).lower(),
            name=m.group(2).lower(),
            args=m.group(3).strip(),
        )

    async def refresh(self) -> None:
        """Force refresh the command cache."""
        self._cache = None
        self._cache_ts = 0
        self._bot_cache.clear()
        self._bot_cache_ts.clear()

    async def _get_global_commands(self) -> list[CommandDescriptor]:
        """Get cached global commands (skills + CLI stubs)."""
        now = time.monotonic()
        if self._cache is not None and (now - self._cache_ts) < _CACHE_TTL:
            return self._cache

        commands: list[CommandDescriptor] = []

        # 1. Discover user-level skills via SkillsService
        try:
            service = get_skills_service()
            all_skills = await service.scan_claude_skills()
            for skill in all_skills:
                # Filter for user-level skills only (from ~/.claude/skills/)
                filepath = skill.filepath or ""
                from pathlib import Path

                home_skills = str(Path.home() / ".claude" / "skills")
                if not filepath.startswith(home_skills):
                    continue

                # Derive a slug from the skill name for the command name
                slug = re.sub(r"[^a-z0-9]+", "-", skill.name.lower()).strip("-")

                commands.append(
                    CommandDescriptor(
                        prefix="skill",
                        name=slug,
                        display_name=skill.name,
                        description=skill.description or f"User skill: {skill.name}",
                        source="user_skill",
                        execution_mode="native",
                        instructions=skill.instructions,
                        tags=skill.tags,
                        icon="sparkles",
                    )
                )
        except Exception as e:
            logger.warning("Failed to discover user skills: %s", e)

        # 2. Register CLI passthrough stubs
        # GSD commands via Claude Code CLI
        if shutil.which("claude"):
            for gsd_cmd in _GSD_COMMANDS:
                commands.append(
                    CommandDescriptor(
                        prefix="gsd",
                        name=gsd_cmd["name"],
                        display_name=f"GSD: {gsd_cmd['name']}",
                        description=gsd_cmd["description"],
                        source="cli",
                        execution_mode="passthrough",
                        cli_binary="claude",
                        icon="terminal",
                    )
                )

        # Codex CLI
        if shutil.which("codex"):
            commands.append(
                CommandDescriptor(
                    prefix="codex",
                    name="run",
                    display_name="Codex",
                    description="Run a task via OpenAI Codex CLI",
                    source="cli",
                    execution_mode="passthrough",
                    cli_binary="codex",
                    icon="cpu",
                )
            )

        # Gemini CLI
        if shutil.which("gemini"):
            commands.append(
                CommandDescriptor(
                    prefix="gemini",
                    name="run",
                    display_name="Gemini",
                    description="Run a task via Gemini CLI",
                    source="cli",
                    execution_mode="passthrough",
                    cli_binary="gemini",
                    icon="cpu",
                )
            )

        self._cache = commands
        self._cache_ts = now
        return commands

    async def _get_bot_commands(self, bot_id: str) -> list[CommandDescriptor]:
        """Get per-bot instruction commands."""
        now = time.monotonic()
        if bot_id in self._bot_cache and (now - self._bot_cache_ts.get(bot_id, 0)) < _CACHE_TTL:
            return self._bot_cache[bot_id]

        commands: list[CommandDescriptor] = []
        try:
            from cachibot.storage.instruction_repository import InstructionRepository

            repo = InstructionRepository()
            instructions = await repo.get_by_bot(bot_id)
            for instr in instructions:
                if not instr.is_active:
                    continue
                slug = re.sub(r"[^a-z0-9]+", "-", instr.name.lower()).strip("-")
                commands.append(
                    CommandDescriptor(
                        prefix="bot",
                        name=slug,
                        display_name=instr.name,
                        description=instr.description or f"Custom instruction: {instr.name}",
                        source="bot_instruction",
                        execution_mode="native",
                        instructions=instr.prompt,
                        icon="book-open",
                        tags=instr.tags or [],
                    )
                )
        except Exception as e:
            logger.warning("Failed to discover bot instructions for %s: %s", bot_id, e)

        self._bot_cache[bot_id] = commands
        self._bot_cache_ts[bot_id] = now
        return commands

    async def resolve(
        self, prefix: str, name: str, bot_id: str | None = None
    ) -> CommandDescriptor | None:
        """Resolve a prefix:name pair to a CommandDescriptor."""
        # Search global commands first
        global_cmds = await self._get_global_commands()
        for cmd in global_cmds:
            if cmd.prefix == prefix and cmd.name == name:
                return cmd

        # For passthrough prefixes, allow arbitrary subcommand names
        if prefix == "gsd":
            if shutil.which("claude"):
                return CommandDescriptor(
                    prefix="gsd",
                    name=name,
                    display_name=f"GSD: {name}",
                    description=f"Run /gsd:{name} via Claude Code",
                    source="cli",
                    execution_mode="passthrough",
                    cli_binary="claude",
                    icon="terminal",
                )
        elif prefix in ("codex", "gemini"):
            binary = prefix if prefix != "codex" else "codex"
            if shutil.which(binary):
                return CommandDescriptor(
                    prefix=prefix,
                    name=name,
                    display_name=f"{prefix.title()}: {name}",
                    description=f"Run task via {prefix.title()} CLI",
                    source="cli",
                    execution_mode="passthrough",
                    cli_binary=binary,
                    icon="cpu",
                )

        # Search bot-specific commands
        if bot_id and prefix == "bot":
            bot_cmds = await self._get_bot_commands(bot_id)
            for cmd in bot_cmds:
                if cmd.name == name:
                    return cmd

        return None

    async def get_all(self, bot_id: str | None = None) -> list[CommandDescriptor]:
        """Get all available commands for autocomplete."""
        commands = list(await self._get_global_commands())
        if bot_id:
            commands.extend(await self._get_bot_commands(bot_id))
        return commands


# Singleton
_registry: CommandRegistry | None = None


def get_command_registry() -> CommandRegistry:
    """Get the shared CommandRegistry instance."""
    global _registry
    if _registry is None:
        _registry = CommandRegistry()
    return _registry

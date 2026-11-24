"""
File operations plugin — workspace-scoped file_read, file_write, file_list, file_edit, file_info.

When the bot's computer is usable, the tools operate on the bot's
/workspace volume in its Vela container through the workspace_* driven
tools (the Docker volume is not the host workspace_path). When the computer
feature is off, the tools keep their host workspace_path behavior.
"""

from pathlib import Path
from typing import Any

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext, skill_of
from cachibot.services.computer.service import (
    ComputerService,
    ComputerStepOutcome,
    get_computer_service,
)

_ENCODING_OPTIONS = ["utf-8", "ascii", "latin-1", "utf-16"]


class FileOpsPlugin(CachibotPlugin):
    """Provides workspace-restricted file operation tools."""

    def __init__(self, ctx: PluginContext, computer_service: ComputerService | None = None) -> None:
        super().__init__("file_ops", ctx)
        self._computer = computer_service
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="file_ops",
            display_name="File Operations",
            icon="folder",
            group="Core",
            requires=PluginRequirements(filesystem=True),
        )

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the workspace."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.ctx.config.workspace_path / p

    # ------------------------------------------------------------------
    # Computer routing (C3): the bot's /workspace volume via driven tools
    # ------------------------------------------------------------------

    def _service(self) -> ComputerService:
        if self._computer is None:
            self._computer = get_computer_service()
        return self._computer

    def _use_computer(self) -> bool:
        """Whether this bot's file tools operate on its computer's /workspace."""
        return self.ctx.bot_id is not None and self._service().computer_tools_available()

    @staticmethod
    def _computer_path(path: str) -> str | None:
        """A workspace-relative path for the computer, or None when it escapes."""
        p = path.strip()
        if p.startswith("/workspace/"):
            p = p[len("/workspace/") :]
        elif p.startswith("/"):
            p = p[1:]
        if p.startswith("./"):
            p = p[2:]
        if p in ("", "."):
            return ""
        if ".." in p.split("/"):
            return None
        return p

    async def _computer_step(self, tool: str, arguments: dict[str, Any]) -> ComputerStepOutcome:
        return await self._service().run_tool_step(
            self.ctx.bot_id or "",
            tool=tool,
            arguments=arguments,
            chat_id=self.ctx.chat_id,
        )

    async def _computer_read(self, path: str) -> str:
        rel = self._computer_path(path)
        if rel is None:
            return f"Error: Path '{path}' is outside the workspace"
        outcome = await self._computer_step("workspace_read", {"path": rel})
        if outcome.status != "result":
            return f"Error: {outcome.message}"
        result = outcome.result or {}
        content = str(result.get("content") or "")
        if result.get("truncated"):
            content += (
                "\n\n... (truncated by the computer; "
                "read in slices with computer_workspace_read offset/limit)"
            )
        return content

    async def _computer_write(self, path: str, content: str) -> str:
        rel = self._computer_path(path)
        if rel is None:
            return f"Error: Path '{path}' is outside the workspace"
        cfg = self.ctx.tool_configs.get("file_write", {})
        allowed_ext: list[str] = cfg.get("allowedExtensions", [])
        suffix = Path(rel).suffix
        if allowed_ext and suffix not in allowed_ext:
            return f"Error: Extension '{suffix}' is not allowed. Allowed: {', '.join(allowed_ext)}"
        outcome = await self._computer_step("workspace_write", {"path": rel, "content": content})
        if outcome.status != "result":
            return f"Error: {outcome.message}"
        return f"Successfully wrote to {path}"

    async def _computer_list(self, path: str, pattern: str, recursive: bool) -> str:
        import fnmatch

        root = self._computer_path(path)
        if root is None:
            return f"Error: Path '{path}' is outside the workspace"
        results: list[str] = []
        folders = [root]
        first_error: str | None = None
        while folders and len(results) < 100:
            current = folders.pop(0)
            outcome = await self._computer_step(
                "workspace_list", {"path": current} if current else {}
            )
            if outcome.status != "result":
                if first_error is None and not results:
                    first_error = outcome.message
                break
            for entry in (outcome.result or {}).get("entries") or []:
                name = str(entry.get("name") or "")
                is_dir = entry.get("kind") == "folder"
                rel_path = f"{current}/{name}" if current else name
                if is_dir and recursive and len(folders) < 20:
                    folders.append(rel_path)
                if not fnmatch.fnmatch(name, pattern):
                    continue
                prefix = "\U0001f4c1 " if is_dir else "\U0001f4c4 "
                results.append(f"{prefix}{rel_path}")
                if len(results) >= 100:
                    break
        if first_error is not None:
            return f"Error: {first_error}"
        if not results:
            return "No files found matching the pattern"
        output = "\n".join(results)
        if folders or len(results) >= 100:
            output += "\n\n... (more entries not listed)"
        return output

    async def _computer_edit(self, path: str, old_text: str, new_text: str) -> str:
        rel = self._computer_path(path)
        if rel is None:
            return f"Error: Path '{path}' is outside the workspace"
        cfg = self.ctx.tool_configs.get("file_edit", {})
        allowed_ext: list[str] = cfg.get("allowedExtensions", [])
        suffix = Path(rel).suffix
        if allowed_ext and suffix not in allowed_ext:
            return f"Error: Extension '{suffix}' is not allowed. Allowed: {', '.join(allowed_ext)}"
        read = await self._computer_step("workspace_read", {"path": rel})
        if read.status != "result":
            return f"Error: {read.message}"
        result = read.result or {}
        if result.get("truncated"):
            return f"Error: '{path}' is too large to edit safely in the computer"
        content = str(result.get("content") or "")
        if old_text not in content:
            return f"Error: Could not find the specified text in {path}"
        count = content.count(old_text)
        new_content = content.replace(old_text, new_text)
        write = await self._computer_step(
            "workspace_write",
            {
                "path": rel,
                "content": new_content,
                "expectedRevision": str(result.get("revision") or ""),
            },
        )
        if write.status != "result":
            return f"Error: {write.message}"
        return f"Successfully edited {path} ({count} replacement{'s' if count > 1 else ''})"

    async def _computer_info(self, path: str) -> str:
        rel = self._computer_path(path)
        if rel is None:
            return f"Error: Path '{path}' is outside the workspace"
        if not rel:
            return f"Path: {path}\nType: directory"
        parent, _, name = rel.rpartition("/")
        outcome = await self._computer_step("workspace_list", {"path": parent} if parent else {})
        if outcome.status != "result":
            return f"Error: {outcome.message}"
        entry = next(
            (e for e in (outcome.result or {}).get("entries") or [] if e.get("name") == name),
            None,
        )
        if entry is None:
            return f"Error: '{path}' does not exist"
        is_dir = entry.get("kind") == "folder"
        lines = [f"Path: {path}", f"Type: {'directory' if is_dir else 'file'}"]
        if not is_dir:
            lines.append(f"Size: {entry.get('size')} bytes")
            if entry.get("modified"):
                lines.append(f"Modified: {entry['modified']}")
            lines.append(f"Extension: {Path(name).suffix or '(none)'}")
        return "\n".join(lines)

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx
        resolve = self._resolve_path

        @skill(
            name="file_read",
            description="Read the contents of a file.",
            category="file",
            tags=["file", "read"],
            idempotent=True,
            requires_filesystem=True,
            display_name="Read File",
            icon="file-text",
            risk_level=RiskLevel.SAFE,
            config_params=[
                ConfigParam(
                    name="maxFileSize",
                    display_name="Max File Size",
                    description="Maximum file size allowed for reading.",
                    type="number",
                    default=10485760,
                    min=1024,
                    max=104857600,
                    unit="bytes",
                ),
                ConfigParam(
                    name="encoding",
                    display_name="Encoding",
                    description="Text encoding used when reading files.",
                    type="select",
                    default="utf-8",
                    options=_ENCODING_OPTIONS,
                ),
            ],
        )
        async def file_read(path: str) -> str:
            """Read the contents of a file.

            Args:
                path: Path to the file (relative to workspace or absolute)

            Returns:
                File contents as string
            """
            if self._use_computer():
                return await self._computer_read(path)
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                cfg = ctx.tool_configs.get("file_read", {})
                max_size: int = cfg.get("maxFileSize", 10485760)
                encoding: str = cfg.get("encoding", "utf-8")

                file_size = full_path.stat().st_size
                if file_size > max_size:
                    return (
                        f"Error: File '{path}' is {file_size} bytes, "
                        f"exceeds limit of {max_size} bytes"
                    )

                return ctx.sandbox.read_file(str(full_path), encoding=encoding)
            except Exception as e:
                return f"Error reading file: {e}"

        @skill(
            name="file_write",
            description="Write content to a file. Creates the file if it doesn't exist.",
            category="file",
            tags=["file", "write"],
            side_effects=True,
            requires_filesystem=True,
            display_name="Write File",
            icon="file-pen",
            risk_level=RiskLevel.MODERATE,
            config_params=[
                ConfigParam(
                    name="encoding",
                    display_name="Encoding",
                    description="Text encoding used when writing files.",
                    type="select",
                    default="utf-8",
                    options=_ENCODING_OPTIONS,
                ),
                ConfigParam(
                    name="allowedExtensions",
                    display_name="Allowed Extensions",
                    description="File extensions allowed for writing. Empty list allows all.",
                    type="string[]",
                    default=[],
                    item_placeholder=".txt, .json, .csv",
                ),
            ],
        )
        async def file_write(path: str, content: str) -> str:
            """Write content to a file. Creates the file if it doesn't exist.

            Args:
                path: Path to the file (relative to workspace or absolute)
                content: Content to write

            Returns:
                Success message or error
            """
            if self._use_computer():
                return await self._computer_write(path, content)
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                cfg = ctx.tool_configs.get("file_write", {})
                encoding: str = cfg.get("encoding", "utf-8")
                allowed_ext: list[str] = cfg.get("allowedExtensions", [])

                if allowed_ext and full_path.suffix not in allowed_ext:
                    return (
                        f"Error: Extension '{full_path.suffix}' is not allowed. "
                        f"Allowed: {', '.join(allowed_ext)}"
                    )

                full_path.parent.mkdir(parents=True, exist_ok=True)
                ctx.sandbox.write_file(str(full_path), content, encoding=encoding)
                return f"Successfully wrote to {path}"
            except Exception as e:
                return f"Error writing file: {e}"

        @skill(
            name="file_list",
            description="List files in a directory.",
            category="file",
            tags=["file", "list"],
            idempotent=True,
            requires_filesystem=True,
            display_name="List Files",
            icon="folder-open",
            risk_level=RiskLevel.SAFE,
        )
        async def file_list(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
            """List files in a directory.

            Args:
                path: Directory path (default: current workspace)
                pattern: Glob pattern to filter files (default: *)
                recursive: Include subdirectories (default: False)

            Returns:
                List of files matching the pattern
            """
            if self._use_computer():
                return await self._computer_list(path, pattern, recursive)
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                if not full_path.is_dir():
                    return f"Error: '{path}' is not a directory"
                if recursive:
                    files = list(full_path.rglob(pattern))
                else:
                    files = list(full_path.glob(pattern))
                files = [f for f in files if not ctx.config.should_ignore(f)]
                result = []
                for f in sorted(files)[:100]:
                    rel_path = f.relative_to(ctx.config.workspace_path)
                    prefix = "\U0001f4c1 " if f.is_dir() else "\U0001f4c4 "
                    result.append(f"{prefix}{rel_path}")
                if not result:
                    return "No files found matching the pattern"
                output = "\n".join(result)
                if len(files) > 100:
                    output += f"\n\n... and {len(files) - 100} more files"
                return output
            except Exception as e:
                return f"Error listing files: {e}"

        @skill(
            name="file_edit",
            description="Edit a file by replacing a specific string with new content.",
            category="file",
            tags=["file", "edit"],
            side_effects=True,
            requires_filesystem=True,
            display_name="Edit File",
            icon="file-search",
            risk_level=RiskLevel.MODERATE,
            config_params=[
                ConfigParam(
                    name="maxFileSize",
                    display_name="Max File Size",
                    description="Maximum file size allowed for editing.",
                    type="number",
                    default=10485760,
                    min=1024,
                    max=104857600,
                    unit="bytes",
                ),
                ConfigParam(
                    name="allowedExtensions",
                    display_name="Allowed Extensions",
                    description="File extensions allowed for editing. Empty list allows all.",
                    type="string[]",
                    default=[],
                    item_placeholder=".txt, .json, .csv",
                ),
            ],
        )
        async def file_edit(path: str, old_text: str, new_text: str) -> str:
            """Edit a file by replacing a specific string with new content.

            Args:
                path: Path to the file (relative to workspace or absolute)
                old_text: The exact text to find and replace
                new_text: The replacement text

            Returns:
                Success message or error
            """
            if self._use_computer():
                return await self._computer_edit(path, old_text, new_text)
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                cfg = ctx.tool_configs.get("file_edit", {})
                max_size: int = cfg.get("maxFileSize", 10485760)
                allowed_ext: list[str] = cfg.get("allowedExtensions", [])

                if allowed_ext and full_path.suffix not in allowed_ext:
                    return (
                        f"Error: Extension '{full_path.suffix}' is not allowed. "
                        f"Allowed: {', '.join(allowed_ext)}"
                    )

                file_size = full_path.stat().st_size
                if file_size > max_size:
                    return (
                        f"Error: File '{path}' is {file_size} bytes, "
                        f"exceeds limit of {max_size} bytes"
                    )

                content = ctx.sandbox.read_file(str(full_path))
                if old_text not in content:
                    return f"Error: Could not find the specified text in {path}"
                count = content.count(old_text)
                new_content = content.replace(old_text, new_text)
                ctx.sandbox.write_file(str(full_path), new_content)
                return f"Successfully edited {path} ({count} replacement{'s' if count > 1 else ''})"
            except Exception as e:
                return f"Error editing file: {e}"

        @skill(
            name="file_info",
            description="Get metadata about a file (size, modified time, type).",
            category="file",
            tags=["file", "info"],
            idempotent=True,
            requires_filesystem=True,
            display_name="File Info",
            icon="file-scan",
            risk_level=RiskLevel.SAFE,
        )
        async def file_info(path: str) -> str:
            """Get metadata about a file.

            Args:
                path: Path to the file (relative to workspace or absolute)

            Returns:
                File metadata as formatted string
            """
            if self._use_computer():
                return await self._computer_info(path)
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                if not full_path.exists():
                    return f"Error: '{path}' does not exist"
                stat = full_path.stat()
                kind = "directory" if full_path.is_dir() else "file"
                size = stat.st_size
                from datetime import datetime, timezone

                modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()
                lines = [
                    f"Path: {path}",
                    f"Type: {kind}",
                    f"Size: {size} bytes",
                    f"Modified: {modified}",
                ]
                if kind == "file":
                    lines.append(f"Extension: {full_path.suffix or '(none)'}")
                return "\n".join(lines)
            except Exception as e:
                return f"Error getting file info: {e}"

        return {
            "file_read": skill_of(file_read),
            "file_write": skill_of(file_write),
            "file_list": skill_of(file_list),
            "file_edit": skill_of(file_edit),
            "file_info": skill_of(file_info),
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

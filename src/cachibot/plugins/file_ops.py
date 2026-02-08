"""
File operations plugin — workspace-scoped file_read, file_write, file_list, file_edit, file_info.
"""

from pathlib import Path

from tukuy.skill import Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext


class FileOpsPlugin(CachibotPlugin):
    """Provides workspace-restricted file operation tools."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("file_ops", ctx)
        self._skills_map = self._build_skills()

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path relative to the workspace."""
        p = Path(path)
        if p.is_absolute():
            return p
        return self.ctx.config.workspace_path / p

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
        )
        def file_read(path: str) -> str:
            """Read the contents of a file.

            Args:
                path: Path to the file (relative to workspace or absolute)

            Returns:
                File contents as string
            """
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                return ctx.sandbox.read_file(str(full_path))
            except Exception as e:
                return f"Error reading file: {e}"

        @skill(
            name="file_write",
            description="Write content to a file. Creates the file if it doesn't exist.",
            category="file",
            tags=["file", "write"],
            side_effects=True,
            requires_filesystem=True,
        )
        def file_write(path: str, content: str) -> str:
            """Write content to a file. Creates the file if it doesn't exist.

            Args:
                path: Path to the file (relative to workspace or absolute)
                content: Content to write

            Returns:
                Success message or error
            """
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
                full_path.parent.mkdir(parents=True, exist_ok=True)
                ctx.sandbox.write_file(str(full_path), content)
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
        )
        def file_list(path: str = ".", pattern: str = "*", recursive: bool = False) -> str:
            """List files in a directory.

            Args:
                path: Directory path (default: current workspace)
                pattern: Glob pattern to filter files (default: *)
                recursive: Include subdirectories (default: False)

            Returns:
                List of files matching the pattern
            """
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
        )
        def file_edit(path: str, old_text: str, new_text: str) -> str:
            """Edit a file by replacing a specific string with new content.

            Args:
                path: Path to the file (relative to workspace or absolute)
                old_text: The exact text to find and replace
                new_text: The replacement text

            Returns:
                Success message or error
            """
            full_path = resolve(path)
            if not ctx.config.is_path_allowed(full_path):
                return f"Error: Path '{path}' is outside the workspace"
            try:
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
        )
        def file_info(path: str) -> str:
            """Get metadata about a file.

            Args:
                path: Path to the file (relative to workspace or absolute)

            Returns:
                File metadata as formatted string
            """
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
            "file_read": file_read.__skill__,
            "file_write": file_write.__skill__,
            "file_list": file_list.__skill__,
            "file_edit": file_edit.__skill__,
            "file_info": file_info.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

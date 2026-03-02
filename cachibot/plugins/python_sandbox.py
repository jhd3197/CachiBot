"""
Python sandbox plugin — sandboxed python_execute tool with risk analysis.
"""

from __future__ import annotations

import asyncio
import logging
import mimetypes
import shutil
import uuid
from pathlib import Path

from prompture import ApprovalRequired
from tukuy import analyze_python
from tukuy.analysis.risk_scoring import RiskLevel as AnalysisRiskLevel
from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)

_DOCUMENT_EXTENSIONS = {".pdf", ".pptx", ".docx", ".xlsx"}

_DOCUMENT_TYPES: dict[str, str] = {
    ".pdf": "pdf",
    ".pptx": "pptx",
    ".docx": "docx",
    ".xlsx": "xlsx",
}


def _snapshot_documents(workspace: Path) -> dict[str, float]:
    """Return {path: mtime} for document files in the workspace."""
    snap: dict[str, float] = {}
    try:
        for p in workspace.rglob("*"):
            if p.is_file() and p.suffix.lower() in _DOCUMENT_EXTENSIONS:
                snap[str(p)] = p.stat().st_mtime
    except OSError:
        pass
    return snap


def _diff_documents(before: dict[str, float], after: dict[str, float]) -> list[str]:
    """Return paths of new or modified document files."""
    changed: list[str] = []
    for path, mtime in after.items():
        if path not in before or mtime > before[path]:
            changed.append(path)
    return changed


async def _emit_document_artifact(
    ctx: PluginContext,
    file_path: str,
) -> None:
    """Copy a generated document to the asset store and emit a document artifact."""
    try:
        from cachibot.models.artifact import Artifact as ArtifactModel
        from cachibot.models.artifact import ArtifactType
        from cachibot.models.asset import Asset
        from cachibot.storage.asset_repository import AssetRepository

        path = Path(file_path)
        if not path.exists() or not path.is_file():
            return

        owner_id = ctx.chat_id or ""
        if not owner_id:
            return

        asset_id = str(uuid.uuid4())
        assets_base = Path.home() / ".cachibot" / "assets"
        storage_dir = assets_base / "chat" / owner_id
        storage_path = storage_dir / asset_id
        storage_path.parent.mkdir(parents=True, exist_ok=True)

        shutil.copy2(str(path), str(storage_path))

        mime_type, _ = mimetypes.guess_type(path.name)
        mime_type = mime_type or "application/octet-stream"
        file_size = path.stat().st_size
        ext = path.suffix.lower()
        doc_type = _DOCUMENT_TYPES.get(ext, "unknown")

        from datetime import datetime, timezone

        asset = Asset(
            id=asset_id,
            owner_type="chat",
            owner_id=owner_id,
            name=path.name,
            original_filename=path.name,
            content_type=mime_type,
            size_bytes=file_size,
            storage_path=str(storage_path),
            uploaded_by_bot_id=ctx.bot_id,
            metadata={"source": "generated", "tool": "python_execute"},
            created_at=datetime.now(timezone.utc),
        )

        repo = AssetRepository()
        await repo.create(asset)

        download_url = f"/api/bots/{ctx.bot_id}/chats/{owner_id}/assets/{asset_id}/download"

        artifact = ArtifactModel(
            id=str(uuid.uuid4()),
            type=ArtifactType.DOCUMENT,
            title=path.name,
            content=download_url,
            metadata={
                "fileName": path.name,
                "fileSize": file_size,
                "mimeType": mime_type,
                "documentType": doc_type,
                "downloadUrl": download_url,
                "assetId": asset_id,
            },
        )

        if ctx.on_artifact:
            await ctx.on_artifact(artifact)

        logger.debug(
            "Emitted document artifact %s for %s",
            artifact.id,
            path.name,
        )

    except Exception:
        logger.debug("Failed to emit document artifact for %s", file_path, exc_info=True)


def _schedule_document_capture(ctx: PluginContext, changed_files: list[str]) -> None:
    """Fire-and-forget async tasks to emit document artifacts for changed files."""
    try:
        loop = asyncio.get_running_loop()
        for file_path in changed_files:
            loop.create_task(_emit_document_artifact(ctx, file_path))
    except RuntimeError:
        pass  # No event loop — skip


class PythonSandboxPlugin(CachibotPlugin):
    """Provides the python_execute tool with AST risk analysis."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("python_sandbox", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="python_sandbox",
            display_name="Code Execution",
            icon="code",
            group="Core",
            requires=PluginRequirements(filesystem=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(  # type: ignore[untyped-decorator]
            name="python_execute",
            description="Execute Python code safely in a sandbox. "
            "Use this to run Python scripts, calculations, data processing, "
            "or any Python code. The code runs in an isolated environment "
            "with restricted imports and filesystem access.",
            category="code",
            tags=["python", "execute", "sandbox"],
            side_effects=True,
            requires_filesystem=True,
            display_name="Execute Python",
            icon="code",
            risk_level=RiskLevel.DANGEROUS,
            config_params=[
                ConfigParam(
                    name="timeoutSeconds",
                    display_name="Timeout",
                    type="number",
                    default=30,
                    min=5,
                    max=120,
                    step=5,
                    unit="seconds",
                ),
                ConfigParam(
                    name="maxOutputLength",
                    display_name="Max Output Length",
                    type="number",
                    default=10000,
                    min=1000,
                    max=50000,
                    step=1000,
                    unit="chars",
                ),
                ConfigParam(
                    name="allowedReadPaths",
                    display_name="Extra Read Paths",
                    description="Additional directories the sandbox can read from "
                    "(workspace is always included).",
                    type="string[]",
                    default=[],
                    placeholder="/data/shared",
                    max_items=20,
                ),
                ConfigParam(
                    name="allowedWritePaths",
                    display_name="Extra Write Paths",
                    description="Additional directories the sandbox can write to "
                    "(workspace is always included).",
                    type="string[]",
                    default=[],
                    placeholder="/data/output",
                    max_items=20,
                ),
                ConfigParam(
                    name="blockedPaths",
                    display_name="Blocked Paths",
                    description="Directories forbidden from access, even if within allowed paths.",
                    type="string[]",
                    default=[],
                    placeholder="/etc/secrets",
                    max_items=20,
                ),
                ConfigParam(
                    name="extraImports",
                    display_name="Extra Imports",
                    description="Additional Python modules to allow beyond the default safe set.",
                    type="string[]",
                    default=[],
                    placeholder="requests",
                    max_items=50,
                ),
                ConfigParam(
                    name="blockedImports",
                    display_name="Blocked Imports",
                    description="Python modules to block, even if in the default safe set.",
                    type="string[]",
                    default=[],
                    placeholder="csv",
                    max_items=50,
                ),
            ],
        )
        def python_execute(code: str) -> str:
            """Execute Python code safely in a sandbox.

            Args:
                code: Python code to execute

            Returns:
                Output from the code execution (stdout + return value)
            """
            # Analyze code first
            analysis = analyze_python(code)

            if analysis.risk_level in (AnalysisRiskLevel.HIGH, AnalysisRiskLevel.CRITICAL):
                raise ApprovalRequired(
                    tool_name="python_execute",
                    action=f"Execute {analysis.risk_level.value}-risk Python code",
                    details={
                        "code": code,
                        "risk_level": analysis.risk_level.value,
                        "reasons": analysis.risk.reasons,
                        "imports": list(analysis.features.imports),
                    },
                )

            # Snapshot document files before execution
            workspace = Path(str(ctx.config.workspace_path))
            before = _snapshot_documents(workspace)

            result = ctx.sandbox.execute(code)

            # Get max output length from tool_configs or use default
            max_output_length = 10000
            if "python_execute" in ctx.tool_configs:
                py_cfg = ctx.tool_configs["python_execute"]
                max_output_length = py_cfg.get("maxOutputLength", max_output_length)

            if result.success:
                # Detect new/modified document files and emit artifacts
                after = _snapshot_documents(workspace)
                changed = _diff_documents(before, after)
                if changed and ctx.on_artifact:
                    _schedule_document_capture(ctx, changed)

                output = result.output.strip() if result.output else ""
                if result.return_value is not None:
                    if output:
                        output += f"\n\nReturn value: {result.return_value}"
                    else:
                        output = f"Return value: {result.return_value}"
                if len(output) > max_output_length:
                    output = output[:max_output_length]
                    output += f"\n\n... (output truncated at {max_output_length} chars)"
                return output or "Code executed successfully (no output)"
            else:
                return f"Error: {result.error}"

        return {"python_execute": python_execute.__skill__}

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

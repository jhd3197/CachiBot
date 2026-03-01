"""
Plugin SDK — helpers for building CachiBot plugins.

Provides convenience functions for creating artifacts from tool skills.
Each helper returns a dict with ``__artifact__: True`` that the WebSocket
handler auto-detects and forwards to the frontend as an ``ARTIFACT`` message.

Usage::

    from cachibot.plugins.sdk import code_artifact, html_artifact

    @skill(name="my_skill", description="Generate code")
    async def my_skill(prompt: str) -> dict:
        code = generate_code(prompt)
        return code_artifact("My Script", code, language="python")
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from cachibot.plugins.base import PluginContext


def artifact(
    type: str,
    title: str,
    content: str,
    *,
    language: str | None = None,
    metadata: dict[str, Any] | None = None,
    plugin: str | None = None,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create an artifact dict that the WS handler auto-detects.

    Args:
        type: Artifact type (code, html, markdown, svg, mermaid, react, image, custom).
        title: Display title for the artifact panel header.
        content: The artifact content.
        language: Programming language for code artifacts.
        metadata: Type-specific metadata.
        plugin: Source plugin name (for custom renderers).
        artifact_id: Optional explicit ID. Generated if not provided.
        version: Version number (default 1).

    Returns:
        Dict with ``__artifact__: True`` marker for WS handler detection.
    """
    result: dict[str, Any] = {
        "__artifact__": True,
        "id": artifact_id or str(uuid.uuid4()),
        "type": type,
        "title": title,
        "content": content,
        "version": version,
    }
    if language is not None:
        result["language"] = language
    if metadata is not None:
        result["metadata"] = metadata
    if plugin is not None:
        result["plugin"] = plugin
    return result


def artifact_update(
    artifact_id: str,
    *,
    content: str | None = None,
    title: str | None = None,
    metadata: dict[str, Any] | None = None,
    version: int | None = None,
) -> dict[str, Any]:
    """Create an artifact update dict for modifying an existing artifact.

    Args:
        artifact_id: ID of the artifact to update.
        content: New content (replaces existing).
        title: New title.
        metadata: Metadata to merge.
        version: New version number.

    Returns:
        Dict with ``__artifact_update__: True`` marker.
    """
    result: dict[str, Any] = {
        "__artifact_update__": True,
        "id": artifact_id,
    }
    if content is not None:
        result["content"] = content
    if title is not None:
        result["title"] = title
    if metadata is not None:
        result["metadata"] = metadata
    if version is not None:
        result["version"] = version
    return result


def code_artifact(
    title: str,
    content: str,
    language: str = "text",
    *,
    editable: bool = True,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a code artifact with syntax highlighting.

    Args:
        title: Display title (e.g., "main.py").
        content: The source code.
        language: Programming language for syntax highlighting.
        editable: Whether the user can edit the code in the panel.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="code",
        title=title,
        content=content,
        language=language,
        metadata={"editable": editable},
        artifact_id=artifact_id,
        version=version,
    )


def html_artifact(
    title: str,
    content: str,
    *,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create an HTML artifact for live preview in a sandboxed iframe.

    Args:
        title: Display title.
        content: Complete HTML content.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="html",
        title=title,
        content=content,
        artifact_id=artifact_id,
        version=version,
    )


def markdown_artifact(
    title: str,
    content: str,
    *,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a markdown document artifact.

    Args:
        title: Display title.
        content: Markdown content.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="markdown",
        title=title,
        content=content,
        artifact_id=artifact_id,
        version=version,
    )


def svg_artifact(
    title: str,
    content: str,
    *,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create an SVG artifact for inline rendering.

    Args:
        title: Display title.
        content: SVG markup.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="svg",
        title=title,
        content=content,
        artifact_id=artifact_id,
        version=version,
    )


def mermaid_artifact(
    title: str,
    content: str,
    *,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a Mermaid diagram artifact.

    Args:
        title: Display title.
        content: Mermaid diagram syntax.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="mermaid",
        title=title,
        content=content,
        artifact_id=artifact_id,
        version=version,
    )


def image_artifact(
    title: str,
    content: str,
    *,
    metadata: dict[str, Any] | None = None,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create an image artifact.

    Args:
        title: Display title.
        content: Image data URI or URL.
        metadata: Image metadata (width, height, format, etc.).
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="image",
        title=title,
        content=content,
        metadata=metadata,
        artifact_id=artifact_id,
        version=version,
    )


def react_artifact(
    title: str,
    content: str,
    *,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a React component artifact for live preview.

    Args:
        title: Display title.
        content: React/JSX source code.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="react",
        title=title,
        content=content,
        language="tsx",
        artifact_id=artifact_id,
        version=version,
    )


def custom_artifact(
    title: str,
    content: str,
    plugin: str,
    *,
    metadata: dict[str, Any] | None = None,
    artifact_id: str | None = None,
    version: int = 1,
) -> dict[str, Any]:
    """Create a custom artifact rendered by a plugin's iframe renderer.

    Args:
        title: Display title.
        content: Content passed to the plugin renderer.
        plugin: Plugin name that provides the custom renderer.
        metadata: Additional metadata for the renderer.
        artifact_id: Optional explicit ID.
        version: Version number.
    """
    return artifact(
        type="custom",
        title=title,
        content=content,
        plugin=plugin,
        metadata=metadata,
        artifact_id=artifact_id,
        version=version,
    )


async def emit_artifact(
    ctx: PluginContext,
    type: str,
    title: str,
    content: str,
    *,
    language: str | None = None,
    metadata: dict[str, Any] | None = None,
    plugin: str | None = None,
    artifact_id: str | None = None,
    version: int = 1,
) -> str | None:
    """Proactively emit an artifact to the frontend via the on_artifact callback.

    Unlike the ``artifact()`` helpers which return a dict for the tool result,
    this function pushes the artifact immediately — useful for streaming
    multiple artifacts from a single tool call or emitting artifacts from
    background tasks.

    Args:
        ctx: The PluginContext (provides the on_artifact callback).
        type: Artifact type (code, html, markdown, etc.).
        title: Display title.
        content: Artifact content.
        language: Language for code artifacts.
        metadata: Type-specific metadata.
        plugin: Source plugin name.
        artifact_id: Optional explicit ID.
        version: Version number.

    Returns:
        The artifact ID if emitted, or None if no callback is available.
    """
    if ctx.on_artifact is None:
        return None

    from cachibot.models.artifact import Artifact as ArtifactModel
    from cachibot.models.artifact import ArtifactType

    aid = artifact_id or str(uuid.uuid4())
    a = ArtifactModel(
        id=aid,
        type=ArtifactType(type),
        title=title,
        content=content,
        language=language,
        metadata=metadata or {},
        plugin=plugin,
        version=version,
    )
    await ctx.on_artifact(a)
    return aid

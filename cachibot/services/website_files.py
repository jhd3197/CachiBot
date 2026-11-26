"""Website Builder file write-back for edited HTML artifacts.

The Website Builder plugin keeps each generated site on disk under
``~/.cachibot/websites/{project_id}/`` with one folder per page and one
folder per version::

    {base}/{project_id}/
    ├── project.json
    └── pages/{slug}/v{N}/index.html

When a user edits a website_builder artifact by hand, the latest version's
``index.html`` is overwritten in place so the plugin's own tools
(``iterate_website`` / ``load_website``) read the edited source on the next
turn. The plugin is external — its layout is mirrored here, never imported.
"""

from __future__ import annotations

import base64
import logging
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# One path segment, no separators; ".." is rejected separately because dots
# are legal inside a segment.
_SEGMENT_RE = re.compile(r"^[A-Za-z0-9._-]+$")
_VERSION_DIR_RE = re.compile(r"^v(\d+)$")

# Website Builder tool results are markdown carrying the project id and an
# inline base64 preview of the page.
_PROJECT_ID_RE = re.compile(r"(?:\*\*Project ID:\*\*|Project:)\s*`([^`]+)`")
_PREVIEW_RE = re.compile(r"!\[Website Preview\]\(data:text/html;base64,([A-Za-z0-9+/=\r\n]+)\)")


def websites_dir() -> Path:
    """Base directory for Website Builder projects (patchable in tests)."""
    return Path.home() / ".cachibot" / "websites"


def _is_safe_segment(value: str) -> bool:
    return bool(_SEGMENT_RE.fullmatch(value)) and ".." not in value and value != "."


def is_website_builder_artifact(plugin: str | None, metadata: dict[str, Any] | None) -> bool:
    """True when the artifact came from the Website Builder plugin."""
    if plugin == "website_builder":
        return True
    md = metadata or {}
    return md.get("source") == "website_builder" or md.get("plugin") == "website_builder"


def project_id_from_metadata(metadata: dict[str, Any] | None) -> str | None:
    """The project id recorded in artifact metadata (both spellings)."""
    md = metadata or {}
    project_id = md.get("project_id") or md.get("projectId")
    return project_id if isinstance(project_id, str) and project_id else None


def write_edited_html(
    *,
    plugin: str | None,
    metadata: dict[str, Any] | None,
    content: str,
) -> bool:
    """Overwrite the latest ``pages/{slug}/v{N}/index.html`` with edited HTML.

    Returns True only when a file was actually written. Never creates a
    project from scratch: the project.json and a version directory must
    already exist. Unsafe project ids/slugs and any target resolving outside
    the project directory are refused (the artifact save itself is the
    caller's concern and still succeeds).
    """
    if not is_website_builder_artifact(plugin, metadata):
        return False
    project_id = project_id_from_metadata(metadata)
    if project_id is None or not _is_safe_segment(project_id):
        logger.warning("Refusing website write-back for unsafe project id %r", project_id)
        return False
    md = metadata or {}
    slug = md.get("slug")
    if not isinstance(slug, str) or not slug:
        slug = "index"
    if not _is_safe_segment(slug):
        logger.warning("Refusing website write-back for unsafe slug %r", slug)
        return False

    try:
        project_root = websites_dir() / project_id
        if not (project_root / "project.json").is_file():
            return False
        pages_dir = project_root / "pages" / slug
        if not pages_dir.is_dir():
            return False

        latest: tuple[int, Path] | None = None
        for child in pages_dir.iterdir():
            match = _VERSION_DIR_RE.fullmatch(child.name)
            if match and child.is_dir():
                version = int(match.group(1))
                if latest is None or version > latest[0]:
                    latest = (version, child)
        if latest is None:
            return False

        target = latest[1] / "index.html"
        # Belt and braces: symlinks or odd names must not escape the project.
        resolved_root = project_root.resolve()
        resolved_target = target.resolve()
        if resolved_target != resolved_root and resolved_root not in resolved_target.parents:
            logger.warning("Refusing website write-back outside %s: %s", resolved_root, target)
            return False

        target.write_text(content, encoding="utf-8")
        return True
    except OSError:
        logger.warning("Website write-back failed for project %s", project_id, exc_info=True)
        return False


@dataclass
class WebsitePreview:
    """A Website Builder tool result parsed back into structured form."""

    project_id: str
    slug: str
    html: str


def parse_website_preview(text: str) -> WebsitePreview | None:
    """Parse a Website Builder markdown result into project id + HTML.

    Matches results carrying ``Project: `<id>``` (or ``**Project ID:**
    `<id>```) and a ``![Website Preview](data:text/html;base64,...)`` image.
    Returns None when the shape does not match or the data URI does not
    decode — callers skip promotion silently.
    """
    project_match = _PROJECT_ID_RE.search(text)
    preview_match = _PREVIEW_RE.search(text)
    if project_match is None or preview_match is None:
        return None
    project_id = project_match.group(1).strip()
    if not project_id:
        return None
    encoded = re.sub(r"\s+", "", preview_match.group(1))
    try:
        html = base64.b64decode(encoded, validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return None
    return WebsitePreview(project_id=project_id, slug="index", html=html)


def website_preview_artifact_id(bot_id: str, project_id: str, slug: str) -> str:
    """Stable artifact id for a promoted website preview.

    A uuid5 over bot + project + slug so repeated tool results (and later
    manual saves) update the same artifact row instead of piling up copies.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"cachibot-website:{bot_id}:{project_id}:{slug}"))

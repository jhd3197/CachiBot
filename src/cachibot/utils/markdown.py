"""
Markdown utilities for platform message formatting.
"""

from __future__ import annotations

import base64
import logging
import re

from cachibot.models.platform import MediaItem

logger = logging.getLogger(__name__)


def strip_markdown(text: str) -> str:
    """
    Strip markdown formatting from text for platforms that don't handle it well.

    Converts:
    - **bold** or __bold__ → bold
    - *italic* or _italic_ → italic
    - ~~strikethrough~~ → strikethrough
    - `code` → code
    - ```code blocks``` → code blocks
    - [link text](url) → link text (url)
    - # Headers → Headers
    - > Blockquotes → Blockquotes (indented)
    - Lists (- or *) → preserved with dash

    Args:
        text: The markdown text to strip

    Returns:
        Plain text with markdown formatting removed
    """
    if not text:
        return text

    result = text

    # Code blocks (``` ... ```) - extract content only
    result = re.sub(r"```(?:\w+)?\n?(.*?)```", r"\1", result, flags=re.DOTALL)

    # Inline code (`code`) - just remove backticks
    result = re.sub(r"`([^`]+)`", r"\1", result)

    # Images ![alt](url) → alt
    result = re.sub(r"!\[([^\]]*)\]\([^)]+\)", r"\1", result)

    # Links [text](url) → text (url)
    result = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1 (\2)", result)

    # Bold **text** or __text__
    result = re.sub(r"\*\*([^*]+)\*\*", r"\1", result)
    result = re.sub(r"__([^_]+)__", r"\1", result)

    # Italic *text* or _text_ (but not inside words like some_var)
    result = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"\1", result)
    result = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"\1", result)

    # Strikethrough ~~text~~
    result = re.sub(r"~~([^~]+)~~", r"\1", result)

    # Headers (# Header) - just remove the # symbols
    result = re.sub(r"^#{1,6}\s+", "", result, flags=re.MULTILINE)

    # Blockquotes (> quote) - remove > but keep text
    result = re.sub(r"^>\s?", "  ", result, flags=re.MULTILINE)

    # Horizontal rules (---, ***, ___) - replace with dashes
    result = re.sub(r"^[-*_]{3,}$", "---", result, flags=re.MULTILINE)

    # Clean up any double spaces
    result = re.sub(r"  +", " ", result)

    return result.strip()


# Regex for inline base64 data URIs in markdown image syntax:
# ![alt text](data:mime/type;base64,DATA)
_DATA_URI_RE = re.compile(
    r"!\[([^\]]*)\]\(data:([^;]+);base64,([A-Za-z0-9+/=\s]+)\)",
    re.DOTALL,
)

# Italic metadata line that often follows a generated image/audio block
# e.g., *Cost: $0.04 | Model: dall-e-3*
_METADATA_LINE_RE = re.compile(r"^\s*\*[^*]+\*\s*$", re.MULTILINE)

# Map MIME type prefixes to file extensions
_MIME_TO_EXT: dict[str, str] = {
    "image/png": "png",
    "image/jpeg": "jpg",
    "image/gif": "gif",
    "image/webp": "webp",
    "audio/mpeg": "mp3",
    "audio/mp3": "mp3",
    "audio/wav": "wav",
    "audio/ogg": "ogg",
}


def extract_media_from_text(text: str) -> tuple[str, list[MediaItem]]:
    """
    Extract base64 data-URI media from markdown text.

    Finds all ``![alt](data:mime;base64,DATA)`` patterns, decodes
    the base64 payload, and returns the cleaned text plus a list
    of MediaItem objects.

    Args:
        text: Markdown text potentially containing inline media.

    Returns:
        A tuple of (cleaned_text, media_items).
    """
    if not text:
        return text, []

    media_items: list[MediaItem] = []
    counter = 0

    def _replace(match: re.Match) -> str:
        nonlocal counter
        alt_text = match.group(1).strip()
        mime_type = match.group(2).strip()
        b64_data = match.group(3).strip()

        try:
            raw_bytes = base64.b64decode(b64_data)
        except Exception:
            logger.warning("Failed to decode base64 media in text")
            return match.group(0)  # Leave original if decode fails

        ext = _MIME_TO_EXT.get(mime_type, mime_type.split("/")[-1])
        counter += 1
        filename = f"media_{counter}.{ext}"

        media_items.append(
            MediaItem(
                media_type=mime_type,
                data=raw_bytes,
                filename=filename,
                alt_text=alt_text,
            )
        )
        return ""

    cleaned = _DATA_URI_RE.sub(_replace, text)

    # If we extracted media, also capture trailing metadata lines
    # and assign them as captions
    if media_items:
        meta_matches = list(_METADATA_LINE_RE.finditer(cleaned))
        for i, meta in enumerate(meta_matches):
            if i < len(media_items):
                media_items[i].metadata_text = meta.group(0).strip().strip("*")
        # Remove metadata lines from cleaned text
        cleaned = _METADATA_LINE_RE.sub("", cleaned)

    # Collapse excessive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()

    return cleaned, media_items


def extract_media_from_steps(steps: list) -> list[MediaItem]:
    """
    Extract media from AgentResult steps.

    Scans tool_result steps for data URIs in the result content.
    Tool results contain the full (non-truncated) output, so they are
    the most reliable source for media data.

    Args:
        steps: List of AgentStep objects from an AgentResult.

    Returns:
        List of MediaItem objects found in tool results.
    """
    all_media: list[MediaItem] = []

    for step in steps:
        # Only look at tool_result steps
        if not hasattr(step, "step_type"):
            continue
        if step.step_type.value != "tool_result":
            continue

        # tool_result can be in step.tool_result or step.content
        for source in (step.tool_result, step.content):
            if not isinstance(source, str):
                continue
            _, media_items = extract_media_from_text(source)
            all_media.extend(media_items)

    return all_media

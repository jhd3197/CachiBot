"""
Platform response models for media-rich bot responses.

Used when sending responses back to Telegram/Discord that may include
images, audio, or other media alongside text.
"""

from dataclasses import dataclass, field


@dataclass
class IncomingMedia:
    """An incoming media attachment from a platform user."""

    media_type: str  # MIME type (e.g., "image/jpeg", "audio/ogg")
    data: bytes  # Raw file bytes
    filename: str  # Original or generated filename
    caption: str = ""  # User caption if any


@dataclass
class MediaItem:
    """A single media attachment in a platform response."""

    media_type: str  # MIME type (e.g., "image/png", "audio/mpeg")
    data: bytes  # Raw media bytes
    filename: str  # Suggested filename (e.g., "image.png")
    alt_text: str = ""  # Alt text / description
    metadata_text: str = ""  # Caption text (e.g., cost/model info)


@dataclass
class PlatformResponse:
    """A bot response that may contain text and/or media attachments."""

    text: str = ""
    media: list[MediaItem] = field(default_factory=list)

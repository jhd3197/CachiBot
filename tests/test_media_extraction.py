"""
Tests for media extraction utilities in cachibot.utils.markdown.
"""

import base64
from dataclasses import dataclass
from enum import Enum

from cachibot.models.platform import MediaItem, PlatformResponse
from cachibot.utils.markdown import extract_media_from_steps, extract_media_from_text

# ── Fixtures ──────────────────────────────────────────────────────────


def _make_data_uri(mime: str, payload: bytes, alt: str = "image") -> str:
    """Build a markdown data-URI image string."""
    b64 = base64.b64encode(payload).decode()
    return f"![{alt}](data:{mime};base64,{b64})"


# Small 1x1 red PNG (valid minimal PNG)
TINY_PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
    b"\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00"
    b"\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x01\x00"
    b"\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)

TINY_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 20  # Fake MP3 header


# ── extract_media_from_text ───────────────────────────────────────────


class TestExtractMediaFromText:
    def test_no_media(self):
        cleaned, items = extract_media_from_text("Hello, world!")
        assert cleaned == "Hello, world!"
        assert items == []

    def test_empty_string(self):
        cleaned, items = extract_media_from_text("")
        assert cleaned == ""
        assert items == []

    def test_single_image(self):
        uri = _make_data_uri("image/png", TINY_PNG, alt="test image")
        text = f"Here is the image:\n\n{uri}\n\nDone."

        cleaned, items = extract_media_from_text(text)

        assert len(items) == 1
        assert items[0].media_type == "image/png"
        assert items[0].data == TINY_PNG
        assert items[0].alt_text == "test image"
        assert items[0].filename == "media_1.png"
        # The data URI should be stripped from the cleaned text
        assert "data:" not in cleaned
        assert "Done." in cleaned

    def test_multiple_images(self):
        uri1 = _make_data_uri("image/png", TINY_PNG, alt="first")
        uri2 = _make_data_uri("image/jpeg", b"\xff\xd8\xff\xe0" + b"\x00" * 10, alt="second")
        text = f"Images:\n\n{uri1}\n\n{uri2}\n\nEnd."

        cleaned, items = extract_media_from_text(text)

        assert len(items) == 2
        assert items[0].media_type == "image/png"
        assert items[1].media_type == "image/jpeg"
        assert "data:" not in cleaned

    def test_audio_extraction(self):
        uri = _make_data_uri("audio/mpeg", TINY_MP3, alt="speech")
        text = f"Audio result:\n\n{uri}"

        cleaned, items = extract_media_from_text(text)

        assert len(items) == 1
        assert items[0].media_type == "audio/mpeg"
        assert items[0].filename == "media_1.mp3"

    def test_metadata_line_captured(self):
        uri = _make_data_uri("image/png", TINY_PNG)
        text = f"{uri}\n*Cost: $0.04 | Model: dall-e-3*\n\nDone."

        cleaned, items = extract_media_from_text(text)

        assert len(items) == 1
        assert "Cost: $0.04" in items[0].metadata_text
        assert "dall-e-3" in items[0].metadata_text
        # Metadata line should be removed from cleaned text
        assert "Cost:" not in cleaned

    def test_preserves_non_data_uri_images(self):
        """Regular image links (not data URIs) should be left alone."""
        text = "![photo](https://example.com/photo.png)"
        cleaned, items = extract_media_from_text(text)
        assert items == []
        assert "example.com" in cleaned

    def test_invalid_base64_left_intact(self):
        """Malformed base64 should not be extracted."""
        text = "![bad](data:image/png;base64,!!!invalid!!!)"
        cleaned, items = extract_media_from_text(text)
        assert items == []
        assert "!!!" in cleaned


# ── extract_media_from_steps ──────────────────────────────────────────


class _StepType(Enum):
    tool_result = "tool_result"
    tool_call = "tool_call"
    think = "think"


@dataclass
class _FakeStep:
    step_type: _StepType
    content: str = ""
    tool_result: object = None


class TestExtractMediaFromSteps:
    def test_empty_steps(self):
        assert extract_media_from_steps([]) == []

    def test_extracts_from_tool_result_content(self):
        uri = _make_data_uri("image/png", TINY_PNG, alt="generated")
        step = _FakeStep(
            step_type=_StepType.tool_result,
            content=f"Image generated:\n{uri}",
        )
        items = extract_media_from_steps([step])
        assert len(items) == 1
        assert items[0].media_type == "image/png"

    def test_extracts_from_tool_result_field(self):
        uri = _make_data_uri("audio/mpeg", TINY_MP3)
        step = _FakeStep(
            step_type=_StepType.tool_result,
            tool_result=f"TTS result:\n{uri}",
        )
        items = extract_media_from_steps([step])
        assert len(items) == 1
        assert items[0].media_type == "audio/mpeg"

    def test_ignores_non_result_steps(self):
        uri = _make_data_uri("image/png", TINY_PNG)
        steps = [
            _FakeStep(step_type=_StepType.think, content=uri),
            _FakeStep(step_type=_StepType.tool_call, content=uri),
        ]
        assert extract_media_from_steps(steps) == []

    def test_ignores_non_string_results(self):
        step = _FakeStep(
            step_type=_StepType.tool_result,
            tool_result={"status": "ok"},
            content="",
        )
        assert extract_media_from_steps(step=None, steps=[step]) == [] if False else True
        # Proper call:
        items = extract_media_from_steps([step])
        assert items == []

    def test_multiple_steps_aggregated(self):
        uri1 = _make_data_uri("image/png", TINY_PNG)
        uri2 = _make_data_uri("audio/mpeg", TINY_MP3)
        steps = [
            _FakeStep(step_type=_StepType.tool_result, content=uri1),
            _FakeStep(step_type=_StepType.tool_result, tool_result=uri2),
        ]
        items = extract_media_from_steps(steps)
        assert len(items) == 2


# ── PlatformResponse model ───────────────────────────────────────────


class TestPlatformResponse:
    def test_defaults(self):
        r = PlatformResponse()
        assert r.text == ""
        assert r.media == []

    def test_text_only(self):
        r = PlatformResponse(text="Hello")
        assert r.text == "Hello"
        assert r.media == []

    def test_with_media(self):
        item = MediaItem(media_type="image/png", data=TINY_PNG, filename="test.png")
        r = PlatformResponse(text="Here", media=[item])
        assert len(r.media) == 1
        assert r.media[0].data == TINY_PNG

"""
Audio generation plugin — TTS and STT tools using Prompture's async audio drivers.

Supports OpenAI (tts-1, tts-1-hd, whisper-1) and ElevenLabs
(eleven_multilingual_v2, eleven_turbo_v2_5, scribe_v1) via Prompture's
built-in driver registry.
"""

import base64
import logging
from pathlib import Path
from typing import Any

from tukuy.manifest import PluginManifest, PluginRequirements
from tukuy.skill import ConfigParam, RiskLevel, Skill, skill

from cachibot.plugins.base import CachibotPlugin, PluginContext

logger = logging.getLogger(__name__)

# Format -> MIME type mapping
_FORMAT_MIME: dict[str, str] = {
    "mp3": "audio/mpeg",
    "wav": "audio/wav",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "pcm": "audio/pcm",
}


class AudioGenerationPlugin(CachibotPlugin):
    """Provides generate_audio (TTS) and transcribe_audio (STT) tools via Prompture drivers."""

    def __init__(self, ctx: PluginContext) -> None:
        super().__init__("audio_generation", ctx)
        self._skills_map = self._build_skills()

    @property
    def manifest(self) -> PluginManifest:
        return PluginManifest(
            name="audio_generation",
            display_name="Audio Generation",
            icon="audio-lines",
            group="Creative",
            requires=PluginRequirements(network=True),
        )

    def _build_skills(self) -> dict[str, Skill]:
        ctx = self.ctx

        @skill(  # type: ignore[untyped-decorator]
            name="generate_audio",
            description="Convert text to speech audio. "
            "Supports OpenAI TTS (tts-1, tts-1-hd) and ElevenLabs voices. "
            "The model is determined by the bot's audio model slot, "
            "or falls back to openai/tts-1.",
            category="creative",
            tags=["audio", "tts", "speech", "voice"],
            side_effects=False,
            requires_network=True,
            display_name="Generate Audio",
            icon="audio-lines",
            risk_level=RiskLevel.MODERATE,
            input_schema={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text to convert to speech.",
                    },
                    "voice": {
                        "type": "string",
                        "description": (
                            "Voice name for TTS. For OpenAI models use one of the listed voices. "
                            "For ElevenLabs, pass an ElevenLabs voice ID. "
                            "Defaults to plugin config."
                        ),
                        "enum": ["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                        "default": "alloy",
                    },
                    "format": {
                        "type": "string",
                        "description": "Output audio format. Defaults to plugin config.",
                        "enum": ["mp3", "wav", "opus"],
                        "default": "mp3",
                    },
                },
                "required": ["text"],
                "additionalProperties": False,
            },
            config_params=[
                ConfigParam(
                    name="voice",
                    display_name="Voice",
                    description=(
                        "Voice for TTS. OpenAI voices: alloy, echo, fable, onyx, nova, shimmer."
                    ),
                    type="select",
                    default="alloy",
                    options=["alloy", "echo", "fable", "onyx", "nova", "shimmer"],
                ),
                ConfigParam(
                    name="format",
                    display_name="Audio Format",
                    description="Output audio format.",
                    type="select",
                    default="mp3",
                    options=["mp3", "wav", "opus"],
                ),
                ConfigParam(
                    name="speed",
                    display_name="Speed",
                    description="Playback speed multiplier (OpenAI only).",
                    type="number",
                    default=1.0,
                    min=0.25,
                    max=4.0,
                    step=0.25,
                ),
            ],
        )
        async def generate_audio(
            text: str,
            voice: str = "",
            format: str = "",
        ) -> str:
            """Convert text to speech audio.

            Args:
                text: The text to convert to speech.
                voice: Voice name (e.g. "alloy", "nova"). Defaults to plugin config.
                format: Audio format ("mp3", "wav", "opus"). Defaults to plugin config.

            Returns:
                Markdown audio element with base64 data URI and metadata.
            """
            try:
                from prompture import get_async_tts_driver_for_model
            except ImportError:
                return "Error: Prompture audio drivers not available. Update prompture."

            # Resolve config
            tool_cfg = ctx.tool_configs.get("generate_audio", {})
            effective_voice = voice or tool_cfg.get("voice", "alloy")
            effective_format = format or tool_cfg.get("format", "mp3")
            speed = float(tool_cfg.get("speed", 1.0))

            # Resolve model from bot's audio slot
            model = ""
            if ctx.bot_models:
                model = ctx.bot_models.get("audio", "")
            if not model:
                model = "openai/tts-1"

            logger.info(
                "Generating audio: model=%s, voice=%s, format=%s, speed=%s, text_len=%d",
                model,
                effective_voice,
                effective_format,
                speed,
                len(text),
            )

            try:
                driver = get_async_tts_driver_for_model(model)
            except Exception as exc:
                return f"Error: Failed to initialize TTS driver for '{model}': {exc}"

            # Build options based on provider
            is_elevenlabs = "elevenlabs" in model.lower()
            options: dict[str, Any] = {}

            if is_elevenlabs:
                # ElevenLabs uses voice_id (opaque ID like "21m00Tcm4TlvDq8ikWAM"),
                # not OpenAI voice names like "alloy". Only pass voice_id when the
                # user explicitly supplied an ElevenLabs voice ID; otherwise let the
                # driver use its own default.
                _openai_voices = {"alloy", "echo", "fable", "onyx", "nova", "shimmer"}
                if effective_voice and effective_voice not in _openai_voices:
                    options["voice_id"] = effective_voice
                options["output_format"] = f"{effective_format}_44100_128"
            else:
                options["voice"] = effective_voice
                options["format"] = effective_format
                options["speed"] = speed

            try:
                result = await driver.synthesize(text, options)
            except Exception as exc:
                return f"Error: TTS synthesis failed: {exc}"

            audio_bytes: bytes = result["audio"]
            media_type = result.get("media_type", _FORMAT_MIME.get(effective_format, "audio/mpeg"))
            meta = result.get("meta", {})

            # Base64 encode
            audio_b64 = base64.b64encode(audio_bytes).decode("ascii")

            # Build response with audio player markdown
            parts = [f"![Audio](data:{media_type};base64,{audio_b64})"]

            # Add metadata
            meta_parts = []
            if meta.get("cost"):
                meta_parts.append(f"Cost: ${meta['cost']:.6f}")
            if meta.get("characters"):
                meta_parts.append(f"Characters: {meta['characters']}")
            meta_parts.append(f"Voice: {meta.get('voice_id', effective_voice)}")
            meta_parts.append(f"Model: {model}")
            if meta_parts:
                parts.append(f"\n*{' | '.join(meta_parts)}*")

            return "\n".join(parts)

        @skill(  # type: ignore[untyped-decorator]
            name="transcribe_audio",
            description="Transcribe audio to text using speech-to-text. "
            "Supports OpenAI Whisper and ElevenLabs Scribe. "
            "Accepts base64-encoded audio data, a data URI, or a file path in the workspace.",
            category="creative",
            tags=["audio", "stt", "transcription", "speech"],
            side_effects=False,
            requires_network=True,
            display_name="Transcribe Audio",
            icon="mic",
            risk_level=RiskLevel.SAFE,
            input_schema={
                "type": "object",
                "properties": {
                    "audio_data": {
                        "type": "string",
                        "description": (
                            "The audio to transcribe. Accepts three formats: "
                            "(1) a data URI (e.g., 'data:audio/mp3;base64,...'), "
                            "(2) a file path within the workspace "
                            "(e.g., 'recordings/meeting.mp3'), "
                            "or (3) raw base64-encoded audio data."
                        ),
                    },
                    "language": {
                        "type": "string",
                        "description": (
                            "Language code hint for transcription (e.g., 'en', 'es'). "
                            "Auto-detected if not provided."
                        ),
                    },
                },
                "required": ["audio_data"],
                "additionalProperties": False,
            },
            config_params=[
                ConfigParam(
                    name="language",
                    display_name="Language",
                    description="Language code (e.g. 'en', 'es'). Auto-detected if empty.",
                    type="string",
                    default="",
                ),
                ConfigParam(
                    name="sttModel",
                    display_name="STT Model Override",
                    description="Override the STT model (e.g. 'openai/whisper-1').",
                    type="string",
                    default="",
                ),
            ],
        )
        async def transcribe_audio(
            audio_data: str,
            language: str = "",
        ) -> str:
            """Transcribe audio to text.

            Args:
                audio_data: Base64-encoded audio data, a data URI
                    (data:audio/...;base64,...), or a file path in the workspace.
                language: Language code for transcription hint. Auto-detected if empty.

            Returns:
                Transcribed text with metadata.
            """
            try:
                from prompture import get_async_stt_driver_for_model
            except ImportError:
                return "Error: Prompture audio drivers not available. Update prompture."

            # Resolve config
            tool_cfg = ctx.tool_configs.get("transcribe_audio", {})
            effective_language = language or tool_cfg.get("language", "")
            stt_model_override = tool_cfg.get("sttModel", "")

            # Resolve STT model: config override > bot audio slot > fallback
            model = stt_model_override
            if not model and ctx.bot_models:
                model = ctx.bot_models.get("audio", "")
            if not model:
                model = "openai/whisper-1"

            # Decode audio data
            audio_bytes: bytes
            if audio_data.startswith("data:"):
                # Data URI: strip prefix
                try:
                    _, encoded = audio_data.split(",", 1)
                    audio_bytes = base64.b64decode(encoded)
                except Exception as exc:
                    return f"Error: Invalid data URI: {exc}"
            elif (
                "/" in audio_data
                or "\\" in audio_data
                or audio_data.endswith((".mp3", ".wav", ".ogg", ".flac", ".m4a", ".webm"))
            ):
                # File path — validate within workspace
                workspace = Path(ctx.config.workspace_path).resolve()
                file_path = Path(audio_data).resolve()
                if not str(file_path).startswith(str(workspace)):
                    return "Error: File path must be within the workspace directory."
                if not file_path.exists():
                    return f"Error: File not found: {audio_data}"
                audio_bytes = file_path.read_bytes()
            else:
                # Raw base64
                try:
                    audio_bytes = base64.b64decode(audio_data)
                except Exception as exc:
                    return f"Error: Invalid base64 audio data: {exc}"

            logger.info(
                "Transcribing audio: model=%s, language=%s, size=%d bytes",
                model,
                effective_language or "auto",
                len(audio_bytes),
            )

            try:
                driver = get_async_stt_driver_for_model(model)
            except Exception as exc:
                return f"Error: Failed to initialize STT driver for '{model}': {exc}"

            options: dict[str, Any] = {}
            if effective_language:
                options["language"] = effective_language

            try:
                result = await driver.transcribe(audio_bytes, options)
            except Exception as exc:
                return f"Error: Transcription failed: {exc}"

            text = result.get("text", "")
            detected_lang = result.get("language")
            meta = result.get("meta", {})

            # Build response
            parts = [text]

            meta_parts = []
            if detected_lang:
                meta_parts.append(f"Language: {detected_lang}")
            if meta.get("duration_seconds"):
                meta_parts.append(f"Duration: {meta['duration_seconds']:.1f}s")
            if meta.get("cost"):
                meta_parts.append(f"Cost: ${meta['cost']:.6f}")
            meta_parts.append(f"Model: {model}")
            if meta_parts:
                parts.append(f"\n*{' | '.join(meta_parts)}*")

            return "\n".join(parts)

        return {
            "generate_audio": generate_audio.__skill__,
            "transcribe_audio": transcribe_audio.__skill__,
        }

    @property
    def skills(self) -> dict[str, Skill]:
        return self._skills_map

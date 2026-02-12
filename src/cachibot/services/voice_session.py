"""Voice session manager for real-time voice conversations."""

import asyncio
import logging
import time
from dataclasses import dataclass, field
from io import BytesIO

from cachibot.models.voice import VoiceSettings

logger = logging.getLogger(__name__)


@dataclass
class VoiceSession:
    """Tracks per-connection voice session state."""

    session_id: str
    bot_id: str
    chat_id: str | None = None
    stt_model: str = "openai/whisper-1"
    tts_model: str = "openai/tts-1"
    voice_settings: VoiceSettings = field(default_factory=VoiceSettings)

    # Audio buffer for accumulating mic chunks between turns
    _audio_buffer: BytesIO = field(default_factory=BytesIO)

    # State flags
    is_transcribing: bool = False
    is_generating_audio: bool = False
    is_cancelled: bool = False

    # Active pipeline task for interruption support
    _active_task: asyncio.Task[None] | None = field(default=None, repr=False)

    # Timing
    _turn_start_time: float = 0.0

    def write_audio(self, chunk: bytes) -> None:
        """Append an audio chunk to the buffer."""
        self._audio_buffer.write(chunk)

    def get_buffered_audio(self) -> bytes:
        """Drain and return all buffered audio, resetting the buffer."""
        data = self._audio_buffer.getvalue()
        self._audio_buffer = BytesIO()
        return data

    @property
    def has_audio(self) -> bool:
        """Check if there is any buffered audio."""
        return self._audio_buffer.tell() > 0

    def start_turn(self) -> None:
        """Mark the beginning of a new voice turn."""
        self.is_cancelled = False
        self._turn_start_time = time.monotonic()

    def cancel(self) -> None:
        """Cancel the active agent/TTS pipeline for interruption."""
        self.is_cancelled = True
        if self._active_task and not self._active_task.done():
            self._active_task.cancel()
            logger.info("Voice session %s: pipeline cancelled (interrupt)", self.session_id)

    def set_active_task(self, task: asyncio.Task[None]) -> None:
        """Track the active pipeline task."""
        self._active_task = task

    @property
    def turn_elapsed_ms(self) -> float:
        """Milliseconds since the current turn started."""
        if self._turn_start_time == 0.0:
            return 0.0
        return (time.monotonic() - self._turn_start_time) * 1000

    def update_settings(self, settings: VoiceSettings) -> None:
        """Update voice settings mid-session."""
        self.voice_settings = settings

    def resolve_models(self, bot_models: dict[str, str] | None) -> None:
        """Resolve STT/TTS models from bot model slots with fallbacks."""
        if not bot_models:
            return
        audio_model = bot_models.get("audio")
        if not audio_model:
            return
        # The audio slot can be a TTS or STT model. Use heuristics:
        # If it contains "whisper" or "scribe", it's STT; otherwise TTS.
        lower = audio_model.lower()
        if "whisper" in lower or "scribe" in lower or "stt" in lower:
            self.stt_model = audio_model
        else:
            self.tts_model = audio_model

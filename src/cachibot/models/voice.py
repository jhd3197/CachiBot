"""Voice protocol models for real-time voice WebSocket communication."""

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class VoiceMessageType(str, Enum):
    """Voice WebSocket message types."""

    # Client -> Server
    VOICE_START = "voice_start"
    END_TURN = "end_turn"
    INTERRUPT = "interrupt"
    MUTE = "mute"
    UNMUTE = "unmute"
    CONFIG_UPDATE = "config_update"

    # Server -> Client
    SESSION_READY = "session_ready"
    TRANSCRIBING = "transcribing"
    TRANSCRIPT = "transcript"
    THINKING = "thinking"
    TOOL_START = "tool_start"
    TOOL_END = "tool_end"
    INSTRUCTION_DELTA = "instruction_delta"
    AUDIO_START = "audio_start"
    AUDIO_END = "audio_end"
    TURN_COMPLETE = "turn_complete"
    ERROR = "error"


class VoiceSettings(BaseModel):
    """Per-session voice configuration."""

    tts_voice: str = Field(default="alloy", description="TTS voice name or ID")
    tts_speed: float = Field(default=1.0, ge=0.5, le=2.0, description="TTS speech speed")
    stt_language: str | None = Field(default=None, description="STT language code (None=auto)")
    enable_interruption: bool = Field(default=True, description="Allow interrupting bot speech")
    save_transcripts: bool = Field(default=True, description="Save voice turns to chat history")


class VoiceStartPayload(BaseModel):
    """Payload for voice_start message to initialize a voice session."""

    bot_id: str = Field(description="Bot ID")
    chat_id: str | None = Field(default=None, description="Chat ID for transcript persistence")
    system_prompt: str | None = Field(default=None, description="System prompt override")
    models: dict[str, str] | None = Field(default=None, description="Multi-model slot config")
    capabilities: dict[str, bool] | None = Field(default=None, description="Capability toggles")
    tool_configs: dict[str, Any] | None = Field(default=None, description="Per-tool configuration")
    voice_settings: VoiceSettings = Field(default_factory=VoiceSettings)


class VoiceMessage(BaseModel):
    """Generic voice WebSocket message wrapper with factory methods."""

    type: VoiceMessageType
    payload: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def session_ready(cls, session_id: str) -> "VoiceMessage":
        return cls(type=VoiceMessageType.SESSION_READY, payload={"sessionId": session_id})

    @classmethod
    def transcribing(cls) -> "VoiceMessage":
        return cls(type=VoiceMessageType.TRANSCRIBING, payload={})

    @classmethod
    def transcript(
        cls, text: str, language: str | None = None, role: str = "user"
    ) -> "VoiceMessage":
        return cls(
            type=VoiceMessageType.TRANSCRIPT,
            payload={"text": text, "language": language, "role": role},
        )

    @classmethod
    def thinking(cls, content: str) -> "VoiceMessage":
        return cls(type=VoiceMessageType.THINKING, payload={"content": content})

    @classmethod
    def tool_start(cls, tool_id: str, tool_name: str, args: dict[str, Any]) -> "VoiceMessage":
        return cls(
            type=VoiceMessageType.TOOL_START,
            payload={"id": tool_id, "tool": tool_name, "args": args},
        )

    @classmethod
    def tool_end(cls, tool_id: str, result: str) -> "VoiceMessage":
        return cls(type=VoiceMessageType.TOOL_END, payload={"id": tool_id, "result": result})

    @classmethod
    def instruction_delta(cls, tool_call_id: str, text: str) -> "VoiceMessage":
        """Incremental text from an instruction's LLM execution."""
        return cls(
            type=VoiceMessageType.INSTRUCTION_DELTA,
            payload={"id": tool_call_id, "text": text},
        )

    @classmethod
    def audio_start(cls, sample_rate: int = 24000, channels: int = 1) -> "VoiceMessage":
        return cls(
            type=VoiceMessageType.AUDIO_START,
            payload={"sampleRate": sample_rate, "channels": channels, "format": "pcm_s16le"},
        )

    @classmethod
    def audio_end(cls, duration_ms: float = 0.0) -> "VoiceMessage":
        return cls(type=VoiceMessageType.AUDIO_END, payload={"durationMs": duration_ms})

    @classmethod
    def turn_complete(cls) -> "VoiceMessage":
        return cls(type=VoiceMessageType.TURN_COMPLETE, payload={})

    @classmethod
    def error(cls, message: str, code: str | None = None) -> "VoiceMessage":
        return cls(type=VoiceMessageType.ERROR, payload={"message": message, "code": code})

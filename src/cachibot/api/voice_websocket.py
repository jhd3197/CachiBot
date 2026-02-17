"""
Voice WebSocket Handler for Cachibot

Handles real-time voice conversations: mic audio in, STT, agent processing, TTS audio out.
Uses mixed binary/JSON protocol: JSON for control messages, binary for audio chunks.
"""

import asyncio
import copy
import json
import logging
import uuid
from datetime import datetime

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from prompture import StreamEventType
from prompture.drivers import get_async_stt_driver_for_model, get_async_tts_driver_for_model

from cachibot.agent import CachibotAgent, load_disabled_capabilities, load_dynamic_instructions
from cachibot.api.auth import get_user_from_token
from cachibot.config import Config
from cachibot.models.auth import User
from cachibot.models.knowledge import BotMessage
from cachibot.models.voice import VoiceMessage, VoiceMessageType, VoiceSettings, VoiceStartPayload
from cachibot.services.voice_session import VoiceSession
from cachibot.storage.repository import KnowledgeRepository

logger = logging.getLogger(__name__)

router = APIRouter()


async def _send_json(ws: WebSocket, msg: VoiceMessage) -> None:
    """Send a JSON voice message over the WebSocket."""
    await ws.send_json(msg.model_dump())


async def _send_bytes(ws: WebSocket, data: bytes) -> None:
    """Send binary audio data over the WebSocket."""
    await ws.send_bytes(data)


async def _run_voice_pipeline(
    session: VoiceSession,
    agent: CachibotAgent,
    websocket: WebSocket,
) -> None:
    """Execute the full voice turn pipeline: STT -> Agent -> TTS -> audio out."""
    repo = KnowledgeRepository()
    session.start_turn()

    # 1. Drain audio buffer
    audio_data = session.get_buffered_audio()
    if not audio_data:
        await _send_json(websocket, VoiceMessage.error("No audio data received"))
        await _send_json(websocket, VoiceMessage.turn_complete())
        return

    # 2. Transcribe (STT)
    session.is_transcribing = True
    await _send_json(websocket, VoiceMessage.transcribing())

    try:
        stt_driver = get_async_stt_driver_for_model(session.stt_model)
        stt_options: dict[str, str] = {}
        if session.voice_settings.stt_language:
            stt_options["language"] = session.voice_settings.stt_language
        stt_options["filename"] = "audio.webm"

        stt_result = await stt_driver.transcribe(audio_data, stt_options)
        transcript_text = stt_result.get("text", "").strip()
        detected_language = stt_result.get("language")
    except Exception as e:
        logger.error("STT failed: %s", e)
        await _send_json(websocket, VoiceMessage.error(f"Transcription failed: {e}"))
        await _send_json(websocket, VoiceMessage.turn_complete())
        session.is_transcribing = False
        return
    finally:
        session.is_transcribing = False

    if not transcript_text:
        await _send_json(websocket, VoiceMessage.error("No speech detected"))
        await _send_json(websocket, VoiceMessage.turn_complete())
        return

    # 3. Send transcript
    await _send_json(websocket, VoiceMessage.transcript(transcript_text, detected_language))

    # Save user message
    if session.voice_settings.save_transcripts and session.bot_id and session.chat_id:
        user_msg = BotMessage(
            id=str(uuid.uuid4()),
            bot_id=session.bot_id,
            chat_id=session.chat_id,
            role="user",
            content=transcript_text,
            timestamp=datetime.utcnow(),
            metadata={"source": "voice"},
        )
        await repo.save_bot_message(user_msg)

    if session.is_cancelled:
        await _send_json(websocket, VoiceMessage.turn_complete())
        return

    # 4. Run agent and accumulate response text
    response_text = ""
    try:
        async for event in agent.run_stream(transcript_text):
            if session.is_cancelled:
                break
            match event.event_type:
                case StreamEventType.text_delta:
                    response_text += event.data
                case StreamEventType.tool_call:
                    await _send_json(
                        websocket,
                        VoiceMessage.tool_start(
                            event.data.get("id", ""),
                            event.data["name"],
                            event.data.get("arguments", {}),
                        ),
                    )
                case StreamEventType.tool_result:
                    await _send_json(
                        websocket,
                        VoiceMessage.tool_end(
                            event.data.get("id", ""),
                            str(event.data.get("result", "")),
                        ),
                    )
                case StreamEventType.output:
                    # Extract final output text from AgentResult
                    agent_result = event.data
                    if agent_result and agent_result.output_text:
                        response_text = agent_result.output_text
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled during agent run")
    except Exception as e:
        logger.error("Agent run failed: %s", e)
        await _send_json(websocket, VoiceMessage.error(f"Agent error: {e}"))
        await _send_json(websocket, VoiceMessage.turn_complete())
        return

    if session.is_cancelled or not response_text:
        await _send_json(websocket, VoiceMessage.turn_complete())
        return

    # Send assistant transcript (so frontend can show it before audio plays)
    await _send_json(websocket, VoiceMessage.transcript(response_text, role="assistant"))

    # 5. TTS streaming
    session.is_generating_audio = True
    await _send_json(websocket, VoiceMessage.audio_start(sample_rate=24000, channels=1))

    total_audio_bytes = 0
    try:
        tts_driver = get_async_tts_driver_for_model(session.tts_model)
        tts_options: dict[str, str | float] = {
            "voice": session.voice_settings.tts_voice,
            "speed": session.voice_settings.tts_speed,
            "format": "pcm",
        }

        async for chunk in tts_driver.synthesize_stream(response_text, tts_options):
            if session.is_cancelled:
                break
            if chunk["type"] == "delta":
                await _send_bytes(websocket, chunk["audio"])
                total_audio_bytes += len(chunk["audio"])
            elif chunk["type"] == "done":
                # Final chunk - send any remaining audio
                if chunk.get("audio"):
                    await _send_bytes(websocket, chunk["audio"])
                    total_audio_bytes += len(chunk["audio"])
    except asyncio.CancelledError:
        logger.info("Voice pipeline cancelled during TTS")
    except NotImplementedError:
        # Driver doesn't support streaming, fall back to non-streaming
        try:
            result = await tts_driver.synthesize(response_text, tts_options)
            if not session.is_cancelled:
                await _send_bytes(websocket, result["audio"])
                total_audio_bytes = len(result["audio"])
        except Exception as e:
            logger.error("TTS fallback failed: %s", e)
            await _send_json(websocket, VoiceMessage.error(f"TTS failed: {e}"))
    except Exception as e:
        logger.error("TTS streaming failed: %s", e)
        await _send_json(websocket, VoiceMessage.error(f"TTS failed: {e}"))
    finally:
        session.is_generating_audio = False

    # Calculate approximate duration from PCM bytes (24kHz, 16-bit mono = 48000 bytes/sec)
    duration_ms = (total_audio_bytes / 48000) * 1000 if total_audio_bytes else 0
    await _send_json(websocket, VoiceMessage.audio_end(duration_ms=duration_ms))

    # Save assistant message
    if session.voice_settings.save_transcripts and session.bot_id and session.chat_id:
        assistant_msg = BotMessage(
            id=str(uuid.uuid4()),
            bot_id=session.bot_id,
            chat_id=session.chat_id,
            role="assistant",
            content=response_text,
            timestamp=datetime.utcnow(),
            metadata={"source": "voice"},
        )
        await repo.save_bot_message(assistant_msg)

    await _send_json(websocket, VoiceMessage.turn_complete())


@router.websocket("/ws/voice")
async def voice_websocket_endpoint(
    websocket: WebSocket,
    token: str | None = Query(default=None),
) -> None:
    """
    Voice WebSocket endpoint for real-time voice conversations.

    Protocol:
    - Client connects with token query parameter: /ws/voice?token=xxx
    - Client sends JSON: { type: "voice_start", payload: { botId, ... } }
    - Client sends binary frames: raw audio chunks (WebM/Opus from MediaRecorder)
    - Client sends JSON: { type: "end_turn" } to trigger STT -> Agent -> TTS pipeline
    - Server sends JSON control messages and binary PCM audio frames
    """
    # Authenticate
    user: User | None = None
    if token:
        user = await get_user_from_token(token)
    if user is None:
        await websocket.close(code=4001, reason="Authentication required")
        return

    await websocket.accept()

    workspace = websocket.app.state.workspace
    config = Config.load(workspace=workspace)

    session: VoiceSession | None = None
    agent: CachibotAgent | None = None
    pipeline_task: asyncio.Task[None] | None = None

    try:
        while True:
            message = await websocket.receive()

            if "bytes" in message and message["bytes"]:
                # Binary frame: audio chunk
                if session:
                    session.write_audio(message["bytes"])
                continue

            if "text" in message and message["text"]:
                # JSON control message
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    await _send_json(websocket, VoiceMessage.error("Invalid JSON"))
                    continue

                msg_type = data.get("type")
                payload = data.get("payload", {})

                if msg_type == VoiceMessageType.VOICE_START:
                    # Initialize voice session
                    start_payload = VoiceStartPayload(**payload)
                    session_id = str(uuid.uuid4())

                    session = VoiceSession(
                        session_id=session_id,
                        bot_id=start_payload.bot_id,
                        chat_id=start_payload.chat_id,
                        voice_settings=start_payload.voice_settings,
                    )

                    # Resolve STT/TTS models from bot_models
                    session.resolve_models(start_payload.models)

                    # Apply per-bot model override
                    agent_config = config
                    effective_model = None
                    if start_payload.models and start_payload.models.get("default"):
                        effective_model = start_payload.models["default"]
                    if effective_model:
                        agent_config = copy.deepcopy(config)
                        agent_config.agent.model = effective_model

                    # Build instruction delta sender for streaming instruction
                    # LLM output to the voice client in real time.
                    async def _instruction_delta_sender(tool_call_id: str, text: str) -> None:
                        await _send_json(
                            websocket,
                            VoiceMessage.instruction_delta(tool_call_id, text),
                        )

                    # Create agent
                    disabled_caps = await load_disabled_capabilities()
                    agent = CachibotAgent(
                        config=agent_config,
                        system_prompt_override=start_payload.system_prompt,
                        capabilities=start_payload.capabilities,
                        bot_id=start_payload.bot_id,
                        bot_models=start_payload.models,
                        tool_configs=start_payload.tool_configs or {},
                        disabled_capabilities=disabled_caps,
                        on_instruction_delta=_instruction_delta_sender,
                    )
                    await load_dynamic_instructions(agent)

                    await _send_json(websocket, VoiceMessage.session_ready(session_id))

                elif msg_type == VoiceMessageType.END_TURN:
                    # Trigger voice pipeline
                    if not session or not agent:
                        await _send_json(websocket, VoiceMessage.error("Session not initialized"))
                        continue

                    # Cancel any existing pipeline
                    if pipeline_task and not pipeline_task.done():
                        pipeline_task.cancel()

                    pipeline_task = asyncio.create_task(
                        _run_voice_pipeline(session, agent, websocket)
                    )
                    session.set_active_task(pipeline_task)

                elif msg_type == VoiceMessageType.INTERRUPT:
                    # Cancel active pipeline
                    if session:
                        session.cancel()
                    if pipeline_task and not pipeline_task.done():
                        pipeline_task.cancel()
                    await _send_json(websocket, VoiceMessage.audio_end(duration_ms=0))

                elif msg_type == VoiceMessageType.CONFIG_UPDATE:
                    # Update voice settings mid-session
                    if session and "voiceSettings" in payload:
                        new_settings = VoiceSettings(**payload["voiceSettings"])
                        session.update_settings(new_settings)

                elif msg_type == VoiceMessageType.MUTE:
                    pass  # Client-side only, no server action needed

                elif msg_type == VoiceMessageType.UNMUTE:
                    pass  # Client-side only, no server action needed

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("Voice WebSocket error: %s", e)
        try:
            await _send_json(websocket, VoiceMessage.error("An internal error occurred"))
        except Exception:
            pass
    finally:
        # Clean up
        if pipeline_task and not pipeline_task.done():
            pipeline_task.cancel()
        if session:
            session.cancel()

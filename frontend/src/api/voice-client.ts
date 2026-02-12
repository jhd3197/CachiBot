/**
 * Voice WebSocket Client
 *
 * Handles real-time voice communication: mic capture, audio playback,
 * VAD (voice activity detection), and the voice protocol.
 */

import { useAuthStore } from '../stores/auth'
import type {
  VoiceControlMessage,
  VoiceMessageType,
  VoiceSettings,
} from '../types/voice'
import type { BotCapabilities, BotModels, ToolConfigs } from '../types'

type JsonMessageHandler = (message: VoiceControlMessage) => void
type AudioChunkHandler = (chunk: ArrayBuffer) => void
type ConnectionHandler = () => void
type ErrorHandler = (error: Event | string) => void
type AudioLevelHandler = (level: number) => void

export class VoiceClient {
  private ws: WebSocket | null = null
  private mediaStream: MediaStream | null = null
  private mediaRecorder: MediaRecorder | null = null
  private audioContext: AudioContext | null = null
  private analyser: AnalyserNode | null = null
  private vadInterval: number | null = null

  // PCM playback state
  private playbackContext: AudioContext | null = null
  private scheduledSources: AudioBufferSourceNode[] = []
  private nextPlayTime = 0

  // VAD state
  private isSpeaking = false
  private silenceStart = 0
  private silenceThreshold = 1500 // ms of silence before end_turn

  // Handlers
  private jsonHandlers: JsonMessageHandler[] = []
  private audioHandlers: AudioChunkHandler[] = []
  private connectHandlers: ConnectionHandler[] = []
  private disconnectHandlers: ConnectionHandler[] = []
  private errorHandlers: ErrorHandler[] = []
  private audioLevelHandlers: AudioLevelHandler[] = []

  // State
  private _isMuted = false

  async connect(
    botId: string,
    chatId: string | null,
    options?: {
      systemPrompt?: string
      models?: BotModels
      capabilities?: BotCapabilities
      toolConfigs?: ToolConfigs
      voiceSettings?: VoiceSettings
    },
  ): Promise<void> {
    if (this.ws?.readyState === WebSocket.OPEN) return

    const { accessToken } = useAuthStore.getState()
    if (!accessToken) {
      this.errorHandlers.forEach((h) => h('Not authenticated'))
      return
    }

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/voice?token=${encodeURIComponent(accessToken)}`

    this.ws = new WebSocket(wsUrl)
    this.ws.binaryType = 'arraybuffer'

    this.ws.onopen = () => {
      this.connectHandlers.forEach((h) => h())

      // Send voice_start
      this.sendJson('voice_start', {
        bot_id: botId,
        chat_id: chatId,
        system_prompt: options?.systemPrompt,
        models: options?.models,
        capabilities: options?.capabilities,
        tool_configs: options?.toolConfigs,
        voice_settings: options?.voiceSettings
          ? {
              tts_voice: options.voiceSettings.ttsVoice,
              tts_speed: options.voiceSettings.ttsSpeed,
              stt_language: options.voiceSettings.sttLanguage,
              enable_interruption: options.voiceSettings.enableInterruption,
              save_transcripts: options.voiceSettings.saveTranscripts,
            }
          : undefined,
      })
    }

    this.ws.onmessage = (event) => {
      if (event.data instanceof ArrayBuffer) {
        // Binary: audio chunk from TTS
        this.audioHandlers.forEach((h) => h(event.data))
      } else {
        // Text: JSON control message
        try {
          const msg = JSON.parse(event.data) as VoiceControlMessage
          this.jsonHandlers.forEach((h) => h(msg))
        } catch {
          console.error('Failed to parse voice message')
        }
      }
    }

    this.ws.onclose = () => {
      this.disconnectHandlers.forEach((h) => h())
      this.cleanup()
    }

    this.ws.onerror = (error) => {
      this.errorHandlers.forEach((h) => h(error))
    }
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.cleanup()
  }

  private cleanup(): void {
    this.stopMic()
    this.stopPlayback()
    this.stopVAD()
  }

  // ── Microphone ──────────────────────────────────────────

  async startMic(): Promise<void> {
    try {
      this.mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        },
      })
    } catch {
      this.errorHandlers.forEach((h) => h('Microphone access denied'))
      return
    }

    // Set up AnalyserNode for VAD and visualization
    this.audioContext = new AudioContext()
    const source = this.audioContext.createMediaStreamSource(this.mediaStream)
    this.analyser = this.audioContext.createAnalyser()
    this.analyser.fftSize = 2048
    source.connect(this.analyser)

    // Start MediaRecorder for WebM/Opus encoding
    const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
      ? 'audio/webm;codecs=opus'
      : 'audio/webm'

    this.mediaRecorder = new MediaRecorder(this.mediaStream, {
      mimeType,
    })

    this.mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0 && this.ws?.readyState === WebSocket.OPEN && !this._isMuted) {
        event.data.arrayBuffer().then((buffer) => {
          this.ws?.send(buffer)
        })
      }
    }

    this.mediaRecorder.start(100) // 100ms chunks
  }

  stopMic(): void {
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      this.mediaRecorder.stop()
    }
    this.mediaRecorder = null

    if (this.mediaStream) {
      this.mediaStream.getTracks().forEach((t) => t.stop())
      this.mediaStream = null
    }

    if (this.audioContext) {
      this.audioContext.close()
      this.audioContext = null
    }
    this.analyser = null
  }

  setMuted(muted: boolean): void {
    this._isMuted = muted
    if (this.mediaStream) {
      this.mediaStream.getAudioTracks().forEach((t) => {
        t.enabled = !muted
      })
    }
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.sendJson(muted ? 'mute' : 'unmute', {})
    }
  }

  get isMuted(): boolean {
    return this._isMuted
  }

  // ── VAD (Voice Activity Detection) ─────────────────────

  startVAD(onSpeechEnd?: () => void): void {
    if (!this.analyser) return

    const dataArray = new Uint8Array(this.analyser.fftSize)

    this.vadInterval = window.setInterval(() => {
      if (!this.analyser) return
      this.analyser.getByteTimeDomainData(dataArray)

      // Compute RMS
      let sum = 0
      for (let i = 0; i < dataArray.length; i++) {
        const v = (dataArray[i] - 128) / 128
        sum += v * v
      }
      const rms = Math.sqrt(sum / dataArray.length)

      // Report audio level for visualization
      this.audioLevelHandlers.forEach((h) => h(rms))

      const threshold = 0.02
      if (rms > threshold) {
        if (!this.isSpeaking) {
          this.isSpeaking = true
        }
        this.silenceStart = 0
      } else if (this.isSpeaking) {
        if (this.silenceStart === 0) {
          this.silenceStart = Date.now()
        } else if (Date.now() - this.silenceStart > this.silenceThreshold) {
          // Silence detected -> end turn
          this.isSpeaking = false
          this.silenceStart = 0
          onSpeechEnd?.()
        }
      }
    }, 100)
  }

  stopVAD(): void {
    if (this.vadInterval !== null) {
      clearInterval(this.vadInterval)
      this.vadInterval = null
    }
    this.isSpeaking = false
    this.silenceStart = 0
  }

  // ── PCM Audio Playback ─────────────────────────────────

  playPCMChunk(pcmData: ArrayBuffer, sampleRate = 24000): void {
    if (!this.playbackContext) {
      this.playbackContext = new AudioContext({ sampleRate })
    }

    // Convert 16-bit signed PCM to Float32
    const int16 = new Int16Array(pcmData)
    const float32 = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768
    }

    // Create AudioBuffer
    const buffer = this.playbackContext.createBuffer(1, float32.length, sampleRate)
    buffer.copyToChannel(float32, 0)

    // Schedule for gapless playback
    const source = this.playbackContext.createBufferSource()
    source.buffer = buffer
    source.connect(this.playbackContext.destination)

    const now = this.playbackContext.currentTime
    const startTime = Math.max(now, this.nextPlayTime)
    source.start(startTime)
    this.nextPlayTime = startTime + buffer.duration

    this.scheduledSources.push(source)

    // Clean up finished sources
    source.onended = () => {
      const idx = this.scheduledSources.indexOf(source)
      if (idx !== -1) this.scheduledSources.splice(idx, 1)
    }
  }

  stopPlayback(): void {
    for (const source of this.scheduledSources) {
      try {
        source.stop()
        source.disconnect()
      } catch {
        // Already stopped
      }
    }
    this.scheduledSources = []
    this.nextPlayTime = 0

    if (this.playbackContext) {
      this.playbackContext.close()
      this.playbackContext = null
    }
  }

  // ── Protocol Messages ──────────────────────────────────

  sendJson(type: VoiceMessageType, payload: Record<string, unknown>): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify({ type, payload }))
  }

  sendEndTurn(): void {
    this.sendJson('end_turn', {})
  }

  sendInterrupt(): void {
    this.sendJson('interrupt', {})
    this.stopPlayback()
  }

  updateSettings(settings: VoiceSettings): void {
    this.sendJson('config_update', {
      voiceSettings: {
        tts_voice: settings.ttsVoice,
        tts_speed: settings.ttsSpeed,
        stt_language: settings.sttLanguage,
        enable_interruption: settings.enableInterruption,
        save_transcripts: settings.saveTranscripts,
      },
    })
  }

  // ── Event Subscription ─────────────────────────────────

  onJsonMessage(handler: JsonMessageHandler): () => void {
    this.jsonHandlers.push(handler)
    return () => { this.jsonHandlers = this.jsonHandlers.filter((h) => h !== handler) }
  }

  onAudioChunk(handler: AudioChunkHandler): () => void {
    this.audioHandlers.push(handler)
    return () => { this.audioHandlers = this.audioHandlers.filter((h) => h !== handler) }
  }

  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.push(handler)
    return () => { this.connectHandlers = this.connectHandlers.filter((h) => h !== handler) }
  }

  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.push(handler)
    return () => { this.disconnectHandlers = this.disconnectHandlers.filter((h) => h !== handler) }
  }

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.push(handler)
    return () => { this.errorHandlers = this.errorHandlers.filter((h) => h !== handler) }
  }

  onAudioLevel(handler: AudioLevelHandler): () => void {
    this.audioLevelHandlers.push(handler)
    return () => { this.audioLevelHandlers = this.audioLevelHandlers.filter((h) => h !== handler) }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

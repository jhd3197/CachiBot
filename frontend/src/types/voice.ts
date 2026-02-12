/** Voice channel protocol types. */

export type VoiceMessageType =
  // Client -> Server
  | 'voice_start'
  | 'end_turn'
  | 'interrupt'
  | 'mute'
  | 'unmute'
  | 'config_update'
  // Server -> Client
  | 'session_ready'
  | 'transcribing'
  | 'transcript'
  | 'thinking'
  | 'tool_start'
  | 'tool_end'
  | 'audio_start'
  | 'audio_end'
  | 'turn_complete'
  | 'error'

export interface VoiceControlMessage {
  type: VoiceMessageType
  payload: Record<string, unknown>
}

export interface VoiceSettings {
  ttsVoice: string
  ttsSpeed: number
  sttLanguage: string | null
  enableInterruption: boolean
  saveTranscripts: boolean
}

export type VoiceState =
  | 'disconnected'
  | 'connecting'
  | 'idle'
  | 'listening'
  | 'transcribing'
  | 'thinking'
  | 'speaking'

export interface VoiceTranscriptEntry {
  id: string
  role: 'user' | 'assistant'
  text: string
  timestamp: number
}

export interface VoiceToolCall {
  id: string
  tool: string
  args: Record<string, unknown>
  result?: string
}

export const DEFAULT_VOICE_SETTINGS: VoiceSettings = {
  ttsVoice: 'alloy',
  ttsSpeed: 1.0,
  sttLanguage: null,
  enableInterruption: true,
  saveTranscripts: true,
}

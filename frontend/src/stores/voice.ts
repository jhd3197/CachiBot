/**
 * Zustand store for voice channel state.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  VoiceState,
  VoiceSettings,
  VoiceTranscriptEntry,
  VoiceToolCall,
} from '../types/voice'
import { DEFAULT_VOICE_SETTINGS } from '../types/voice'

interface VoiceStore {
  // State
  voiceState: VoiceState
  isMuted: boolean
  pushToTalkMode: boolean
  isHoldingPTT: boolean
  transcripts: VoiceTranscriptEntry[]
  currentThinking: string | null
  activeToolCalls: VoiceToolCall[]
  error: string | null
  audioLevel: number
  voiceSettings: VoiceSettings

  // Actions
  setVoiceState: (state: VoiceState) => void
  setMuted: (muted: boolean) => void
  toggleMute: () => void
  setPushToTalkMode: (ptt: boolean) => void
  togglePTTMode: () => void
  setHoldingPTT: (holding: boolean) => void
  addTranscript: (entry: VoiceTranscriptEntry) => void
  setCurrentThinking: (text: string | null) => void
  addToolCall: (tc: VoiceToolCall) => void
  updateToolCall: (id: string, result: string) => void
  clearActiveToolCalls: () => void
  setError: (error: string | null) => void
  setAudioLevel: (level: number) => void
  clearTranscripts: () => void
  updateVoiceSettings: (settings: Partial<VoiceSettings>) => void
  reset: () => void
}

export const useVoiceStore = create<VoiceStore>()(
  persist(
    (set) => ({
      // Initial state
      voiceState: 'disconnected',
      isMuted: false,
      pushToTalkMode: false,
      isHoldingPTT: false,
      transcripts: [],
      currentThinking: null,
      activeToolCalls: [],
      error: null,
      audioLevel: 0,
      voiceSettings: DEFAULT_VOICE_SETTINGS,

      // Actions
      setVoiceState: (voiceState) => set({ voiceState, error: null }),
      setMuted: (isMuted) => set({ isMuted }),
      toggleMute: () => set((s) => ({ isMuted: !s.isMuted })),
      setPushToTalkMode: (pushToTalkMode) => set({ pushToTalkMode }),
      togglePTTMode: () => set((s) => ({ pushToTalkMode: !s.pushToTalkMode })),
      setHoldingPTT: (isHoldingPTT) => set({ isHoldingPTT }),
      addTranscript: (entry) =>
        set((s) => ({ transcripts: [...s.transcripts, entry] })),
      setCurrentThinking: (currentThinking) => set({ currentThinking }),
      addToolCall: (tc) =>
        set((s) => ({ activeToolCalls: [...s.activeToolCalls, tc] })),
      updateToolCall: (id, result) =>
        set((s) => ({
          activeToolCalls: s.activeToolCalls.map((tc) =>
            tc.id === id ? { ...tc, result } : tc,
          ),
        })),
      clearActiveToolCalls: () => set({ activeToolCalls: [] }),
      setError: (error) => set({ error }),
      setAudioLevel: (audioLevel) => set({ audioLevel }),
      clearTranscripts: () => set({ transcripts: [] }),
      updateVoiceSettings: (partial) =>
        set((s) => ({ voiceSettings: { ...s.voiceSettings, ...partial } })),
      reset: () =>
        set({
          voiceState: 'disconnected',
          isMuted: false,
          isHoldingPTT: false,
          transcripts: [],
          currentThinking: null,
          activeToolCalls: [],
          error: null,
          audioLevel: 0,
        }),
    }),
    {
      name: 'cachibot-voice',
      partialize: (state) => ({
        voiceSettings: state.voiceSettings,
        pushToTalkMode: state.pushToTalkMode,
      }),
    },
  ),
)

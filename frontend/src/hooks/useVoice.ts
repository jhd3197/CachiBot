/**
 * useVoice hook — wires VoiceClient to the Zustand voice store.
 *
 * Provides connect/disconnect/interrupt/endTurn actions and
 * maps voice WebSocket events to store state.
 */

import { useCallback, useEffect, useRef } from 'react'
import { VoiceClient } from '../api/voice-client'
import { useVoiceStore } from '../stores/voice'
import type { VoiceControlMessage } from '../types/voice'
import type { BotCapabilities, BotModels, ToolConfigs } from '../types'

export function useVoice() {
  const clientRef = useRef<VoiceClient | null>(null)
  const store = useVoiceStore()

  // Ensure single client instance
  if (!clientRef.current) {
    clientRef.current = new VoiceClient()
  }
  const client = clientRef.current

  // Wire up event handlers once
  useEffect(() => {
    const unsubConnect = client.onConnect(() => {
      useVoiceStore.getState().setVoiceState('connecting')
    })

    const unsubDisconnect = client.onDisconnect(() => {
      useVoiceStore.getState().setVoiceState('disconnected')
    })

    const unsubError = client.onError((err) => {
      const message = typeof err === 'string' ? err : 'Connection error'
      useVoiceStore.getState().setError(message)
    })

    const unsubAudioLevel = client.onAudioLevel((level) => {
      useVoiceStore.getState().setAudioLevel(level)
    })

    // Handle JSON control messages from server
    const unsubJson = client.onJsonMessage((msg: VoiceControlMessage) => {
      const s = useVoiceStore.getState()

      switch (msg.type) {
        case 'session_ready':
          s.setVoiceState('idle')
          break

        case 'transcribing':
          s.setVoiceState('transcribing')
          break

        case 'transcript': {
          const role = (msg.payload.role as 'user' | 'assistant') || 'user'
          s.addTranscript({
            id: crypto.randomUUID(),
            role,
            text: msg.payload.text as string,
            timestamp: Date.now(),
          })
          if (role === 'user') {
            s.setVoiceState('thinking')
          }
          break
        }

        case 'thinking':
          s.setCurrentThinking(msg.payload.content as string)
          break

        case 'tool_start':
          s.addToolCall({
            id: msg.payload.id as string,
            tool: msg.payload.tool as string,
            args: (msg.payload.args as Record<string, unknown>) || {},
          })
          break

        case 'tool_end':
          s.updateToolCall(
            msg.payload.id as string,
            msg.payload.result as string,
          )
          break

        case 'audio_start':
          s.setVoiceState('speaking')
          break

        case 'audio_end':
          // Audio finished, stay in speaking until turn_complete
          break

        case 'turn_complete':
          s.setCurrentThinking(null)
          s.clearActiveToolCalls()
          s.setVoiceState('idle')
          // Auto-start listening if not muted
          if (!useVoiceStore.getState().isMuted) {
            s.setVoiceState('listening')
          }
          break

        case 'error':
          s.setError(msg.payload.message as string)
          // Recover to idle if we were in a transient state
          if (['transcribing', 'thinking', 'speaking'].includes(s.voiceState)) {
            s.setVoiceState('idle')
          }
          break
      }
    })

    // Handle binary audio chunks — PCM playback
    const unsubAudio = client.onAudioChunk((chunk) => {
      client.playPCMChunk(chunk)
    })

    return () => {
      unsubConnect()
      unsubDisconnect()
      unsubError()
      unsubAudioLevel()
      unsubJson()
      unsubAudio()
    }
  }, [client])

  const connect = useCallback(
    async (
      botId: string,
      chatId: string | null,
      options?: {
        systemPrompt?: string
        models?: BotModels
        capabilities?: BotCapabilities
        toolConfigs?: ToolConfigs
      },
    ) => {
      const s = useVoiceStore.getState()
      s.setVoiceState('connecting')
      s.setError(null)

      await client.connect(botId, chatId, {
        ...options,
        voiceSettings: s.voiceSettings,
      })

      // Start microphone
      await client.startMic()

      // Start VAD if not in PTT mode
      if (!useVoiceStore.getState().pushToTalkMode) {
        client.startVAD(() => {
          // On speech end, send end_turn
          client.sendEndTurn()
        })
        useVoiceStore.getState().setVoiceState('listening')
      }
    },
    [client],
  )

  const disconnect = useCallback(() => {
    client.disconnect()
    useVoiceStore.getState().reset()
  }, [client])

  const toggleMute = useCallback(() => {
    const s = useVoiceStore.getState()
    const newMuted = !s.isMuted
    s.setMuted(newMuted)
    client.setMuted(newMuted)
  }, [client])

  const endTurn = useCallback(() => {
    client.sendEndTurn()
  }, [client])

  const interrupt = useCallback(() => {
    client.sendInterrupt()
    const s = useVoiceStore.getState()
    s.setVoiceState('idle')
  }, [client])

  const startPTT = useCallback(() => {
    useVoiceStore.getState().setHoldingPTT(true)
    useVoiceStore.getState().setVoiceState('listening')
  }, [])

  const stopPTT = useCallback(() => {
    useVoiceStore.getState().setHoldingPTT(false)
    client.sendEndTurn()
  }, [client])

  // When PTT mode toggled, start/stop VAD
  useEffect(() => {
    if (store.voiceState === 'disconnected' || store.voiceState === 'connecting') return

    if (store.pushToTalkMode) {
      client.stopVAD()
    } else {
      client.startVAD(() => {
        client.sendEndTurn()
      })
      if (store.voiceState === 'idle') {
        useVoiceStore.getState().setVoiceState('listening')
      }
    }
  }, [store.pushToTalkMode, client, store.voiceState])

  return {
    // State (from store)
    voiceState: store.voiceState,
    isMuted: store.isMuted,
    pushToTalkMode: store.pushToTalkMode,
    isHoldingPTT: store.isHoldingPTT,
    transcripts: store.transcripts,
    currentThinking: store.currentThinking,
    activeToolCalls: store.activeToolCalls,
    error: store.error,
    audioLevel: store.audioLevel,
    voiceSettings: store.voiceSettings,

    // Actions
    connect,
    disconnect,
    toggleMute,
    endTurn,
    interrupt,
    startPTT,
    stopPTT,
    togglePTTMode: store.togglePTTMode,
    clearTranscripts: store.clearTranscripts,
    updateVoiceSettings: store.updateVoiceSettings,
  }
}

/**
 * VoiceView — Full-screen voice call experience.
 *
 * Shows waveform visualization, live transcripts, tool call indicators,
 * and voice controls (connect, mute, PTT, interrupt, settings).
 */

import { useEffect, useRef, useCallback } from 'react'
import {
  Phone,
  PhoneOff,
  Mic,
  MicOff,
  Ear,
  Hand,
  VolumeX,
  Loader2,
  AlertCircle,
  Wrench,
} from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { useChatStore } from '../../stores/bots'
import { useVoice } from '../../hooks/useVoice'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'
import { getEffectiveModels } from '../../stores/bots'
import type { VoiceState } from '../../types/voice'

const STATE_LABELS: Record<VoiceState, string> = {
  disconnected: 'Disconnected',
  connecting: 'Connecting...',
  idle: 'Ready',
  listening: 'Listening...',
  transcribing: 'Transcribing...',
  thinking: 'Thinking...',
  speaking: 'Speaking...',
}

const STATE_COLORS: Record<VoiceState, string> = {
  disconnected: 'text-[var(--color-text-secondary)]',
  connecting: 'text-yellow-400',
  idle: 'text-green-400',
  listening: 'text-blue-400',
  transcribing: 'text-purple-400',
  thinking: 'text-amber-400',
  speaking: 'text-emerald-400',
}

export function VoiceView() {
  const { getActiveBot } = useBotStore()
  const { activeChatId } = useChatStore()
  const activeBot = getActiveBot()

  const {
    voiceState,
    isMuted,
    pushToTalkMode,
    isHoldingPTT,
    transcripts,
    currentThinking,
    activeToolCalls,
    error,
    audioLevel,
    connect,
    disconnect,
    toggleMute,
    interrupt,
    startPTT,
    stopPTT,
    togglePTTMode,
    clearTranscripts,
  } = useVoice()

  const transcriptEndRef = useRef<HTMLDivElement>(null)
  const canvasRef = useRef<HTMLCanvasElement>(null)
  const animFrameRef = useRef<number>(0)

  // Auto-scroll transcripts
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcripts.length])

  // Waveform visualization
  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    const draw = () => {
      const w = canvas.width
      const h = canvas.height
      ctx.clearRect(0, 0, w, h)

      // Draw waveform based on audio level
      const level = audioLevel
      const isActive = ['listening', 'speaking'].includes(voiceState)

      ctx.lineWidth = 2
      ctx.strokeStyle = voiceState === 'speaking'
        ? '#34d399' // emerald-400
        : voiceState === 'listening'
          ? '#60a5fa' // blue-400
          : '#52525b' // zinc-600

      ctx.beginPath()
      const segments = 64
      for (let i = 0; i <= segments; i++) {
        const x = (i / segments) * w
        const amplitude = isActive ? level * h * 3 : 2
        const frequency = isActive ? 3 + level * 8 : 2
        const y = h / 2 + Math.sin((i / segments) * Math.PI * frequency + Date.now() / 300) * amplitude
        if (i === 0) ctx.moveTo(x, y)
        else ctx.lineTo(x, y)
      }
      ctx.stroke()

      animFrameRef.current = requestAnimationFrame(draw)
    }

    // Size canvas
    const resizeCanvas = () => {
      const rect = canvas.parentElement?.getBoundingClientRect()
      if (rect) {
        canvas.width = rect.width
        canvas.height = rect.height
      }
    }
    resizeCanvas()
    window.addEventListener('resize', resizeCanvas)

    draw()

    return () => {
      cancelAnimationFrame(animFrameRef.current)
      window.removeEventListener('resize', resizeCanvas)
    }
  }, [audioLevel, voiceState])

  // Push-to-talk keyboard handler
  useEffect(() => {
    if (!pushToTalkMode || voiceState === 'disconnected') return

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.code === 'Space' && !e.repeat && !isHoldingPTT) {
        e.preventDefault()
        startPTT()
      }
    }

    const onKeyUp = (e: KeyboardEvent) => {
      if (e.code === 'Space' && isHoldingPTT) {
        e.preventDefault()
        stopPTT()
      }
    }

    window.addEventListener('keydown', onKeyDown)
    window.addEventListener('keyup', onKeyUp)
    return () => {
      window.removeEventListener('keydown', onKeyDown)
      window.removeEventListener('keyup', onKeyUp)
    }
  }, [pushToTalkMode, voiceState, isHoldingPTT, startPTT, stopPTT])

  const handleConnect = useCallback(() => {
    if (!activeBot) return
    const models = getEffectiveModels(activeBot)
    connect(activeBot.id, activeChatId, {
      systemPrompt: activeBot.systemPrompt,
      models,
      capabilities: activeBot.capabilities,
      toolConfigs: activeBot.toolConfigs,
    })
  }, [activeBot, activeChatId, connect])

  if (!activeBot) {
    return (
      <div className="flex h-full items-center justify-center text-[var(--color-text-secondary)]">
        No bot selected
      </div>
    )
  }

  const isConnected = voiceState !== 'disconnected' && voiceState !== 'connecting'
  const isBotSpeaking = voiceState === 'speaking'

  return (
    <div className="flex h-full flex-col bg-zinc-50 dark:bg-[var(--color-bg-app)]">
      {/* Header */}
      <div className="flex items-center gap-3 border-b border-zinc-200 px-6 py-4 dark:border-[var(--color-border-primary)]">
        <div
          className="flex h-10 w-10 items-center justify-center rounded-xl"
          style={{ backgroundColor: activeBot.color + '20' }}
        >
          <BotIconRenderer icon={activeBot.icon} size={22} />
        </div>
        <div className="flex-1">
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">
            {activeBot.name}
          </h2>
          <div className="flex items-center gap-2">
            <span className={cn('text-xs font-medium', STATE_COLORS[voiceState])}>
              {STATE_LABELS[voiceState]}
            </span>
            {voiceState === 'connecting' && <Loader2 className="h-3 w-3 animate-spin text-yellow-400" />}
          </div>
        </div>
        {transcripts.length > 0 && isConnected && (
          <button
            onClick={clearTranscripts}
            className="rounded-lg px-3 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:bg-zinc-200 hover:text-zinc-700 dark:hover:bg-[var(--color-hover-bg)] dark:hover:text-[var(--color-text-primary)]"
          >
            Clear
          </button>
        )}
      </div>

      {/* Transcript area */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {transcripts.length === 0 ? (
          <div className="flex h-full flex-col items-center justify-center gap-3 text-[var(--color-text-secondary)]">
            {isConnected ? (
              <>
                <Mic className="h-8 w-8 opacity-50" />
                <p className="text-sm">
                  {pushToTalkMode ? 'Hold Space to talk' : 'Start speaking...'}
                </p>
              </>
            ) : (
              <>
                <Phone className="h-8 w-8 opacity-50" />
                <p className="text-sm">Connect to start a voice conversation</p>
              </>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {transcripts.map((entry) => (
              <div
                key={entry.id}
                className={cn(
                  'flex gap-3',
                  entry.role === 'user' ? 'justify-end' : 'justify-start',
                )}
              >
                <div
                  className={cn(
                    'max-w-[80%] rounded-2xl px-4 py-2.5',
                    entry.role === 'user'
                      ? 'bg-accent-600 text-white'
                      : 'bg-zinc-200 text-zinc-900 dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-primary)]',
                  )}
                >
                  <p className="text-sm leading-relaxed">{entry.text}</p>
                  <p className="mt-1 text-[10px] opacity-60">
                    {new Date(entry.timestamp).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            ))}

            {/* Active tool calls */}
            {activeToolCalls.length > 0 && (
              <div className="flex items-center gap-2 text-xs text-amber-400">
                <Wrench className="h-3.5 w-3.5 animate-spin" />
                <span>
                  Using {activeToolCalls[activeToolCalls.length - 1].tool}...
                </span>
              </div>
            )}

            {/* Thinking indicator */}
            {currentThinking && (
              <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
                <span className="italic">Thinking...</span>
              </div>
            )}

            <div ref={transcriptEndRef} />
          </div>
        )}
      </div>

      {/* Error banner */}
      {error && (
        <div className="mx-6 mb-2 flex items-center gap-2 rounded-lg bg-red-500/10 px-4 py-2 text-sm text-red-400">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span className="flex-1">{error}</span>
        </div>
      )}

      {/* Waveform visualizer */}
      <div className="mx-6 h-16 overflow-hidden rounded-xl bg-zinc-100 dark:bg-[var(--color-bg-primary)]/50">
        <canvas ref={canvasRef} className="h-full w-full" />
      </div>

      {/* PTT indicator */}
      {pushToTalkMode && isConnected && (
        <div className="py-2 text-center text-xs text-[var(--color-text-secondary)]">
          {isHoldingPTT ? (
            <span className="font-medium text-blue-400">Recording...</span>
          ) : (
            'Hold Space to talk'
          )}
        </div>
      )}

      {/* Controls bar */}
      <div className="flex items-center justify-center gap-3 border-t border-zinc-200 px-6 py-5 dark:border-[var(--color-border-primary)]">
        {/* Mute button */}
        {isConnected && (
          <button
            onClick={toggleMute}
            className={cn(
              'flex h-12 w-12 items-center justify-center rounded-full transition-all',
              isMuted
                ? 'bg-red-500/20 text-red-400 hover:bg-red-500/30'
                : 'bg-zinc-200 text-[var(--color-text-tertiary)] hover:bg-zinc-300 dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-secondary)] dark:hover:bg-[var(--color-hover-bg)]',
            )}
            title={isMuted ? 'Unmute' : 'Mute'}
          >
            {isMuted ? <MicOff className="h-5 w-5" /> : <Mic className="h-5 w-5" />}
          </button>
        )}

        {/* Connect / Disconnect button */}
        <button
          onClick={isConnected ? disconnect : handleConnect}
          className={cn(
            'flex h-14 w-14 items-center justify-center rounded-full transition-all',
            isConnected
              ? 'bg-red-500 text-white hover:bg-red-600'
              : 'bg-green-500 text-white hover:bg-green-600',
            voiceState === 'connecting' && 'animate-pulse',
          )}
          title={isConnected ? 'Disconnect' : 'Connect'}
        >
          {isConnected ? (
            <PhoneOff className="h-6 w-6" />
          ) : voiceState === 'connecting' ? (
            <Loader2 className="h-6 w-6 animate-spin" />
          ) : (
            <Phone className="h-6 w-6" />
          )}
        </button>

        {/* Mode toggle (VAD/PTT) */}
        {isConnected && (
          <button
            onClick={togglePTTMode}
            className={cn(
              'flex h-12 w-12 items-center justify-center rounded-full transition-all',
              'bg-zinc-200 text-[var(--color-text-tertiary)] hover:bg-zinc-300 dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-secondary)] dark:hover:bg-[var(--color-hover-bg)]',
            )}
            title={pushToTalkMode ? 'Switch to auto-detect (VAD)' : 'Switch to push-to-talk'}
          >
            {pushToTalkMode ? <Hand className="h-5 w-5" /> : <Ear className="h-5 w-5" />}
          </button>
        )}

        {/* Interrupt button */}
        {isBotSpeaking && (
          <button
            onClick={interrupt}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/20 text-amber-400 transition-all hover:bg-amber-500/30"
            title="Interrupt"
          >
            <VolumeX className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  )
}

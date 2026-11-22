import { useEffect, useRef } from 'react'
import { Mic, MicOff } from 'lucide-react'
import { useVoice } from '../../hooks/useVoice'
import { getEffectiveModels } from '../../stores/bots'
import { BotAvatar } from '../common/Avatar'
import { cn } from '../../lib/utils'
import type { Bot } from '../../types'

interface VoiceModeProps {
  bot: Bot
  /** Creates the chat when none exists yet, so transcripts have somewhere to save */
  ensureChat: () => string | null
  onExit: () => void
}

// Fixed bar pattern (design 15 waveform) scaled by the live audio level
const BAR_HEIGHTS = [6, 12, 20, 28, 18, 32, 24, 14, 26, 10, 22, 30, 16, 8, 20, 12]

/**
 * Voice mode in the chat (design view 15). Reuses the existing voice
 * pipeline (useVoice → VoiceClient WS, VAD, STT → agent → TTS); the server
 * saves both sides of each turn into this chat as normal text messages
 * (voice pipeline save_transcripts), so the transcript lines here and the
 * saved chat messages are the same real data.
 */
export function VoiceMode({ bot, ensureChat, onExit }: VoiceModeProps) {
  const {
    voiceState,
    isMuted,
    transcripts,
    error,
    audioLevel,
    connect,
    disconnect,
    toggleMute,
    interrupt,
  } = useVoice()

  const transcriptEndRef = useRef<HTMLDivElement>(null)
  const chatIdRef = useRef<string | null>(null)

  // Enter voice: make sure the chat exists (transcripts save into it), then
  // connect the voice channel with the bot's real configuration.
  useEffect(() => {
    chatIdRef.current = ensureChat()
    connect(bot.id, chatIdRef.current, {
      systemPrompt: bot.systemPrompt,
      models: getEffectiveModels(bot),
      capabilities: bot.capabilities,
      toolConfigs: bot.toolConfigs,
    })
    return () => disconnect()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [bot.id])

  // Follow the transcript as lines arrive
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcripts.length])

  const active = voiceState === 'listening' || voiceState === 'speaking'

  const statusLine = (() => {
    if (error) return error
    switch (voiceState) {
      case 'connecting':
      case 'disconnected':
        return 'Connecting…'
      case 'listening':
        return 'Listening · just start speaking'
      case 'transcribing':
        return 'Transcribing…'
      case 'thinking':
        return `${bot.name} is thinking…`
      case 'speaking':
        return `${bot.name} is talking · tap Interrupt or just start speaking`
      default:
        return 'Connected · just start speaking'
    }
  })()

  return (
    <div className="v2-voice">
      <div className="v2-voice__stage">
        <span
          className={cn('v2-voice__avatar', active && 'v2-voice__avatar--active')}
          style={{ ['--v2-voice-ring' as string]: bot.color }}
        >
          <BotAvatar color={bot.color} name={bot.name} size={112} />
        </span>
        <span className={cn('v2-voice__status', error && 'v2-voice__status--error')}>
          {statusLine}
        </span>
        {transcripts.length > 0 && (
          <div className="v2-voice__transcript">
            {transcripts.map((entry) =>
              entry.role === 'user' ? (
                <p key={entry.id} className="v2-voice__line v2-voice__line--you">
                  <b>You</b> {entry.text}
                </p>
              ) : (
                <p key={entry.id} className="v2-voice__line v2-voice__line--bot">
                  <b>{bot.name}</b> {entry.text}
                </p>
              )
            )}
            <div ref={transcriptEndRef} />
          </div>
        )}
      </div>

      <div className="v2-voice__bar-wrap">
        <div className="v2-voice__bar">
          <button
            type="button"
            className={cn('v2-voice__mic', isMuted && 'v2-voice__mic--muted')}
            aria-label={isMuted ? 'Unmute your mic' : 'Mute your mic'}
            title={isMuted ? 'Unmute your mic' : 'Mute your mic'}
            onClick={toggleMute}
          >
            {isMuted ? <MicOff size={18} strokeWidth={1.8} /> : <Mic size={18} strokeWidth={1.8} />}
          </button>
          <span className="v2-voice__wave" aria-hidden="true">
            {BAR_HEIGHTS.map((h, i) => (
              <span
                key={i}
                style={{
                  height: active ? Math.max(3, h * (0.35 + audioLevel * 2.5)) : 3,
                }}
              />
            ))}
          </span>
          <span className="v2-voice__note">Everything said is saved here as text</span>
          <span className="v2-voice__actions">
            {voiceState === 'speaking' && (
              <button type="button" className="v2-voice__interrupt" onClick={interrupt}>
                Interrupt
              </button>
            )}
            <button type="button" className="v2-voice__back" onClick={onExit}>
              Back to typing
            </button>
          </span>
        </div>
      </div>
    </div>
  )
}

/**
 * ComputerStateCard — the 16:10 computer card in the states of designs
 * 09 (off / first use), 11 (asleep), 04 (awake, working) and 08 (needs
 * you / you're driving). Every state renders only what the service really
 * reports; control buttons require operator+ (callers gate them).
 */

import { Maximize2 } from 'lucide-react'
import { BotAvatar } from '../common/Avatar'
import { Spinner } from '../common/Spinner'
import type { Bot, BotComputer } from '../../types'
import { computerStateLabel } from './utils'
import { cn } from '../../lib/utils'

interface ComputerStateCardProps {
  bot: Bot
  computer: BotComputer | undefined
  /** Live preview object URL (only set while the computer is awake). */
  previewUrl: string | null
  /** Operator+ affordances; null/undefined hides the control. */
  canOperate: boolean
  onTurnOn?: () => void
  onWake?: () => void
  /** Opens the full-window surface (design 05). */
  onOpen?: () => void
  /** A wake/turn-on request is in flight. */
  pending?: boolean
}

export function ComputerStateCard({
  bot,
  computer,
  previewUrl,
  canOperate,
  onTurnOn,
  onWake,
  onOpen,
  pending,
}: ComputerStateCardProps) {
  const state = computer?.state
  const driving = !!computer?.driver
  const needsYou = state === 'needs_you'
  const showPreview = (state === 'awake' || needsYou) && previewUrl

  return (
    <div
      className={cn(
        'computer-card',
        needsYou && 'computer-card--needs-you',
        showPreview && onOpen && 'computer-card--clickable'
      )}
      role={onOpen && (state === 'awake' || needsYou) ? 'button' : undefined}
      tabIndex={onOpen && (state === 'awake' || needsYou) ? 0 : undefined}
      aria-label={onOpen && (state === 'awake' || needsYou) ? 'Open the computer' : undefined}
      onClick={onOpen && (state === 'awake' || needsYou) ? onOpen : undefined}
      onKeyDown={
        onOpen && (state === 'awake' || needsYou)
          ? (e) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault()
                onOpen()
              }
            }
          : undefined
      }
    >
      {showPreview ? (
        <>
          <img className="computer-card__frame" src={previewUrl} alt="" draggable={false} />
          {needsYou && <span className="computer-card__pill computer-card__pill--amber">Needs you</span>}
          {driving && (
            <span className="computer-card__pill computer-card__pill--amber">You're driving</span>
          )}
          {onOpen && (
            <span className="computer-card__open">
              <Maximize2 size={12} strokeWidth={1.8} />
              Open
            </span>
          )}
        </>
      ) : (
        <div className="computer-card__idle">
          {state === 'building' || state === 'starting' ? (
            <>
              <Spinner size="md" />
              <span className="computer-card__idle-label">
                {state === 'building' ? 'Building…' : 'Starting…'}
              </span>
              {state === 'building' && computer?.build?.line && (
                <span className="computer-card__idle-line" title={computer.build.line}>
                  {computer.build.step != null && computer.build.total != null
                    ? `${computer.build.step}/${computer.build.total} · `
                    : ''}
                  {computer.build.line}
                </span>
              )}
              {state === 'building' && computer?.build?.status === 'failed' && computer.lastError && (
                <span className="computer-card__idle-line">{computer.lastError}</span>
              )}
            </>
          ) : (
            <>
              <span className="computer-card__idle-avatar" aria-hidden="true">
                <BotAvatar color={bot.color} name={bot.name} size={40} />
              </span>
              <span className="computer-card__idle-label">{computerStateLabel(state) || 'Off'}</span>
              {state === 'off' && canOperate && (
                <button
                  type="button"
                  className="computer-card__btn computer-card__btn--primary"
                  disabled={pending}
                  onClick={(e) => {
                    e.stopPropagation()
                    onTurnOn?.()
                  }}
                >
                  {pending ? 'Turning on…' : 'Turn on'}
                </button>
              )}
              {state === 'asleep' && canOperate && (
                <button
                  type="button"
                  className="computer-card__btn"
                  disabled={pending}
                  onClick={(e) => {
                    e.stopPropagation()
                    onWake?.()
                  }}
                >
                  {pending ? 'Waking…' : 'Wake'}
                </button>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}

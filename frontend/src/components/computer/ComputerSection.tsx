/**
 * ComputerSection — the design-04 computer panel next to the chat (and the
 * inspector's Computer block): the live state card, the one-line activity,
 * the open-windows list, and the take-over / hand-back controls (operator+;
 * viewers get the text without control buttons).
 *
 * Everything is real C2 state: the activity line from `computer.activity`,
 * the windows from the store's `windowsByBot`, the driver from
 * `computer.driver`. Nothing here wakes the computer — the preview hook
 * heartbeats while mounted, which is what watching does.
 */

import { useEffect } from 'react'
import {
  AppWindow,
  Globe,
  Hand,
  Terminal as TerminalIcon,
  FileText,
  Square,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useComputerStore } from '../../stores/computer'
import { useComputerPreview } from '../../hooks/useComputerPreview'
import { ComputerStateCard } from './ComputerStateCard'
import { Spinner } from '../common/Spinner'
import type { Bot, BotComputer, ComputerWindow } from '../../types'
import { cn } from '../../lib/utils'

function windowIcon(kind: string) {
  switch (kind) {
    case 'web':
      return Globe
    case 'terminal':
      return TerminalIcon
    case 'editor':
      return FileText
    default:
      return AppWindow
  }
}

interface ComputerSectionProps {
  bot: Bot
  canOperate: boolean
  userId: string | undefined
  /** Selected window in the full-window surface (highlighted here). */
  selectedWindowId?: string | null
  /** Compact card only (the inspector); the chat also shows activity/windows. */
  compact?: boolean
}

export function ComputerSection({ bot, canOperate, userId, selectedWindowId, compact }: ComputerSectionProps) {
  const navigate = useNavigate()
  const status = useComputerStore((s) => s.status)
  const computer = useComputerStore((s) => s.byBot[bot.id])
  const windows = useComputerStore((s) => s.windowsByBot[bot.id])
  const { previewUrl } = useComputerPreview(
    status?.available ? bot.id : null,
    selectedWindowId ?? null
  )

  const state = computer?.state
  const live = state === 'awake' || state === 'needs_you'

  useEffect(() => {
    if (!status?.available) return
    void useComputerStore.getState().ensureForBot(bot.id)
    void useComputerStore.getState().fetchViews(bot.id)
  }, [status?.available, bot.id])

  // Keep the window list fresh while the computer works (windows count from
  // the WS is the signal that the list changed).
  const windowsCount = computer?.windowsCount ?? 0
  useEffect(() => {
    if (!status?.available || !live) return
    void useComputerStore.getState().fetchViews(bot.id)
  }, [status?.available, live, windowsCount, bot.id])

  if (!status?.available) return null

  const openFull = (windowId?: string | null) =>
    navigate(windowId ? `/${bot.id}/computer?view=${windowId}` : `/${bot.id}/computer`)

  return (
    <div className="computer-section" data-testid="computer-section">
      <ComputerStateCard
        bot={bot}
        computer={computer}
        previewUrl={previewUrl}
        canOperate={canOperate}
        onTurnOn={() => void useComputerStore.getState().wake(bot.id)}
        onWake={() => void useComputerStore.getState().wake(bot.id)}
        onOpen={() => openFull(selectedWindowId)}
      />
      {!compact && <ActivityRow bot={bot} computer={computer} canOperate={canOperate} userId={userId} />}
      {!compact && live && windows && windows.length > 0 && (
        <div className="computer-section__windows">
          {windows.map((w) => (
            <WindowRow
              key={w.id}
              window={w}
              selected={w.id === selectedWindowId}
              onOpen={() => openFull(w.id)}
            />
          ))}
        </div>
      )}
    </div>
  )
}

function ActivityRow({
  bot,
  computer,
  canOperate,
  userId,
}: {
  bot: Bot
  computer: BotComputer | undefined
  canOperate: boolean
  userId: string | undefined
}) {
  const drivingMe = !!computer?.driver && computer.driver.userId === userId
  const drivingOther = !!computer?.driver && computer.driver.userId !== userId

  const handBack = () => void useComputerStore.getState().handback(bot.id)
  const takeOver = () => void useComputerStore.getState().respondNeedsYou(bot.id, 'takeover')
  const stop = () => void useComputerStore.getState().stop(bot.id)

  if (drivingMe) {
    return (
      <div className="computer-activity computer-activity--driving">
        <Hand size={14} strokeWidth={1.8} />
        <span className="computer-activity__text">You have control</span>
        {canOperate && (
          <button type="button" className="computer-activity__btn" onClick={handBack}>
            Hand back
          </button>
        )}
      </div>
    )
  }
  if (computer?.state === 'needs_you') {
    return (
      <div className="computer-activity computer-activity--needs-you">
        <Hand size={14} strokeWidth={1.8} />
        <span className="computer-activity__text" title={computer.needsYou ?? ''}>
          {computer.needsYou || 'Needs you'}
        </span>
        {canOperate && (
          <button type="button" className="computer-activity__btn" onClick={takeOver}>
            Take over
          </button>
        )}
      </div>
    )
  }
  if (drivingOther) {
    return (
      <div className="computer-activity">
        <span className="computer-activity__text">
          {computer?.driver?.name ?? 'Someone'} is driving
        </span>
      </div>
    )
  }
  if (computer?.activity?.text) {
    return (
      <div className="computer-activity">
        <Spinner size="sm" label="" aria-hidden="true" />
        <span className="computer-activity__text">{computer.activity.text}</span>
        {canOperate && (
          <button
            type="button"
            className="computer-activity__btn"
            title="Stop the computer"
            onClick={stop}
          >
            <Square size={10} strokeWidth={2} />
            Stop
          </button>
        )}
      </div>
    )
  }
  return null
}

function WindowRow({
  window: w,
  selected,
  onOpen,
}: {
  window: ComputerWindow
  selected: boolean
  onOpen: () => void
}) {
  const Icon = windowIcon(w.kind)
  return (
    <button
      type="button"
      className={cn('computer-window', selected && 'computer-window--selected')}
      onClick={onOpen}
    >
      <Icon size={15} strokeWidth={1.8} />
      <span className="computer-window__texts">
        <span className="computer-window__app">{w.app}</span>
        <span className="computer-window__title" title={w.title}>
          {w.title}
        </span>
      </span>
    </button>
  )
}

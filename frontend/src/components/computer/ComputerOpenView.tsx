/**
 * ComputerOpenView — the bot's computer full window (design 05): the live
 * desktop preview, or one selected window's frame full size (the browser /
 * terminal presentations of designs 06/07 — real frames only, never a faked
 * page). Vela's own top bar is mirrored with real C2 state: who is driving,
 * Take over / Hand back (operator+; hidden for viewers) and Stop.
 *
 * Take-over (design 08): while the current user holds the lease, pointer
 * input on the selected window's frame is forwarded through the C2 input
 * API (bounds-validated on the server). The desktop preview itself is
 * watch-only — input targets one window, so a window must be picked first;
 * that hint is shown instead of pretending the click landed.
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { X, Hand, Square, AppWindow, Globe, Terminal as TerminalIcon, FileText } from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { useAuthStore } from '../../stores/auth'
import { useComputerStore } from '../../stores/computer'
import { useBotAccess } from '../../hooks/useBotAccess'
import { useComputerPreview } from '../../hooks/useComputerPreview'
import { sendComputerInput } from '../../api/computer'
import { BotAvatar } from '../common/Avatar'
import { StatusLine } from '../common/StatusLine'
import type { ComputerWindow } from '../../types'
import { cn } from '../../lib/utils'

const NAMED_KEYS: Record<string, string> = {
  Enter: 'enter',
  Tab: 'tab',
  Escape: 'escape',
  Backspace: 'backspace',
  Delete: 'delete',
  ArrowUp: 'arrowup',
  ArrowDown: 'arrowdown',
  ArrowLeft: 'arrowleft',
  ArrowRight: 'arrowright',
  Home: 'home',
  End: 'end',
  PageUp: 'pageup',
  PageDown: 'pagedown',
}

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

export function ComputerOpenView() {
  const { botId } = useParams<{ botId: string }>()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const bot = useBotStore((s) => s.bots.find((b) => b.id === botId))
  const user = useAuthStore((s) => s.user)
  const access = useBotAccess(botId ?? null)
  const status = useComputerStore((s) => s.status)
  const computer = useComputerStore((s) => (botId ? s.byBot[botId] : undefined))
  const windows = useComputerStore((s) => (botId ? s.windowsByBot[botId] : undefined))

  const selectedWindowId = searchParams.get('view')
  const selectedWindow = useMemo(
    () => windows?.find((w) => w.id === selectedWindowId) ?? null,
    [windows, selectedWindowId]
  )
  // A window that is no longer open can't be shown — fall back to the
  // desktop preview instead of polling a gone frame.
  const activeViewId = selectedWindow ? selectedWindowId : null
  const { previewUrl, updatedAt } = useComputerPreview(
    status?.available && botId ? botId : null,
    activeViewId
  )

  const drivingMe = !!computer?.driver && computer.driver.userId === user?.id
  const needsYou = computer?.state === 'needs_you'

  useEffect(() => {
    if (!status?.available || !botId) return
    void useComputerStore.getState().ensureForBot(botId)
    void useComputerStore.getState().fetchViews(botId)
  }, [status?.available, botId])

  const windowsCount = computer?.windowsCount ?? 0
  useEffect(() => {
    if (!status?.available || !botId || computer?.state === 'asleep' || computer?.state === 'off')
      return
    void useComputerStore.getState().fetchViews(botId)
  }, [status?.available, botId, windowsCount, computer?.state])

  if (!bot || !status?.available) return null

  const close = () => navigate(`/${bot.id}/chats`)
  const selectWindow = (id: string | null) =>
    setSearchParams(id ? { view: id } : {}, { replace: true })

  return (
    <div className="computer-open">
      <div className="computer-open__bar">
        <button type="button" className="v2-icon-btn" aria-label="Back to chat" onClick={close}>
          <X size={17} strokeWidth={1.8} />
        </button>
        <span className="computer-open__title">
          <BotAvatar color={bot.color} name={bot.name} size={22} />
          {bot.name}’s computer
        </span>
        <span className="computer-open__chiprow">
          {needsYou ? (
            <span className="computer-open__chip computer-open__chip--amber">Needs you</span>
          ) : drivingMe ? (
            <span className="computer-open__chip computer-open__chip--amber">
              You’re driving · {bot.name} waits
            </span>
          ) : computer?.driver ? (
            <span className="computer-open__chip">{computer.driver.name} is driving</span>
          ) : computer?.state === 'awake' ? (
            <span className="computer-open__chip">{bot.name} is driving</span>
          ) : (
            <span className="computer-open__chip">
              {computer?.state === 'asleep'
                ? 'Asleep'
                : computer?.state === 'building'
                  ? 'Building…'
                  : computer?.state === 'starting'
                    ? 'Starting…'
                    : 'Off'}
            </span>
          )}
          {access.canOperate &&
            (drivingMe ? (
              <button
                type="button"
                className="computer-open__action"
                onClick={() => void useComputerStore.getState().handback(bot.id)}
              >
                Hand back
              </button>
            ) : (
              <button
                type="button"
                className="computer-open__action"
                onClick={() =>
                  needsYou
                    ? void useComputerStore.getState().respondNeedsYou(bot.id, 'takeover')
                    : void useComputerStore.getState().takeover(bot.id)
                }
              >
                Take over
              </button>
            ))}
          {access.canOperate && (computer?.state === 'awake' || needsYou) && (
            <button
              type="button"
              className="computer-open__action computer-open__action--muted"
              onClick={() => void useComputerStore.getState().stop(bot.id)}
            >
              <Square size={11} strokeWidth={2} />
              Stop
            </button>
          )}
        </span>
      </div>

      {needsYou && computer.needsYou && (
        <div className="computer-open__needs-you" role="alert">
          <Hand size={15} strokeWidth={1.8} />
          <span>{computer.needsYou}</span>
          {access.canOperate && (
            <span className="computer-open__needs-you-actions">
              <button
                type="button"
                className="computer-open__action"
                onClick={() => void useComputerStore.getState().respondNeedsYou(bot.id, 'takeover')}
              >
                Take over
              </button>
              <button
                type="button"
                className="computer-open__action computer-open__action--muted"
                onClick={() => void useComputerStore.getState().respondNeedsYou(bot.id, 'skip')}
              >
                Skip this step
              </button>
            </span>
          )}
        </div>
      )}

      <div className="computer-open__stage">
        {(computer?.state === 'awake' || needsYou) && previewUrl ? (
          <DriveableFrame
            botId={bot.id}
            view={selectedWindow}
            url={previewUrl}
            frameAt={updatedAt}
            driving={drivingMe}
          />
        ) : (
          <div className="computer-open__empty">
            <StatusLine pending={computer?.state === 'building' || computer?.state === 'starting'}>
              {computer?.state === 'asleep'
                ? 'The computer is asleep.'
                : computer?.state === 'off'
                  ? 'The computer is off.'
                  : computer?.state === 'building'
                    ? 'Building the computer…'
                    : computer?.state === 'starting'
                      ? 'Starting the computer…'
                      : 'Waiting for the first frame…'}
            </StatusLine>
            {access.canOperate && (computer?.state === 'asleep' || computer?.state === 'off') && (
              <button
                type="button"
                className="computer-open__action"
                onClick={() => void useComputerStore.getState().wake(bot.id)}
              >
                {computer.state === 'asleep' ? 'Wake' : 'Turn on'}
              </button>
            )}
          </div>
        )}
      </div>

      {windows && windows.length > 0 && (
        <div className="computer-open__windows" role="tablist" aria-label="Open windows">
          {windows.map((w) => {
            const Icon = windowIcon(w.kind)
            return (
              <button
                key={w.id}
                type="button"
                role="tab"
                aria-selected={w.id === selectedWindowId}
                className={cn(
                  'computer-open__window',
                  w.id === selectedWindowId && 'computer-open__window--selected'
                )}
                onClick={() => selectWindow(w.id === selectedWindowId ? null : w.id)}
              >
                <Icon size={14} strokeWidth={1.8} />
                <span className="computer-open__window-name">{w.app}</span>
                <span className="computer-open__window-title" title={w.title}>
                  {w.title}
                </span>
              </button>
            )
          })}
        </div>
      )}
    </div>
  )
}

/**
 * The live frame. While the caller holds the take-over, pointer and keyboard
 * input on a *selected window's* frame is forwarded (design 08); the desktop
 * preview without a window stays watch-only and says so.
 */
function DriveableFrame({
  botId,
  view,
  url,
  frameAt,
  driving,
}: {
  botId: string
  view: ComputerWindow | null
  url: string
  frameAt: number | null
  driving: boolean
}) {
  const imgRef = useRef<HTMLImageElement>(null)
  const [typeText, setTypeText] = useState('')

  const send = (input: Parameters<typeof sendComputerInput>[1]) => {
    if (!driving) return
    void sendComputerInput(botId, { frameAt: frameAt ?? undefined, ...input }).catch((err) => {
      toast.error(err instanceof Error ? err.message : 'The computer refused that input')
    })
  }

  const pointOf = (e: { clientX: number; clientY: number }): { x: number; y: number } | null => {
    const img = imgRef.current
    if (!img) return null
    const rect = img.getBoundingClientRect()
    if (rect.width === 0 || rect.height === 0) return null
    // Vela's input space is the window's own pixel space — the frame's
    // natural size is exactly that.
    const x = Math.round(((e.clientX - rect.left) / rect.width) * img.naturalWidth)
    const y = Math.round(((e.clientY - rect.top) / rect.height) * img.naturalHeight)
    if (!Number.isFinite(x) || !Number.isFinite(y) || img.naturalWidth === 0) return null
    return { x, y }
  }

  const inputTarget = view?.id

  const onKeyDown = (e: { key: string; preventDefault: () => void }) => {
    if (!inputTarget) return
    const named = NAMED_KEYS[e.key]
    if (named) {
      e.preventDefault()
      send({ kind: 'key', viewId: inputTarget, key: named })
    }
  }

  return (
    <div
      className={cn('computer-frame', driving && inputTarget && 'computer-frame--driving')}
      tabIndex={driving && inputTarget ? 0 : undefined}
      onKeyDown={driving && inputTarget ? onKeyDown : undefined}
    >
      <img
        ref={imgRef}
        src={url}
        alt={view ? `${view.app} — ${view.title}` : 'The bot’s computer'}
        draggable={false}
        onClick={(e) => {
          if (!inputTarget) return
          const point = pointOf(e)
          if (point) send({ kind: 'click', viewId: inputTarget, point, button: 'left' })
        }}
        onContextMenu={(e) => {
          if (!inputTarget) return
          e.preventDefault()
          const point = pointOf(e)
          if (point) send({ kind: 'click', viewId: inputTarget, point, button: 'right' })
        }}
        onWheel={(e) => {
          if (!inputTarget) return
          send({ kind: 'scroll', viewId: inputTarget, dx: Math.round(e.deltaX), dy: Math.round(e.deltaY) })
        }}
      />
      {driving && !inputTarget && (
        <div className="computer-frame__hint">Pick a window below to click, scroll and type.</div>
      )}
      {driving && inputTarget && (
        <form
          className="computer-frame__type"
          onSubmit={(e) => {
            e.preventDefault()
            if (typeText.trim()) {
              send({ kind: 'type', viewId: inputTarget, text: typeText })
              setTypeText('')
            }
          }}
        >
          <input
            type="text"
            value={typeText}
            onChange={(e) => setTypeText(e.target.value)}
            onKeyDown={(e) => e.stopPropagation()}
            placeholder="Type on the computer · Enter sends"
            aria-label="Type on the computer"
          />
        </form>
      )}
    </div>
  )
}

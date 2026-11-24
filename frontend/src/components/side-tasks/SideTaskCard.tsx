/**
 * Side-task cards (design 11a/11c "States"): one card per side task in the
 * parent chat, plus one card per bot-started helper group. Every state the
 * backend records is rendered from the real record; nothing here is
 * placeholder. Cards open the side task's own chat.
 */

import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Check,
  Clock,
  FileDiff,
  GitBranch,
  Hand,
  Square,
  XCircle,
} from 'lucide-react'
import { useSideTasksStore, sideTaskMayHaveDiff } from '../../stores/side-tasks'
import { SideTaskDiffDialog } from './SideTaskDiffDialog'
import { Spinner } from '../common/Spinner'
import { cn, parseApiDate } from '../../lib/utils'
import type { SideTask, SideTaskStatus } from '../../types'

// Re-render running timers every 30s so "Working · 0:32" stays live.
function useNow(intervalMs = 30000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

/** "0:32" / "1:52" elapsed, from the real startedAt timestamp. */
export function formatElapsed(startedAt: string, now: number): string {
  const secs = Math.max(0, Math.floor((now - parseApiDate(startedAt).getTime()) / 1000))
  const m = Math.floor(secs / 60)
  const s = secs % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

function shortSha(sha: string | null): string | null {
  return sha ? sha.slice(0, 7) : null
}

function filesLabel(files: Array<{ path: string }>): string {
  const n = files.length
  return `${n} ${n === 1 ? 'file' : 'files'} changed`
}

/** Human wording for the recorded needs-you reason. */
function reasonLabel(reason: string | null): string {
  if (!reason) return ''
  if (reason === 'merge_conflict') return 'merge conflict'
  return reason
}

function StatusIcon({ status }: { status: SideTaskStatus }) {
  const cls = 'side-task-card__status-icon'
  switch (status) {
    case 'running':
      return <Spinner size="sm" label="" aria-hidden="true" className={cls} />
    case 'needs_you':
      return <Hand className={cls} strokeWidth={1.8} />
    case 'failed':
      return <XCircle className={cls} strokeWidth={1.8} />
    case 'stopped':
      return <Square className={cls} strokeWidth={1.8} />
    case 'waiting_for_slot':
      return <Clock className={cls} strokeWidth={1.8} />
    default:
      return <Check className={cls} strokeWidth={1.8} />
  }
}

interface StatusLine {
  text: string
  tone?: 'needs-you' | 'failed'
  detail?: string
}

/** Everything the card says about a state, computed from the real record. */
export function sideTaskStatusLine(task: SideTask, now: number): StatusLine {
  switch (task.status) {
    case 'waiting_for_slot':
      return { text: 'Waiting for a slot' }
    case 'running':
      return task.startedAt
        ? { text: `Working · ${formatElapsed(task.startedAt, now)}` }
        : { text: 'Working' }
    case 'needs_you': {
      const reason = reasonLabel(task.needsYouReason)
      const detail =
        task.needsYouReason === 'merge_conflict' && task.conflictFiles.length > 0
          ? task.conflictFiles.join('\n')
          : undefined
      return { text: reason ? `Needs you: ${reason}` : 'Needs you', tone: 'needs-you', detail }
    }
    case 'merged': {
      const commit = shortSha(task.mergedCommit)
      return {
        text: `Brought in · ${filesLabel(task.mergedFiles)}${commit ? ` · ${commit}` : ''}`,
        detail: task.mergedFiles.length > 0 ? task.mergedFiles.map((f) => f.path).join('\n') : undefined,
      }
    }
    case 'done':
      return { text: 'Done · no changes' }
    case 'failed':
      return {
        text: task.error ? `Failed · ${truncateOneLine(task.error, 90)}` : 'Failed',
        tone: 'failed',
      }
    case 'stopped':
      return { text: 'Stopped' }
  }
}

function truncateOneLine(text: string, max: number): string {
  const oneLine = text.replace(/\s+/g, ' ').trim()
  return oneLine.length > max ? `${oneLine.slice(0, max - 1)}…` : oneLine
}

interface SideTaskCardProps {
  task: SideTask
  /** Operator+ sees Retry merge / Discard (the API requires it) */
  canOperate: boolean
  /** Used inside the side task's own chat: no "Open" affordance, not a link */
  hideOpen?: boolean
}

/**
 * One side-task card in the parent chat (design 11a/11c). Yellow border and
 * amber status while it needs you; the conflicting paths and the merge result
 * come from the record itself.
 */
export function SideTaskCard({ task, canOperate, hideOpen }: SideTaskCardProps) {
  const navigate = useNavigate()
  const retryMerge = useSideTasksStore((s) => s.retryMerge)
  const discard = useSideTasksStore((s) => s.discard)
  const [busy, setBusy] = useState(false)
  const [diffOpen, setDiffOpen] = useState(false)
  const now = useNow()

  const line = sideTaskStatusLine(task, now)
  const open = () => {
    if (!hideOpen) navigate(`/${task.botId}/chats/${task.chatId}`)
  }

  const run = async (fn: () => Promise<unknown>, success: string) => {
    if (busy) return
    setBusy(true)
    try {
      await fn()
      toast.success(success)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setBusy(false)
    }
  }

  const isMergeConflict = task.status === 'needs_you' && task.needsYouReason === 'merge_conflict'
  const canDiscard = task.status === 'stopped' || task.status === 'failed' || isMergeConflict

  return (
    <div
      className={cn('side-task-card', task.status === 'needs_you' && 'side-task-card--needs-you')}
      role={hideOpen ? undefined : 'link'}
      tabIndex={hideOpen ? undefined : 0}
      onClick={open}
      onKeyDown={(e) => {
        if (!hideOpen && e.key === 'Enter') open()
      }}
    >
      <span className="side-task-card__tile">
        <GitBranch size={16} strokeWidth={1.8} />
      </span>
      <span className="side-task-card__main">
        <span className="side-task-card__eyebrow">Side task</span>
        <span className="side-task-card__title">{task.title}</span>
        <span
          className={cn(
            'side-task-card__status',
            line.tone === 'needs-you' && 'side-task-card__status--needs-you',
            line.tone === 'failed' && 'side-task-card__status--failed'
          )}
        >
          <StatusIcon status={task.status} />
          <span>{line.text}</span>
        </span>
        {line.detail && <pre className="side-task-card__detail">{line.detail}</pre>}
        {((hideOpen && sideTaskMayHaveDiff(task)) ||
          (canOperate && (isMergeConflict || canDiscard))) && (
          // One actions row: "View changes" (also the mobile home for the
          // diff, since the side-chat header is hidden there) next to
          // Retry merge / Discard.
          <span className="side-task-card__actions" onClick={(e) => e.stopPropagation()}>
            {hideOpen && sideTaskMayHaveDiff(task) && (
              <button type="button" className="v2-mini-btn" onClick={() => setDiffOpen(true)}>
                <FileDiff size={13} strokeWidth={1.8} />
                View changes
              </button>
            )}
            {canOperate && isMergeConflict && (
              <button
                type="button"
                className="v2-mini-btn v2-mini-btn--primary"
                disabled={busy}
                onClick={() => run(() => retryMerge(task.botId, task.id), 'Merge retried')}
              >
                Retry merge
              </button>
            )}
            {canOperate && canDiscard && (
              <button
                type="button"
                className="v2-mini-btn"
                disabled={busy}
                onClick={() => run(() => discard(task.botId, task.id), 'Side task discarded')}
              >
                Discard
              </button>
            )}
          </span>
        )}
      </span>
      {!hideOpen && <span className="side-task-card__open">Open</span>}
      {diffOpen && (
        <SideTaskDiffDialog
          botId={task.botId}
          sideTaskId={task.id}
          title={task.title}
          onClose={() => setDiffOpen(false)}
        />
      )}
    </div>
  )
}

interface SideTaskGroupCardProps {
  title: string | null
  items: SideTask[]
  botName: string
}

/**
 * One helper group card ("3 helpers · started by CachiBot · 1 of 3 done")
 * with a real status row per helper (design 11a/11c). Rows open that
 * helper's chat.
 */
export function SideTaskGroupCard({ title, items, botName }: SideTaskGroupCardProps) {
  const navigate = useNavigate()
  const now = useNow()

  const total = items.length
  const done = items.filter((t) => t.status === 'done' || t.status === 'merged').length
  const needsYou = items.some((t) => t.status === 'needs_you')

  const openTask = (task: SideTask) => navigate(`/${task.botId}/chats/${task.chatId}`)
  // Open the most attention-worthy helper from the header action.
  const headline = (['needs_you', 'failed', 'running', 'waiting_for_slot'] as SideTaskStatus[])
    .map((s) => items.find((t) => t.status === s))
    .find(Boolean)

  return (
    <div className={cn('side-task-group', needsYou && 'side-task-group--needs-you')}>
      <div className="side-task-group__header">
        <GitBranch size={16} strokeWidth={1.8} className="side-task-group__header-icon" />
        <span className="side-task-group__header-title">
          {title ?? `${total} ${total === 1 ? 'helper' : 'helpers'}`}
        </span>
        <span className="side-task-group__header-meta">
          started by {botName} · {done} of {total} done
        </span>
        {headline && (
          <button
            type="button"
            className="side-task-group__header-open"
            onClick={() => openTask(headline)}
          >
            Open
          </button>
        )}
      </div>
      {items.map((task) => {
        const line = sideTaskStatusLine(task, now)
        return (
          <button
            key={task.id}
            type="button"
            className="side-task-group__item"
            onClick={() => openTask(task)}
          >
            <span
              className={cn(
                'side-task-group__item-icon',
                task.status === 'needs_you' && 'side-task-group__item-icon--needs-you',
                task.status === 'failed' && 'side-task-group__item-icon--failed'
              )}
            >
              <StatusIcon status={task.status} />
            </span>
            <span className="side-task-group__item-name">{task.title}</span>
            <span
              className={cn(
                'side-task-group__item-status',
                task.status === 'needs_you' && 'side-task-group__item-status--needs-you',
                task.status === 'failed' && 'side-task-group__item-status--failed'
              )}
            >
              {line.text}
            </span>
          </button>
        )
      })}
    </div>
  )
}

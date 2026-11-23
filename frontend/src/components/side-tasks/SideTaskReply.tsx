/**
 * Side-task thread replies (design 11a "Side-task replies"): the compact
 * WhatsApp/Slack-style reply a side task persists in the parent chat when
 * it settles, plus the quiet one-line indicator shown under the source
 * message while side tasks wait or run. Everything renders from the real
 * record/message metadata; states with no persisted message (waiting,
 * running) never appear here — the indicator covers them.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  Check,
  ChevronDown,
  Clock,
  GitBranch,
  Hand,
  Loader2,
  Reply,
  Square,
  XCircle,
} from 'lucide-react'
import { useSideTasksStore } from '../../stores/side-tasks'
import { useChatStore } from '../../stores/bots'
import { scrollToMessage } from '../chat/MessageBubble'
import { cn } from '../../lib/utils'
import { sideTaskStatusLine } from './SideTaskCard'
import type {
  SideTask,
  SideTaskGroupReplyItem,
  SideTaskGroupReplyMetadata,
  SideTaskReplyMetadata,
  SideTaskStatus,
} from '../../types'

// =============================================================================
// METADATA GUARDS
// =============================================================================

export function sideTaskReplyMetadata(
  metadata: Record<string, unknown> | undefined
): SideTaskReplyMetadata | null {
  if (metadata?.kind === 'side_task_reply') return metadata as unknown as SideTaskReplyMetadata
  return null
}

export function sideTaskGroupReplyMetadata(
  metadata: Record<string, unknown> | undefined
): SideTaskGroupReplyMetadata | null {
  if (metadata?.kind === 'side_task_group_reply') {
    return metadata as unknown as SideTaskGroupReplyMetadata
  }
  return null
}

// =============================================================================
// SHARED BITS
// =============================================================================

function ReplyStatusIcon({ status }: { status: SideTaskStatus | 'settled' }) {
  const cls = 'side-reply__icon'
  switch (status) {
    case 'running':
      return <Loader2 className={cn(cls, 'animate-spin')} strokeWidth={1.8} />
    case 'needs_you':
      return <Hand className={cn(cls, 'side-reply__icon--amber')} strokeWidth={1.8} />
    case 'failed':
      return <XCircle className={cn(cls, 'side-reply__icon--red')} strokeWidth={1.8} />
    case 'stopped':
      return <Square className={cls} strokeWidth={1.8} />
    case 'waiting_for_slot':
      return <Clock className={cls} strokeWidth={1.8} />
    default:
      return <Check className={cls} strokeWidth={1.8} />
  }
}

function shortSha(sha: string | null | undefined): string | null {
  return sha ? sha.slice(0, 7) : null
}

/** The quoted original message; hidden when the source is not loaded. */
function QuotedSource({ chatId, replyToId }: { chatId: string; replyToId: string | null }) {
  const getMessageById = useChatStore((s) => s.getMessageById)
  if (!replyToId) return null
  const source = getMessageById(chatId, replyToId)
  if (!source) return null
  const snippet = source.content.replace(/\s+/g, ' ').trim()
  return (
    <button
      type="button"
      className="side-reply__quote"
      onClick={() => scrollToMessage(source.id)}
      title="Jump to the original message"
    >
      <Reply className="side-reply__quote-icon" strokeWidth={1.8} />
      <span className="side-reply__quote-author">
        {source.role === 'user' ? 'You' : 'Assistant'}
      </span>
      <span className="side-reply__quote-text">
        {snippet.slice(0, 90)}
        {snippet.length > 90 ? '…' : ''}
      </span>
    </button>
  )
}

function ViewThreadLink({ botId, chatId }: { botId: string; chatId: string }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      className="side-reply__thread"
      onClick={() => navigate(`/${botId}/chats/${chatId}`)}
    >
      View thread
    </button>
  )
}

function useRun(fn: () => Promise<unknown>, success: string) {
  const [busy, setBusy] = useState(false)
  const run = async () => {
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
  return { busy, run }
}

// =============================================================================
// SINGLE SIDE-TASK REPLY (kind: side_task_reply)
// =============================================================================

interface SideTaskReplyViewProps {
  metadata: SideTaskReplyMetadata
  content: string
  chatId: string
  replyToId: string | null
  botId: string
  canOperate: boolean
}

export function SideTaskReplyView({
  metadata,
  content,
  chatId,
  replyToId,
  botId,
  canOperate,
}: SideTaskReplyViewProps) {
  const retryMerge = useSideTasksStore((s) => s.retryMerge)
  const discard = useSideTasksStore((s) => s.discard)
  const retry = useRun(() => retryMerge(botId, metadata.sideTaskId), 'Merge retried')
  const drop = useRun(() => discard(botId, metadata.sideTaskId), 'Side task discarded')

  const status = metadata.status
  const isNeedsYou = status === 'needs_you'
  const isMergeConflict = isNeedsYou && metadata.needsYouReason === 'merge_conflict'
  const canDiscard = status === 'stopped' || status === 'failed' || isMergeConflict

  const commit = shortSha(metadata.mergedCommit)
  const fileCount = metadata.mergedFiles?.length ?? 0

  return (
    <div className={cn('side-reply', isNeedsYou && 'side-reply--needs-you')}>
      <QuotedSource chatId={chatId} replyToId={replyToId ?? metadata.replyTo ?? null} />

      <div className="side-reply__head">
        <GitBranch className="side-reply__head-icon" strokeWidth={1.8} />
        <span className="side-reply__eyebrow">Side task</span>
        <span className="side-reply__title">{metadata.title}</span>
        <ReplyStatusIcon status={status} />
      </div>

      {content && <p className="side-reply__summary">{content}</p>}

      {status === 'merged' && fileCount > 0 && (
        <p className="side-reply__meta">
          {fileCount} {fileCount === 1 ? 'file' : 'files'} changed
          {commit ? ` · ${commit}` : ''}
        </p>
      )}
      {status === 'merged' && fileCount === 0 && commit && (
        <p className="side-reply__meta">{commit}</p>
      )}
      {status === 'failed' && metadata.error && (
        <p className="side-reply__meta side-reply__meta--red">{metadata.error}</p>
      )}
      {isNeedsYou && (
        <p className="side-reply__meta side-reply__meta--amber">
          Needs you
          {metadata.needsYouReason === 'merge_conflict'
            ? ': merge conflict'
            : metadata.needsYouReason
              ? `: ${metadata.needsYouReason}`
              : ''}
        </p>
      )}
      {isMergeConflict && metadata.conflictFiles && metadata.conflictFiles.length > 0 && (
        <p className="side-reply__meta">{metadata.conflictFiles.join(' · ')}</p>
      )}
      {status === 'stopped' && <p className="side-reply__meta">Stopped</p>}
      {status === 'done' && <p className="side-reply__meta">Done — no changes to bring back</p>}

      <div className="side-reply__actions">
        <ViewThreadLink botId={botId} chatId={metadata.chatId} />
        {canOperate && isMergeConflict && (
          <button
            type="button"
            className="v2-mini-btn v2-mini-btn--primary"
            disabled={retry.busy}
            onClick={() => void retry.run()}
          >
            Retry merge
          </button>
        )}
        {canOperate && canDiscard && (
          <button
            type="button"
            className="v2-mini-btn"
            disabled={drop.busy}
            onClick={() => void drop.run()}
          >
            Discard
          </button>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// HELPER GROUP REPLY (kind: side_task_group_reply) — updates in place
// =============================================================================

/** Short per-helper status label for the expanded group list. */
function groupItemLabel(status: SideTaskStatus): string {
  switch (status) {
    case 'waiting_for_slot':
      return 'Waiting for a slot'
    case 'running':
      return 'Working'
    case 'needs_you':
      return 'Needs you'
    case 'merged':
      return 'Brought in'
    case 'done':
      return 'Done'
    case 'failed':
      return 'Failed'
    case 'stopped':
      return 'Stopped'
  }
}

function GroupItemRow({ botId, item }: { botId: string; item: SideTaskGroupReplyItem }) {
  const navigate = useNavigate()
  return (
    <button
      type="button"
      className="side-reply__item"
      onClick={() => navigate(`/${botId}/chats/${item.chatId}`)}
    >
      <ReplyStatusIcon status={item.status} />
      <span className="side-reply__item-name">{item.title}</span>
      <span className="side-reply__item-status">{groupItemLabel(item.status)}</span>
    </button>
  )
}

interface SideTaskGroupReplyViewProps {
  metadata: SideTaskGroupReplyMetadata
  content: string
  chatId: string
  replyToId: string | null
  botId: string
}

export function SideTaskGroupReplyView({
  metadata,
  content,
  chatId,
  replyToId,
  botId,
}: SideTaskGroupReplyViewProps) {
  const [expanded, setExpanded] = useState(false)
  const attention = metadata.status === 'needs_you' || metadata.status === 'failed'

  return (
    <div className={cn('side-reply', metadata.status === 'needs_you' && 'side-reply--needs-you')}>
      <QuotedSource chatId={chatId} replyToId={replyToId ?? metadata.replyTo ?? null} />

      <div className="side-reply__head">
        <GitBranch className="side-reply__head-icon" strokeWidth={1.8} />
        <span className="side-reply__eyebrow">Helpers</span>
        <span className="side-reply__title">{metadata.title}</span>
        <ReplyStatusIcon status={metadata.status === 'settled' ? 'done' : metadata.status} />
      </div>

      {content && <p className="side-reply__summary">{content}</p>}

      {attention && (
        <p className={cn('side-reply__meta', metadata.status === 'needs_you' && 'side-reply__meta--amber', metadata.status === 'failed' && 'side-reply__meta--red')}>
          {metadata.status === 'needs_you'
            ? `${metadata.needsYou ?? 1} needs you`
            : `${metadata.failed} failed`}
        </p>
      )}

      <div className="side-reply__actions">
        <ViewThreadLink botId={botId} chatId={metadata.items[0]?.chatId ?? chatId} />
        <button
          type="button"
          className="side-reply__expand"
          aria-expanded={expanded}
          onClick={() => setExpanded(!expanded)}
        >
          {expanded ? 'Hide helpers' : `${metadata.total} helpers`}
          <ChevronDown
            className={cn('side-reply__expand-chevron', expanded && 'side-reply__expand-chevron--open')}
            strokeWidth={1.8}
          />
        </button>
      </div>

      {expanded && (
        <div className="side-reply__items">
          {metadata.items.map((item) => (
            <GroupItemRow key={item.id} botId={botId} item={item} />
          ))}
        </div>
      )}
    </div>
  )
}

// =============================================================================
// QUIET INDICATOR under the source message while side tasks wait or run
// =============================================================================

function useNow(intervalMs = 30000): number {
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), intervalMs)
    return () => window.clearInterval(id)
  }, [intervalMs])
  return now
}

function IndicatorRow({ task }: { task: SideTask }) {
  const navigate = useNavigate()
  const now = useNow()
  const line = sideTaskStatusLine(task, now)
  return (
    <button
      type="button"
      className="side-indicator__row"
      onClick={() => navigate(`/${task.botId}/chats/${task.chatId}`)}
    >
      {task.status === 'running' ? (
        <Loader2 className="side-indicator__icon animate-spin" strokeWidth={1.8} />
      ) : (
        <Clock className="side-indicator__icon" strokeWidth={1.8} />
      )}
      <span className="side-indicator__text">
        <span className="side-indicator__title">{task.title}</span>
        <span>{line.text}</span>
      </span>
    </button>
  )
}

interface SideTaskIndicatorProps {
  /** Ungrouped side tasks of ONE source message, still waiting or running. */
  tasks: SideTask[]
}

/**
 * One quiet line under the source message. A single side task shows its
 * name and state; several from the same message collapse into one line
 * that opens a tiny popover listing them.
 */
export function SideTaskIndicator({ tasks }: SideTaskIndicatorProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  if (tasks.length === 0) return null

  if (tasks.length === 1) {
    return (
      <div className="side-indicator">
        <IndicatorRow task={tasks[0]} />
      </div>
    )
  }

  const working = tasks.filter((t) => t.status === 'running').length
  const waiting = tasks.length - working
  return (
    <div className="side-indicator" ref={ref}>
      <button
        type="button"
        className="side-indicator__row side-indicator__collapse"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
      >
        <GitBranch className="side-indicator__icon" strokeWidth={1.8} />
        <span className="side-indicator__text">
          {tasks.length} side tasks
          {working > 0 && waiting > 0
            ? ` · ${working} working, ${waiting} waiting`
            : working > 0
              ? ' · working'
              : ' · waiting for a slot'}
        </span>
        <ChevronDown
          className={cn('side-indicator__chevron', open && 'side-indicator__chevron--open')}
          strokeWidth={1.8}
        />
      </button>
      {open && (
        <div className="side-indicator__popover">
          {tasks.map((task) => (
            <IndicatorRow key={task.id} task={task} />
          ))}
        </div>
      )}
    </div>
  )
}

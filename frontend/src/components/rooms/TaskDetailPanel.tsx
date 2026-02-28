import { useEffect, useMemo } from 'react'
import { X, Clock, Tag, Calendar, User, Bot, AlertTriangle, ArrowUpCircle } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { getRoomTaskEvents } from '../../api/room-tasks'
import type { RoomTask, RoomTaskEvent, RoomTaskEventAction } from '../../types'

const STATUS_LABELS: Record<string, string> = {
  todo: 'To Do',
  in_progress: 'In Progress',
  done: 'Done',
  blocked: 'Blocked',
}

const STATUS_COLORS: Record<string, string> = {
  todo: 'var(--color-text-secondary)',
  in_progress: 'var(--accent-500)',
  done: '#22c55e',
  blocked: '#ef4444',
}

const PRIORITY_COLORS: Record<string, string> = {
  low: 'var(--color-text-tertiary)',
  normal: 'var(--accent-500)',
  high: '#f59e0b',
  urgent: '#ef4444',
}

const EVENT_DOT_COLORS: Record<RoomTaskEventAction, string> = {
  created: '#22c55e',
  status_changed: 'var(--accent-500)',
  priority_changed: '#f59e0b',
  assigned: '#a855f7',
  updated: 'var(--color-text-secondary)',
  deleted: '#ef4444',
}

interface TaskDetailPanelProps {
  roomId: string
  task: RoomTask
  onClose: () => void
  resolveActorName: (userId: string | null, botId: string | null) => string
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const seconds = Math.floor(diff / 1000)
  if (seconds < 60) return 'just now'
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  if (days < 30) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

function describeEvent(event: RoomTaskEvent, actorName: string): string {
  const field = event.field
  switch (event.action) {
    case 'created':
      return `${actorName} created this task`
    case 'deleted':
      return `${actorName} deleted this task`
    case 'status_changed':
      return `${actorName} changed status from ${STATUS_LABELS[event.oldValue ?? ''] ?? event.oldValue} to ${STATUS_LABELS[event.newValue ?? ''] ?? event.newValue}`
    case 'priority_changed':
      return `${actorName} changed priority from ${event.oldValue} to ${event.newValue}`
    case 'assigned': {
      const target = field === 'assigned_to_bot_id' ? 'bot' : 'user'
      if (event.newValue && !event.oldValue) return `${actorName} assigned ${target} ${event.newValue}`
      if (!event.newValue && event.oldValue) return `${actorName} unassigned ${target}`
      return `${actorName} changed ${target} assignment`
    }
    case 'updated':
      return `${actorName} updated ${field ?? 'task'}`
    default:
      return `${actorName} modified task`
  }
}

export function TaskDetailPanel({ roomId, task, onClose, resolveActorName }: TaskDetailPanelProps) {
  const { taskEvents, taskEventsLoading, setTaskEvents, setTaskEventsLoading } = useRoomStore()
  const events = taskEvents[task.id] || []
  const loading = taskEventsLoading[task.id] ?? false

  useEffect(() => {
    let cancelled = false
    async function load() {
      setTaskEventsLoading(task.id, true)
      try {
        const data = await getRoomTaskEvents(roomId, task.id)
        if (!cancelled) setTaskEvents(task.id, data)
      } catch {
        // ignore
      } finally {
        if (!cancelled) setTaskEventsLoading(task.id, false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [roomId, task.id, setTaskEvents, setTaskEventsLoading])

  const sortedEvents = useMemo(
    () => [...events].sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()),
    [events]
  )

  return (
    <div className="task-detail-panel">
      <div className="task-detail-panel__header">
        <h3 className="task-detail-panel__title">{task.title}</h3>
        <button className="task-detail-panel__close" onClick={onClose}>
          <X size={16} />
        </button>
      </div>

      <div className="task-detail-panel__metadata">
        {/* Status badge */}
        <div className="task-detail-panel__meta-row">
          <span className="task-detail-panel__meta-label">Status</span>
          <span
            className="task-detail-panel__badge"
            style={{ background: `${STATUS_COLORS[task.status]}20`, color: STATUS_COLORS[task.status] }}
          >
            {STATUS_LABELS[task.status] ?? task.status}
          </span>
        </div>

        {/* Priority badge */}
        <div className="task-detail-panel__meta-row">
          <span className="task-detail-panel__meta-label">Priority</span>
          <span
            className="task-detail-panel__badge"
            style={{ background: `${PRIORITY_COLORS[task.priority]}20`, color: PRIORITY_COLORS[task.priority] }}
          >
            {task.priority === 'urgent' && <AlertTriangle size={10} />}
            {task.priority === 'high' && <ArrowUpCircle size={10} />}
            {task.priority}
          </span>
        </div>

        {/* Assignee */}
        {(task.assignedToBotId || task.assignedToUserId) && (
          <div className="task-detail-panel__meta-row">
            <span className="task-detail-panel__meta-label">Assignee</span>
            <span className="task-detail-panel__meta-value">
              {task.assignedToBotId ? <Bot size={12} /> : <User size={12} />}
              {resolveActorName(task.assignedToUserId, task.assignedToBotId)}
            </span>
          </div>
        )}

        {/* Due date */}
        {task.dueAt && (
          <div className="task-detail-panel__meta-row">
            <span className="task-detail-panel__meta-label">Due</span>
            <span className="task-detail-panel__meta-value">
              <Calendar size={12} />
              {new Date(task.dueAt).toLocaleDateString()}
            </span>
          </div>
        )}

        {/* Tags */}
        {task.tags.length > 0 && (
          <div className="task-detail-panel__meta-row">
            <span className="task-detail-panel__meta-label">Tags</span>
            <div className="task-detail-panel__tags">
              {task.tags.map((tag) => (
                <span key={tag} className="task-detail-panel__tag">
                  <Tag size={10} /> {tag}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Description */}
        {task.description && (
          <div className="task-detail-panel__description">
            {task.description}
          </div>
        )}
      </div>

      <div className="task-detail-panel__activity">
        <h4 className="task-detail-panel__activity-title">
          <Clock size={14} /> Activity
        </h4>

        {loading ? (
          <div className="task-detail-panel__loading">Loading activity...</div>
        ) : sortedEvents.length === 0 ? (
          <div className="task-detail-panel__empty">No activity yet</div>
        ) : (
          <div className="task-detail-panel__timeline">
            {sortedEvents.map((event) => {
              const actorName = resolveActorName(event.actorUserId, event.actorBotId)
              return (
                <div key={event.id} className="task-detail-panel__event">
                  <div
                    className="task-detail-panel__event-dot"
                    style={{ background: EVENT_DOT_COLORS[event.action] ?? 'var(--color-text-secondary)' }}
                  />
                  <div className="task-detail-panel__event-content">
                    <span className="task-detail-panel__event-text">
                      {describeEvent(event, actorName)}
                    </span>
                    <span className="task-detail-panel__event-time">
                      {formatRelativeTime(event.createdAt)}
                    </span>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </div>
    </div>
  )
}

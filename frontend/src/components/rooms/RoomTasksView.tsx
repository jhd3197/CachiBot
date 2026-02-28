import { useEffect, useState, useCallback } from 'react'
import { Plus, MoreVertical, Calendar, Tag, AlertTriangle, ArrowUpCircle, List, LayoutGrid } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { getRoomTasks, createRoomTask, updateRoomTask, deleteRoomTask } from '../../api/room-tasks'
import { TaskDetailPanel } from './TaskDetailPanel'
import type { RoomTask, RoomTaskStatus, RoomTaskPriority, CreateRoomTaskRequest } from '../../types'

const COLUMNS: { key: RoomTaskStatus; label: string; color: string }[] = [
  { key: 'todo', label: 'To Do', color: 'var(--color-text-secondary)' },
  { key: 'in_progress', label: 'In Progress', color: 'var(--accent-500)' },
  { key: 'blocked', label: 'Blocked', color: '#ef4444' },
  { key: 'done', label: 'Done', color: '#22c55e' },
]

const PRIORITY_COLORS: Record<RoomTaskPriority, string> = {
  low: 'var(--color-text-tertiary)',
  normal: 'var(--accent-500)',
  high: '#f59e0b',
  urgent: '#ef4444',
}

interface RoomTasksViewProps {
  roomId: string
}

export function RoomTasksView({ roomId }: RoomTasksViewProps) {
  const { rooms, roomTasks, selectedTaskId, setRoomTasks, addRoomTask, updateRoomTask: updateStoreTask, deleteRoomTask: deleteStoreTask, setSelectedTask } = useRoomStore()
  const tasks = roomTasks[roomId] || []
  const [viewType, setViewType] = useState<'kanban' | 'list'>('kanban')
  const [showNewTask, setShowNewTask] = useState(false)
  const [menuTaskId, setMenuTaskId] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)

  const room = rooms.find((r) => r.id === roomId)
  const activeTaskId = selectedTaskId[roomId] ?? null
  const activeTask = activeTaskId ? tasks.find((t) => t.id === activeTaskId) ?? null : null

  const resolveActorName = useCallback((userId: string | null, botId: string | null): string => {
    if (botId && room) {
      const bot = room.bots.find((b) => b.botId === botId)
      if (bot) return bot.botName
    }
    if (userId && room) {
      const member = room.members.find((m) => m.userId === userId)
      if (member) return member.username
    }
    return userId || botId || 'Unknown'
  }, [room])

  useEffect(() => {
    let cancelled = false
    async function load() {
      setLoading(true)
      try {
        const data = await getRoomTasks(roomId)
        if (!cancelled) setRoomTasks(roomId, data)
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    load()
    return () => { cancelled = true }
  }, [roomId, setRoomTasks])

  const handleCreate = useCallback(async (data: CreateRoomTaskRequest) => {
    try {
      const task = await createRoomTask(roomId, data)
      addRoomTask(roomId, task)
      setShowNewTask(false)
    } catch {
      // ignore
    }
  }, [roomId, addRoomTask])

  const handleStatusChange = useCallback(async (taskId: string, status: RoomTaskStatus) => {
    try {
      const updated = await updateRoomTask(roomId, taskId, { status })
      updateStoreTask(roomId, taskId, updated)
    } catch {
      // ignore
    }
    setMenuTaskId(null)
  }, [roomId, updateStoreTask])

  const handleDelete = useCallback(async (taskId: string) => {
    try {
      await deleteRoomTask(roomId, taskId)
      deleteStoreTask(roomId, taskId)
    } catch {
      // ignore
    }
    setMenuTaskId(null)
  }, [roomId, deleteStoreTask])

  const tasksByStatus = (status: RoomTaskStatus) =>
    tasks.filter((t) => t.status === status).sort((a, b) => a.position - b.position)

  if (loading) {
    return <div className="tasks-empty">Loading tasks...</div>
  }

  return (
    <div className="tasks-view">
      <div className="tasks-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '0.75rem 1rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <span className="tasks-header__title" style={{ fontSize: '0.9rem' }}>Tasks</span>
          <span style={{ fontSize: '0.75rem', color: 'var(--color-text-secondary)' }}>
            {tasks.length} total
          </span>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <div className="tasks-view-toggle">
            <button
              className={`tasks-view-toggle__btn ${viewType === 'kanban' ? 'tasks-view-toggle__btn--active' : ''}`}
              onClick={() => setViewType('kanban')}
              title="Kanban view"
            >
              <LayoutGrid size={14} />
            </button>
            <button
              className={`tasks-view-toggle__btn ${viewType === 'list' ? 'tasks-view-toggle__btn--active' : ''}`}
              onClick={() => setViewType('list')}
              title="List view"
            >
              <List size={14} />
            </button>
          </div>
          <button
            className="btn btn--primary btn--sm"
            onClick={() => setShowNewTask(true)}
            style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}
          >
            <Plus size={14} /> New Task
          </button>
        </div>
      </div>

      <div className="tasks-view__body">
        <div className="tasks-view__content">
          {viewType === 'kanban' ? (
            <div className="tasks-kanban" style={{ padding: '0 1rem' }}>
              {COLUMNS.map((col) => {
                const colTasks = tasksByStatus(col.key)
                return (
                  <div key={col.key} className="tasks-column">
                    <div className="tasks-column__header">
                      <div style={{ width: 8, height: 8, borderRadius: '50%', background: col.color }} />
                      <span className="tasks-column__label">{col.label}</span>
                      <span className="tasks-column__count">{colTasks.length}</span>
                    </div>
                    <div className="tasks-column__body" style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {colTasks.map((task) => (
                        <TaskCard
                          key={task.id}
                          task={task}
                          selected={activeTaskId === task.id}
                          menuOpen={menuTaskId === task.id}
                          onMenuToggle={() => setMenuTaskId(menuTaskId === task.id ? null : task.id)}
                          onClick={() => setSelectedTask(roomId, activeTaskId === task.id ? null : task.id)}
                          onStatusChange={handleStatusChange}
                          onDelete={handleDelete}
                        />
                      ))}
                      {colTasks.length === 0 && (
                        <div style={{ padding: '1rem', textAlign: 'center', fontSize: '0.75rem', color: 'var(--color-text-tertiary)' }}>
                          No tasks
                        </div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ padding: '0 1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem', overflow: 'auto', flex: 1 }}>
              {tasks.length === 0 ? (
                <div className="tasks-empty">No tasks yet</div>
              ) : (
                tasks.sort((a, b) => a.position - b.position).map((task) => (
                  <div
                    key={task.id}
                    className={`task-list-row ${activeTaskId === task.id ? 'task-list-row--selected' : ''}`}
                    onClick={() => setSelectedTask(roomId, activeTaskId === task.id ? null : task.id)}
                    style={{ cursor: 'pointer' }}
                  >
                    <button
                      className={`task-list-row__checkbox ${task.status === 'done' ? 'task-list-row__checkbox--done' : ''}`}
                      onClick={(e) => { e.stopPropagation(); handleStatusChange(task.id, task.status === 'done' ? 'todo' : 'done') }}
                    />
                    <span className={`task-list-row__title ${task.status === 'done' ? 'task-list-row__title--done' : ''}`}>
                      {task.title}
                    </span>
                    {task.tags.map((tag) => (
                      <span key={tag} className="task-list-row__tag">{tag}</span>
                    ))}
                    <span className={`task-list-row__priority task-list-row__priority--${task.priority === 'urgent' ? 'high' : task.priority}`}>
                      {task.priority}
                    </span>
                    <select
                      className="task-list-row__status-select"
                      value={task.status}
                      onClick={(e) => e.stopPropagation()}
                      onChange={(e) => handleStatusChange(task.id, e.target.value as RoomTaskStatus)}
                    >
                      {COLUMNS.map((c) => (
                        <option key={c.key} value={c.key}>{c.label}</option>
                      ))}
                    </select>
                    <button
                      className="task-list-row__delete-btn"
                      onClick={(e) => { e.stopPropagation(); handleDelete(task.id) }}
                      title="Delete"
                    >
                      &times;
                    </button>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        {activeTask && (
          <TaskDetailPanel
            roomId={roomId}
            task={activeTask}
            onClose={() => setSelectedTask(roomId, null)}
            resolveActorName={resolveActorName}
          />
        )}
      </div>

      {showNewTask && (
        <NewTaskModal
          onClose={() => setShowNewTask(false)}
          onCreate={handleCreate}
        />
      )}
    </div>
  )
}

function TaskCard({
  task,
  selected,
  menuOpen,
  onMenuToggle,
  onClick,
  onStatusChange,
  onDelete,
}: {
  task: RoomTask
  selected: boolean
  menuOpen: boolean
  onMenuToggle: () => void
  onClick: () => void
  onStatusChange: (taskId: string, status: RoomTaskStatus) => void
  onDelete: (taskId: string) => void
}) {
  return (
    <div
      className={`task-card ${task.status === 'done' ? 'task-card--done' : ''} ${selected ? 'task-card--selected' : ''}`}
      onClick={onClick}
      style={{ cursor: 'pointer' }}
    >
      <div
        className="task-card__priority-bar"
        style={{ background: PRIORITY_COLORS[task.priority] }}
      />
      <div className="task-card__content">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <span className={`task-card__title ${task.status === 'done' ? 'task-card__title--done' : ''}`}>
            {task.title}
          </span>
          <button className="task-card__menu-btn" onClick={(e) => { e.stopPropagation(); onMenuToggle() }}>
            <MoreVertical size={14} />
          </button>
        </div>
        {task.description && (
          <div className="task-card__description">{task.description}</div>
        )}
        <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap', marginTop: '0.5rem' }}>
          {task.tags.map((tag) => (
            <span key={tag} className="task-card__tag">
              <Tag size={10} /> {tag}
            </span>
          ))}
          {task.priority !== 'normal' && (
            <span className={`task-card__priority task-card__priority--${task.priority === 'urgent' ? 'high' : task.priority}`}>
              {task.priority === 'urgent' ? <AlertTriangle size={10} /> : <ArrowUpCircle size={10} />}
              {task.priority}
            </span>
          )}
          {task.dueAt && (
            <span className="task-card__due">
              <Calendar size={10} />
              {new Date(task.dueAt).toLocaleDateString()}
            </span>
          )}
        </div>
      </div>
      {menuOpen && (
        <div className="task-context-menu" onClick={(e) => e.stopPropagation()}>
          {COLUMNS.filter((c) => c.key !== task.status).map((c) => (
            <button
              key={c.key}
              className="task-context-menu__item"
              onClick={() => onStatusChange(task.id, c.key)}
            >
              Move to {c.label}
            </button>
          ))}
          <div className="task-context-menu__divider" />
          <button
            className="task-context-menu__item--danger"
            onClick={() => onDelete(task.id)}
          >
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

function NewTaskModal({
  onClose,
  onCreate,
}: {
  onClose: () => void
  onCreate: (data: CreateRoomTaskRequest) => void
}) {
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [priority, setPriority] = useState<RoomTaskPriority>('normal')

  const handleSubmit = () => {
    if (!title.trim()) return
    onCreate({
      title: title.trim(),
      description: description.trim() || undefined,
      priority,
    })
  }

  return (
    <div className="task-modal" onClick={onClose}>
      <div className="task-modal__panel" onClick={(e) => e.stopPropagation()}>
        <h3 className="task-modal__title">New Task</h3>
        <input
          className="task-modal__input"
          placeholder="Task title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSubmit()}
          autoFocus
        />
        <textarea
          className="task-modal__input"
          placeholder="Description (optional)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          rows={3}
          style={{ resize: 'vertical', height: 'auto' }}
        />
        <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
          {(['low', 'normal', 'high', 'urgent'] as RoomTaskPriority[]).map((p) => (
            <button
              key={p}
              className={`task-card__priority task-card__priority--${p === 'urgent' ? 'high' : p}`}
              style={{
                cursor: 'pointer',
                opacity: priority === p ? 1 : 0.5,
                border: priority === p ? '1px solid currentColor' : '1px solid transparent',
              }}
              onClick={() => setPriority(p)}
            >
              {p}
            </button>
          ))}
        </div>
        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
          <button className="task-modal__cancel" onClick={onClose}>Cancel</button>
          <button className="btn btn--primary btn--sm" onClick={handleSubmit} disabled={!title.trim()}>
            Create
          </button>
        </div>
      </div>
    </div>
  )
}

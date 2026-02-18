import { useState, useMemo } from 'react'
import {
  Plus,
  Search,
  LayoutGrid,
  List,
  Calendar,
  Flag,
  MoreHorizontal,
  Trash2,
  ArrowRight,
  CheckCircle2,
  Circle,
  Clock,
  AlertCircle,
} from 'lucide-react'
import { useTaskStore, useBotStore } from '../../stores/bots'
import { cn } from '../../lib/utils'
import type { Task, TaskStatus, TaskPriority } from '../../types'

type ViewMode = 'kanban' | 'list'

export function TasksView() {
  const { getActiveBot } = useBotStore()
  const { getTasksByBot, addTask, updateTask, deleteTask, filter, setFilter } = useTaskStore()
  const [viewMode, setViewMode] = useState<ViewMode>('kanban')
  const [search, setSearch] = useState('')
  const [showNewTask, setShowNewTask] = useState(false)

  const activeBot = getActiveBot()
  if (!activeBot) return null

  const allTasks = getTasksByBot(activeBot.id)
  const tasks = allTasks.filter(
    (task) => !search || task.title.toLowerCase().includes(search.toLowerCase())
  )

  const handleNewTask = (title: string, status: TaskStatus = 'todo') => {
    const newTask: Task = {
      id: crypto.randomUUID(),
      botId: activeBot.id,
      title,
      status,
      priority: 'medium',
      tags: [],
      createdAt: new Date().toISOString(),
    }
    addTask(newTask)
    setShowNewTask(false)
  }

  const handleMoveTask = (taskId: string, newStatus: TaskStatus) => {
    updateTask(taskId, {
      status: newStatus,
      completedAt: newStatus === 'done' ? new Date().toISOString() : undefined,
    })
  }

  const stats = {
    todo: tasks.filter((t) => t.status === 'todo').length,
    in_progress: tasks.filter((t) => t.status === 'in_progress').length,
    done: tasks.filter((t) => t.status === 'done').length,
    blocked: tasks.filter((t) => t.status === 'blocked').length,
  }

  return (
    <div className="tasks-view">
      {/* Header */}
      <div className="tasks-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="tasks-header__title">Tasks</h1>
            <p className="tasks-header__subtitle">
              {stats.done}/{tasks.length} completed
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* View toggle */}
            <div className="tasks-view-toggle">
              <button
                onClick={() => setViewMode('kanban')}
                className={cn(
                  'tasks-view-toggle__btn',
                  viewMode === 'kanban'
                    ? 'tasks-view-toggle__btn--active'
                    : 'tasks-view-toggle__btn--inactive'
                )}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'tasks-view-toggle__btn',
                  viewMode === 'list'
                    ? 'tasks-view-toggle__btn--active'
                    : 'tasks-view-toggle__btn--inactive'
                )}
              >
                <List className="h-4 w-4" />
              </button>
            </div>

            <button
              onClick={() => setShowNewTask(true)}
              className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500"
            >
              <Plus className="h-4 w-4" />
              Add Task
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="mt-4 flex items-center gap-3">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="tasks-search"
            />
          </div>

          <select
            value={filter.priority}
            onChange={(e) => setFilter({ priority: e.target.value as TaskPriority | 'all' })}
            className="tasks-filter-select"
          >
            <option value="all">All priorities</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-hidden p-6">
        {viewMode === 'kanban' ? (
          <KanbanBoard
            tasks={tasks}
            onMoveTask={handleMoveTask}
            onDeleteTask={deleteTask}
            onAddTask={handleNewTask}
          />
        ) : (
          <TaskListView
            tasks={tasks}
            onMoveTask={handleMoveTask}
            onDeleteTask={deleteTask}
          />
        )}
      </div>

      {/* New task modal */}
      {showNewTask && (
        <NewTaskModal onClose={() => setShowNewTask(false)} onSave={handleNewTask} />
      )}
    </div>
  )
}

// =============================================================================
// KANBAN BOARD
// =============================================================================

interface KanbanBoardProps {
  tasks: Task[]
  onMoveTask: (id: string, status: TaskStatus) => void
  onDeleteTask: (id: string) => void
  onAddTask: (title: string, status: TaskStatus) => void
}

const columns: { id: TaskStatus; label: string; icon: React.ComponentType<{ className?: string }>; color: string }[] = [
  { id: 'todo', label: 'To Do', icon: Circle, color: 'text-[var(--color-text-secondary)]' },
  { id: 'in_progress', label: 'In Progress', icon: Clock, color: 'text-blue-400' },
  { id: 'blocked', label: 'Blocked', icon: AlertCircle, color: 'text-red-400' },
  { id: 'done', label: 'Done', icon: CheckCircle2, color: 'text-green-400' },
]

function KanbanBoard({ tasks, onMoveTask, onDeleteTask, onAddTask }: KanbanBoardProps) {
  const tasksByStatus = useMemo(() => {
    const grouped: Record<TaskStatus, Task[]> = {
      todo: [],
      in_progress: [],
      blocked: [],
      done: [],
    }
    tasks.forEach((task) => {
      grouped[task.status].push(task)
    })
    return grouped
  }, [tasks])

  return (
    <div className="tasks-kanban">
      {columns.map((column) => (
        <div key={column.id} className="tasks-column">
          {/* Column header */}
          <div className="tasks-column__header">
            <column.icon className={cn('h-5 w-5', column.color)} />
            <span className="tasks-column__label">{column.label}</span>
            <span className="tasks-column__count">
              {tasksByStatus[column.id].length}
            </span>
          </div>

          {/* Tasks */}
          <div className="tasks-column__body space-y-2">
            {tasksByStatus[column.id].map((task) => (
              <TaskCard
                key={task.id}
                task={task}
                onMove={onMoveTask}
                onDelete={onDeleteTask}
              />
            ))}

            {/* Add task button */}
            {column.id === 'todo' && (
              <button
                onClick={() => {
                  const title = prompt('Task title:')
                  if (title) onAddTask(title, column.id)
                }}
                className="tasks-add-btn"
              >
                <Plus className="h-4 w-4" />
                Add task
              </button>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

// =============================================================================
// TASK CARD
// =============================================================================

interface TaskCardProps {
  task: Task
  onMove: (id: string, status: TaskStatus) => void
  onDelete: (id: string) => void
}

function TaskCard({ task, onMove, onDelete }: TaskCardProps) {
  const [menuOpen, setMenuOpen] = useState(false)

  return (
    <div
      className={cn(
        'task-card group',
        task.status === 'done' && 'task-card--done'
      )}
    >
      {/* Priority indicator */}
      <div className="task-card__priority-bar"
        style={{
          background: task.priority === 'high'
            ? 'linear-gradient(to bottom, #ef4444, #f87171)'
            : task.priority === 'medium'
            ? 'linear-gradient(to bottom, #eab308, #facc15)'
            : 'linear-gradient(to bottom, #71717a, #a1a1aa)'
        }}
      />

      {/* Content */}
      <div className="task-card__content">
        <div className="flex items-start justify-between gap-2">
          <span
            className={cn(
              'task-card__title',
              task.status === 'done' && 'task-card__title--done'
            )}
          >
            {task.title}
          </span>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="task-card__menu-btn"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>

        {task.description && (
          <p className="task-card__description line-clamp-2">{task.description}</p>
        )}

        {/* Tags */}
        {task.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {task.tags.map((tag) => (
              <span key={tag} className="task-card__tag">
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between">
          <div className={cn(
            'task-card__priority',
            task.priority === 'high' && 'task-card__priority--high',
            task.priority === 'medium' && 'task-card__priority--medium',
            task.priority === 'low' && 'task-card__priority--low'
          )}>
            <Flag className="h-3 w-3" />
            {task.priority}
          </div>
          {task.dueDate && (
            <div className="task-card__due">
              <Calendar className="h-3 w-3" />
              {new Date(task.dueDate).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>

      {/* Context menu */}
      {menuOpen && (
        <div className="task-context-menu">
          {columns
            .filter((col) => col.id !== task.status)
            .map((col) => (
              <button
                key={col.id}
                onClick={() => {
                  onMove(task.id, col.id)
                  setMenuOpen(false)
                }}
                className="task-context-menu__item"
              >
                <ArrowRight className="h-4 w-4" />
                Move to {col.label}
              </button>
            ))}
          <div className="task-context-menu__divider" />
          <button
            onClick={() => {
              onDelete(task.id)
              setMenuOpen(false)
            }}
            className="task-context-menu__item--danger"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// LIST VIEW
// =============================================================================

interface TaskListViewProps {
  tasks: Task[]
  onMoveTask: (id: string, status: TaskStatus) => void
  onDeleteTask: (id: string) => void
}

function TaskListView({ tasks, onMoveTask, onDeleteTask }: TaskListViewProps) {
  return (
    <div className="space-y-1">
      {tasks.map((task) => (
        <div key={task.id} className="task-list-row">
          {/* Checkbox */}
          <button
            onClick={() =>
              onMoveTask(task.id, task.status === 'done' ? 'todo' : 'done')
            }
            className={cn(
              'task-list-row__checkbox',
              task.status === 'done' && 'task-list-row__checkbox--done'
            )}
          >
            {task.status === 'done' && <CheckCircle2 className="h-4 w-4" />}
          </button>

          {/* Title */}
          <span
            className={cn(
              'task-list-row__title',
              task.status === 'done' && 'task-list-row__title--done'
            )}
          >
            {task.title}
          </span>

          {/* Tags */}
          <div className="flex items-center gap-2">
            {task.tags.map((tag) => (
              <span key={tag} className="task-list-row__tag">
                {tag}
              </span>
            ))}
          </div>

          {/* Priority */}
          <div
            className={cn(
              'task-list-row__priority',
              task.priority === 'high' && 'task-list-row__priority--high',
              task.priority === 'medium' && 'task-list-row__priority--medium',
              task.priority === 'low' && 'task-list-row__priority--low'
            )}
          >
            {task.priority}
          </div>

          {/* Status */}
          <select
            value={task.status}
            onChange={(e) => onMoveTask(task.id, e.target.value as TaskStatus)}
            className="task-list-row__status-select"
          >
            {columns.map((col) => (
              <option key={col.id} value={col.id}>
                {col.label}
              </option>
            ))}
          </select>

          {/* Delete */}
          <button
            onClick={() => onDeleteTask(task.id)}
            className="task-list-row__delete-btn"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}

      {tasks.length === 0 && (
        <div className="tasks-empty">No tasks yet</div>
      )}
    </div>
  )
}

// =============================================================================
// NEW TASK MODAL
// =============================================================================

function NewTaskModal({
  onClose,
  onSave,
}: {
  onClose: () => void
  onSave: (title: string, status: TaskStatus) => void
}) {
  const [title, setTitle] = useState('')

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (title.trim()) {
      onSave(title.trim(), 'todo')
    }
  }

  return (
    <div className="task-modal">
      <div className="task-modal__panel">
        <h2 className="task-modal__title">New Task</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Task title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className="task-modal__input"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="task-modal__cancel"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={!title.trim()}
              className="rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500 disabled:opacity-50"
            >
              Create Task
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

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
    <div className="flex h-full flex-col bg-zinc-950">
      {/* Header */}
      <div className="border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">Tasks</h1>
            <p className="text-sm text-zinc-500">
              {stats.done}/{tasks.length} completed
            </p>
          </div>

          <div className="flex items-center gap-3">
            {/* View toggle */}
            <div className="flex items-center rounded-lg border border-zinc-700 bg-zinc-800/50 p-1">
              <button
                onClick={() => setViewMode('kanban')}
                className={cn(
                  'rounded-md p-1.5 transition-colors',
                  viewMode === 'kanban'
                    ? 'bg-zinc-700 text-zinc-100'
                    : 'text-zinc-400 hover:text-zinc-200'
                )}
              >
                <LayoutGrid className="h-4 w-4" />
              </button>
              <button
                onClick={() => setViewMode('list')}
                className={cn(
                  'rounded-md p-1.5 transition-colors',
                  viewMode === 'list'
                    ? 'bg-zinc-700 text-zinc-100'
                    : 'text-zinc-400 hover:text-zinc-200'
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
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-4 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500"
            />
          </div>

          <select
            value={filter.priority}
            onChange={(e) => setFilter({ priority: e.target.value as TaskPriority | 'all' })}
            className="h-9 rounded-lg border border-zinc-700 bg-zinc-800/50 px-3 text-sm text-zinc-300 outline-none focus:border-cachi-500"
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
  { id: 'todo', label: 'To Do', icon: Circle, color: 'text-zinc-400' },
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
    <div className="flex h-full gap-4 overflow-x-auto pb-4">
      {columns.map((column) => (
        <div
          key={column.id}
          className="flex w-80 flex-shrink-0 flex-col rounded-xl border border-zinc-800 bg-zinc-900/30"
        >
          {/* Column header */}
          <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3">
            <column.icon className={cn('h-5 w-5', column.color)} />
            <span className="font-medium text-zinc-200">{column.label}</span>
            <span className="ml-auto rounded-full bg-zinc-800 px-2 py-0.5 text-xs text-zinc-400">
              {tasksByStatus[column.id].length}
            </span>
          </div>

          {/* Tasks */}
          <div className="flex-1 space-y-2 overflow-y-auto p-3">
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
                className="flex w-full items-center gap-2 rounded-lg border border-dashed border-zinc-700 p-3 text-sm text-zinc-500 transition-colors hover:border-cachi-500 hover:text-cachi-400"
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

  const priorityConfig = {
    high: { color: 'text-red-400', bg: 'bg-red-500/10' },
    medium: { color: 'text-yellow-400', bg: 'bg-yellow-500/10' },
    low: { color: 'text-zinc-400', bg: 'bg-zinc-700' },
  }

  const config = priorityConfig[task.priority]

  return (
    <div
      className={cn(
        'group relative rounded-lg border bg-zinc-800/50 p-3 transition-all hover:border-zinc-600',
        task.status === 'done' ? 'border-green-500/30' : 'border-zinc-700'
      )}
    >
      {/* Priority indicator */}
      <div className="absolute left-0 top-3 h-5 w-1 rounded-r-full bg-gradient-to-b"
        style={{
          background: task.priority === 'high'
            ? 'linear-gradient(to bottom, #ef4444, #f87171)'
            : task.priority === 'medium'
            ? 'linear-gradient(to bottom, #eab308, #facc15)'
            : 'linear-gradient(to bottom, #71717a, #a1a1aa)'
        }}
      />

      {/* Content */}
      <div className="ml-2">
        <div className="flex items-start justify-between gap-2">
          <span
            className={cn(
              'text-sm font-medium',
              task.status === 'done' ? 'text-zinc-500 line-through' : 'text-zinc-200'
            )}
          >
            {task.title}
          </span>
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="flex-shrink-0 rounded p-1 text-zinc-500 opacity-0 transition-opacity hover:bg-zinc-700 group-hover:opacity-100"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </div>

        {task.description && (
          <p className="mt-1 text-xs text-zinc-500 line-clamp-2">{task.description}</p>
        )}

        {/* Tags */}
        {task.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {task.tags.map((tag) => (
              <span
                key={tag}
                className="rounded bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-400"
              >
                {tag}
              </span>
            ))}
          </div>
        )}

        {/* Footer */}
        <div className="mt-3 flex items-center justify-between">
          <div className={cn('flex items-center gap-1 rounded px-1.5 py-0.5 text-xs', config.bg, config.color)}>
            <Flag className="h-3 w-3" />
            {task.priority}
          </div>
          {task.dueDate && (
            <div className="flex items-center gap-1 text-xs text-zinc-500">
              <Calendar className="h-3 w-3" />
              {new Date(task.dueDate).toLocaleDateString()}
            </div>
          )}
        </div>
      </div>

      {/* Context menu */}
      {menuOpen && (
        <div className="absolute right-0 top-8 z-10 w-48 rounded-lg border border-zinc-700 bg-zinc-800 py-1 shadow-xl">
          {columns
            .filter((col) => col.id !== task.status)
            .map((col) => (
              <button
                key={col.id}
                onClick={() => {
                  onMove(task.id, col.id)
                  setMenuOpen(false)
                }}
                className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
              >
                <ArrowRight className="h-4 w-4" />
                Move to {col.label}
              </button>
            ))}
          <div className="my-1 h-px bg-zinc-700" />
          <button
            onClick={() => {
              onDelete(task.id)
              setMenuOpen(false)
            }}
            className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-red-400 hover:bg-zinc-700"
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
        <div
          key={task.id}
          className="flex items-center gap-4 rounded-lg border border-zinc-800 bg-zinc-900/30 px-4 py-3"
        >
          {/* Checkbox */}
          <button
            onClick={() =>
              onMoveTask(task.id, task.status === 'done' ? 'todo' : 'done')
            }
            className={cn(
              'flex h-5 w-5 items-center justify-center rounded border transition-colors',
              task.status === 'done'
                ? 'border-green-500 bg-green-500 text-white'
                : 'border-zinc-600 hover:border-cachi-500'
            )}
          >
            {task.status === 'done' && <CheckCircle2 className="h-4 w-4" />}
          </button>

          {/* Title */}
          <span
            className={cn(
              'flex-1',
              task.status === 'done' ? 'text-zinc-500 line-through' : 'text-zinc-200'
            )}
          >
            {task.title}
          </span>

          {/* Tags */}
          <div className="flex items-center gap-2">
            {task.tags.map((tag) => (
              <span key={tag} className="rounded bg-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
                {tag}
              </span>
            ))}
          </div>

          {/* Priority */}
          <div
            className={cn(
              'rounded px-2 py-0.5 text-xs font-medium',
              task.priority === 'high' && 'bg-red-500/20 text-red-400',
              task.priority === 'medium' && 'bg-yellow-500/20 text-yellow-400',
              task.priority === 'low' && 'bg-zinc-700 text-zinc-400'
            )}
          >
            {task.priority}
          </div>

          {/* Status */}
          <select
            value={task.status}
            onChange={(e) => onMoveTask(task.id, e.target.value as TaskStatus)}
            className="rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-1 text-xs text-zinc-300 outline-none"
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
            className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-red-400"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      ))}

      {tasks.length === 0 && (
        <div className="py-12 text-center text-zinc-500">No tasks yet</div>
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="w-full max-w-md rounded-2xl border border-zinc-800 bg-zinc-900 p-6 shadow-2xl">
        <h2 className="mb-4 text-lg font-bold text-zinc-100">New Task</h2>
        <form onSubmit={handleSubmit}>
          <input
            type="text"
            placeholder="Task title..."
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            autoFocus
            className="mb-4 h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500"
          />
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
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

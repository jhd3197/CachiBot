import { useState } from 'react'
import {
  FolderKanban,
  Play,
  CheckCircle2,
  Clock,
  XCircle,
  Pause,
  Search,
  ChevronRight,
  AlertCircle,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useBotStore, useWorkStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { cn } from '../../lib/utils'
import type { Work, WorkStatus } from '../../types'

export function WorkView() {
  const { getActiveBot } = useBotStore()
  const { workSection } = useUIStore()

  const activeBot = getActiveBot()
  if (!activeBot) return null

  return (
    <div className="flex h-full flex-col bg-zinc-100 dark:bg-[var(--color-bg-app)]">
      {workSection === 'overview' && <WorkOverview botId={activeBot.id} />}
      {workSection === 'active' && <WorkListSection botId={activeBot.id} filter="active" />}
      {workSection === 'completed' && <WorkListSection botId={activeBot.id} filter="completed" />}
      {workSection === 'history' && <WorkListSection botId={activeBot.id} filter="all" />}
    </div>
  )
}

// =============================================================================
// WORK OVERVIEW
// =============================================================================

function WorkOverview({ botId }: { botId: string }) {
  const { getWorkByBot, getActiveWork } = useWorkStore()
  const allWork = getWorkByBot(botId)
  const activeWork = getActiveWork(botId)

  const stats = {
    total: allWork.length,
    active: activeWork.length,
    pending: allWork.filter((w) => w.status === 'pending').length,
    completed: allWork.filter((w) => w.status === 'completed').length,
    failed: allWork.filter((w) => w.status === 'failed').length,
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-[var(--color-border-primary)] px-6 py-4">
        <h1 className="text-xl font-bold text-[var(--color-text-primary)]">Work Overview</h1>
        <p className="text-sm text-[var(--color-text-secondary)]">Manage your work items, tasks, and jobs</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        {/* Stats grid */}
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-5">
          <StatCard label="Total" value={stats.total} color="zinc" />
          <StatCard label="Active" value={stats.active} color="blue" pulse />
          <StatCard label="Pending" value={stats.pending} color="yellow" />
          <StatCard label="Completed" value={stats.completed} color="green" />
          <StatCard label="Failed" value={stats.failed} color="red" />
        </div>

        {/* Recent active work */}
        {activeWork.length > 0 && (
          <div className="mb-8">
            <h2 className="mb-4 text-lg font-semibold text-[var(--color-text-primary)]">Active Work</h2>
            <div className="space-y-3">
              {activeWork.slice(0, 5).map((work) => (
                <WorkCard key={work.id} work={work} />
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {allWork.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-[var(--color-bg-secondary)]">
              <FolderKanban className="h-8 w-8 text-[var(--color-text-secondary)]" />
            </div>
            <h3 className="mb-2 text-lg font-medium text-[var(--color-text-primary)]">No work items yet</h3>
            <p className="mb-6 text-center text-sm text-[var(--color-text-secondary)]">
              Work items will appear here when created through chat or automations.
            </p>
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// WORK LIST SECTION
// =============================================================================

function WorkListSection({ botId, filter }: { botId: string; filter: 'active' | 'completed' | 'all' }) {
  const navigate = useNavigate()
  const { getWorkByBot, activeWorkId, setActiveWork } = useWorkStore()
  const [search, setSearch] = useState('')

  const allWork = getWorkByBot(botId)
  const filteredWork = allWork.filter((work) => {
    // Apply status filter
    if (filter === 'active' && !['pending', 'in_progress', 'paused'].includes(work.status)) return false
    if (filter === 'completed' && work.status !== 'completed') return false

    // Apply search
    if (search && !work.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const selectedWork = filteredWork.find((w) => w.id === activeWorkId)

  const titles: Record<string, string> = {
    active: 'Active Work',
    completed: 'Completed Work',
    all: 'Work History',
  }

  const descriptions: Record<string, string> = {
    active: 'Work items currently in progress or pending',
    completed: 'Successfully completed work items',
    all: 'All work items including failed and cancelled',
  }

  const handleWorkClick = (work: Work) => {
    setActiveWork(work.id)
    navigate(`/${botId}/work/${work.id}`)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-[var(--color-border-primary)] px-6 py-4">
        <h1 className="text-xl font-bold text-[var(--color-text-primary)]">{titles[filter]}</h1>
        <p className="text-sm text-[var(--color-text-secondary)]">{descriptions[filter]}</p>
      </div>

      {/* Search */}
      <div className="border-b border-[var(--color-border-primary)] px-6 py-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
          <input
            type="text"
            placeholder="Search work items..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--card-bg)] pl-10 pr-4 text-sm text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-blue-500"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Work list */}
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-[var(--color-border-primary)] p-4">
          {filteredWork.length === 0 ? (
            <div className="py-12 text-center">
              <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[var(--color-text-tertiary)]" />
              <p className="text-sm text-[var(--color-text-secondary)]">
                {search ? 'No work items match your search' : 'No work items'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredWork.map((work) => (
                <WorkCard
                  key={work.id}
                  work={work}
                  selected={activeWorkId === work.id}
                  onClick={() => handleWorkClick(work)}
                  compact
                />
              ))}
            </div>
          )}
        </div>

        {/* Work details */}
        <div className="flex-1 overflow-y-auto">
          {selectedWork ? (
            <WorkDetails work={selectedWork} />
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-[var(--color-text-secondary)]">Select a work item to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// COMPONENTS
// =============================================================================

function StatCard({
  label,
  value,
  color,
  pulse,
}: {
  label: string
  value: number
  color: 'blue' | 'green' | 'red' | 'yellow' | 'zinc'
  pulse?: boolean
}) {
  const colors = {
    blue: 'border-blue-500/30 bg-blue-500/10 text-blue-400',
    green: 'border-green-500/30 bg-green-500/10 text-green-400',
    red: 'border-red-500/30 bg-red-500/10 text-red-400',
    yellow: 'border-yellow-500/30 bg-yellow-500/10 text-yellow-400',
    zinc: 'border-[var(--color-border-secondary)] bg-[var(--card-bg)] text-[var(--color-text-primary)]',
  }

  return (
    <div className={cn('rounded-xl border p-4', colors[color])}>
      <div className={cn('text-3xl font-bold', pulse && value > 0 && 'animate-pulse')}>
        {value}
      </div>
      <div className="mt-1 text-sm opacity-80">{label}</div>
    </div>
  )
}

function WorkCard({
  work,
  selected,
  onClick,
  compact,
}: {
  work: Work
  selected?: boolean
  onClick?: () => void
  compact?: boolean
}) {
  const getStatusIcon = (status: WorkStatus) => {
    switch (status) {
      case 'pending': return <Clock className="h-4 w-4 text-[var(--color-text-secondary)]" />
      case 'in_progress': return <Play className="h-4 w-4 text-blue-400" />
      case 'completed': return <CheckCircle2 className="h-4 w-4 text-green-400" />
      case 'failed': return <XCircle className="h-4 w-4 text-red-400" />
      case 'cancelled': return <XCircle className="h-4 w-4 text-[var(--color-text-secondary)]" />
      case 'paused': return <Pause className="h-4 w-4 text-yellow-400" />
    }
  }

  const getStatusColor = (status: WorkStatus) => {
    switch (status) {
      case 'pending': return 'border-[var(--color-border-secondary)] bg-[var(--card-bg)]'
      case 'in_progress': return 'border-blue-500/30 bg-blue-500/10'
      case 'completed': return 'border-green-500/30 bg-green-500/10'
      case 'failed': return 'border-red-500/30 bg-red-500/10'
      case 'cancelled': return 'border-[var(--color-border-secondary)] bg-[var(--card-bg)]'
      case 'paused': return 'border-yellow-500/30 bg-yellow-500/10'
    }
  }

  const getPriorityBadge = (priority: string) => {
    const colors: Record<string, string> = {
      urgent: 'bg-red-500/20 text-red-400',
      high: 'bg-orange-500/20 text-orange-400',
      normal: 'bg-zinc-500/20 text-[var(--color-text-secondary)]',
      low: 'bg-zinc-600/20 text-[var(--color-text-secondary)]',
    }
    return colors[priority] || colors.normal
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded-xl border p-4 text-left transition-all',
        selected && 'ring-1 ring-blue-500',
        getStatusColor(work.status),
        onClick && 'hover:border-[var(--color-border-secondary)]'
      )}
    >
      <div className="flex items-start gap-3">
        {getStatusIcon(work.status)}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-[var(--color-text-primary)]">{work.title}</span>
            {work.priority !== 'normal' && (
              <span className={cn('rounded px-1.5 py-0.5 text-[10px] font-medium uppercase', getPriorityBadge(work.priority))}>
                {work.priority}
              </span>
            )}
          </div>
          {work.description && !compact && (
            <p className="mt-1 truncate text-sm text-[var(--color-text-secondary)]">{work.description}</p>
          )}

          {/* Progress bar */}
          {work.status === 'in_progress' && work.progress > 0 && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                <span>Progress</span>
                <span>{work.progress}%</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-[var(--color-hover-bg)]">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${work.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Task count */}
          {work.taskCount !== undefined && work.taskCount > 0 && (
            <div className="mt-2 flex items-center gap-1 text-xs text-[var(--color-text-secondary)]">
              <CheckCircle2 className="h-3 w-3" />
              {work.completedTaskCount || 0}/{work.taskCount} tasks
            </div>
          )}
        </div>
        {onClick && <ChevronRight className="h-4 w-4 text-[var(--color-text-tertiary)]" />}
      </div>
    </button>
  )
}

function WorkDetails({ work }: { work: Work }) {
  const formatTime = (isoString: string) => {
    return new Date(isoString).toLocaleString()
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6">
        <h2 className="text-xl font-bold text-[var(--color-text-primary)]">{work.title}</h2>
        {work.description && <p className="mt-1 text-[var(--color-text-secondary)]">{work.description}</p>}
        {work.goal && (
          <div className="mt-3 rounded-lg border border-blue-500/30 bg-blue-500/10 p-3">
            <div className="text-xs font-medium uppercase text-blue-400">Goal</div>
            <p className="mt-1 text-sm text-[var(--color-text-primary)]">{work.goal}</p>
          </div>
        )}
      </div>

      {/* Info grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <InfoCard label="Status" value={work.status.replace('_', ' ')} />
        <InfoCard label="Priority" value={work.priority} />
        <InfoCard label="Progress" value={`${work.progress}%`} />
        <InfoCard label="Created" value={formatTime(work.createdAt)} />
      </div>

      {/* Progress bar */}
      {work.status === 'in_progress' && (
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-[var(--color-text-secondary)]">Progress</span>
            <span className="font-mono text-[var(--color-text-primary)]">{work.progress}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-[var(--color-bg-secondary)]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-blue-400 transition-all duration-300"
              style={{ width: `${work.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {work.error && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="h-5 w-5" />
            <span className="font-medium">Error</span>
          </div>
          <pre className="mt-2 overflow-x-auto text-sm text-red-300">{work.error}</pre>
        </div>
      )}

      {/* Result */}
      {work.result !== undefined && work.result !== null && (
        <div className="mb-6 rounded-xl border border-green-500/30 bg-green-500/10 p-4">
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle2 className="h-5 w-5" />
            <span className="font-medium">Result</span>
          </div>
          <pre className="mt-2 overflow-x-auto text-sm text-green-300">
            {typeof work.result === 'string' ? work.result : String(JSON.stringify(work.result, null, 2))}
          </pre>
        </div>
      )}

      {/* Tags */}
      {work.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {work.tags.map((tag) => (
            <span key={tag} className="rounded-full bg-[var(--color-bg-secondary)] px-3 py-1 text-sm text-[var(--color-text-secondary)]">
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  )
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-[var(--color-border-primary)] bg-[var(--color-bg-primary)]/50 p-3">
      <div className="text-xs text-[var(--color-text-secondary)]">{label}</div>
      <div className="mt-1 font-medium capitalize text-[var(--color-text-primary)]">{value}</div>
    </div>
  )
}

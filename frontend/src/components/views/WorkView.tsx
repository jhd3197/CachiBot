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
    <div className="work-view">
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
      <div className="work-header">
        <h1 className="work-header__title">Work Overview</h1>
        <p className="work-header__subtitle">Manage your work items, tasks, and jobs</p>
      </div>

      <div className="work-content">
        {/* Stats grid */}
        <div className="mb-8 grid grid-cols-2 gap-4 lg:grid-cols-5">
          <WorkStatCard label="Total" value={stats.total} color="zinc" />
          <WorkStatCard label="Active" value={stats.active} color="blue" pulse />
          <WorkStatCard label="Pending" value={stats.pending} color="yellow" />
          <WorkStatCard label="Completed" value={stats.completed} color="green" />
          <WorkStatCard label="Failed" value={stats.failed} color="red" />
        </div>

        {/* Recent active work */}
        {activeWork.length > 0 && (
          <div className="mb-8">
            <h2 className="work-section-title">Active Work</h2>
            <div className="space-y-3">
              {activeWork.slice(0, 5).map((work) => (
                <WorkCard key={work.id} work={work} />
              ))}
            </div>
          </div>
        )}

        {/* Empty state */}
        {allWork.length === 0 && (
          <div className="work-empty">
            <div className="work-empty__icon-wrap">
              <FolderKanban className="h-8 w-8 text-[var(--color-text-secondary)]" />
            </div>
            <h3 className="work-empty__title">No work items yet</h3>
            <p className="work-empty__description">
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
      <div className="work-header">
        <h1 className="work-header__title">{titles[filter]}</h1>
        <p className="work-header__subtitle">{descriptions[filter]}</p>
      </div>

      {/* Search */}
      <div className="work-search">
        <div className="work-search__input-wrap">
          <Search className="h-4 w-4 work-search__icon" />
          <input
            type="text"
            placeholder="Search work items..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="work-search__input"
          />
        </div>
      </div>

      {/* Content */}
      <div className="work-split">
        {/* Work list */}
        <div className="work-split__list">
          {filteredWork.length === 0 ? (
            <div className="work-list-empty">
              <AlertCircle className="mx-auto h-8 w-8 work-list-empty__icon" />
              <p className="work-list-empty__text">
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
        <div className="work-split__detail">
          {selectedWork ? (
            <WorkDetails work={selectedWork} />
          ) : (
            <div className="work-split__detail-empty">
              <p>Select a work item to view details</p>
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

function WorkStatCard({
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
  return (
    <div className={cn('work-stat', `work-stat--${color}`)}>
      <div className={cn('work-stat__value', pulse && value > 0 && 'animate-pulse')}>
        {value}
      </div>
      <div className="work-stat__label">{label}</div>
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

  const getPriorityClass = (priority: string) => {
    const map: Record<string, string> = {
      urgent: 'work-card__priority--urgent',
      high: 'work-card__priority--high',
      normal: 'work-card__priority--normal',
      low: 'work-card__priority--low',
    }
    return map[priority] || 'work-card__priority--normal'
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        'work-card',
        `work-card--${work.status}`,
        selected && 'work-card--selected',
        onClick && 'work-card--clickable'
      )}
    >
      <div className="flex items-start gap-3">
        {getStatusIcon(work.status)}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="work-card__title">{work.title}</span>
            {work.priority !== 'normal' && (
              <span className={cn('work-card__priority', getPriorityClass(work.priority))}>
                {work.priority}
              </span>
            )}
          </div>
          {work.description && !compact && (
            <p className="work-card__description">{work.description}</p>
          )}

          {/* Progress bar */}
          {work.status === 'in_progress' && work.progress > 0 && (
            <div className="work-card__progress">
              <div className="work-card__progress-header">
                <span>Progress</span>
                <span>{work.progress}%</span>
              </div>
              <div className="work-card__progress-bar">
                <div
                  className="work-card__progress-fill"
                  style={{ width: `${work.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Task count */}
          {work.taskCount !== undefined && work.taskCount > 0 && (
            <div className="work-card__tasks">
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
    <div className="work-details">
      {/* Header */}
      <div className="mb-6">
        <h2 className="work-details__title">{work.title}</h2>
        {work.description && <p className="work-details__description">{work.description}</p>}
        {work.goal && (
          <div className="work-details__goal">
            <div className="work-details__goal-label">Goal</div>
            <p className="work-details__goal-text">{work.goal}</p>
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
        <div className="work-detail-progress">
          <div className="work-detail-progress__header">
            <span className="work-detail-progress__label">Progress</span>
            <span className="work-detail-progress__value">{work.progress}%</span>
          </div>
          <div className="work-detail-progress__bar">
            <div
              className="work-detail-progress__fill"
              style={{ width: `${work.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {work.error && (
        <div className="work-error-box">
          <div className="work-error-box__header">
            <XCircle className="h-5 w-5" />
            <span className="work-error-box__title">Error</span>
          </div>
          <pre className="work-error-box__content">{work.error}</pre>
        </div>
      )}

      {/* Result */}
      {work.result !== undefined && work.result !== null && (
        <div className="work-result-box">
          <div className="work-result-box__header">
            <CheckCircle2 className="h-5 w-5" />
            <span className="work-result-box__title">Result</span>
          </div>
          <pre className="work-result-box__content">
            {typeof work.result === 'string' ? work.result : String(JSON.stringify(work.result, null, 2))}
          </pre>
        </div>
      )}

      {/* Tags */}
      {work.tags.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {work.tags.map((tag) => (
            <span key={tag} className="work-tag">
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
    <div className="work-info-card">
      <div className="work-info-card__label">{label}</div>
      <div className="work-info-card__value">{value}</div>
    </div>
  )
}

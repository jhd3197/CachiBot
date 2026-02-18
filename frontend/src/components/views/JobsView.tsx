import { useState } from 'react'
import {
  Pause,
  RotateCcw,
  Trash2,
  ChevronDown,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  AlertCircle,
  Search,
} from 'lucide-react'
import { useJobStore, useBotStore } from '../../stores/bots'
import { cn } from '../../lib/utils'
import type { Job, JobStatus } from '../../types'

export function JobsView() {
  const { getActiveBot } = useBotStore()
  const { getJobsByBot, activeJobId, setActiveJob, updateJob, deleteJob } = useJobStore()
  const [statusFilter, setStatusFilter] = useState<JobStatus | 'all'>('all')
  const [search, setSearch] = useState('')

  const activeBot = getActiveBot()
  if (!activeBot) return null

  const allJobs = getJobsByBot(activeBot.id)
  const jobs = allJobs.filter((job) => {
    if (statusFilter !== 'all' && job.status !== statusFilter) return false
    if (search && !job.title.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const selectedJob = jobs.find((j) => j.id === activeJobId)

  const stats = {
    total: allJobs.length,
    running: allJobs.filter((j) => j.status === 'running').length,
    pending: allJobs.filter((j) => j.status === 'pending').length,
    completed: allJobs.filter((j) => j.status === 'completed').length,
    failed: allJobs.filter((j) => j.status === 'failed').length,
  }

  return (
    <div className="jobs-view">
      {/* Header */}
      <div className="jobs-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="jobs-header__title">Jobs</h1>
            <p className="jobs-header__subtitle">Background tasks and executions</p>
          </div>

          {/* Stats */}
          <div className="flex items-center gap-4">
            <Stat label="Running" value={stats.running} color="blue" pulse />
            <Stat label="Pending" value={stats.pending} color="zinc" />
            <Stat label="Completed" value={stats.completed} color="green" />
            <Stat label="Failed" value={stats.failed} color="red" />
          </div>
        </div>

        {/* Filters */}
        <div className="mt-4 flex items-center gap-3">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
            <input
              type="text"
              placeholder="Search jobs..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="jobs-search"
            />
          </div>

          <div className="jobs-filter-bar">
            {(['all', 'running', 'pending', 'completed', 'failed'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={cn(
                  'jobs-filter-bar__btn',
                  statusFilter === status
                    ? 'jobs-filter-bar__btn--active'
                    : 'jobs-filter-bar__btn--inactive'
                )}
              >
                {status.charAt(0).toUpperCase() + status.slice(1)}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Job list */}
        <div className="jobs-list">
          {jobs.length === 0 ? (
            <div className="jobs-list__empty">
              <AlertCircle className="jobs-list__empty-icon h-8 w-8" />
              <p className="jobs-list__empty-text">
                {search || statusFilter !== 'all' ? 'No jobs match your filters' : 'No jobs yet'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {jobs.map((job) => (
                <JobCard
                  key={job.id}
                  job={job}
                  selected={activeJobId === job.id}
                  onClick={() => setActiveJob(job.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Job details */}
        <div className="flex-1 overflow-y-auto">
          {selectedJob ? (
            <JobDetails
              job={selectedJob}
              onRetry={() => updateJob(selectedJob.id, { status: 'pending', error: undefined })}
              onCancel={() => updateJob(selectedJob.id, { status: 'cancelled' })}
              onDelete={() => deleteJob(selectedJob.id)}
            />
          ) : (
            <div className="job-details__empty">
              <p>Select a job to view details</p>
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

function Stat({
  label,
  value,
  color,
  pulse,
}: {
  label: string
  value: number
  color: 'blue' | 'green' | 'red' | 'zinc'
  pulse?: boolean
}) {
  return (
    <div className="job-stat">
      <div
        className={cn(
          'job-stat__value',
          `job-stat__value--${color}`,
          pulse && value > 0 && 'animate-pulse'
        )}
      >
        {value}
      </div>
      <span className="job-stat__label">{label}</span>
    </div>
  )
}

function JobCard({
  job,
  selected,
  onClick,
}: {
  job: Job
  selected: boolean
  onClick: () => void
}) {
  const statusConfig: Record<Job['status'], { icon: typeof Clock; color: string; spin?: boolean }> = {
    pending: { icon: Clock, color: 'text-[var(--color-text-secondary)]' },
    running: { icon: Loader2, color: 'text-blue-400', spin: true },
    completed: { icon: CheckCircle, color: 'text-green-400' },
    failed: { icon: XCircle, color: 'text-red-400' },
    cancelled: { icon: AlertCircle, color: 'text-[var(--color-text-secondary)]' },
  }

  const config = statusConfig[job.status]
  const Icon = config.icon

  return (
    <button
      onClick={onClick}
      className={cn(
        'job-card',
        selected && 'job-card--selected'
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-0.5', config.color)}>
          <Icon className={cn('h-5 w-5', config.spin && 'animate-spin')} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="job-card__title">{job.title}</span>
            <span
              className={cn(
                'job-card__priority',
                job.priority === 'urgent' && 'job-card__priority--urgent',
                job.priority === 'high' && 'job-card__priority--high',
                job.priority === 'normal' && 'job-card__priority--normal',
                job.priority === 'low' && 'job-card__priority--low'
              )}
            >
              {job.priority}
            </span>
          </div>
          {job.description && (
            <p className="job-card__description">{job.description}</p>
          )}

          {/* Progress bar */}
          {job.status === 'running' && (
            <div className="job-progress">
              <div className="job-progress__header">
                <span>Progress</span>
                <span>{job.progress}%</span>
              </div>
              <div className="job-progress__track">
                <div
                  className="job-progress__bar"
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Timestamp */}
          <div className="job-card__timestamp">
            {job.completedAt
              ? `Completed ${formatTime(job.completedAt)}`
              : job.startedAt
              ? `Started ${formatTime(job.startedAt)}`
              : `Created ${formatTime(job.createdAt)}`}
          </div>
        </div>
      </div>
    </button>
  )
}

function JobDetails({
  job,
  onRetry,
  onCancel,
  onDelete,
}: {
  job: Job
  onRetry: () => void
  onCancel: () => void
  onDelete: () => void
}) {
  const [showLogs, setShowLogs] = useState(true)

  return (
    <div className="job-details">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="job-details__title">{job.title}</h2>
          {job.description && <p className="job-details__description">{job.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {job.status === 'running' && (
            <button onClick={onCancel} className="job-btn job-btn--cancel">
              <Pause className="h-4 w-4" />
              Cancel
            </button>
          )}
          {(job.status === 'failed' || job.status === 'cancelled') && (
            <button onClick={onRetry} className="job-btn job-btn--retry">
              <RotateCcw className="h-4 w-4" />
              Retry
            </button>
          )}
          <button onClick={onDelete} className="job-btn job-btn--delete">
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Status and timing */}
      <div className="job-info-grid">
        <InfoCard label="Status" value={job.status} />
        <InfoCard label="Priority" value={job.priority} />
        <InfoCard label="Created" value={formatTime(job.createdAt)} />
        <InfoCard
          label="Duration"
          value={
            job.startedAt
              ? formatDuration(job.startedAt, job.completedAt || new Date().toISOString())
              : '-'
          }
        />
      </div>

      {/* Progress */}
      {job.status === 'running' && (
        <div className="job-detail-progress">
          <div className="job-detail-progress__header">
            <span className="job-detail-progress__label">Progress</span>
            <span className="job-detail-progress__value">{job.progress}%</span>
          </div>
          <div className="job-detail-progress__track">
            <div
              className="job-detail-progress__bar"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {job.error && (
        <div className="job-error-panel">
          <div className="job-error-panel__header">
            <XCircle className="h-5 w-5" />
            <span>Error</span>
          </div>
          <pre className="job-error-panel__content">{job.error}</pre>
        </div>
      )}

      {/* Result */}
      {job.result && (
        <div className="job-result-panel">
          <div className="job-result-panel__header">
            <CheckCircle className="h-5 w-5" />
            <span>Result</span>
          </div>
          <pre className="job-result-panel__content">
            {typeof job.result === 'string' ? job.result : String(JSON.stringify(job.result, null, 2))}
          </pre>
        </div>
      )}

      {/* Logs */}
      {job.logs && job.logs.length > 0 && (
        <div className="job-logs">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="job-logs__toggle"
          >
            <span className="job-logs__title">Logs ({job.logs.length})</span>
            <ChevronDown
              className={cn(
                'h-5 w-5 text-[var(--color-text-secondary)] transition-transform',
                showLogs && 'rotate-180'
              )}
            />
          </button>
          {showLogs && (
            <div className="job-logs__body">
              <div className="job-logs__list space-y-1">
                {job.logs.map((log, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="job-logs__timestamp">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span
                      className={cn(
                        'job-logs__level',
                        log.level === 'error' && 'job-logs__level--error',
                        log.level === 'warn' && 'job-logs__level--warn',
                        log.level === 'info' && 'job-logs__level--info',
                        log.level === 'debug' && 'job-logs__level--debug'
                      )}
                    >
                      {log.level}
                    </span>
                    <span className="job-logs__message">{log.message}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="job-info-card">
      <div className="job-info-card__label">{label}</div>
      <div className="job-info-card__value">{value}</div>
    </div>
  )
}

// =============================================================================
// HELPERS
// =============================================================================

function formatTime(isoString: string): string {
  const date = new Date(isoString)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMs / 3600000)
  const diffDays = Math.floor(diffMs / 86400000)

  if (diffMins < 1) return 'just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function formatDuration(start: string, end: string): string {
  const diffMs = new Date(end).getTime() - new Date(start).getTime()
  const seconds = Math.floor(diffMs / 1000)
  const minutes = Math.floor(seconds / 60)
  const hours = Math.floor(minutes / 60)

  if (hours > 0) return `${hours}h ${minutes % 60}m`
  if (minutes > 0) return `${minutes}m ${seconds % 60}s`
  return `${seconds}s`
}

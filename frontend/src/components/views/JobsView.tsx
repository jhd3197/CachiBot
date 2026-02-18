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
    <div className="flex h-full flex-col bg-white dark:bg-[var(--color-bg-app)]">
      {/* Header */}
      <div className="border-b border-zinc-200 dark:border-[var(--color-border-primary)] px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-900 dark:text-[var(--color-text-primary)]">Jobs</h1>
            <p className="text-sm text-[var(--color-text-secondary)]">Background tasks and executions</p>
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
              className="h-9 w-full rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] bg-zinc-100 dark:bg-[var(--card-bg)] pl-10 pr-4 text-sm text-zinc-900 dark:text-[var(--color-text-primary)] placeholder-[var(--input-placeholder)] outline-none focus:border-[var(--color-border-focus)]"
            />
          </div>

          <div className="flex items-center gap-1 rounded-lg border border-zinc-300 dark:border-[var(--color-border-secondary)] bg-zinc-100 dark:bg-[var(--card-bg)] p-1">
            {(['all', 'running', 'pending', 'completed', 'failed'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={cn(
                  'rounded-md px-3 py-1 text-xs font-medium transition-colors',
                  statusFilter === status
                    ? 'bg-zinc-200 dark:bg-[var(--color-hover-bg)] text-zinc-900 dark:text-[var(--color-text-primary)]'
                    : 'text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)] hover:text-zinc-900 dark:hover:text-[var(--color-text-primary)]'
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
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-zinc-200 dark:border-[var(--color-border-primary)] p-4">
          {jobs.length === 0 ? (
            <div className="py-12 text-center">
              <AlertCircle className="mx-auto mb-3 h-8 w-8 text-[var(--color-text-tertiary)]" />
              <p className="text-sm text-[var(--color-text-secondary)]">
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
            <div className="flex h-full items-center justify-center">
              <p className="text-[var(--color-text-secondary)]">Select a job to view details</p>
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
  const colors = {
    blue: 'bg-blue-500/20 text-blue-400',
    green: 'bg-green-500/20 text-green-400',
    red: 'bg-red-500/20 text-red-400',
    zinc: 'bg-zinc-200 dark:bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]',
  }

  return (
    <div className="flex items-center gap-2">
      <div
        className={cn(
          'flex h-8 min-w-[2rem] items-center justify-center rounded-lg px-2 text-sm font-bold',
          colors[color],
          pulse && value > 0 && 'animate-pulse'
        )}
      >
        {value}
      </div>
      <span className="text-xs text-[var(--color-text-secondary)]">{label}</span>
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
  const statusConfig: Record<Job['status'], { icon: typeof Clock; color: string; bg: string; spin?: boolean }> = {
    pending: { icon: Clock, color: 'text-[var(--color-text-secondary)]', bg: 'bg-zinc-500' },
    running: { icon: Loader2, color: 'text-blue-400', bg: 'bg-blue-500', spin: true },
    completed: { icon: CheckCircle, color: 'text-green-400', bg: 'bg-green-500' },
    failed: { icon: XCircle, color: 'text-red-400', bg: 'bg-red-500' },
    cancelled: { icon: AlertCircle, color: 'text-[var(--color-text-secondary)]', bg: 'bg-zinc-600' },
  }

  const config = statusConfig[job.status]
  const Icon = config.icon

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded-xl border p-4 text-left transition-all',
        selected
          ? 'border-cachi-500 bg-cachi-500/10'
          : 'border-zinc-200 dark:border-[var(--color-border-primary)] bg-zinc-50 dark:bg-[var(--color-bg-primary)]/50 hover:border-zinc-400 dark:hover:border-[var(--color-border-secondary)]'
      )}
    >
      <div className="flex items-start gap-3">
        <div className={cn('mt-0.5', config.color)}>
          <Icon className={cn('h-5 w-5', config.spin && 'animate-spin')} />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <span className="truncate font-medium text-zinc-800 dark:text-[var(--color-text-primary)]">{job.title}</span>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-xs font-medium',
                job.priority === 'urgent' && 'bg-red-500/20 text-red-400',
                job.priority === 'high' && 'bg-orange-500/20 text-orange-400',
                job.priority === 'normal' && 'bg-zinc-200 dark:bg-[var(--color-hover-bg)] text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]',
                job.priority === 'low' && 'bg-zinc-200 dark:bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)]'
              )}
            >
              {job.priority}
            </span>
          </div>
          {job.description && (
            <p className="mt-1 truncate text-sm text-[var(--color-text-secondary)]">{job.description}</p>
          )}

          {/* Progress bar */}
          {job.status === 'running' && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-[var(--color-text-secondary)]">
                <span>Progress</span>
                <span>{job.progress}%</span>
              </div>
              <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-zinc-200 dark:bg-[var(--color-bg-secondary)]">
                <div
                  className="h-full rounded-full bg-blue-500 transition-all duration-300"
                  style={{ width: `${job.progress}%` }}
                />
              </div>
            </div>
          )}

          {/* Timestamp */}
          <div className="mt-2 text-xs text-[var(--color-text-tertiary)]">
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
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-xl font-bold text-zinc-900 dark:text-[var(--color-text-primary)]">{job.title}</h2>
          {job.description && <p className="mt-1 text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">{job.description}</p>}
        </div>
        <div className="flex items-center gap-2">
          {job.status === 'running' && (
            <button
              onClick={onCancel}
              className="flex items-center gap-2 rounded-lg bg-zinc-200 dark:bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-zinc-700 dark:text-[var(--color-text-primary)] hover:bg-zinc-200 dark:hover:bg-[var(--color-hover-bg)]"
            >
              <Pause className="h-4 w-4" />
              Cancel
            </button>
          )}
          {(job.status === 'failed' || job.status === 'cancelled') && (
            <button
              onClick={onRetry}
              className="flex items-center gap-2 rounded-lg bg-blue-600 px-3 py-2 text-sm text-white hover:bg-blue-500"
            >
              <RotateCcw className="h-4 w-4" />
              Retry
            </button>
          )}
          <button
            onClick={onDelete}
            className="flex items-center gap-2 rounded-lg bg-red-600/20 px-3 py-2 text-sm text-red-400 hover:bg-red-600/30"
          >
            <Trash2 className="h-4 w-4" />
            Delete
          </button>
        </div>
      </div>

      {/* Status and timing */}
      <div className="mb-6 grid grid-cols-4 gap-4">
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
        <div className="mb-6">
          <div className="mb-2 flex items-center justify-between text-sm">
            <span className="text-[var(--color-text-secondary)] dark:text-[var(--color-text-secondary)]">Progress</span>
            <span className="font-mono text-zinc-700 dark:text-[var(--color-text-primary)]">{job.progress}%</span>
          </div>
          <div className="h-3 overflow-hidden rounded-full bg-zinc-200 dark:bg-[var(--color-bg-secondary)]">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-600 to-cachi-500 transition-all duration-300"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {/* Error message */}
      {job.error && (
        <div className="mb-6 rounded-xl border border-red-500/30 bg-red-500/10 p-4">
          <div className="flex items-center gap-2 text-red-400">
            <XCircle className="h-5 w-5" />
            <span className="font-medium">Error</span>
          </div>
          <pre className="mt-2 overflow-x-auto text-sm text-red-300">{job.error}</pre>
        </div>
      )}

      {/* Result */}
      {job.result && (
        <div className="mb-6 rounded-xl border border-green-500/30 bg-green-500/10 p-4">
          <div className="flex items-center gap-2 text-green-400">
            <CheckCircle className="h-5 w-5" />
            <span className="font-medium">Result</span>
          </div>
          <pre className="mt-2 overflow-x-auto text-sm text-green-300">
            {typeof job.result === 'string' ? job.result : String(JSON.stringify(job.result, null, 2))}
          </pre>
        </div>
      )}

      {/* Logs */}
      {job.logs && job.logs.length > 0 && (
        <div className="rounded-xl border border-zinc-200 dark:border-[var(--color-border-primary)] bg-zinc-50 dark:bg-[var(--color-bg-primary)]/50">
          <button
            onClick={() => setShowLogs(!showLogs)}
            className="flex w-full items-center justify-between px-4 py-3"
          >
            <span className="font-medium text-zinc-700 dark:text-[var(--color-text-primary)]">Logs ({job.logs.length})</span>
            <ChevronDown
              className={cn(
                'h-5 w-5 text-[var(--color-text-secondary)] transition-transform',
                showLogs && 'rotate-180'
              )}
            />
          </button>
          {showLogs && (
            <div className="border-t border-zinc-200 dark:border-[var(--color-border-primary)] p-4">
              <div className="max-h-80 space-y-1 overflow-y-auto font-mono text-xs">
                {job.logs.map((log, i) => (
                  <div key={i} className="flex gap-3">
                    <span className="flex-shrink-0 text-[var(--color-text-tertiary)]">
                      {new Date(log.timestamp).toLocaleTimeString()}
                    </span>
                    <span
                      className={cn(
                        'flex-shrink-0 w-12 uppercase',
                        log.level === 'error' && 'text-red-400',
                        log.level === 'warn' && 'text-yellow-400',
                        log.level === 'info' && 'text-blue-400',
                        log.level === 'debug' && 'text-[var(--color-text-secondary)]'
                      )}
                    >
                      {log.level}
                    </span>
                    <span className="text-zinc-700 dark:text-[var(--color-text-primary)]">{log.message}</span>
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
    <div className="rounded-xl border border-zinc-200 dark:border-[var(--color-border-primary)] bg-zinc-50 dark:bg-[var(--color-bg-primary)]/50 p-3">
      <div className="text-xs text-[var(--color-text-secondary)]">{label}</div>
      <div className="mt-1 font-medium capitalize text-zinc-800 dark:text-[var(--color-text-primary)]">{value}</div>
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

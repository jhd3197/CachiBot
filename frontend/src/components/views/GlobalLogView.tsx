import { useState, useEffect } from 'react'
import {
  Activity,
  AlertCircle,
  Download,
  Loader2,
  Search,
  XCircle,
  StopCircle,
  CheckCircle2,
  Clock,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  adminGetExecutions,
  adminGetStats,
  adminGetErrorSpotlight,
  adminGetCostAnalysis,
  adminGetRunning,
  adminCancelExecution,
  adminCancelAll,
  adminExportCsv,
  type ExecutionLog,
  type ExecutionStats,
  type ErrorSpotlight,
  type CostEntry,
} from '../../api/execution-log'
import { cn } from '../../lib/utils'

type AdminTab = 'logs' | 'errors' | 'costs'

const statusColors: Record<string, string> = {
  running: 'text-blue-500',
  success: 'text-green-500',
  error: 'text-red-500',
  timeout: 'text-yellow-500',
  cancelled: 'text-[var(--color-text-secondary)]',
}

const statusIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  running: Loader2,
  success: CheckCircle2,
  error: XCircle,
  timeout: Clock,
  cancelled: StopCircle,
}

export function GlobalLogView() {
  const [tab, setTab] = useState<AdminTab>('logs')
  const [logs, setLogs] = useState<ExecutionLog[]>([])
  const [stats, setStats] = useState<ExecutionStats | null>(null)
  const [errors, setErrors] = useState<ErrorSpotlight[]>([])
  const [costs, setCosts] = useState<CostEntry[]>([])
  const [running, setRunning] = useState<ExecutionLog[]>([])
  const [loading, setLoading] = useState(true)
  const [period, setPeriod] = useState('24h')
  const [search, setSearch] = useState('')

  useEffect(() => {
    let cancelled = false
    setLoading(true)

    Promise.all([
      adminGetExecutions({ limit: 100 }),
      adminGetStats(period),
      adminGetRunning(),
    ]).then(([execLogs, execStats, runningExecs]) => {
      if (cancelled) return
      setLogs(execLogs)
      setStats(execStats)
      setRunning(runningExecs)
      setLoading(false)
    }).catch((err) => {
      if (!cancelled) {
        setLoading(false)
        toast.error(err?.message || 'Failed to load execution logs')
      }
    })

    return () => { cancelled = true }
  }, [period])

  useEffect(() => {
    if (tab === 'errors') {
      adminGetErrorSpotlight(7).then(setErrors).catch(() => {})
    } else if (tab === 'costs') {
      adminGetCostAnalysis(30, 20).then(setCosts).catch(() => {})
    }
  }, [tab])

  const handleCancel = async (execId: string) => {
    try {
      await adminCancelExecution(execId)
      setRunning((prev) => prev.filter((r) => r.id !== execId))
      toast.success('Execution cancelled')
    } catch {
      toast.error('Failed to cancel execution')
    }
  }

  const handleCancelAll = async () => {
    try {
      const { cancelledCount } = await adminCancelAll()
      setRunning([])
      toast.success(`Cancelled ${cancelledCount} executions`)
    } catch {
      toast.error('Failed to cancel all')
    }
  }

  const handleExport = async () => {
    try {
      const csv = await adminExportCsv()
      const blob = new Blob([csv], { type: 'text/csv' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = 'execution_logs.csv'
      a.click()
      URL.revokeObjectURL(url)
    } catch {
      toast.error('Export failed')
    }
  }

  const filteredLogs = search
    ? logs.filter(
        (l) =>
          l.sourceName.toLowerCase().includes(search.toLowerCase()) ||
          l.executionType.toLowerCase().includes(search.toLowerCase()) ||
          l.status.toLowerCase().includes(search.toLowerCase())
      )
    : logs

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-[var(--color-border-primary)]">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">
            Execution Dashboard
          </h1>
          <p className="text-xs text-[var(--color-text-secondary)]">Global execution logs and analytics</p>
        </div>
        <div className="flex items-center gap-2">
          {running.length > 0 && (
            <button
              onClick={handleCancelAll}
              className="flex items-center gap-1.5 rounded-lg bg-red-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-red-700"
            >
              <StopCircle className="h-3.5 w-3.5" />
              Cancel All ({running.length})
            </button>
          )}
          <button
            onClick={handleExport}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-200 px-3 py-1.5 text-xs font-medium text-zinc-700 hover:bg-zinc-50 dark:border-[var(--color-border-secondary)] dark:text-[var(--color-text-primary)] dark:hover:bg-[var(--color-hover-bg)]"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="grid grid-cols-4 gap-4 border-b border-zinc-200 px-6 py-3 dark:border-[var(--color-border-primary)]">
          <StatCard label="Total Runs" value={stats.totalRuns.toString()} icon={Activity} />
          <StatCard
            label="Success Rate"
            value={stats.totalRuns > 0 ? `${Math.round((stats.successCount / stats.totalRuns) * 100)}%` : '0%'}
            icon={CheckCircle2}
            color="text-green-500"
          />
          <StatCard
            label="Errors"
            value={stats.errorCount.toString()}
            icon={AlertCircle}
            color="text-red-500"
          />
          <StatCard
            label="Avg Duration"
            value={`${Math.round(stats.avgDurationMs)}ms`}
            icon={Clock}
          />
        </div>
      )}

      {/* Tabs + period selector */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-6 dark:border-[var(--color-border-primary)]">
        <div className="flex items-center gap-1">
          {(['logs', 'errors', 'costs'] as AdminTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'border-b-2 px-3 py-2 text-xs font-medium capitalize transition-colors',
                tab === t
                  ? 'border-accent-600 text-accent-600 dark:text-accent-400'
                  : 'border-transparent text-[var(--color-text-secondary)] hover:text-zinc-700 dark:hover:text-[var(--color-text-primary)]'
              )}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2">
          {tab === 'logs' && (
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-text-secondary)]" />
              <input
                type="text"
                placeholder="Search logs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-7 w-40 rounded-md border border-zinc-200 bg-white pl-8 pr-3 text-xs text-zinc-900 placeholder-[var(--input-placeholder)] focus:border-accent-500 focus:outline-none dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-primary)]"
              />
            </div>
          )}
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="h-7 rounded-md border border-zinc-200 bg-white px-2 text-xs text-zinc-700 dark:border-[var(--color-border-secondary)] dark:bg-[var(--color-bg-secondary)] dark:text-[var(--color-text-primary)]"
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
          </div>
        ) : (
          <>
            {tab === 'logs' && (
              <div className="divide-y divide-zinc-100 dark:divide-[var(--color-border-primary)]/50">
                {filteredLogs.map((log) => {
                  const StatusIcon = statusIcons[log.status] || Clock
                  return (
                    <div
                      key={log.id}
                      className="flex items-center gap-4 px-6 py-3 hover:bg-zinc-50 dark:hover:bg-[var(--color-bg-primary)]/50"
                    >
                      <StatusIcon
                        className={cn(
                          'h-4 w-4 flex-shrink-0',
                          statusColors[log.status] || 'text-[var(--color-text-secondary)]',
                          log.status === 'running' && 'animate-spin'
                        )}
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-zinc-900 dark:text-[var(--color-text-primary)] truncate">
                            {log.sourceName}
                          </span>
                          <span className="rounded bg-zinc-100 px-1.5 py-0.5 text-[10px] text-[var(--color-text-secondary)] dark:bg-[var(--color-bg-secondary)]">
                            {log.executionType}
                          </span>
                        </div>
                        <p className="mt-0.5 text-[10px] text-[var(--color-text-secondary)] truncate">
                          {log.trigger} - {new Date(log.startedAt).toLocaleString()}
                        </p>
                      </div>
                      <div className="flex items-center gap-3 text-[10px] text-[var(--color-text-secondary)]">
                        {log.durationMs != null && <span>{log.durationMs}ms</span>}
                        {log.tokensUsed > 0 && <span>{log.tokensUsed} tok</span>}
                        {log.creditsConsumed > 0 && <span>${log.creditsConsumed.toFixed(4)}</span>}
                      </div>
                      {log.status === 'running' && (
                        <button
                          onClick={() => handleCancel(log.id)}
                          className="text-[10px] text-red-500 hover:underline"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  )
                })}
                {filteredLogs.length === 0 && (
                  <div className="py-12 text-center text-sm text-[var(--color-text-secondary)]">No execution logs found</div>
                )}
              </div>
            )}

            {tab === 'errors' && (
              <div className="p-6 space-y-3">
                {errors.length === 0 ? (
                  <div className="text-center py-12 text-sm text-[var(--color-text-secondary)]">No errors in the last 7 days</div>
                ) : (
                  errors.map((err, i) => (
                    <div
                      key={i}
                      className="rounded-lg border border-zinc-200 p-4 dark:border-[var(--color-border-primary)]"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium text-red-500">{err.errorType}</span>
                        <span className="rounded-full bg-red-500/10 px-2 py-0.5 text-[10px] font-medium text-red-500">
                          {err.count}x
                        </span>
                      </div>
                      <p className="mt-1 text-[10px] text-[var(--color-text-secondary)]">
                        Last seen: {new Date(err.lastSeen).toLocaleString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}

            {tab === 'costs' && (
              <div className="p-6">
                {costs.length === 0 ? (
                  <div className="text-center py-12 text-sm text-[var(--color-text-secondary)]">No cost data available</div>
                ) : (
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-zinc-200 text-left text-[var(--color-text-secondary)] dark:border-[var(--color-border-primary)]">
                        <th className="pb-2 font-medium">Bot</th>
                        <th className="pb-2 font-medium text-right">Executions</th>
                        <th className="pb-2 font-medium text-right">Tokens</th>
                        <th className="pb-2 font-medium text-right">Credits</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-zinc-100 dark:divide-[var(--color-border-primary)]/50">
                      {costs.map((c, i) => (
                        <tr key={i}>
                          <td className="py-2 font-medium text-zinc-900 dark:text-[var(--color-text-primary)]">
                            {c.botName || c.botId}
                          </td>
                          <td className="py-2 text-right text-[var(--color-text-secondary)]">{c.executionCount}</td>
                          <td className="py-2 text-right text-[var(--color-text-secondary)]">{c.totalTokens.toLocaleString()}</td>
                          <td className="py-2 text-right text-[var(--color-text-secondary)]">${c.totalCredits.toFixed(4)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string
  value: string
  icon: React.ComponentType<{ className?: string }>
  color?: string
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-100 dark:bg-[var(--color-bg-secondary)]">
        <Icon className={cn('h-4 w-4', color || 'text-[var(--color-text-secondary)]')} />
      </div>
      <div>
        <p className="text-xs text-[var(--color-text-secondary)]">{label}</p>
        <p className="text-sm font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">{value}</p>
      </div>
    </div>
  )
}

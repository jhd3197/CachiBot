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
    <div className="global-log">
      {/* Header */}
      <div className="global-log-header">
        <div>
          <h1 className="global-log-header__title">
            Execution Dashboard
          </h1>
          <p className="global-log-header__subtitle">Global execution logs and analytics</p>
        </div>
        <div className="global-log-header__actions">
          {running.length > 0 && (
            <button
              onClick={handleCancelAll}
              className="global-log-btn global-log-btn--danger"
            >
              <StopCircle className="h-3.5 w-3.5" />
              Cancel All ({running.length})
            </button>
          )}
          <button
            onClick={handleExport}
            className="global-log-btn global-log-btn--secondary"
          >
            <Download className="h-3.5 w-3.5" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="global-log-stats">
          <LogStatCard label="Total Runs" value={stats.totalRuns.toString()} icon={Activity} />
          <LogStatCard
            label="Success Rate"
            value={stats.totalRuns > 0 ? `${Math.round((stats.successCount / stats.totalRuns) * 100)}%` : '0%'}
            icon={CheckCircle2}
            color="text-green-500"
          />
          <LogStatCard
            label="Errors"
            value={stats.errorCount.toString()}
            icon={AlertCircle}
            color="text-red-500"
          />
          <LogStatCard
            label="Avg Duration"
            value={`${Math.round(stats.avgDurationMs)}ms`}
            icon={Clock}
          />
        </div>
      )}

      {/* Tabs + period selector */}
      <div className="global-log-tabs">
        <div className="global-log-tabs__list">
          {(['logs', 'errors', 'costs'] as AdminTab[]).map((t) => (
            <button
              key={t}
              onClick={() => setTab(t)}
              className={cn(
                'global-log-tabs__tab',
                tab === t && 'global-log-tabs__tab--active'
              )}
            >
              {t}
            </button>
          ))}
        </div>
        <div className="global-log-tabs__controls">
          {tab === 'logs' && (
            <div className="global-log-search">
              <Search className="h-3.5 w-3.5 global-log-search__icon" />
              <input
                type="text"
                placeholder="Search logs..."
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="global-log-search__input"
              />
            </div>
          )}
          <select
            value={period}
            onChange={(e) => setPeriod(e.target.value)}
            className="global-log-select"
          >
            <option value="24h">Last 24h</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>
        </div>
      </div>

      {/* Content */}
      <div className="global-log-content">
        {loading ? (
          <div className="global-log-loading">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : (
          <>
            {tab === 'logs' && (
              <div className="global-log-list">
                {filteredLogs.map((log) => {
                  const StatusIcon = statusIcons[log.status] || Clock
                  return (
                    <div
                      key={log.id}
                      className="log-entry"
                    >
                      <StatusIcon
                        className={cn(
                          'h-4 w-4 log-entry__status-icon',
                          statusColors[log.status] || 'text-[var(--color-text-secondary)]',
                          log.status === 'running' && 'animate-spin'
                        )}
                      />
                      <div className="log-entry__body">
                        <div className="flex items-center gap-2">
                          <span className="log-entry__name">
                            {log.sourceName}
                          </span>
                          <span className="log-entry__type-badge">
                            {log.executionType}
                          </span>
                        </div>
                        <p className="log-entry__meta">
                          {log.trigger} - {new Date(log.startedAt).toLocaleString()}
                        </p>
                      </div>
                      <div className="log-entry__metrics">
                        {log.durationMs != null && <span>{log.durationMs}ms</span>}
                        {log.tokensUsed > 0 && <span>{log.tokensUsed} tok</span>}
                        {log.creditsConsumed > 0 && <span>${log.creditsConsumed.toFixed(4)}</span>}
                      </div>
                      {log.status === 'running' && (
                        <button
                          onClick={() => handleCancel(log.id)}
                          className="log-entry__cancel"
                        >
                          Cancel
                        </button>
                      )}
                    </div>
                  )
                })}
                {filteredLogs.length === 0 && (
                  <div className="global-log-empty">No execution logs found</div>
                )}
              </div>
            )}

            {tab === 'errors' && (
              <div className="global-log-errors">
                {errors.length === 0 ? (
                  <div className="global-log-empty">No errors in the last 7 days</div>
                ) : (
                  errors.map((err, i) => (
                    <div
                      key={i}
                      className="error-entry"
                    >
                      <div className="error-entry__header">
                        <span className="error-entry__type">{err.errorType}</span>
                        <span className="error-entry__count">
                          {err.count}x
                        </span>
                      </div>
                      <p className="error-entry__meta">
                        Last seen: {new Date(err.lastSeen).toLocaleString()}
                      </p>
                    </div>
                  ))
                )}
              </div>
            )}

            {tab === 'costs' && (
              <div className="global-log-costs">
                {costs.length === 0 ? (
                  <div className="global-log-empty">No cost data available</div>
                ) : (
                  <table className="cost-table">
                    <thead>
                      <tr className="cost-table__head-row">
                        <th className="cost-table__th">Bot</th>
                        <th className="cost-table__th cost-table__th--right">Executions</th>
                        <th className="cost-table__th cost-table__th--right">Tokens</th>
                        <th className="cost-table__th cost-table__th--right">Credits</th>
                      </tr>
                    </thead>
                    <tbody className="cost-table__body">
                      {costs.map((c, i) => (
                        <tr key={i}>
                          <td className="cost-table__td cost-table__td--name">
                            {c.botName || c.botId}
                          </td>
                          <td className="cost-table__td cost-table__td--right">{c.executionCount}</td>
                          <td className="cost-table__td cost-table__td--right">{c.totalTokens.toLocaleString()}</td>
                          <td className="cost-table__td cost-table__td--right">${c.totalCredits.toFixed(4)}</td>
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

function LogStatCard({
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
    <div className="global-log-stat">
      <div className="global-log-stat__icon-wrap">
        <Icon className={cn('h-4 w-4', color || 'text-[var(--color-text-secondary)]')} />
      </div>
      <div>
        <p className="global-log-stat__label">{label}</p>
        <p className="global-log-stat__value">{value}</p>
      </div>
    </div>
  )
}

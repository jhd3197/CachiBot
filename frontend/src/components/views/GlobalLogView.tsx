import { useState, useEffect, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Ban,
  ChevronDown,
  ChevronLeft,
  Copy,
  Loader2,
  MessageSquare,
} from 'lucide-react'
import { toast } from 'sonner'
import {
  adminGetExecutions,
  adminGetErrorSpotlight,
  adminGetCostAnalysis,
  adminGetRunning,
  adminCancelExecution,
  adminCancelAll,
  adminExportCsv,
  type ExecutionLog,
  type ErrorSpotlight,
  type CostEntry,
} from '../../api/execution-log'
import { useBotStore } from '../../stores/bots'
import { BotAvatar } from '../common/Avatar'
import { cn, parseApiDate } from '../../lib/utils'

/**
 * Activity log (design view 20, admins only): every tool and code run across
 * all bots from the real admin executions API. The design's "Blocked" state
 * has no source — the API has no blocked status/policy-reason fields — so the
 * Blocked chip and blocked card are hidden (see UI_V2_PLAN.md). Failed runs
 * expand into the design's explanation card, backed by the log's real
 * error/output, with Open the chat (when the run links a chat) and
 * Cancel (for running executions). Error spotlight and per-bot cost analysis
 * from the same API stay reachable below the table.
 */

type LogFilter = 'all' | 'failed' | 'running'
type Period = 'today' | '7d' | '30d'

const PERIOD_MS: Record<Exclude<Period, 'today'>, number> = {
  '7d': 7 * 24 * 60 * 60 * 1000,
  '30d': 30 * 24 * 60 * 60 * 1000,
}

const LOAD_LIMIT = 200

const FILTERS: { id: LogFilter; label: string }[] = [
  { id: 'all', label: 'All' },
  { id: 'failed', label: 'Failed' },
  { id: 'running', label: 'Running' },
]

function periodFromDate(period: Period): string | undefined {
  if (period === 'today') {
    const d = new Date()
    d.setHours(0, 0, 0, 0)
    return d.toISOString()
  }
  return new Date(Date.now() - PERIOD_MS[period]).toISOString()
}

type RowStatus = 'done' | 'failed' | 'running' | 'cancelled' | 'needs-you'

function rowStatus(log: ExecutionLog): RowStatus {
  switch (log.status) {
    case 'error':
    case 'timeout':
      return 'failed'
    case 'cancelled':
      return 'cancelled'
    case 'credit_exhausted':
      return 'needs-you'
    case 'running':
      return 'running'
    default:
      return 'done'
  }
}

const STATUS_META: Record<RowStatus, { label: string; className: string }> = {
  done: { label: 'Done', className: '' },
  failed: { label: 'Failed', className: 'v2-log__cell--result--failed' },
  running: { label: 'Running', className: 'v2-log__cell--result--running' },
  cancelled: { label: 'Cancelled', className: '' },
  'needs-you': { label: 'Needs you', className: 'v2-log__cell--result--blocked' },
}

/** Design duration format: "0.4s" under 10s, "0:41" under an hour, "1:52" beyond. */
function formatDuration(ms: number | null): string {
  if (ms == null) return '—'
  const s = ms / 1000
  if (s < 10) return `${s.toFixed(1)}s`
  const whole = Math.round(s)
  const m = Math.floor(whole / 60)
  if (m < 60) return `${m}:${String(whole % 60).padStart(2, '0')}`
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`
}

function formatTime(d: Date, period: Period): string {
  const time = d.toLocaleTimeString(undefined, { hour12: false })
  if (period !== 'today') {
    return `${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}, ${time}`
  }
  return time
}

export function GlobalLogView() {
  const navigate = useNavigate()
  const { bots } = useBotStore()
  const [logs, setLogs] = useState<ExecutionLog[]>([])
  const [running, setRunning] = useState<ExecutionLog[]>([])
  const [errors, setErrors] = useState<ErrorSpotlight[]>([])
  const [costs, setCosts] = useState<CostEntry[]>([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [filter, setFilter] = useState<LogFilter>('all')
  const [period, setPeriod] = useState<Period>('today')
  const [botFilter, setBotFilter] = useState('all')
  const [openId, setOpenId] = useState<string | null>(null)

  const botById = useMemo(() => new Map(bots.map((b) => [b.id, b])), [bots])

  const load = async () => {
    setLoading(true)
    setLoadError(false)
    try {
      const fromDate = periodFromDate(period)
      const [execLogs, runningExecs] = await Promise.all([
        adminGetExecutions({ fromDate, limit: LOAD_LIMIT }),
        adminGetRunning(),
      ])
      setLogs(execLogs)
      setRunning(runningExecs)
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    void load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period])

  // Analytics from the same admin API (kept from the old dashboard)
  useEffect(() => {
    adminGetErrorSpotlight(7).then(setErrors).catch(() => {})
    adminGetCostAnalysis(30, 20).then(setCosts).catch(() => {})
  }, [])

  const counts = useMemo(() => {
    let failed = 0
    let runningCount = 0
    for (const log of logs) {
      const status = rowStatus(log)
      if (status === 'failed') failed++
      if (status === 'running') runningCount++
    }
    return { failed, running: runningCount }
  }, [logs])

  // If the last running/failed row disappears while its chip is active, back to All
  useEffect(() => {
    if (filter === 'failed' && counts.failed === 0) setFilter('all')
    if (filter === 'running' && counts.running === 0) setFilter('all')
  }, [filter, counts.failed, counts.running])

  const filtered = useMemo(() => {
    return logs
      .filter((log) => botFilter === 'all' || log.botId === botFilter)
      .filter((log) => {
        if (filter === 'all') return true
        const status = rowStatus(log)
        if (filter === 'failed') return status === 'failed'
        return status === 'running'
      })
      .sort((a, b) => parseApiDate(b.startedAt).getTime() - parseApiDate(a.startedAt).getTime())
  }, [logs, filter, botFilter])

  const handleCancel = async (exec: ExecutionLog) => {
    try {
      await adminCancelExecution(exec.id)
      setRunning((prev) => prev.filter((r) => r.id !== exec.id))
      setLogs((prev) => prev.map((l) => (l.id === exec.id ? { ...l, status: 'cancelled' } : l)))
      toast.success('Execution cancelled')
    } catch {
      toast.error('Failed to cancel execution')
    }
  }

  const handleCancelAll = async () => {
    try {
      const { cancelledCount } = await adminCancelAll()
      setRunning([])
      setLogs((prev) => prev.map((l) => (l.status === 'running' ? { ...l, status: 'cancelled' } : l)))
      toast.success(`Cancelled ${cancelledCount} executions`)
    } catch {
      toast.error('Failed to cancel all')
    }
  }

  const handleExport = async () => {
    try {
      const csv = await adminExportCsv(
        botFilter !== 'all' ? botFilter : undefined,
        periodFromDate(period)
      )
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

  const copyDetails = (log: ExecutionLog) => {
    const text = JSON.stringify(
      {
        id: log.id,
        botId: log.botId,
        sourceName: log.sourceName,
        executionType: log.executionType,
        sourceType: log.sourceType,
        status: log.status,
        trigger: log.trigger,
        startedAt: log.startedAt,
        durationMs: log.durationMs,
        error: log.error,
        output: log.output,
        exitCode: log.exitCode,
        tokensUsed: log.tokensUsed,
        creditsConsumed: log.creditsConsumed,
      },
      null,
      2
    )
    navigator.clipboard
      .writeText(text)
      .then(() => toast.success('Details copied'))
      .catch(() => toast.error('Copy failed'))
  }

  return (
    <div className="v2-log">
      <div className="v2-log__column">
        <button type="button" className="v2-log__back" onClick={() => navigate('/settings/advanced')}>
          <ChevronLeft size={14} strokeWidth={1.8} aria-hidden="true" />
          Settings
        </button>

        <header className="v2-log__header">
          <h1 className="v2-log__title">Activity log</h1>
          <p className="v2-log__subtitle">Every tool and code run, across all bots. Only admins see this.</p>
        </header>

        {/* Filter chips + dropdowns + export */}
        <div className="v2-log__toolbar">
          {FILTERS.map((f) => {
            const count = f.id === 'failed' ? counts.failed : f.id === 'running' ? counts.running : null
            // Hidden when nothing matches — the count is real and currently 0
            if (f.id !== 'all' && count === 0) return null
            return (
              <button
                key={f.id}
                type="button"
                className={cn('v2-log__chip', filter === f.id && 'v2-log__chip--active')}
                onClick={() => setFilter(f.id)}
              >
                {f.label}
                {count != null && ` · ${count}`}
              </button>
            )
          })}
          {running.length > 0 && (
            <button type="button" className="v2-log__chip" onClick={() => void handleCancelAll()}>
              Cancel all
            </button>
          )}
          <span className="v2-log__toolbar-right">
            <span className="v2-log__select-wrap">
              <select
                className="v2-log__select"
                value={botFilter}
                aria-label="Filter by bot"
                onChange={(e) => setBotFilter(e.target.value)}
              >
                <option value="all">All bots</option>
                {bots.map((bot) => (
                  <option key={bot.id} value={bot.id}>
                    {bot.name}
                  </option>
                ))}
              </select>
              <ChevronDown size={12} strokeWidth={1.8} aria-hidden="true" />
            </span>
            <span className="v2-log__select-wrap">
              <select
                className="v2-log__select"
                value={period}
                aria-label="Period"
                onChange={(e) => setPeriod(e.target.value as Period)}
              >
                <option value="today">Today</option>
                <option value="7d">Last 7 days</option>
                <option value="30d">Last 30 days</option>
              </select>
              <ChevronDown size={12} strokeWidth={1.8} aria-hidden="true" />
            </span>
            <button type="button" className="v2-log__chip" onClick={() => void handleExport()}>
              Export
            </button>
          </span>
        </div>

        {/* Table */}
        <section className="v2-log__grid" aria-label="Execution log">
          <div className="v2-log__head" aria-hidden="true">
            <span>Time</span>
            <span>Bot</span>
            <span>Tool</span>
            <span>What</span>
            <span>Result</span>
            <span className="v2-log__head-took">Took</span>
          </div>

          {loading ? (
            <div className="v2-log__loading">
              <Loader2 size={18} strokeWidth={1.8} className="runs__spin" aria-hidden="true" />
            </div>
          ) : loadError ? (
            <div className="v2-log__empty">
              <p>Couldn't load the activity log.</p>
              <button type="button" className="v2-btn v2-btn--secondary" onClick={() => void load()}>
                Try again
              </button>
            </div>
          ) : filtered.length === 0 ? (
            <div className="v2-log__empty">
              {filter !== 'all' || botFilter !== 'all'
                ? 'No runs match this filter.'
                : 'No runs in this period.'}
            </div>
          ) : (
            filtered.map((log) => {
              const bot = botById.get(log.botId)
              const status = rowStatus(log)
              const isOpen = openId === log.id
              return (
                <div key={log.id}>
                  <button
                    type="button"
                    className={cn('v2-log__row', isOpen && 'v2-log__row--open')}
                    aria-expanded={isOpen}
                    onClick={() => setOpenId(isOpen ? null : log.id)}
                  >
                    <span className="v2-log__cell--time">
                      {formatTime(parseApiDate(log.startedAt), period)}
                    </span>
                    <span className="v2-log__cell--bot">
                      <BotAvatar
                        color={bot?.color}
                        name={bot?.name ?? 'Unknown bot'}
                        size={20}
                      />
                      {bot?.name ?? log.botId.slice(0, 8)}
                    </span>
                    <span className="v2-log__cell--tool" title={log.executionType}>
                      {log.executionType}
                    </span>
                    <span className="v2-log__cell--what" title={log.sourceName}>
                      {log.sourceName}
                    </span>
                    <span className={cn('v2-log__cell--result', STATUS_META[status].className)}>
                      {status === 'running' && (
                        <Loader2 size={12} strokeWidth={1.8} className="runs__spin" aria-hidden="true" />
                      )}
                      {STATUS_META[status].label}
                    </span>
                    <span className="v2-log__cell--took">{formatDuration(log.durationMs)}</span>
                  </button>

                  {isOpen && (
                    <div className="v2-log__detail">
                      {/* The design's explanation card, backed by the real
                          error/output the API returns */}
                      {log.error ? (
                        <pre className="v2-log__detail-pre">{log.error}</pre>
                      ) : log.output ? (
                        <pre className="v2-log__detail-pre">{log.output}</pre>
                      ) : (
                        <p className="v2-log__detail-text">
                          {status === 'running'
                            ? 'This run is still in progress.'
                            : status === 'cancelled'
                              ? 'This run was cancelled.'
                              : 'This run finished without output.'}
                        </p>
                      )}
                      <div className="v2-log__detail-actions">
                        {log.chatId && (
                          <button
                            type="button"
                            className="v2-btn v2-btn--primary"
                            onClick={() => navigate(`/${log.botId}/chats/${log.chatId}`)}
                          >
                            <MessageSquare size={14} strokeWidth={1.8} aria-hidden="true" />
                            Open the chat
                          </button>
                        )}
                        <button
                          type="button"
                          className="v2-btn v2-btn--secondary"
                          onClick={() => copyDetails(log)}
                        >
                          <Copy size={14} strokeWidth={1.8} aria-hidden="true" />
                          Copy details
                        </button>
                        {status === 'running' && (
                          <button
                            type="button"
                            className="v2-btn v2-btn--secondary"
                            onClick={() => void handleCancel(log)}
                          >
                            <Ban size={14} strokeWidth={1.8} aria-hidden="true" />
                            Cancel
                          </button>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </section>

        {/* Error spotlight (real, last 7 days) */}
        {errors.length > 0 && (
          <>
            <h2 className="v2-log__section-title">Errors · last 7 days</h2>
            <div className="v2-log__errors">
              {errors.map((err, i) => (
                <div key={i} className="v2-log__error">
                  <span className="v2-log__error-type" title={err.errorType}>
                    {err.errorType}
                  </span>
                  <span className="v2-log__error-count">{err.count}&times;</span>
                  <span className="v2-log__error-seen">
                    last seen {parseApiDate(err.lastSeen).toLocaleString()}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}

        {/* Cost analysis (real, last 30 days) */}
        {costs.length > 0 && (
          <>
            <h2 className="v2-log__section-title">Costs per bot · last 30 days</h2>
            <table className="v2-log__cost-table">
              <thead>
                <tr>
                  <th>Bot</th>
                  <th>Executions</th>
                  <th>Tokens</th>
                  <th>Credits</th>
                </tr>
              </thead>
              <tbody>
                {costs.map((c, i) => (
                  <tr key={`${c.botId}-${i}`}>
                    <td>{c.botName || c.botId}</td>
                    <td>{c.executionCount}</td>
                    <td>{c.totalTokens.toLocaleString()}</td>
                    <td>${c.totalCredits.toFixed(4)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        )}
      </div>
    </div>
  )
}

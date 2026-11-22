import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Ban,
  Check,
  ChevronDown,
  ChevronLeft,
  CircleDot,
  Clock,
  GitCommit,
  Loader2,
  Pencil,
  Plus,
  Power,
  PowerOff,
  Trash2,
  X,
} from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { useAuthStore } from '../../stores/auth'
import { useApprovalsStore } from '../../stores/approvals'
import {
  cancelExecution,
  getExecutionLines,
  getExecutionStats,
  getExecutions,
  getRunningExecutions,
  type ExecutionLog,
  type LogLine,
} from '../../api/execution-log'
import { getBotTimeline, runScript, type TimelineEvent } from '../../api/automations'
import {
  dismissTodo,
  getSchedule,
  getOpenTodos,
  markTodoDone,
  runFunction,
} from '../../api/client'
import { botAccessRank } from '../../hooks/useBotAccess'
import { BotAvatar } from '../common/Avatar'
import { cn, parseApiDate } from '../../lib/utils'
import type { Todo } from '../../types'

/**
 * Cross-bot Runs page (design views 16 / 12): everything the bots did on
 * their own (routines/schedules, functions, scripts, work) grouped by day.
 * Per the "where things moved" map: Work merged into Runs (its runs are the
 * "work"-typed rows), quick tasks are a checklist here, and the Automations
 * timeline lives here. Operator+ only.
 *
 * Data sources (all real):
 * - Runs: GET /api/bots/{id}/executions + /executions/running, fanned out over
 *   the bots the user can operate (there is no non-admin cross-bot endpoint).
 *   A bot whose calls fail is dropped; if every call fails the page shows an
 *   error state.
 * - Quick tasks checklist: GET /api/bots/{id}/todos/open per operable bot;
 *   checking completes via POST /todos/{id}/done, ✕ dismisses via /dismiss.
 * - Timeline: GET /api/bots/{id}/timeline per operable bot (events written by
 *   job_runner and the scripts API).
 * - Stuck banner: running executions older than 1h; "Clear them" cancels each
 *   via POST /api/bots/{id}/executions/{execId}/cancel. Hidden when none.
 * - Needs you: executions with status credit_exhausted, or still running with a
 *   pending tool approval in their chat (stores/approvals.ts, live WS state).
 * - Step/output lines: GET /api/bots/{id}/executions/{execId}/lines, falling
 *   back to the log's error/output (see UI_V2_PLAN.md — lines aren't written
 *   by the backend yet).
 * - Open in chat: only shown when the execution links a chatId.
 * - Run again: only for script (POST /scripts/{id}/run), function
 *   (POST /functions/{id}/run) and schedule (its function with the schedule's
 *   stored params) sources — the only real re-run endpoints.
 * - Footer retention: retentionDays from GET /api/bots/{id}/executions/stats
 *   (same value the server's log retention service enforces); hidden on error.
 * - Export: client-side CSV of the rows currently loaded.
 * - Activity log: link to /admin/logs, admins only (per the moved map).
 */

/** A run still "running" after an hour is stuck (routine timeouts default to 5 min). */
const STUCK_MS = 60 * 60 * 1000
/** Load window: widest retention tier; the server only returns what it kept. */
const WINDOW_MS = 90 * 24 * 60 * 60 * 1000
/** Cap per bot — the executions API max (le). */
const PER_BOT_LIMIT = 200
/** Timeline events shown at most (across bots). */
const TIMELINE_CAP = 60

type RunStatus = 'done' | 'running' | 'failed' | 'stuck' | 'cancelled' | 'needs-you'
type RunFilter = 'all' | 'needs-you' | 'failed' | 'running'

const STATUS_META: Record<RunStatus, { label: string; className: string }> = {
  done: { label: 'Done', className: 'runs__status--done' },
  running: { label: 'Running', className: 'runs__status--running' },
  failed: { label: 'Failed', className: 'runs__status--failed' },
  stuck: { label: 'Stuck', className: 'runs__status--stuck' },
  cancelled: { label: 'Cancelled', className: 'runs__status--stuck' },
  'needs-you': { label: 'Needs you', className: 'runs__status--needs-you' },
}

export function RunsView() {
  const navigate = useNavigate()
  const { bots } = useBotStore()
  const { user } = useAuthStore()
  const { pending: pendingApprovals } = useApprovalsStore()
  const [searchParams] = useSearchParams()
  const [runs, setRuns] = useState<ExecutionLog[]>([])
  const [todos, setTodos] = useState<Todo[]>([])
  const [timelineEvents, setTimelineEvents] = useState<TimelineEvent[]>([])
  const [anyReachable, setAnyReachable] = useState(true)
  const [loaded, setLoaded] = useState(false)
  const [retentionDays, setRetentionDays] = useState<number | null>(null)
  const retentionRef = useRef<number | null>(null)
  const [filter, setFilter] = useState<RunFilter>('all')
  // ?bot=<id> preselects the bot filter (e.g. from Workspace needs-you items)
  const [botFilter, setBotFilter] = useState<string>(() => searchParams.get('bot') ?? 'all')
  const [openId, setOpenId] = useState<string | null>(null)
  const [linesById, setLinesById] = useState<Record<string, LogLine[] | null>>({})
  const [clearing, setClearing] = useState(false)
  const [rerunningId, setRerunningId] = useState<string | null>(null)

  const botById = useMemo(() => new Map(bots.map((b) => [b.id, b])), [bots])
  const isAdmin = user?.role === 'admin'
  // Runs is operator+ (per the "where things moved" map); viewers see no data
  const operableBots = useMemo(
    () => bots.filter((b) => botAccessRank(b, isAdmin) >= 2),
    [bots, isAdmin]
  )
  // Ignore a ?bot= that doesn't match a known bot
  const activeBotFilter = bots.some((b) => b.id === botFilter) ? botFilter : 'all'

  const load = useCallback(async () => {
    if (operableBots.length === 0) {
      setLoaded(true)
      return
    }
    const fromDate = new Date(Date.now() - WINDOW_MS).toISOString()
    const results = await Promise.all(
      operableBots.map(async (bot) => {
        const [history, running, openTodos, events] = await Promise.all([
          getExecutions(bot.id, { fromDate, limit: PER_BOT_LIMIT }).catch(() => null),
          getRunningExecutions(bot.id).catch(() => null),
          getOpenTodos(bot.id).catch(() => null),
          getBotTimeline(bot.id, 50).catch(() => null),
        ])
        return { history, running, openTodos, events }
      })
    )
    if (results.every((r) => r.history === null && r.running === null)) {
      setAnyReachable(false)
      setRuns([])
      setTodos([])
      setTimelineEvents([])
      setLoaded(true)
      return
    }
    // Merge history + running, dedupe by id (running entries may appear in both)
    const byId = new Map<string, ExecutionLog>()
    const todoById = new Map<string, Todo>()
    const eventById = new Map<string, TimelineEvent>()
    for (const { history, running, openTodos, events } of results) {
      for (const run of history ?? []) byId.set(run.id, run)
      for (const run of running ?? []) byId.set(run.id, run)
      for (const todo of openTodos ?? []) todoById.set(todo.id, todo)
      for (const event of events ?? []) eventById.set(event.id, event)
    }
    setRuns([...byId.values()])
    setTodos(
      [...todoById.values()].sort(
        (a, b) => parseApiDate(b.createdAt).getTime() - parseApiDate(a.createdAt).getTime()
      )
    )
    setTimelineEvents(
      [...eventById.values()]
        .sort((a, b) => parseApiDate(b.createdAt).getTime() - parseApiDate(a.createdAt).getTime())
        .slice(0, TIMELINE_CAP)
    )
    setAnyReachable(true)
    setLoaded(true)
    // Retention setting is server-wide — the first stats call that answers is enough
    if (retentionRef.current === null) {
      for (const bot of operableBots) {
        try {
          const stats = await getExecutionStats(bot.id, '30d')
          if (typeof stats.retentionDays === 'number') {
            retentionRef.current = stats.retentionDays
            setRetentionDays(stats.retentionDays)
            break
          }
        } catch {
          // try the next bot; footer text stays hidden when none answer
        }
      }
    }
  }, [operableBots])

  useEffect(() => {
    setLoaded(false)
    void load()
  }, [load])

  const statusOf = useCallback(
    (run: ExecutionLog): RunStatus => {
      if (run.status === 'credit_exhausted') return 'needs-you'
      if (run.status === 'running') {
        const waiting = pendingApprovals.some(
          (a) => a.botId === run.botId && !!a.chatId && a.chatId === run.chatId
        )
        if (waiting) return 'needs-you'
        return Date.now() - parseApiDate(run.startedAt).getTime() > STUCK_MS ? 'stuck' : 'running'
      }
      if (run.status === 'error' || run.status === 'timeout') return 'failed'
      if (run.status === 'cancelled') return 'cancelled'
      return 'done'
    },
    [pendingApprovals]
  )

  const counts = useMemo(() => {
    let needsYou = 0
    let failed = 0
    let running = 0
    for (const run of runs) {
      const status = statusOf(run)
      if (status === 'needs-you') needsYou++
      if (status === 'failed') failed++
      if (status === 'running' || status === 'stuck') running++
    }
    return { needsYou, failed, running }
  }, [runs, statusOf])

  // If the last needs-you run clears while that chip is active, fall back to All
  useEffect(() => {
    if (filter === 'needs-you' && counts.needsYou === 0) setFilter('all')
  }, [filter, counts.needsYou])

  const filtered = useMemo(() => {
    return runs
      .filter((run) => activeBotFilter === 'all' || run.botId === activeBotFilter)
      .filter((run) => {
        if (filter === 'all') return true
        const status = statusOf(run)
        if (filter === 'needs-you') return status === 'needs-you'
        if (filter === 'failed') return status === 'failed'
        return status === 'running' || status === 'stuck'
      })
      .sort((a, b) => parseApiDate(b.startedAt).getTime() - parseApiDate(a.startedAt).getTime())
  }, [runs, filter, activeBotFilter, statusOf])

  const filteredTodos = useMemo(
    () => todos.filter((t) => activeBotFilter === 'all' || t.botId === activeBotFilter),
    [todos, activeBotFilter]
  )

  const filteredEvents = useMemo(
    () => timelineEvents.filter((e) => activeBotFilter === 'all' || e.botId === activeBotFilter),
    [timelineEvents, activeBotFilter]
  )

  // Timeline events grouped by the same local-day computation as runs
  const eventGroups = useMemo(() => {
    const map = new Map<string, { label: string; dayStart: number; events: TimelineEvent[] }>()
    for (const event of filteredEvents) {
      const group = dayGroup(parseApiDate(event.createdAt))
      let entry = map.get(group.key)
      if (!entry) {
        entry = { label: group.label, dayStart: group.dayStart, events: [] }
        map.set(group.key, entry)
      }
      entry.events.push(event)
    }
    return [...map.values()].sort((a, b) => b.dayStart - a.dayStart)
  }, [filteredEvents])

  // Day groups, most recent day first. Key and label come from the same
  // local-date computation, so one group per day with a consistent label.
  const groups = useMemo(() => {
    const map = new Map<string, { label: string; dayStart: number; runs: ExecutionLog[] }>()
    for (const run of filtered) {
      const group = dayGroup(parseApiDate(run.startedAt))
      let entry = map.get(group.key)
      if (!entry) {
        entry = { label: group.label, dayStart: group.dayStart, runs: [] }
        map.set(group.key, entry)
      }
      entry.runs.push(run)
    }
    return [...map.values()].sort((a, b) => b.dayStart - a.dayStart)
  }, [filtered])

  // Stuck runs for the banner (all bots, before filters)
  const stuckRuns = useMemo(
    () => runs.filter((run) => statusOf(run) === 'stuck'),
    [runs, statusOf]
  )
  const earliestStuck = stuckRuns.reduce<ExecutionLog | null>(
    (earliest, r) =>
      !earliest || parseApiDate(r.startedAt) < parseApiDate(earliest.startedAt) ? r : earliest,
    null
  )

  const clearStuck = async () => {
    if (stuckRuns.length === 0) return
    setClearing(true)
    let cleared = 0
    let failures = 0
    for (const run of stuckRuns) {
      try {
        await cancelExecution(run.botId, run.id)
        cleared++
      } catch {
        failures++
      }
    }
    setClearing(false)
    if (failures === 0) {
      toast.success(cleared === 1 ? 'Run cancelled' : `${cleared} runs cancelled`)
    } else {
      toast.error(`Cancelled ${cleared}; ${failures} couldn't be cancelled`)
    }
    await load()
  }

  const toggleOpen = (run: ExecutionLog) => {
    const next = openId === run.id ? null : run.id
    setOpenId(next)
    if (next && linesById[run.id] === undefined) {
      getExecutionLines(run.botId, run.id, 100)
        .then((lines) => setLinesById((prev) => ({ ...prev, [run.id]: lines })))
        .catch(() => setLinesById((prev) => ({ ...prev, [run.id]: null })))
    }
  }

  // Quick tasks checklist: checking completes the todo, ✕ dismisses it
  const completeTodo = async (todo: Todo) => {
    try {
      await markTodoDone(todo.botId, todo.id)
      setTodos((prev) => prev.filter((t) => t.id !== todo.id))
    } catch {
      toast.error("Couldn't complete the task")
    }
  }

  const dismissOpenTodo = async (todo: Todo) => {
    try {
      await dismissTodo(todo.botId, todo.id)
      setTodos((prev) => prev.filter((t) => t.id !== todo.id))
    } catch {
      toast.error("Couldn't dismiss the task")
    }
  }

  /** Only sources with a real re-run endpoint get a "Run again" action. */
  const rerunTarget = (run: ExecutionLog): boolean =>
    !!run.sourceId && ['script', 'function', 'schedule'].includes(run.sourceType)

  const rerun = async (run: ExecutionLog) => {
    if (!run.sourceId) return
    setRerunningId(run.id)
    try {
      if (run.sourceType === 'script') {
        await runScript(run.botId, run.sourceId)
      } else if (run.sourceType === 'function') {
        await runFunction(run.botId, run.sourceId)
      } else if (run.sourceType === 'schedule') {
        const schedule = await getSchedule(run.botId, run.sourceId)
        if (!schedule.functionId) throw new Error('This schedule has no function to run')
        await runFunction(run.botId, schedule.functionId, schedule.functionParams)
      } else {
        return
      }
      toast.success('Run started again')
      await load()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Couldn't start the run again")
    } finally {
      setRerunningId(null)
    }
  }

  const openInChat = (run: ExecutionLog) => {
    if (run.chatId) navigate(`/${run.botId}/chats/${run.chatId}`)
  }

  const exportCsv = () => {
    const escape = (v: string) => `"${v.replace(/"/g, '""')}"`
    const rows = filtered.map((run) => {
      const status = statusOf(run)
      return [
        dayGroup(parseApiDate(run.startedAt)).label,
        botById.get(run.botId)?.name ?? run.botId,
        run.sourceName,
        run.sourceType,
        triggerLabel(run),
        parseApiDate(run.startedAt).toISOString(),
        run.durationMs ?? '',
        STATUS_META[status].label,
      ]
        .map((v) => escape(String(v)))
        .join(',')
    })
    const csv = ['Day,Bot,Name,Type,Trigger,Started,Duration (ms),Status', ...rows].join('\n')
    const url = URL.createObjectURL(new Blob([csv], { type: 'text/csv' }))
    const a = document.createElement('a')
    a.href = url
    a.download = 'cachibot-runs.csv'
    a.click()
    URL.revokeObjectURL(url)
  }

  const chips: { id: RunFilter; label: string; count?: number }[] = [
    { id: 'all', label: 'All' },
    // Hidden when nothing needs the user — the count is real and currently 0
    ...(counts.needsYou > 0
      ? [{ id: 'needs-you' as const, label: 'Needs you', count: counts.needsYou }]
      : []),
    { id: 'failed', label: 'Failed', count: counts.failed },
    { id: 'running', label: 'Running', count: counts.running },
  ]

  return (
    <div className="runs">
      <div className="runs__column">
        <button type="button" className="runs__back" onClick={() => navigate('/dashboard')}>
          <ChevronLeft size={14} strokeWidth={1.8} aria-hidden="true" />
          Workspace
        </button>

        <header className="runs__header">
          <h1 className="runs__title">Runs</h1>
          <p className="runs__subtitle">
            Everything your bots did on their own: routines, work and scripts.
          </p>
        </header>

        {/* Stuck runs — hidden when none are really stuck */}
        {stuckRuns.length > 0 && (
          <div className="runs__banner" role="status">
            <span className="runs__banner-text">
              {stuckRuns.length}{' '}
              {stuckRuns.length === 1 ? 'run has' : 'runs have'} been stuck since{' '}
              {formatStuckSince(earliestStuck?.startedAt)}.
            </span>
            <button
              type="button"
              className="v2-btn v2-btn--primary"
              disabled={clearing}
              onClick={() => void clearStuck()}
            >
              {clearing ? 'Clearing…' : 'Clear them'}
            </button>
          </div>
        )}

        {/* Filter chips + bot filter */}
        <div className="runs__toolbar">
          {chips.map((chip) => (
            <button
              key={chip.id}
              type="button"
              className={cn('runs__chip', filter === chip.id && 'runs__chip--active')}
              onClick={() => setFilter(chip.id)}
            >
              {chip.label}
              {chip.count != null && chip.count > 0 && ` · ${chip.count}`}
            </button>
          ))}
          <span className="runs__bot-filter">
            <select
              className="runs__bot-filter-select"
              value={activeBotFilter}
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
        </div>

        {/* Quick tasks checklist (real open todos; hidden when none) */}
        {loaded && anyReachable && filteredTodos.length > 0 && (
          <section aria-label="Quick tasks">
            <h2 className="runs__day">
              Quick tasks
              <span className="runs__day-count">{filteredTodos.length}</span>
            </h2>
            {filteredTodos.map((todo) => {
              const bot = botById.get(todo.botId)
              return (
                <div key={todo.id} className="runs__task">
                  <button
                    type="button"
                    role="checkbox"
                    aria-checked={false}
                    className="runs__task-check"
                    aria-label={`Mark "${todo.title}" as done`}
                    onClick={() => void completeTodo(todo)}
                  >
                    <Check size={13} strokeWidth={2} aria-hidden="true" />
                  </button>
                  <span className="runs__task-main">
                    <span className="runs__task-title">{todo.title}</span>
                    <span className="runs__task-meta">{bot?.name ?? 'Unknown bot'}</span>
                  </span>
                  <button
                    type="button"
                    className="runs__task-dismiss"
                    aria-label={`Dismiss "${todo.title}"`}
                    onClick={() => void dismissOpenTodo(todo)}
                  >
                    <X size={14} strokeWidth={1.8} aria-hidden="true" />
                  </button>
                </div>
              )
            })}
          </section>
        )}

        {/* Day-grouped run list */}
        {!loaded ? (
          <div className="runs__empty">
            <Loader2 className="runs__spinner" size={18} strokeWidth={1.8} />
          </div>
        ) : !anyReachable ? (
          <div className="runs__empty">
            <p>Couldn't load runs.</p>
            <button type="button" className="v2-btn v2-btn--secondary" onClick={() => void load()}>
              Try again
            </button>
          </div>
        ) : bots.length === 0 ? (
          <p className="runs__empty">No bots yet.</p>
        ) : operableBots.length === 0 ? (
          <p className="runs__empty">Runs is available to operators and above.</p>
        ) : groups.length === 0 ? (
          <p className="runs__empty">
            {filter !== 'all' || activeBotFilter !== 'all'
              ? 'No runs match this filter.'
              : `No runs in the last ${retentionDays ?? 30} days.`}
          </p>
        ) : (
          <section aria-label="Runs">
            {groups.map((group) => (
              <div key={group.dayStart}>
                <h2 className="runs__day">{group.label}</h2>
                {group.runs.map((run) => {
                  const bot = botById.get(run.botId)
                  const status = statusOf(run)
                  const duration = formatDuration(run.durationMs)
                  const isOpen = openId === run.id
                  return (
                    <div key={run.id}>
                      <button
                        type="button"
                        className={cn('runs__row', isOpen && 'runs__row--open')}
                        aria-expanded={isOpen}
                        onClick={() => toggleOpen(run)}
                      >
                        <BotAvatar
                          color={bot?.color}
                          name={bot?.name ?? 'Unknown bot'}
                          size={32}
                        />
                        <span className="runs__row-main">
                          <span className="runs__row-name">{run.sourceName}</span>
                          <span className="runs__row-meta">
                            {bot?.name ?? 'Unknown bot'} · {triggerLabel(run)} ·{' '}
                            {formatRunTime(parseApiDate(run.startedAt))}
                            {duration && ` · ${duration}`}
                          </span>
                        </span>
                        <span className={cn('runs__status', STATUS_META[status].className)}>
                          <StatusIcon status={status} />
                          {STATUS_META[status].label}
                        </span>
                      </button>
                      {isOpen && (
                        <div className="runs__detail">
                          {linesById[run.id] === undefined ? (
                            <Loader2 className="runs__spinner" size={16} strokeWidth={1.8} />
                          ) : (
                            <>
                              {(linesById[run.id] ?? []).map((line) => (
                                <p
                                  key={line.id}
                                  className={cn(
                                    'runs__line',
                                    (line.level === 'error' || line.level === 'stderr') &&
                                      'runs__line--error'
                                  )}
                                >
                                  {line.level === 'error' || line.level === 'stderr' ? (
                                    <X size={14} strokeWidth={1.8} aria-hidden="true" />
                                  ) : (
                                    <Check size={14} strokeWidth={1.8} aria-hidden="true" />
                                  )}
                                  {line.content}
                                </p>
                              ))}
                              {(linesById[run.id] ?? []).length === 0 &&
                                (run.error ? (
                                  <p className="runs__line runs__line--error">
                                    <X size={14} strokeWidth={1.8} aria-hidden="true" />
                                    {run.error}
                                  </p>
                                ) : run.output ? (
                                  <pre className="runs__output">{run.output}</pre>
                                ) : null)}
                              {(run.chatId || rerunTarget(run)) && (
                                <div className="runs__actions">
                                  {run.chatId && (
                                    <button
                                      type="button"
                                      className="v2-btn v2-btn--primary"
                                      onClick={() => openInChat(run)}
                                    >
                                      Open in chat
                                    </button>
                                  )}
                                  {rerunTarget(run) && (
                                    <button
                                      type="button"
                                      className="v2-btn v2-btn--secondary"
                                      disabled={rerunningId === run.id}
                                      onClick={() => void rerun(run)}
                                    >
                                      {rerunningId === run.id ? 'Starting…' : 'Run again'}
                                    </button>
                                  )}
                                </div>
                              )}
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </section>
        )}

        {/* Automations timeline (real TimelineEvents from job_runner/scripts) */}
        {loaded && anyReachable && eventGroups.length > 0 && (
          <section aria-label="Timeline">
            <h2 className="runs__section-label">Timeline</h2>
            {eventGroups.map((group) => (
              <div key={group.dayStart}>
                <h3 className="runs__day">{group.label}</h3>
                {group.events.map((event) => {
                  const bot = botById.get(event.botId)
                  return (
                    <div key={event.id} className="runs__event">
                      <EventIcon eventType={event.eventType} />
                      <span className="runs__event-main">
                        <span className="runs__event-title">{event.title}</span>
                        <span className="runs__event-meta">
                          {bot?.name ?? 'Unknown bot'} · {event.eventType} ·{' '}
                          {formatRunTime(parseApiDate(event.createdAt))}
                        </span>
                      </span>
                      {event.description && (
                        <span className="runs__event-desc">{event.description}</span>
                      )}
                    </div>
                  )
                })}
              </div>
            ))}
          </section>
        )}

        {/* Footer: retention text only with a real setting; Export = CSV of the loaded rows;
            Activity log is admins-only (per the "where things moved" map) */}
        {(retentionDays != null || filtered.length > 0 || isAdmin) && (
          <p className="runs__footer">
            {retentionDays != null && <>Older runs are kept for {retentionDays} days. </>}
            {filtered.length > 0 && (
              <button type="button" className="runs__footer-link" onClick={exportCsv}>
                Export
              </button>
            )}
            {retentionDays != null && filtered.length > 0 && isAdmin && ' · '}
            {isAdmin && (
              <button
                type="button"
                className="runs__footer-link"
                onClick={() => navigate('/admin/logs')}
              >
                Activity log
              </button>
            )}
          </p>
        )}
      </div>
    </div>
  )
}

function EventIcon({ eventType }: { eventType: string }) {
  const props = { size: 14, strokeWidth: 1.8, 'aria-hidden': true } as const
  switch (eventType) {
    case 'created':
      return <Plus {...props} />
    case 'edited':
      return <Pencil {...props} />
    case 'version':
      return <GitCommit {...props} />
    case 'execution':
      return <CircleDot {...props} />
    case 'enabled':
      return <Power {...props} />
    case 'disabled':
      return <PowerOff {...props} />
    case 'deleted':
      return <Trash2 {...props} />
    default:
      return <CircleDot {...props} />
  }
}

function StatusIcon({ status }: { status: RunStatus }) {
  switch (status) {
    case 'running':
      return <Loader2 size={14} strokeWidth={1.8} className="runs__spin" aria-hidden="true" />
    case 'failed':
      return <X size={14} strokeWidth={1.8} aria-hidden="true" />
    case 'stuck':
    case 'needs-you':
      return <Clock size={14} strokeWidth={1.8} aria-hidden="true" />
    case 'cancelled':
      return <Ban size={14} strokeWidth={1.8} aria-hidden="true" />
    default:
      return <Check size={14} strokeWidth={1.8} aria-hidden="true" />
  }
}

/** Human trigger label per source (design: "routine", "work", "asked in chat"). */
function triggerLabel(run: ExecutionLog): string {
  switch (run.sourceType) {
    case 'schedule':
      return 'routine'
    case 'script':
      return 'script'
    case 'function':
      return 'function'
    case 'work':
    case 'job':
      return 'work'
    case 'manual':
      return run.chatId ? 'asked in chat' : 'manual'
    default:
      return run.sourceType
  }
}

/** Design duration format: "4s" under 10s, "0:41" under an hour, "1:52" beyond. */
function formatDuration(ms: number | null): string | null {
  if (ms == null) return null
  const s = Math.round(ms / 1000)
  if (s < 10) return `${s}s`
  const m = Math.floor(s / 60)
  if (m < 60) return `${m}:${String(s % 60).padStart(2, '0')}`
  return `${Math.floor(m / 60)}:${String(m % 60).padStart(2, '0')}`
}

/**
 * Local-day bucket for a run: the group key and the label are derived from
 * the same local date, so a day renders exactly one group.
 */
function dayGroup(d: Date): { key: string; label: string; dayStart: number } {
  const dayStart = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const start = dayStart(d)
  const diffDays = Math.round((dayStart(new Date()) - start) / 86400000)
  const label =
    diffDays <= 0
      ? 'Today'
      : diffDays === 1
        ? 'Yesterday'
        : d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  return { key: String(start), label, dayStart: start }
}

function formatRunTime(d: Date): string {
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

function formatStuckSince(iso: string | undefined): string {
  if (!iso) return 'earlier'
  return parseApiDate(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

import { useEffect, useMemo, useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { ChevronDown, ChevronLeft, Clock, Loader2, Plus, X, Zap } from 'lucide-react'
import { toast } from 'sonner'
import {
  createSchedule,
  deleteSchedule,
  getFunctions,
  getSchedule,
  runSchedule,
  toggleSchedule,
  updateSchedule,
} from '../../api/client'
import type { BotFunction, Schedule, ScheduleType } from '../../types'
import { useBotStore } from '../../stores/bots'
import { useBotAccess } from '../../hooks/useBotAccess'

// One trigger card. The schedules API stores a single trigger per schedule
// (scheduleType + its fields), so the list holds at most one entry.
type RoutineTrigger =
  | { kind: 'daily'; time: string }
  | { kind: 'weekdays'; time: string }
  | { kind: 'weekly'; time: string; day: number }
  | { kind: 'hourly'; minute: number }
  | { kind: 'cron'; expression: string }
  | { kind: 'interval'; amount: number; unit: 'minutes' | 'hours' }
  | { kind: 'once'; runAt: string }
  | { kind: 'event'; event: string }

const KIND_OPTIONS: { value: RoutineTrigger['kind']; label: string }[] = [
  { value: 'daily', label: 'Every day' },
  { value: 'weekdays', label: 'Weekdays' },
  { value: 'weekly', label: 'Weekly' },
  { value: 'hourly', label: 'Hourly' },
  { value: 'cron', label: 'Custom cron' },
  { value: 'interval', label: 'Every N minutes / hours' },
  { value: 'once', label: 'One time' },
  { value: 'event', label: 'Event' },
]

const WEEKDAY_NAMES = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']

const DEFAULT_TIME = '09:00'

function parseTrigger(schedule: Schedule): RoutineTrigger {
  const { scheduleType, cronExpression, intervalSeconds, runAt, eventTrigger } = schedule

  if (scheduleType === 'interval') {
    const seconds = intervalSeconds ?? 3600
    return seconds % 3600 === 0
      ? { kind: 'interval', amount: seconds / 3600, unit: 'hours' }
      : { kind: 'interval', amount: seconds / 60, unit: 'minutes' }
  }

  if (scheduleType === 'once') {
    return { kind: 'once', runAt: runAt ? isoToLocalInput(runAt) : '' }
  }

  if (scheduleType === 'event') {
    return { kind: 'event', event: eventTrigger ?? '' }
  }

  if (scheduleType === 'cron' && cronExpression) {
    const parts = cronExpression.trim().split(/\s+/)
    if (parts.length === 5) {
      const [minute, hour, dom, month, dow] = parts
      if (dom === '*' && month === '*') {
        if (hour === '*' && /^\d{1,2}$/.test(minute)) {
          return { kind: 'hourly', minute: parseInt(minute, 10) }
        }
        if (dow === '*' && /^\d{1,2}$/.test(minute) && /^\d{1,2}$/.test(hour)) {
          return { kind: 'daily', time: `${pad(hour)}:${pad(minute)}` }
        }
        if (dow === '1-5' && /^\d{1,2}$/.test(minute) && /^\d{1,2}$/.test(hour)) {
          return { kind: 'weekdays', time: `${pad(hour)}:${pad(minute)}` }
        }
        if (/^\d{1,2}$/.test(dow) && /^\d{1,2}$/.test(minute) && /^\d{1,2}$/.test(hour)) {
          return {
            kind: 'weekly',
            time: `${pad(hour)}:${pad(minute)}`,
            day: parseInt(dow, 10) % 7,
          }
        }
      }
    }
    return { kind: 'cron', expression: cronExpression }
  }

  return { kind: 'daily', time: DEFAULT_TIME }
}

function buildTriggerPayload(trigger: RoutineTrigger): {
  scheduleType: ScheduleType
  cronExpression?: string
  intervalSeconds?: number
  runAt?: string
  eventTrigger?: string
} {
  switch (trigger.kind) {
    case 'daily':
      return { scheduleType: 'cron', cronExpression: cronAt(trigger.time, '*') }
    case 'weekdays':
      return { scheduleType: 'cron', cronExpression: cronAt(trigger.time, '1-5') }
    case 'weekly':
      return { scheduleType: 'cron', cronExpression: cronAt(trigger.time, String(trigger.day)) }
    case 'hourly':
      return { scheduleType: 'cron', cronExpression: `${trigger.minute} * * * *` }
    case 'cron':
      return { scheduleType: 'cron', cronExpression: trigger.expression }
    case 'interval':
      return {
        scheduleType: 'interval',
        intervalSeconds: Math.max(60, Math.round(trigger.amount * (trigger.unit === 'hours' ? 3600 : 60))),
      }
    case 'once':
      return { scheduleType: 'once', runAt: trigger.runAt ? new Date(trigger.runAt).toISOString() : undefined }
    case 'event':
      return { scheduleType: 'event', eventTrigger: trigger.event }
  }
}

function triggerSummary(trigger: RoutineTrigger): { title: string; detail: string } {
  switch (trigger.kind) {
    case 'daily':
      return { title: 'Every day', detail: `at ${formatTime(trigger.time)}` }
    case 'weekdays':
      return { title: 'Weekdays', detail: `at ${formatTime(trigger.time)}` }
    case 'weekly':
      return { title: 'Weekly', detail: `on ${WEEKDAY_NAMES[trigger.day]} at ${formatTime(trigger.time)}` }
    case 'hourly':
      return { title: 'Hourly', detail: `at :${pad(trigger.minute)} past the hour` }
    case 'cron':
      return { title: 'Custom cron', detail: trigger.expression }
    case 'interval':
      return {
        title: 'Every ' + (trigger.unit === 'hours' ? `${trigger.amount} hours` : `${trigger.amount} minutes`),
        detail: '',
      }
    case 'once':
      return { title: 'One time', detail: trigger.runAt ? formatDateTime(trigger.runAt) : 'pick a date and time' }
    case 'event':
      return { title: 'Event', detail: trigger.event || 'name the event' }
  }
}

function validateTrigger(trigger: RoutineTrigger): string | null {
  switch (trigger.kind) {
    case 'cron': {
      const parts = trigger.expression.trim().split(/\s+/)
      if (parts.length !== 5 || parts.some((p) => !p)) {
        return 'A cron expression needs 5 fields, e.g. "0 9 * * *"'
      }
      return null
    }
    case 'interval':
      return trigger.amount > 0 ? null : 'Interval must be greater than zero'
    case 'once':
      return trigger.runAt ? null : 'Pick a date and time'
    case 'event':
      return trigger.event.trim() ? null : 'Name the event'
    default:
      return null
  }
}

function pad(n: string | number): string {
  return String(n).padStart(2, '0')
}

function cronAt(time: string, dow: string): string {
  const [hour, minute] = time.split(':')
  return `${parseInt(minute, 10)} ${parseInt(hour, 10)} * * ${dow}`
}

function formatTime(time: string): string {
  const [hourStr, minute] = time.split(':')
  const hour = parseInt(hourStr, 10)
  const suffix = hour >= 12 ? 'PM' : 'AM'
  const h12 = hour % 12 === 0 ? 12 : hour % 12
  return `${h12}:${minute} ${suffix}`
}

function formatDateTime(localValue: string): string {
  return new Date(localValue).toLocaleString(undefined, {
    month: 'short',
    day: 'numeric',
    hour: 'numeric',
    minute: '2-digit',
  })
}

function isoToLocalInput(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// Quarter-hour options; the current value is always included so schedules
// with off-grid minutes (e.g. "0 9 7 * *") still display their real time.
function timeOptions(current: string): string[] {
  const options: string[] = []
  for (let h = 0; h < 24; h++) {
    for (const m of [0, 15, 30, 45]) {
      options.push(`${pad(h)}:${pad(m)}`)
    }
  }
  if (!options.includes(current)) options.push(current)
  return options.sort()
}

export function RoutineEditorView() {
  const navigate = useNavigate()
  const { botId = '', routineId } = useParams<{ botId: string; routineId: string }>()
  const { getActiveBot } = useBotStore()
  const bot = getActiveBot()

  // Routines are Operator+; editing/creating/deleting is Editor+ (matches the
  // schedules API levels). Viewers get a read-only notice.
  const { canOperate, canEdit } = useBotAccess(botId || null)
  const readOnly = !canEdit

  const isNew = !routineId

  // The cron hour/minute fields are interpreted in the schedule's own zone
  // when editing; new routines default to the browser zone and save it.
  const browserTimezone = Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'

  const [schedule, setSchedule] = useState<Schedule | null>(null)
  const [loading, setLoading] = useState(!isNew)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [functions, setFunctions] = useState<BotFunction[]>([])

  const [name, setName] = useState('')
  const [messageText, setMessageText] = useState('')
  const [description, setDescription] = useState('')
  const [trigger, setTrigger] = useState<RoutineTrigger | null>({ kind: 'daily', time: DEFAULT_TIME })
  const [enabled, setEnabled] = useState(true)
  const [functionId, setFunctionId] = useState('')
  const [maxConcurrent, setMaxConcurrent] = useState(1)
  const [catchUp, setCatchUp] = useState(false)

  const [advancedOpen, setAdvancedOpen] = useState(false)
  const [saving, setSaving] = useState(false)
  const [running, setRunning] = useState(false)
  const [toggling, setToggling] = useState(false)

  const timezone = schedule?.timezone || browserTimezone

  useEffect(() => {
    if (!botId) return
    let cancelled = false

    getFunctions(botId)
      .then((fns) => {
        if (!cancelled) setFunctions(fns)
      })
      .catch(() => {
        // Advanced function picker stays empty; the rest of the editor works
      })

    if (isNew) return

    getSchedule(botId, routineId!)
      .then((sch) => {
        if (cancelled) return
        setSchedule(sch)
        setName(sch.name)
        const message = sch.functionParams?.message
        setMessageText(typeof message === 'string' ? message : (sch.description ?? ''))
        setDescription(sch.description ?? '')
        setTrigger(parseTrigger(sch))
        setEnabled(sch.enabled)
        setFunctionId(sch.functionId ?? '')
        setMaxConcurrent(sch.maxConcurrent ?? 1)
        setCatchUp(sch.catchUp ?? false)
        setLoading(false)
      })
      .catch((err) => {
        if (cancelled) return
        setLoadError(err instanceof Error ? err.message : 'Failed to load routine')
        setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [botId, routineId, isNew])

  const timeSelectOptions = useMemo(
    () => (trigger && 'time' in trigger ? timeOptions(trigger.time) : []),
    [trigger]
  )

  if (!bot) return null

  const goBack = () => navigate(`/${botId}/routines`)

  const handleToggle = async () => {
    if (!routineId || toggling) return
    setToggling(true)
    try {
      const updated = await toggleSchedule(botId, routineId)
      setEnabled(updated.enabled)
      setSchedule(updated)
    } catch (err) {
      toast.error(`Failed to toggle: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setToggling(false)
    }
  }

  const handleTestRun = async () => {
    if (!routineId || running) return
    setRunning(true)
    try {
      const updated = await runSchedule(botId, routineId)
      setSchedule(updated)
      toast.success(`Test run of "${updated.name}" started`)
    } catch (err) {
      toast.error(`Failed to run: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setRunning(false)
    }
  }

  const handleDelete = async () => {
    if (!routineId) return
    if (!confirm(`Delete routine "${name}"? This cannot be undone.`)) return
    try {
      await deleteSchedule(botId, routineId)
      toast.success('Routine deleted')
      goBack()
    } catch (err) {
      toast.error(`Failed to delete: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleSave = async () => {
    if (readOnly) return
    if (!name.trim()) {
      toast.error('Give the routine a name')
      return
    }
    if (!trigger) {
      toast.error('Add a trigger to save this routine')
      return
    }
    const triggerError = validateTrigger(trigger)
    if (triggerError) {
      toast.error(triggerError)
      return
    }

    setSaving(true)
    try {
      const triggerPayload = buildTriggerPayload(trigger)
      if (isNew) {
        const created = await createSchedule(botId, {
          name: name.trim(),
          description: description.trim() || undefined,
          functionParams: { message: messageText },
          timezone,
          maxConcurrent,
          catchUp,
          functionId: functionId || undefined,
          ...triggerPayload,
        })
        toast.success('Routine created')
        navigate(`/${botId}/routines/${created.id}`, { replace: true })
      } else {
        const updated = await updateSchedule(botId, routineId!, {
          name: name.trim(),
          description: description.trim() || undefined,
          functionParams: { ...schedule?.functionParams, message: messageText },
          maxConcurrent,
          catchUp,
          functionId: functionId || undefined,
          ...triggerPayload,
        })
        setSchedule(updated)
        toast.success('Routine saved')
      }
    } catch (err) {
      toast.error(`Failed to save: ${err instanceof Error ? err.message : 'Unknown error'}`)
    } finally {
      setSaving(false)
    }
  }

  const updateTrigger = <K extends RoutineTrigger['kind']>(
    kind: K,
    patch: Partial<Extract<RoutineTrigger, { kind: K }>>
  ) => {
    setTrigger((prev) => {
      const base = prev && prev.kind === kind ? prev : defaultTriggerFor(kind)
      return { ...base, ...patch } as RoutineTrigger
    })
  }

  const summary = trigger ? triggerSummary(trigger) : null

  return (
    <div className="routine">
      {loading ? (
        <div className="routine__loading">
          <Loader2 className="h-5 w-5 animate-spin" />
        </div>
      ) : loadError ? (
        <div className="routine__error">
          <p>{loadError}</p>
        </div>
      ) : (
        <div className="routine__column">
          {/* Header: back + title + close */}
          <div className="routine__header">
            <button type="button" aria-label="Back" className="routine__icon-btn" onClick={goBack}>
              <ChevronLeft size={18} strokeWidth={1.8} />
            </button>
            <h1 className="routine__title">Routine</h1>
            <button type="button" aria-label="Close" className="routine__icon-btn" onClick={goBack}>
              <X size={18} strokeWidth={1.8} />
            </button>
          </div>

          {/* Active toggle + Delete / Test run (role-gated: toggle/run are
              Operator+, delete is Editor+; viewers see none of these) */}
          {canOperate && (
            <div className="routine__status-row">
              <button
                type="button"
                role="switch"
                aria-checked={enabled}
                aria-label="Active"
                className="routine__switch"
                disabled={isNew || toggling}
                onClick={handleToggle}
              >
                <span className="routine__switch-knob" />
              </button>
              <span className="routine__switch-label">Active</span>
              <span className="routine__actions">
                {!isNew && canEdit && (
                  <button type="button" className="routine__btn-secondary" onClick={handleDelete}>
                    Delete
                  </button>
                )}
                {!isNew && (
                  <button
                    type="button"
                    className="routine__btn-secondary"
                    onClick={handleTestRun}
                    disabled={running}
                  >
                    {running ? <Loader2 size={14} className="animate-spin" /> : <Zap size={14} />}
                    Test run
                  </button>
                )}
              </span>
            </div>
          )}

          {readOnly && (
            <p className="routine__notice">
              {canOperate
                ? 'You can toggle or test-run this routine, but changing it needs editor access.'
                : `You have view-only access to ${bot.name}. Routines can be changed by operators and editors.`}
            </p>
          )}

          {canOperate && (
          <>
          {/* Name */}
          <label className="routine__field">
            <span className="routine__label">Name</span>
            <input
              type="text"
              className="routine__input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Daily Telegram greeting"
              disabled={readOnly}
            />
          </label>

          {/* What the bot should do */}
          <label className="routine__field">
            <span className="routine__label">What should {bot.name} do?</span>
            <textarea
              rows={3}
              className="routine__textarea"
              value={messageText}
              onChange={(e) => setMessageText(e.target.value)}
              placeholder="Describe the task in plain words — this is the message the bot receives when the routine runs."
              disabled={readOnly}
            />
          </label>

          {/* When to run */}
          <section className="routine__triggers">
            <span className="routine__label">
              When to run <span className="routine__label-note">· your time zone ({timezone})</span>
            </span>

            {trigger && summary && (
              <div className="routine__trigger-card">
                <div className="routine__trigger-summary">
                  <Clock size={16} strokeWidth={1.8} className="routine__trigger-summary-icon" />
                  <strong>{summary.title}</strong>
                  {summary.detail && <span className="routine__trigger-summary-detail">{summary.detail}</span>}
                  {!readOnly && (
                    <button
                      type="button"
                      aria-label="Remove trigger"
                      className="routine__icon-btn routine__trigger-remove"
                      onClick={() => setTrigger(null)}
                    >
                      <X size={14} strokeWidth={1.8} />
                    </button>
                  )}
                </div>

                <div className="routine__trigger-row">
                  <span className="routine__chip">
                    <select
                      className="routine__chip-select"
                      value={trigger.kind}
                      onChange={(e) =>
                        setTrigger(defaultTriggerFor(e.target.value as RoutineTrigger['kind'], trigger))
                      }
                      aria-label="Trigger type"
                      disabled={readOnly}
                    >
                      {KIND_OPTIONS.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
                    <ChevronDown size={14} strokeWidth={1.8} color="var(--v2-text-tertiary)" />
                  </span>

                  {trigger.kind === 'daily' ||
                  trigger.kind === 'weekdays' ||
                  trigger.kind === 'weekly' ? (
                    <>
                      {trigger.kind === 'weekly' && (
                        <>
                          on
                          <span className="routine__chip">
                            <select
                              className="routine__chip-select"
                              value={trigger.day}
                              onChange={(e) =>
                                updateTrigger('weekly', { day: parseInt(e.target.value, 10) })
                              }
                              aria-label="Day of week"
                              disabled={readOnly}
                            >
                              {WEEKDAY_NAMES.map((dayName, i) => (
                                <option key={dayName} value={i}>
                                  {dayName}
                                </option>
                              ))}
                            </select>
                            <ChevronDown size={14} strokeWidth={1.8} color="var(--v2-text-tertiary)" />
                          </span>
                        </>
                      )}
                      at
                      <span className="routine__chip">
                        <select
                          className="routine__chip-select"
                          value={trigger.time}
                          onChange={(e) => {
                            const time = e.target.value
                            if (trigger.kind === 'daily') updateTrigger('daily', { time })
                            else if (trigger.kind === 'weekdays') updateTrigger('weekdays', { time })
                            else updateTrigger('weekly', { time })
                          }}
                          aria-label="Time of day"
                          disabled={readOnly}
                        >
                          {timeSelectOptions.map((t) => (
                            <option key={t} value={t}>
                              {formatTime(t)}
                            </option>
                          ))}
                        </select>
                        <ChevronDown size={14} strokeWidth={1.8} color="var(--v2-text-tertiary)" />
                      </span>
                    </>
                  ) : trigger.kind === 'hourly' ? (
                    <>
                      at minute
                      <input
                        type="number"
                        min={0}
                        max={59}
                        className="routine__chip routine__chip--narrow"
                        value={trigger.minute}
                        onChange={(e) =>
                          updateTrigger('hourly', {
                            minute: Math.min(59, Math.max(0, parseInt(e.target.value, 10) || 0)),
                          })
                        }
                        aria-label="Minute of the hour"
                        disabled={readOnly}
                      />
                    </>
                  ) : trigger.kind === 'cron' ? (
                    <input
                      type="text"
                      className="routine__chip"
                      style={{ flex: 1 }}
                      value={trigger.expression}
                      onChange={(e) => updateTrigger('cron', { expression: e.target.value })}
                      placeholder="0 9 * * *"
                      aria-label="Cron expression"
                      disabled={readOnly}
                    />
                  ) : trigger.kind === 'interval' ? (
                    <>
                      every
                      <input
                        type="number"
                        min={1}
                        step="any"
                        className="routine__chip routine__chip--narrow"
                        value={trigger.amount}
                        onChange={(e) =>
                          updateTrigger('interval', { amount: parseFloat(e.target.value) || 0 })
                        }
                        aria-label="Interval amount"
                        disabled={readOnly}
                      />
                      <span className="routine__chip">
                        <select
                          className="routine__chip-select"
                          value={trigger.unit}
                          onChange={(e) =>
                            updateTrigger('interval', {
                              unit: e.target.value as 'minutes' | 'hours',
                            })
                          }
                          aria-label="Interval unit"
                          disabled={readOnly}
                        >
                          <option value="minutes">minutes</option>
                          <option value="hours">hours</option>
                        </select>
                        <ChevronDown size={14} strokeWidth={1.8} color="var(--v2-text-tertiary)" />
                      </span>
                    </>
                  ) : trigger.kind === 'once' ? (
                    <input
                      type="datetime-local"
                      className="routine__chip"
                      value={trigger.runAt}
                      onChange={(e) => updateTrigger('once', { runAt: e.target.value })}
                      aria-label="Run at"
                      disabled={readOnly}
                    />
                  ) : (
                    <input
                      type="text"
                      className="routine__chip"
                      style={{ flex: 1 }}
                      value={trigger.event}
                      onChange={(e) => updateTrigger('event', { event: e.target.value })}
                      placeholder="event name"
                      aria-label="Event name"
                      disabled={readOnly}
                    />
                  )}
                </div>
              </div>
            )}

            {trigger ? null : !readOnly ? (
              <button type="button" className="routine__add-trigger" onClick={() => setTrigger({ kind: 'daily', time: DEFAULT_TIME })}>
                <Plus size={15} strokeWidth={1.8} />
                Add trigger
              </button>
            ) : null}

            <p className="routine__helper">
              Triggers: a schedule — daily, weekdays, weekly, hourly, custom cron, one-time, or every
              N minutes — or an event. One trigger per routine.
            </p>
          </section>

          {/* Advanced */}
          <button
            type="button"
            className={`routine__advanced-toggle${advancedOpen ? ' routine__advanced-toggle--open' : ''}`}
            onClick={() => setAdvancedOpen((open) => !open)}
          >
            Advanced: function, limits, catch-up, description
            <ChevronDown size={14} strokeWidth={1.8} />
          </button>

          {advancedOpen && (
            <div className="routine__advanced">
              <label className="routine__field">
                <span className="routine__label">Description</span>
                <input
                  type="text"
                  className="routine__input"
                  value={description}
                  onChange={(e) => setDescription(e.target.value)}
                  placeholder="Optional notes about this routine"
                  disabled={readOnly}
                />
              </label>

              <div className="routine__advanced-row">
                <span className="routine__label">Function</span>
                <span className="routine__chip">
                  <select
                    className="routine__chip-select"
                    value={functionId}
                    onChange={(e) => setFunctionId(e.target.value)}
                    aria-label="Function"
                    disabled={readOnly}
                  >
                    <option value="">None</option>
                    {functions.map((fn) => (
                      <option key={fn.id} value={fn.id}>
                        {fn.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={14} strokeWidth={1.8} color="var(--v2-text-tertiary)" />
                </span>
              </div>

              <div className="routine__advanced-row">
                <span className="routine__label">Max concurrent runs</span>
                <input
                  type="number"
                  min={1}
                  className="routine__input"
                  value={maxConcurrent}
                  onChange={(e) => setMaxConcurrent(Math.max(1, parseInt(e.target.value, 10) || 1))}
                  aria-label="Max concurrent runs"
                  disabled={readOnly}
                />
              </div>

              <label className="routine__check">
                <input
                  type="checkbox"
                  checked={catchUp}
                  onChange={(e) => setCatchUp(e.target.checked)}
                  disabled={readOnly}
                />
                Catch up missed runs
              </label>

              {schedule && (
                <p className="routine__meta">
                  {[
                    schedule.nextRunAt ? `Next run ${new Date(schedule.nextRunAt).toLocaleString()}` : null,
                    schedule.lastRunAt ? `Last run ${new Date(schedule.lastRunAt).toLocaleString()}` : null,
                    `${schedule.runCount} run${schedule.runCount === 1 ? '' : 's'}`,
                    `Time zone ${schedule.timezone}`,
                  ]
                    .filter(Boolean)
                    .join(' · ')}
                </p>
              )}
            </div>
          )}

          {/* Save (Editor+) */}
          {!readOnly && (
            <div>
              <button
                type="button"
                className="routine__save"
                onClick={handleSave}
                disabled={saving || !name.trim()}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}
          </>
          )}
        </div>
      )}
    </div>
  )
}

function defaultTriggerFor(kind: RoutineTrigger['kind'], prev?: RoutineTrigger | null): RoutineTrigger {
  const prevTime = prev && 'time' in prev ? prev.time : DEFAULT_TIME
  switch (kind) {
    case 'daily':
      return { kind: 'daily', time: prevTime }
    case 'weekdays':
      return { kind: 'weekdays', time: prevTime }
    case 'weekly':
      return { kind: 'weekly', time: prevTime, day: prev && prev.kind === 'weekly' ? prev.day : 1 }
    case 'hourly':
      return { kind: 'hourly', minute: 0 }
    case 'cron':
      return { kind: 'cron', expression: prev && prev.kind === 'cron' ? prev.expression : '0 9 * * *' }
    case 'interval':
      return { kind: 'interval', amount: 30, unit: 'minutes' }
    case 'once':
      return { kind: 'once', runAt: prev && prev.kind === 'once' ? prev.runAt : '' }
    case 'event':
      return { kind: 'event', event: prev && prev.kind === 'event' ? prev.event : '' }
  }
}

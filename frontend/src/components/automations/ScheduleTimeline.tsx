import { useState, useEffect, useMemo } from 'react'
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  ArrowRight,
  Loader2,
  CalendarClock,
} from 'lucide-react'
import { CronExpressionParser } from 'cron-parser'
import { getBotTimeline, type TimelineEvent } from '../../api/automations'
import type { Schedule } from '../../types'

interface ScheduleTimelineProps {
  botId: string
  schedules: Schedule[]
  timezone: string
}

type TimelineEntry = {
  id: string
  title: string
  description: string | null
  time: Date
  type: 'past' | 'future'
  eventType: string
  sourceType: string
  status?: string
}

const eventDotClass: Record<string, string> = {
  execution_start: 'timeline__dot--blue',
  execution_success: 'timeline__dot--green',
  execution_error: 'timeline__dot--red',
  execution_timeout: 'timeline__dot--yellow',
  execution_cancelled: 'timeline__dot--zinc',
  status_change: 'timeline__dot--purple',
  version_created: 'timeline__dot--cyan',
  created: 'timeline__dot--blue',
  version: 'timeline__dot--cyan',
  upcoming: 'timeline__dot--blue',
}

const eventIcons: Record<string, React.ComponentType<{ className?: string; size?: number }>> = {
  execution_start: Play,
  execution_success: CheckCircle2,
  execution_error: XCircle,
  execution_timeout: AlertCircle,
  execution_cancelled: XCircle,
  status_change: ArrowRight,
  version_created: Clock,
  created: Play,
  version: Clock,
  upcoming: CalendarClock,
}

/**
 * Compute the next N upcoming runs for a schedule using cron-parser.
 */
function computeUpcoming(schedule: Schedule, count: number, tz: string): TimelineEntry[] {
  if (!schedule.enabled) return []

  const entries: TimelineEntry[] = []

  if (schedule.scheduleType === 'cron' && schedule.cronExpression) {
    try {
      const parser = CronExpressionParser.parse(schedule.cronExpression, {
        currentDate: new Date(),
        tz,
      })
      for (let i = 0; i < count; i++) {
        const next = parser.next()
        entries.push({
          id: `future-${schedule.id}-${i}`,
          title: schedule.name,
          description: `Cron: ${schedule.cronExpression}`,
          time: next.toDate(),
          type: 'future',
          eventType: 'upcoming',
          sourceType: 'schedule',
          status: 'scheduled',
        })
      }
    } catch {
      // Invalid cron — skip
    }
  } else if (schedule.scheduleType === 'interval' && schedule.intervalSeconds && schedule.nextRunAt) {
    const base = new Date(schedule.nextRunAt)
    for (let i = 0; i < count; i++) {
      const time = new Date(base.getTime() + i * schedule.intervalSeconds * 1000)
      if (time <= new Date()) continue
      entries.push({
        id: `future-${schedule.id}-${i}`,
        title: schedule.name,
        description: `Every ${formatInterval(schedule.intervalSeconds)}`,
        time,
        type: 'future',
        eventType: 'upcoming',
        sourceType: 'schedule',
        status: 'scheduled',
      })
    }
  } else if (schedule.scheduleType === 'once' && schedule.runAt) {
    const runAt = new Date(schedule.runAt)
    if (runAt > new Date()) {
      entries.push({
        id: `future-${schedule.id}-0`,
        title: schedule.name,
        description: 'One-time schedule',
        time: runAt,
        type: 'future',
        eventType: 'upcoming',
        sourceType: 'schedule',
        status: 'scheduled',
      })
    }
  }

  return entries
}

function formatInterval(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.round(seconds / 60)}m`
  if (seconds < 86400) return `${Math.round(seconds / 3600)}h`
  return `${Math.round(seconds / 86400)}d`
}

function formatTime(date: Date, tz: string): string {
  try {
    return new Intl.DateTimeFormat('en-US', {
      timeZone: tz,
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true,
    }).format(date)
  } catch {
    return date.toLocaleString()
  }
}

export function ScheduleTimeline({ botId, schedules, timezone }: ScheduleTimelineProps) {
  const [pastEvents, setPastEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getBotTimeline(botId, 50, 0)
      .then((data) => {
        if (!cancelled) setPastEvents(data)
      })
      .catch(() => {
        if (!cancelled) setPastEvents([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [botId])

  // Compute upcoming runs from enabled schedules
  const upcomingEntries = useMemo(() => {
    const entries: TimelineEntry[] = []
    for (const sch of schedules) {
      entries.push(...computeUpcoming(sch, 5, timezone))
    }
    return entries
  }, [schedules, timezone])

  // Convert past events to entries
  const pastEntries = useMemo<TimelineEntry[]>(
    () =>
      pastEvents.map((e) => ({
        id: e.id,
        title: e.title,
        description: e.description,
        time: new Date(e.createdAt),
        type: 'past' as const,
        eventType: e.eventType,
        sourceType: e.sourceType,
      })),
    [pastEvents]
  )

  // Merge and sort: future ascending after now, past descending before now
  const allEntries = useMemo(() => {
    const now = new Date()
    const past = pastEntries.sort((a, b) => b.time.getTime() - a.time.getTime())
    const future = upcomingEntries.sort((a, b) => a.time.getTime() - b.time.getTime())

    // Interleave: past (newest first) → NOW → future (soonest first)
    const result: (TimelineEntry | 'now')[] = []
    result.push(...past)
    if (past.length > 0 || future.length > 0) {
      result.push('now')
    }
    // For future entries after now divider, keep them in ascending order
    // but we want them displayed top-to-bottom as soonest first
    result.push(...future)

    // Filter: only show entries within reasonable range
    return result.filter((e) => {
      if (e === 'now') return true
      const entry = e as TimelineEntry
      const diffMs = Math.abs(entry.time.getTime() - now.getTime())
      // Show past events within 30 days, future within 7 days
      if (entry.type === 'past') return diffMs < 30 * 86400 * 1000
      return diffMs < 7 * 86400 * 1000
    })
  }, [pastEntries, upcomingEntries])

  if (loading) {
    return (
      <div className="timeline__loading">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
      </div>
    )
  }

  if (allEntries.length === 0 || (allEntries.length === 1 && allEntries[0] === 'now')) {
    return (
      <div className="timeline__empty">
        <CalendarClock size={32} style={{ marginBottom: '0.5rem' }} />
        <p style={{ fontSize: '0.875rem' }}>No timeline events yet</p>
        <p style={{ fontSize: '0.75rem', marginTop: '0.25rem' }}>
          Create and enable schedules to see upcoming runs
        </p>
      </div>
    )
  }

  return (
    <div className="timeline">
      {allEntries.map((entry, i) => {
        if (entry === 'now') {
          return (
            <div key="now-marker" className="timeline__now-marker">
              <div className="timeline__now-marker__line" />
              <span className="timeline__now-marker__label">Now</span>
              <div className="timeline__now-marker__line" />
            </div>
          )
        }

        const Icon = eventIcons[entry.eventType] || Clock
        const dotClass = eventDotClass[entry.eventType] || 'timeline__dot--zinc'
        const isFuture = entry.type === 'future'

        // Count non-'now' entries for line rendering
        const remaining = allEntries.slice(i + 1).filter((e) => e !== 'now')

        return (
          <div
            key={entry.id}
            className={`timeline__item${isFuture ? ' timeline__item--future' : ''}`}
          >
            <div className="timeline__dot-wrap">
              <div
                className={`timeline__dot ${dotClass}${isFuture ? ' timeline__dot--future' : ''}`}
              >
                <Icon size={14} />
              </div>
              {remaining.length > 0 && <div className="timeline__line" />}
            </div>

            <div className="timeline__content">
              <p className="timeline__title">
                {entry.title}
                {isFuture && (
                  <span
                    style={{
                      marginLeft: '0.5rem',
                      fontSize: '0.625rem',
                      fontWeight: 600,
                      textTransform: 'uppercase',
                      color: 'var(--accent-500)',
                      letterSpacing: '0.04em',
                    }}
                  >
                    upcoming
                  </span>
                )}
              </p>
              {entry.description && (
                <p className="timeline__description">{entry.description}</p>
              )}
              <p className="timeline__time">
                {formatTime(entry.time, timezone)}
                {timezone !== 'UTC' && (
                  <span style={{ marginLeft: '0.5rem', opacity: 0.6 }}>({timezone})</span>
                )}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

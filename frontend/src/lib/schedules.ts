import type { Schedule } from '../types'

// Plain-words one-liner for a schedule's trigger, e.g. "Every Monday at 7:30 AM".
// Used by the Routines list; parses the real trigger fields only.
export function describeSchedule(schedule: Schedule): string {
  const { scheduleType, cronExpression, intervalSeconds, runAt, eventTrigger } = schedule

  if (scheduleType === 'interval') {
    const seconds = intervalSeconds ?? 0
    if (seconds > 0 && seconds % 3600 === 0) {
      const hours = seconds / 3600
      return `Every ${hours} hour${hours === 1 ? '' : 's'}`
    }
    if (seconds > 0 && seconds % 60 === 0) {
      const minutes = seconds / 60
      return `Every ${minutes} minute${minutes === 1 ? '' : 's'}`
    }
    return `Every ${seconds} seconds`
  }

  if (scheduleType === 'once') {
    if (!runAt) return 'One time'
    const d = new Date(runAt)
    if (Number.isNaN(d.getTime())) return 'One time'
    return `One time · ${d.toLocaleString(undefined, {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
    })}`
  }

  if (scheduleType === 'event') {
    return eventTrigger ? `When event "${eventTrigger}" fires` : 'On an event'
  }

  if (scheduleType === 'cron' && cronExpression) {
    const parts = cronExpression.trim().split(/\s+/)
    if (parts.length === 5) {
      const [minute, hour, dom, month, dow] = parts
      if (dom === '*' && month === '*' && /^\d{1,2}$/.test(minute) && /^\d{1,2}$/.test(hour)) {
        const time = formatHourMinute(parseInt(hour, 10), parseInt(minute, 10))
        if (dow === '*') return `Every day at ${time}`
        if (dow === '1-5') return `Every weekday at ${time}`
        if (/^\d{1,2}$/.test(dow)) {
          const day = parseInt(dow, 10) % 7
          return `Every ${WEEKDAY_NAMES[day]} at ${time}`
        }
      }
      if (parts[1] === '*' && /^\d{1,2}$/.test(parts[0])) {
        return `Every hour at :${parts[0].padStart(2, '0')}`
      }
    }
    return `Cron: ${cronExpression}`
  }

  return 'Scheduled'
}

const WEEKDAY_NAMES = [
  'Sunday',
  'Monday',
  'Tuesday',
  'Wednesday',
  'Thursday',
  'Friday',
  'Saturday',
]

function formatHourMinute(hour: number, minute: number): string {
  const suffix = hour >= 12 ? 'PM' : 'AM'
  const h12 = hour % 12 === 0 ? 12 : hour % 12
  return `${h12}:${String(minute).padStart(2, '0')} ${suffix}`
}

// Relative "last run" label from the real lastRunAt; null when never run.
export function formatLastRun(iso: string | undefined): string | null {
  if (!iso) return null
  const diff = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(diff) || diff < 0) return null
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

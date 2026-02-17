import { useState, useEffect } from 'react'
import {
  Play,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  ArrowRight,
  Loader2,
} from 'lucide-react'
import { cn } from '../../lib/utils'
import { getTimeline, type TimelineEvent } from '../../api/automations'

interface TimelineTabProps {
  botId: string
  sourceType: string
  sourceId: string
}

const eventIcons: Record<string, React.ComponentType<{ className?: string }>> = {
  execution_start: Play,
  execution_success: CheckCircle2,
  execution_error: XCircle,
  execution_timeout: AlertCircle,
  execution_cancelled: XCircle,
  status_change: ArrowRight,
  version_created: Clock,
}

const eventColors: Record<string, string> = {
  execution_start: 'text-blue-500 bg-blue-500/10',
  execution_success: 'text-green-500 bg-green-500/10',
  execution_error: 'text-red-500 bg-red-500/10',
  execution_timeout: 'text-yellow-500 bg-yellow-500/10',
  execution_cancelled: 'text-zinc-500 bg-zinc-500/10',
  status_change: 'text-purple-500 bg-purple-500/10',
  version_created: 'text-cyan-500 bg-cyan-500/10',
}

export function TimelineTab({ botId, sourceType, sourceId }: TimelineTabProps) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getTimeline(botId, sourceType, sourceId, 50, 0)
      .then((data) => {
        if (!cancelled) setEvents(data)
      })
      .catch(() => {
        if (!cancelled) setEvents([])
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [botId, sourceType, sourceId])

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
        <Clock className="mb-2 h-8 w-8" />
        <p className="text-sm">No timeline events yet</p>
      </div>
    )
  }

  return (
    <div className="space-y-1 py-2">
      {events.map((event, i) => {
        const Icon = eventIcons[event.eventType] || Clock
        const colorClass = eventColors[event.eventType] || 'text-zinc-500 bg-zinc-500/10'
        const [textColor, bgColor] = colorClass.split(' ')

        return (
          <div key={event.id} className="flex gap-3 px-4 py-2">
            {/* Timeline line + dot */}
            <div className="flex flex-col items-center">
              <div className={cn('flex h-7 w-7 items-center justify-center rounded-full', bgColor)}>
                <Icon className={cn('h-3.5 w-3.5', textColor)} />
              </div>
              {i < events.length - 1 && (
                <div className="w-px flex-1 bg-zinc-200 dark:bg-zinc-800" />
              )}
            </div>

            {/* Content */}
            <div className="flex-1 pb-4">
              <p className="text-sm font-medium text-zinc-900 dark:text-zinc-100">
                {event.title}
              </p>
              {event.description && (
                <p className="mt-0.5 text-xs text-zinc-500">{event.description}</p>
              )}
              <p className="mt-1 text-xs text-zinc-400">
                {new Date(event.createdAt).toLocaleString()}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

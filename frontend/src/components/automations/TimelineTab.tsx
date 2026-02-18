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
import { getTimeline, type TimelineEvent } from '../../api/automations'

interface TimelineTabProps {
  botId: string
  sourceType: string
  sourceId: string
}

const eventIcons: Record<string, React.ComponentType<{ className?: string; size?: number }>> = {
  execution_start: Play,
  execution_success: CheckCircle2,
  execution_error: XCircle,
  execution_timeout: AlertCircle,
  execution_cancelled: XCircle,
  status_change: ArrowRight,
  version_created: Clock,
}

const eventDotClass: Record<string, string> = {
  execution_start: 'timeline__dot--blue',
  execution_success: 'timeline__dot--green',
  execution_error: 'timeline__dot--red',
  execution_timeout: 'timeline__dot--yellow',
  execution_cancelled: 'timeline__dot--zinc',
  status_change: 'timeline__dot--purple',
  version_created: 'timeline__dot--cyan',
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
      <div className="timeline__loading">
        <Loader2 size={20} className="animate-spin" style={{ color: 'var(--color-text-tertiary)' }} />
      </div>
    )
  }

  if (events.length === 0) {
    return (
      <div className="timeline__empty">
        <Clock size={32} style={{ marginBottom: '0.5rem' }} />
        <p style={{ fontSize: '0.875rem' }}>No timeline events yet</p>
      </div>
    )
  }

  return (
    <div className="timeline">
      {events.map((event, i) => {
        const Icon = eventIcons[event.eventType] || Clock
        const dotClass = eventDotClass[event.eventType] || 'timeline__dot--zinc'

        return (
          <div key={event.id} className="timeline__item">
            {/* Timeline line + dot */}
            <div className="timeline__dot-wrap">
              <div className={`timeline__dot ${dotClass}`}>
                <Icon size={14} />
              </div>
              {i < events.length - 1 && (
                <div className="timeline__line" />
              )}
            </div>

            {/* Content */}
            <div className="timeline__content">
              <p className="timeline__title">
                {event.title}
              </p>
              {event.description && (
                <p className="timeline__description">{event.description}</p>
              )}
              <p className="timeline__time">
                {new Date(event.createdAt).toLocaleString()}
              </p>
            </div>
          </div>
        )
      })}
    </div>
  )
}

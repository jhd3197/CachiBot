import {
  Play,
  Pause,
  Clock,
  CheckCircle2,
  Code,
  CalendarClock,
  FolderKanban,
} from 'lucide-react'

interface AutomationCardProps {
  id: string
  name: string
  description: string
  type: 'function' | 'script' | 'schedule'
  status: string
  lastRunAt: string | null
  runCount: number
  onClick: () => void
  onRun?: () => void
  onToggle?: () => void
}

const typeIcons = {
  function: FolderKanban,
  script: Code,
  schedule: CalendarClock,
}

export function AutomationCard({
  name,
  description,
  type,
  status,
  lastRunAt,
  runCount,
  onClick,
  onRun,
  onToggle,
}: AutomationCardProps) {
  const TypeIcon = typeIcons[type]

  return (
    <div onClick={onClick} className="automation-card">
      <div className="automation-card__header">
        <div className="automation-card__info">
          <div className="automation-card__icon">
            <TypeIcon size={16} />
          </div>
          <div>
            <h3 className="automation-card__name">{name}</h3>
            <p className="automation-card__type">{description || 'No description'}</p>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.25rem' }}>
          {/* Status badge */}
          <span className={`automation-card__status automation-card__status--${status}`}>
            {status}
          </span>

          {/* Actions */}
          <div className="automation-card__actions">
            {onRun && status !== 'disabled' && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onRun()
                }}
                className="automation-card__action-btn"
              >
                <Play size={14} />
              </button>
            )}
            {onToggle && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onToggle()
                }}
                className="automation-card__action-btn"
              >
                {status === 'disabled' ? (
                  <Play size={14} />
                ) : (
                  <Pause size={14} />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Footer stats */}
      <div className="automation-card__footer">
        <span className="automation-card__stat">
          <CheckCircle2 size={12} />
          {runCount} runs
        </span>
        {lastRunAt && (
          <span className="automation-card__stat">
            <Clock size={12} />
            {formatRelativeTime(lastRunAt)}
          </span>
        )}
      </div>
    </div>
  )
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

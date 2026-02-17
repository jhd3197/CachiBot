import {
  Play,
  Pause,
  MoreHorizontal,
  Clock,
  AlertCircle,
  CheckCircle2,
  Code,
  CalendarClock,
  FolderKanban,
} from 'lucide-react'
import { cn } from '../../lib/utils'

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

const statusColors: Record<string, string> = {
  active: 'text-green-500',
  enabled: 'text-green-500',
  draft: 'text-zinc-400',
  disabled: 'text-zinc-400',
  error: 'text-red-500',
}

const statusBgs: Record<string, string> = {
  active: 'bg-green-500/10',
  enabled: 'bg-green-500/10',
  draft: 'bg-zinc-500/10',
  disabled: 'bg-zinc-500/10',
  error: 'bg-red-500/10',
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
    <div
      onClick={onClick}
      className="group cursor-pointer rounded-lg border border-zinc-200 bg-white p-4 transition-all hover:border-zinc-300 hover:shadow-sm dark:border-zinc-800 dark:bg-zinc-900 dark:hover:border-zinc-700"
    >
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-zinc-100 dark:bg-zinc-800">
            <TypeIcon className="h-4 w-4 text-zinc-600 dark:text-zinc-400" />
          </div>
          <div>
            <h3 className="text-sm font-medium text-zinc-900 dark:text-zinc-100">{name}</h3>
            <p className="mt-0.5 text-xs text-zinc-500 line-clamp-1">{description || 'No description'}</p>
          </div>
        </div>

        <div className="flex items-center gap-1">
          {/* Status badge */}
          <span
            className={cn(
              'rounded-full px-2 py-0.5 text-xs font-medium',
              statusBgs[status] || 'bg-zinc-500/10',
              statusColors[status] || 'text-zinc-400'
            )}
          >
            {status}
          </span>

          {/* Actions */}
          <div className="flex items-center gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            {onRun && status !== 'disabled' && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onRun()
                }}
                className="flex h-7 w-7 items-center justify-center rounded text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
              >
                <Play className="h-3.5 w-3.5" />
              </button>
            )}
            {onToggle && (
              <button
                onClick={(e) => {
                  e.stopPropagation()
                  onToggle()
                }}
                className="flex h-7 w-7 items-center justify-center rounded text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600 dark:hover:bg-zinc-800 dark:hover:text-zinc-300"
              >
                {status === 'disabled' ? (
                  <Play className="h-3.5 w-3.5" />
                ) : (
                  <Pause className="h-3.5 w-3.5" />
                )}
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Footer stats */}
      <div className="mt-3 flex items-center gap-4 text-xs text-zinc-400">
        <span className="flex items-center gap-1">
          <CheckCircle2 className="h-3 w-3" />
          {runCount} runs
        </span>
        {lastRunAt && (
          <span className="flex items-center gap-1">
            <Clock className="h-3 w-3" />
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

/**
 * TaskProgress — inline task checklist component for workspace mode.
 * Shows numbered steps with status icons, a progress bar, and a counter.
 */

import { Circle, Loader2, CheckCircle, XCircle } from 'lucide-react'
import type { TaskProgress as TaskProgressType } from '../../stores/workspace'

interface TaskProgressProps {
  progress: TaskProgressType
}

const STATUS_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  pending: Circle,
  in_progress: Loader2,
  done: CheckCircle,
  failed: XCircle,
}

const STATUS_CLASS: Record<string, string> = {
  pending: 'task-item--pending',
  in_progress: 'task-item--in-progress',
  done: 'task-item--done',
  failed: 'task-item--failed',
}

export function TaskProgress({ progress }: TaskProgressProps) {
  const { tasks, completedCount, totalCount } = progress
  const percent = totalCount > 0 ? Math.round((completedCount / totalCount) * 100) : 0

  return (
    <div className="task-progress">
      <div className="task-progress__header">
        <span className="task-progress__title">Progress</span>
        <span className="task-progress__count">
          {completedCount}/{totalCount} done
        </span>
      </div>
      <div className="task-progress__bar-bg">
        <div
          className="task-progress__bar-fill"
          style={{ width: `${percent}%` }}
        />
      </div>
      <ol className="task-progress__list">
        {tasks.map((task, idx) => {
          const Icon = STATUS_ICON[task.status] || Circle
          const cls = STATUS_CLASS[task.status] || ''
          return (
            <li key={idx} className={`task-item ${cls}`}>
              <Icon
                className={`task-item__icon ${task.status === 'in_progress' ? 'animate-spin' : ''}`}
              />
              <span className="task-item__desc">{task.description}</span>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

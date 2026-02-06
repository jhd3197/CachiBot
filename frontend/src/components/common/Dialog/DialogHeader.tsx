import { X } from 'lucide-react'
import { cn } from '../../../lib/utils'
import type { ReactNode } from 'react'

export interface DialogHeaderProps {
  title: string
  subtitle?: string
  icon?: ReactNode
  iconClassName?: string
  onClose?: () => void
  className?: string
  children?: ReactNode
}

export function DialogHeader({
  title,
  subtitle,
  icon,
  iconClassName,
  onClose,
  className,
  children,
}: DialogHeaderProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between border-b border-zinc-800 px-6 py-4',
        className
      )}
    >
      <div className="flex items-center gap-3">
        {icon && (
          <div
            className={cn(
              'flex h-10 w-10 items-center justify-center rounded-xl bg-cachi-600/20',
              iconClassName
            )}
          >
            {icon}
          </div>
        )}
        <div>
          <h2 className="text-lg font-bold text-zinc-100">{title}</h2>
          {subtitle && <p className="text-sm text-zinc-500">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {children}
        {onClose && (
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 transition-colors"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  )
}

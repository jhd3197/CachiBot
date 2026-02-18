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
    <div className={cn('dialog__header', className)}>
      <div className="flex items-center gap-3">
        {icon && (
          <div className={cn('dialog__header-icon', iconClassName)}>
            {icon}
          </div>
        )}
        <div>
          <h2 className="text-dialog-title">{title}</h2>
          {subtitle && <p className="text-label">{subtitle}</p>}
        </div>
      </div>
      <div className="flex items-center gap-2">
        {children}
        {onClose && (
          <button
            onClick={onClose}
            className="btn-close"
            aria-label="Close dialog"
          >
            <X className="h-5 w-5" />
          </button>
        )}
      </div>
    </div>
  )
}

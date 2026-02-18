import { cn } from '../../../lib/utils'
import type { ReactNode } from 'react'

export interface DialogFooterProps {
  children: ReactNode
  className?: string
  leftContent?: ReactNode
}

export function DialogFooter({
  children,
  className,
  leftContent,
}: DialogFooterProps) {
  return (
    <div className={cn('dialog__footer', className)}>
      <div>{leftContent}</div>
      <div className="flex items-center gap-2">{children}</div>
    </div>
  )
}

// Common button styles for dialog actions
export interface DialogButtonProps {
  onClick?: () => void
  disabled?: boolean
  children: ReactNode
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  className?: string
  type?: 'button' | 'submit'
}

export function DialogButton({
  onClick,
  disabled,
  children,
  variant = 'secondary',
  className,
  type = 'button',
}: DialogButtonProps) {
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={cn('btn', `btn--${variant}`, 'btn--md', className)}
    >
      {children}
    </button>
  )
}

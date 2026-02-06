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
    <div
      className={cn(
        'flex items-center justify-between border-t border-zinc-800 px-6 py-4',
        className
      )}
    >
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

const variantClasses = {
  primary:
    'rounded-lg bg-cachi-600 px-6 py-2 text-sm font-medium text-white hover:bg-cachi-500 disabled:opacity-50 disabled:cursor-not-allowed',
  secondary:
    'rounded-lg border border-zinc-700 bg-zinc-800 px-6 py-2 text-sm font-medium text-zinc-300 hover:bg-zinc-700 disabled:opacity-50 disabled:cursor-not-allowed',
  danger:
    'rounded-lg bg-red-600 px-6 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50 disabled:cursor-not-allowed',
  ghost:
    'rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50 disabled:cursor-not-allowed',
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
      className={cn(variantClasses[variant], className)}
    >
      {children}
    </button>
  )
}

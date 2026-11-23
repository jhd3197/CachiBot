import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'

interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
  /**
   * Screen-reader label rendered as visually-hidden text. Pass an empty
   * string for a decorative spinner (pair with aria-hidden on the parent).
   */
  label?: string
}

export function Spinner({ size = 'md', label = 'Loading...', className, ...props }: SpinnerProps) {
  return (
    <div className={cn('spinner', `spinner--${size}`, className)} role="status" {...props}>
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  )
}

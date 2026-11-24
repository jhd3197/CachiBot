import type { HTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
import { useDelayedFlag } from '../../hooks/useDelayedFlag'

interface SpinnerProps extends HTMLAttributes<HTMLDivElement> {
  size?: 'sm' | 'md' | 'lg'
  /**
   * Screen-reader label rendered as visually-hidden text. Pass an empty
   * string for a decorative spinner (pair with aria-hidden on the parent).
   */
  label?: string
  /**
   * When provided, the spinner stays hidden (holding its layout space) until
   * it has been mounted for delayMs — pass it for spinners on fast actions so
   * they do not flash (default suggestion: 200). Omit to show immediately.
   */
  delayMs?: number
}

export function Spinner({ size = 'md', label = 'Loading...', delayMs, className, ...props }: SpinnerProps) {
  const delayed = useDelayedFlag(delayMs !== undefined, delayMs)
  const show = delayMs === undefined ? true : delayed
  if (!show) {
    return (
      <div
        className={cn('spinner', `spinner--${size}`, className)}
        style={{ visibility: 'hidden' }}
        aria-hidden="true"
        {...props}
      />
    )
  }
  return (
    <div className={cn('spinner', `spinner--${size}`, className)} role="status" {...props}>
      {label ? <span className="sr-only">{label}</span> : null}
    </div>
  )
}

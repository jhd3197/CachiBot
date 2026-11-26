import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Spinner } from './Spinner'
import { useDelayedFlag } from '../../hooks/useDelayedFlag'

interface PageLoadingProps {
  /**
   * When provided, the block stays hidden until pending has been true for
   * delayMs (no flash on fast loads). Omit to show immediately.
   */
  pending?: boolean
  /** Delay before showing when pending is provided (default 200ms). */
  delayMs?: number
  /** Screen-reader label for the spinner. */
  label?: string
  /** Optional placeholder content (e.g. Skeleton) rendered under the spinner. */
  children?: ReactNode
  className?: string
}

/**
 * In-panel loading state: a centered Spinner (md), never a full-viewport
 * takeover. Render it where the content goes.
 */
export function PageLoading({
  pending,
  delayMs,
  label = 'Loading...',
  children,
  className,
}: PageLoadingProps) {
  const delayed = useDelayedFlag(pending ?? false, delayMs)
  const show = pending === undefined ? true : delayed
  if (!show) return null
  return (
    <div className={cn('v2-page-loading', className)}>
      <Spinner size="md" label={label} />
      {children}
    </div>
  )
}

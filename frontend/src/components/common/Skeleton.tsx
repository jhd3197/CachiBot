import { cn } from '../../lib/utils'

interface SkeletonProps {
  /** `list` composes `rows` rows; `row` is an avatar block plus two lines. */
  variant?: 'line' | 'row' | 'card' | 'list'
  /** Number of composed rows for variant="list" (default 3). */
  rows?: number
  className?: string
}

/**
 * Placeholder surfaces that pulse between --v2-bg-hover and --v2-bg-inset.
 * Purely visual — always rendered aria-hidden; pair with a status label
 * (or PageLoading) when the wait needs announcing.
 */
export function Skeleton({ variant = 'line', rows = 3, className }: SkeletonProps) {
  switch (variant) {
    case 'row':
      return (
        <div className={cn('v2-skeleton-row', className)} aria-hidden="true">
          <span className="v2-skeleton v2-skeleton-row__avatar" />
          <span className="v2-skeleton-row__main">
            <span className="v2-skeleton v2-skeleton-row__line" />
            <span className="v2-skeleton v2-skeleton-row__line v2-skeleton-row__line--short" />
          </span>
        </div>
      )
    case 'card':
      return (
        <div className={cn('v2-skeleton-card', className)} aria-hidden="true">
          <span className="v2-skeleton v2-skeleton-card__line v2-skeleton-card__line--title" />
          <span className="v2-skeleton v2-skeleton-card__line" />
          <span className="v2-skeleton v2-skeleton-card__line v2-skeleton-card__line--short" />
        </div>
      )
    case 'list':
      return (
        <div className={cn('v2-skeleton-list', className)} aria-hidden="true">
          {Array.from({ length: rows }, (_, i) => (
            <Skeleton key={i} variant="row" />
          ))}
        </div>
      )
    default:
      return <span className={cn('v2-skeleton', 'v2-skeleton--line', className)} aria-hidden="true" />
  }
}

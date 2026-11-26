import type { ReactNode } from 'react'
import { cn } from '../../lib/utils'
import { Spinner } from './Spinner'

interface StatusLineProps {
  /** Shows a Spinner (sm) before the text unless an explicit icon is given. */
  pending?: boolean
  /** Custom leading icon; wins over the pending spinner. */
  icon?: ReactNode
  /**
   * Optional bot accent dot (e.g. the bot's color). Omit for no mark —
   * the line itself stays grey either way.
   */
  markColor?: string
  className?: string
  children: ReactNode
}

/**
 * Grey v2 status line (styles/v2/chat.less .v2-status-line): 13px tertiary
 * text with an optional leading mark, icon, or pending spinner. Used by the
 * L3 chat work indicators; usable anywhere a quiet status line fits.
 */
export function StatusLine({ pending, icon, markColor, className, children }: StatusLineProps) {
  return (
    <div className={cn('v2-status-line', className)} role="status">
      {markColor ? (
        <span
          className="v2-status-line__mark"
          style={{ backgroundColor: markColor }}
          aria-hidden="true"
        />
      ) : null}
      {icon ?? (pending ? <Spinner size="sm" /> : null)}
      {children}
    </div>
  )
}

import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  /**
   * Pending state: disables the button immediately (no double-submit), marks
   * it aria-busy, and overlays a small spinner while the label keeps its
   * layout space — the button width does not jump when pending toggles. The
   * overlaid spinner appears only after 200ms so sub-200ms work does not
   * flash; disabling is never delayed.
   */
  pending?: boolean
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', disabled, pending, children, ...props }, ref) => {
    return (
      <button
        ref={ref}
        disabled={disabled || pending}
        aria-busy={pending || undefined}
        className={cn('btn', `btn--${variant}`, `btn--${size}`, pending && 'btn--pending', className)}
        {...props}
      >
        {pending ? (
          <>
            <span className="btn__spinner" aria-hidden="true">
              <Spinner size="sm" label="" delayMs={200} />
            </span>
            <span className="btn__label">{children}</span>
          </>
        ) : (
          children
        )}
      </button>
    )
  }
)

Button.displayName = 'Button'

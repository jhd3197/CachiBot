import { forwardRef, type ButtonHTMLAttributes } from 'react'
import { cn } from '../../lib/utils'
import { Spinner } from './Spinner'

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger'
  size?: 'sm' | 'md' | 'lg'
  /**
   * Pending state: disables the button, marks it aria-busy, and overlays a
   * small spinner while the label keeps its layout space — the button width
   * does not jump when pending toggles.
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
              <Spinner size="sm" label="" />
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

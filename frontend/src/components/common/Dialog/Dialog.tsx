import { useEffect, useRef, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { cn } from '../../../lib/utils'

export interface DialogProps {
  open: boolean
  onClose: () => void
  children: ReactNode
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full'
  className?: string
  closeOnBackdrop?: boolean
  closeOnEscape?: boolean
  ariaLabel?: string
  ariaLabelledBy?: string
}

export function Dialog({
  open,
  onClose,
  children,
  size = 'lg',
  className,
  closeOnBackdrop = true,
  closeOnEscape = true,
  ariaLabel,
  ariaLabelledBy,
}: DialogProps) {
  const dialogRef = useRef<HTMLDivElement>(null)

  // Handle escape key
  useEffect(() => {
    if (!open || !closeOnEscape) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose()
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open, closeOnEscape, onClose])

  // Lock body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden'
    } else {
      document.body.style.overflow = ''
    }
    return () => {
      document.body.style.overflow = ''
    }
  }, [open])

  // Focus trap: keep Tab navigation within the dialog
  useEffect(() => {
    if (!open) return

    const focusableSelector =
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'

    // Focus the first focusable element when the dialog opens
    const panel = dialogRef.current
    if (panel) {
      const firstFocusable = panel.querySelector<HTMLElement>(focusableSelector)
      firstFocusable?.focus()
    }

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return

      const panel = dialogRef.current
      if (!panel) return

      const focusableElements = Array.from(
        panel.querySelectorAll<HTMLElement>(focusableSelector)
      )
      if (focusableElements.length === 0) return

      const firstElement = focusableElements[0]
      const lastElement = focusableElements[focusableElements.length - 1]

      if (e.shiftKey) {
        // Shift+Tab: wrap from first to last
        if (document.activeElement === firstElement) {
          e.preventDefault()
          lastElement.focus()
        }
      } else {
        // Tab: wrap from last to first
        if (document.activeElement === lastElement) {
          e.preventDefault()
          firstElement.focus()
        }
      }
    }

    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [open])

  if (!open) return null

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (closeOnBackdrop && e.target === e.currentTarget) {
      onClose()
    }
  }

  return createPortal(
    <div className="dialog__backdrop" onClick={handleBackdropClick}>
      <div
        ref={dialogRef}
        className={cn('dialog__panel', `dialog__panel--${size}`, className)}
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        aria-labelledby={ariaLabelledBy}
      >
        {children}
      </div>
    </div>,
    document.body
  )
}

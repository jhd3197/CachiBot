import { useEffect, useRef, type ReactNode } from 'react'
import { cn } from '../../lib/utils'

/**
 * UI v2 dropdown menu (design views 13/14): 260px panel, 6px padding,
 * 14px radius, 36px items. The caller positions it inside a relative
 * wrapper via `className`, with the trigger as a sibling that toggles its
 * visibility.
 *
 * Closing: Escape, any V2MenuItem's own handler, or a click outside the
 * menu. The outside-click listener is registered one tick after mount on
 * purpose: the menu usually mounts while the opening click is still
 * bubbling to the document (React flushes effects synchronously for
 * click-triggered updates), so registering immediately would close the
 * menu on the very click that opened it.
 */

interface V2MenuProps {
  onClose: () => void
  className?: string
  children: ReactNode
}

export function V2Menu({ onClose, className, children }: V2MenuProps) {
  const ref = useRef<HTMLDivElement>(null)
  const onCloseRef = useRef(onClose)
  onCloseRef.current = onClose

  useEffect(() => {
    const onDocClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onCloseRef.current()
      }
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onCloseRef.current()
    }
    const timer = window.setTimeout(() => {
      document.addEventListener('click', onDocClick)
    }, 0)
    document.addEventListener('keydown', onKey)
    return () => {
      window.clearTimeout(timer)
      document.removeEventListener('click', onDocClick)
      document.removeEventListener('keydown', onKey)
    }
  }, [])

  return (
    <div
      ref={ref}
      role="menu"
      className={cn('v2-menu', className)}
      onClick={(e) => e.stopPropagation()}
    >
      {children}
    </div>
  )
}

interface V2MenuItemProps {
  onClick: () => void
  icon: ReactNode
  children: ReactNode
  /** Muted right-hand annotation (real counts/labels only) */
  suffix?: ReactNode
  danger?: boolean
}

export function V2MenuItem({ onClick, icon, children, suffix, danger }: V2MenuItemProps) {
  return (
    <button
      type="button"
      role="menuitem"
      className={cn('v2-menu__item', danger && 'v2-menu__item--danger')}
      onClick={onClick}
    >
      <span className="v2-menu__item-icon">{icon}</span>
      <span className="v2-menu__item-label">{children}</span>
      {suffix != null && <span className="v2-menu__item-suffix">{suffix}</span>}
    </button>
  )
}

export function V2MenuLabel({ children }: { children: ReactNode }) {
  return <div className="v2-menu__label">{children}</div>
}

export function V2MenuDivider() {
  return <div className="v2-menu__divider" />
}

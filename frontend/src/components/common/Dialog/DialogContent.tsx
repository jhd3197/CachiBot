import { cn } from '../../../lib/utils'
import type { ReactNode } from 'react'

export interface DialogContentProps {
  children: ReactNode
  className?: string
  scrollable?: boolean
  maxHeight?: string
}

export function DialogContent({
  children,
  className,
  scrollable = false,
  maxHeight = 'max-h-[60vh]',
}: DialogContentProps) {
  return (
    <div
      className={cn(
        'p-6',
        scrollable && `overflow-y-auto ${maxHeight}`,
        className
      )}
    >
      {children}
    </div>
  )
}

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
}: DialogContentProps) {
  return (
    <div className={cn(scrollable ? 'dialog__body' : 'dialog__body-base', className)}>
      {children}
    </div>
  )
}

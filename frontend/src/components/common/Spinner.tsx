import { cn } from '../../lib/utils'

interface SpinnerProps {
  size?: 'sm' | 'md' | 'lg'
  className?: string
}

export function Spinner({ size = 'md', className }: SpinnerProps) {
  return (
    <div className={cn('spinner', `spinner--${size}`, className)}>
      <span className="sr-only">Loading...</span>
    </div>
  )
}

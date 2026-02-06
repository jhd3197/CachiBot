import { Check } from 'lucide-react'
import { cn } from '../../../lib/utils'

export interface Step {
  id: string
  label: string
  description?: string
}

export interface DialogStepperProps {
  steps: Step[]
  currentStep: string
  completedSteps?: string[]
  onStepClick?: (stepId: string) => void
  variant?: 'horizontal' | 'vertical' | 'compact'
  className?: string
}

export function DialogStepper({
  steps,
  currentStep,
  completedSteps = [],
  onStepClick,
  variant = 'horizontal',
  className,
}: DialogStepperProps) {
  const currentIndex = steps.findIndex((s) => s.id === currentStep)

  if (variant === 'compact') {
    return (
      <div className={cn('flex items-center gap-1.5', className)}>
        {steps.map((step, index) => {
          const isCompleted = completedSteps.includes(step.id)
          const isCurrent = step.id === currentStep
          const isPast = index < currentIndex

          return (
            <button
              key={step.id}
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || (!isCompleted && !isPast && !isCurrent)}
              className={cn(
                'h-2 rounded-full transition-all',
                isCurrent
                  ? 'w-8 bg-cachi-500'
                  : isCompleted || isPast
                    ? 'w-2 bg-cachi-600'
                    : 'w-2 bg-zinc-700',
                onStepClick && (isCompleted || isPast || isCurrent)
                  ? 'cursor-pointer hover:opacity-80'
                  : 'cursor-default'
              )}
              title={step.label}
            />
          )
        })}
      </div>
    )
  }

  if (variant === 'vertical') {
    return (
      <nav className={cn('space-y-2', className)}>
        {steps.map((step, index) => {
          const isCompleted = completedSteps.includes(step.id)
          const isCurrent = step.id === currentStep
          const isPast = index < currentIndex

          return (
            <button
              key={step.id}
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || (!isCompleted && !isPast && !isCurrent)}
              className={cn(
                'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left transition-colors',
                isCurrent
                  ? 'bg-cachi-600/20 text-cachi-400'
                  : isCompleted || isPast
                    ? 'text-zinc-400 hover:bg-zinc-800/50'
                    : 'text-zinc-600',
                onStepClick && (isCompleted || isPast || isCurrent)
                  ? 'cursor-pointer'
                  : 'cursor-default'
              )}
            >
              <div
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded-full text-xs font-medium',
                  isCurrent
                    ? 'bg-cachi-600 text-white'
                    : isCompleted
                      ? 'bg-cachi-600/30 text-cachi-400'
                      : 'bg-zinc-800 text-zinc-500'
                )}
              >
                {isCompleted ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  index + 1
                )}
              </div>
              <div>
                <div className="text-sm font-medium">{step.label}</div>
                {step.description && (
                  <div className="text-xs text-zinc-500">{step.description}</div>
                )}
              </div>
            </button>
          )
        })}
      </nav>
    )
  }

  // Horizontal (default)
  return (
    <nav className={cn('flex items-center justify-center gap-2', className)}>
      {steps.map((step, index) => {
        const isCompleted = completedSteps.includes(step.id)
        const isCurrent = step.id === currentStep
        const isPast = index < currentIndex

        return (
          <div key={step.id} className="flex items-center">
            <button
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || (!isCompleted && !isPast && !isCurrent)}
              className={cn(
                'flex items-center gap-2 rounded-lg px-3 py-1.5 text-sm transition-colors',
                isCurrent
                  ? 'bg-cachi-600/20 text-cachi-400'
                  : isCompleted || isPast
                    ? 'text-zinc-400 hover:text-zinc-300'
                    : 'text-zinc-600',
                onStepClick && (isCompleted || isPast || isCurrent)
                  ? 'cursor-pointer'
                  : 'cursor-default'
              )}
            >
              <div
                className={cn(
                  'flex h-5 w-5 items-center justify-center rounded-full text-[10px] font-medium',
                  isCurrent
                    ? 'bg-cachi-600 text-white'
                    : isCompleted
                      ? 'bg-cachi-600/30 text-cachi-400'
                      : 'bg-zinc-800 text-zinc-500'
                )}
              >
                {isCompleted ? (
                  <Check className="h-3 w-3" />
                ) : (
                  index + 1
                )}
              </div>
              <span className="hidden sm:inline">{step.label}</span>
            </button>
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'mx-1 h-px w-4',
                  isPast ? 'bg-cachi-600/50' : 'bg-zinc-700'
                )}
              />
            )}
          </div>
        )
      })}
    </nav>
  )
}

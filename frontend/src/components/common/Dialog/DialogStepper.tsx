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
  variant?: 'horizontal' | 'vertical' | 'compact' | 'progress'
  className?: string
}

function stepState(
  step: Step,
  index: number,
  currentStep: string,
  currentIndex: number,
  completedSteps: string[]
) {
  const isCurrent = step.id === currentStep
  const isCompleted = completedSteps.includes(step.id)
  const isPast = index < currentIndex
  return {
    isCurrent,
    isCompleted,
    isPast,
    stateClass: isCurrent
      ? 'stepper__step--active'
      : isCompleted || isPast
        ? 'stepper__step--completed'
        : 'stepper__step--upcoming',
    isClickable: isCompleted || isPast || isCurrent,
  }
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

  if (variant === 'progress') {
    return (
      <div className={cn('stepper stepper--progress', className)}>
        {steps.map((step, index) => {
          const s = stepState(step, index, currentStep, currentIndex, completedSteps)
          return (
            <div
              key={step.id}
              className={cn('stepper__bar', s.stateClass)}
              title={step.label}
            />
          )
        })}
      </div>
    )
  }

  if (variant === 'compact') {
    return (
      <div className={cn('stepper stepper--compact', className)}>
        {steps.map((step, index) => {
          const s = stepState(step, index, currentStep, currentIndex, completedSteps)
          return (
            <button
              key={step.id}
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || !s.isClickable}
              className={cn(
                'stepper__step',
                s.stateClass,
                onStepClick && s.isClickable && 'stepper__step--clickable'
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
      <nav className={cn('stepper stepper--vertical', className)}>
        {steps.map((step, index) => {
          const s = stepState(step, index, currentStep, currentIndex, completedSteps)
          return (
            <button
              key={step.id}
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || !s.isClickable}
              className={cn(
                'stepper__step',
                s.stateClass,
                onStepClick && s.isClickable && 'stepper__step--clickable'
              )}
            >
              <div className="stepper__indicator">
                {s.isCompleted ? (
                  <Check className="h-3.5 w-3.5" />
                ) : (
                  index + 1
                )}
              </div>
              <div>
                <div className="stepper__label">{step.label}</div>
                {step.description && (
                  <div className="stepper__description">{step.description}</div>
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
    <nav className={cn('stepper stepper--horizontal', className)}>
      {steps.map((step, index) => {
        const s = stepState(step, index, currentStep, currentIndex, completedSteps)
        return (
          <div key={step.id} className="stepper__step-group">
            <button
              onClick={() => onStepClick?.(step.id)}
              disabled={!onStepClick || !s.isClickable}
              className={cn(
                'stepper__step',
                s.stateClass,
                onStepClick && s.isClickable && 'stepper__step--clickable'
              )}
            >
              <div className="stepper__indicator">
                {s.isCompleted ? (
                  <Check className="h-3 w-3" />
                ) : (
                  index + 1
                )}
              </div>
              <span className="stepper__label">{step.label}</span>
            </button>
            {index < steps.length - 1 && (
              <div
                className={cn(
                  'stepper__connector',
                  s.isPast && 'stepper__connector--completed'
                )}
              />
            )}
          </div>
        )
      })}
    </nav>
  )
}

import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Rocket, Key, HardDrive, Mail, Palette, Check } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useOnboardingStore, ONBOARDING_STEPS } from '../../stores/onboarding'
import { useProvidersStore } from '../../stores/providers'
import { useModelsStore } from '../../stores/models'
import { DialogStepper, type Step } from '../common/Dialog'
import { ProviderStep } from '../dialogs/OnboardingWizard/steps/ProviderStep'
import { DatabaseStep } from '../dialogs/OnboardingWizard/steps/DatabaseStep'
import { SmtpStep } from '../dialogs/OnboardingWizard/steps/SmtpStep'
import { PreferencesStep } from '../dialogs/OnboardingWizard/steps/PreferencesStep'
import { CompleteStep } from '../dialogs/OnboardingWizard/steps/CompleteStep'
import { cn } from '../../lib/utils'

import type { LucideIcon } from 'lucide-react'

interface StepMeta {
  title: string
  subtitle: string
  icon: LucideIcon
  label: string
}

const STEP_META: Record<string, StepMeta> = {
  provider: {
    title: 'Connect a Provider',
    subtitle: 'Add at least one API key and choose a default model.',
    icon: Key,
    label: 'Provider',
  },
  database: {
    title: 'Choose Your Database',
    subtitle: 'Select where CachiBot stores its data. You can change this later.',
    icon: HardDrive,
    label: 'Database',
  },
  email: {
    title: 'Email Configuration',
    subtitle: 'Configure SMTP for notifications and alerts. This step is optional.',
    icon: Mail,
    label: 'Email',
  },
  style: {
    title: 'Personalize Your Experience',
    subtitle: 'Customize how CachiBot looks and feels.',
    icon: Palette,
    label: 'Style',
  },
  done: {
    title: "You're All Set!",
    subtitle: "Here's a summary of your setup.",
    icon: Check,
    label: 'Done',
  },
}

// Mobile compact stepper only
const WIZARD_STEPS: Step[] = ONBOARDING_STEPS.map((id) => ({
  id,
  label: STEP_META[id].label,
}))

export function OnboardingPage() {
  const navigate = useNavigate()
  const { isAuthenticated } = useAuthStore()
  const {
    currentStep,
    nextStep,
    prevStep,
    completeOnboarding,
    skipOnboarding,
    databaseType,
    databaseConfigured,
  } = useOnboardingStore()
  const { providers } = useProvidersStore()
  const { defaultModel } = useModelsStore()

  useEffect(() => {
    if (!isAuthenticated) {
      navigate('/login', { replace: true })
    }
  }, [isAuthenticated, navigate])

  const stepId = ONBOARDING_STEPS[currentStep]
  const completedSteps = ONBOARDING_STEPS.slice(0, currentStep)
  const meta = STEP_META[stepId]

  const canProceed = (): boolean => {
    switch (stepId) {
      case 'provider':
        return providers.some((p) => p.configured) && defaultModel !== ''
      case 'database':
        return databaseType === 'sqlite' || databaseConfigured
      default:
        return true
    }
  }

  const renderStep = () => {
    switch (stepId) {
      case 'provider':
        return <ProviderStep />
      case 'database':
        return <DatabaseStep />
      case 'email':
        return <SmtpStep />
      case 'style':
        return <PreferencesStep />
      case 'done':
        return <CompleteStep />
      default:
        return <ProviderStep />
    }
  }

  const isFirstStep = currentStep === 0
  const isLastStep = stepId === 'done'

  const handleComplete = () => {
    completeOnboarding()
    navigate('/', { replace: true })
  }

  const handleSkip = () => {
    skipOnboarding()
    navigate('/', { replace: true })
  }

  const getNavState = (index: number): 'active' | 'completed' | 'upcoming' => {
    if (index === currentStep) return 'active'
    if (index < currentStep) return 'completed'
    return 'upcoming'
  }

  if (!isAuthenticated) return null

  return (
    <div className="onboarding">
      {/* Sidebar (desktop) */}
      <aside className="onboarding__sidebar">
        <div className="onboarding__brand">
          <div className="onboarding__brand-icon">
            <Rocket className="h-5 w-5 text-white" />
          </div>
          <div className="onboarding__brand-label">
            <span className="onboarding__brand-name">CachiBot</span>
            <span className="onboarding__brand-tag">Setup Wizard</span>
          </div>
        </div>

        {/* Progress segments */}
        <div className="onboarding__progress">
          {ONBOARDING_STEPS.map((id, i) => (
            <div
              key={id}
              className={cn(
                'onboarding__progress-segment',
                i < currentStep && 'onboarding__progress-segment--done',
                i === currentStep && 'onboarding__progress-segment--active'
              )}
            />
          ))}
        </div>

        {/* Nav items */}
        <nav className="onboarding__nav">
          {ONBOARDING_STEPS.map((id, index) => {
            const state = getNavState(index)
            const stepMeta = STEP_META[id]
            const Icon = stepMeta.icon

            return (
              <button
                key={id}
                className={cn('onboarding__nav-item', `onboarding__nav-item--${state}`)}
                disabled={state === 'upcoming'}
                onClick={state === 'completed' ? () => useOnboardingStore.setState({ currentStep: index }) : undefined}
              >
                <div className="onboarding__nav-icon">
                  {state === 'completed' ? (
                    <Check className="h-4 w-4" />
                  ) : (
                    <Icon className="h-4 w-4" />
                  )}
                </div>
                <span className="onboarding__nav-label">{stepMeta.label}</span>
              </button>
            )
          })}
        </nav>

        {/* Sidebar footer */}
        <div className="onboarding__sidebar-footer">
          <span className="onboarding__step-count">
            Step {currentStep + 1} of {ONBOARDING_STEPS.length}
          </span>
          <button onClick={handleSkip} className="onboarding__skip">
            Skip for now
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="onboarding__main">
        {/* Compact stepper (mobile) */}
        <div className="onboarding__compact-stepper">
          <DialogStepper
            steps={WIZARD_STEPS}
            currentStep={stepId}
            completedSteps={completedSteps}
            variant="compact"
          />
        </div>

        {/* Step header */}
        <div className="onboarding__header">
          <h1 className="onboarding__title">{meta?.title}</h1>
          <p className="onboarding__subtitle">{meta?.subtitle}</p>
        </div>

        {/* Step content */}
        <div className="onboarding__content">
          {renderStep()}
        </div>

        {/* Footer */}
        <div className="onboarding__footer">
          <div>
            {isFirstStep ? (
              <span />
            ) : (
              <button
                onClick={prevStep}
                className="btn btn--ghost btn--md"
              >
                Back
              </button>
            )}
          </div>
          <div>
            {isLastStep ? (
              <button
                onClick={handleComplete}
                className="btn btn--primary btn--md"
              >
                Get Started
              </button>
            ) : (
              <button
                onClick={nextStep}
                disabled={!canProceed()}
                className="btn btn--primary btn--md"
              >
                Continue
              </button>
            )}
          </div>
        </div>

        {/* Mobile skip (shown below footer on small screens) */}
        <div className="onboarding__skip-mobile">
          <button onClick={handleSkip}>Skip for now</button>
        </div>
      </main>
    </div>
  )
}

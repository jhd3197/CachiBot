import { useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Rocket } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { useOnboardingStore, ONBOARDING_STEPS } from '../../stores/onboarding'
import { useProvidersStore } from '../../stores/providers'
import { useModelsStore } from '../../stores/models'
import { DialogStepper, type Step } from '../common/Dialog'
import { WelcomeStep } from '../dialogs/OnboardingWizard/steps/WelcomeStep'
import { ApiKeyStep } from '../dialogs/OnboardingWizard/steps/ApiKeyStep'
import { ModelStep } from '../dialogs/OnboardingWizard/steps/ModelStep'
import { DatabaseStep } from '../dialogs/OnboardingWizard/steps/DatabaseStep'
import { SmtpStep } from '../dialogs/OnboardingWizard/steps/SmtpStep'
import { PreferencesStep } from '../dialogs/OnboardingWizard/steps/PreferencesStep'
import { CompleteStep } from '../dialogs/OnboardingWizard/steps/CompleteStep'

const WIZARD_STEPS: Step[] = [
  { id: 'welcome', label: 'Welcome' },
  { id: 'api-key', label: 'API Key' },
  { id: 'model', label: 'Model' },
  { id: 'database', label: 'Database' },
  { id: 'smtp', label: 'Email' },
  { id: 'preferences', label: 'Style' },
  { id: 'complete', label: 'Done' },
]

function getStepSubtitle(step: string): string {
  const subtitles: Record<string, string> = {
    welcome: 'Get started with CachiBot',
    'api-key': 'Connect an AI provider',
    model: 'Choose your default model',
    database: 'Choose your database backend',
    smtp: 'Configure email (optional)',
    preferences: 'Personalize your experience',
    complete: 'Setup complete',
  }
  return subtitles[step] || ''
}

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

  const canProceed = (): boolean => {
    switch (stepId) {
      case 'api-key':
        return providers.some((p) => p.configured)
      case 'model':
        return defaultModel !== ''
      case 'database':
        return databaseType === 'sqlite' || databaseConfigured
      default:
        return true
    }
  }

  const renderStep = () => {
    switch (stepId) {
      case 'welcome':
        return <WelcomeStep />
      case 'api-key':
        return <ApiKeyStep />
      case 'model':
        return <ModelStep />
      case 'database':
        return <DatabaseStep />
      case 'smtp':
        return <SmtpStep />
      case 'preferences':
        return <PreferencesStep />
      case 'complete':
        return <CompleteStep />
      default:
        return <WelcomeStep />
    }
  }

  const isFirstStep = currentStep === 0
  const isLastStep = stepId === 'complete'

  const handleComplete = () => {
    completeOnboarding()
    navigate('/', { replace: true })
  }

  const handleSkip = () => {
    skipOnboarding()
    navigate('/', { replace: true })
  }

  if (!isAuthenticated) return null

  return (
    <div className="layout-auth">
      <div className="onboarding">
        {/* Header */}
        <div className="onboarding__header">
          <div className="onboarding__header-left">
            <div className="onboarding__icon">
              <Rocket className="h-5 w-5 text-white" />
            </div>
            <div>
              <h1 className="onboarding__title">Setup Wizard</h1>
              <p className="onboarding__subtitle">{getStepSubtitle(stepId)}</p>
            </div>
          </div>
          <DialogStepper
            steps={WIZARD_STEPS}
            currentStep={stepId}
            completedSteps={completedSteps}
            variant="compact"
          />
        </div>

        {/* Step content */}
        <div className="onboarding__content">
          {renderStep()}
        </div>

        {/* Footer */}
        <div className="onboarding__footer">
          <div>
            {isFirstStep ? (
              <button onClick={handleSkip} className="onboarding__skip">
                Skip for now
              </button>
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
      </div>
    </div>
  )
}

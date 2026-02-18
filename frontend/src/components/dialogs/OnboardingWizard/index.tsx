import { Rocket } from 'lucide-react'
import { useOnboardingStore, ONBOARDING_STEPS } from '../../../stores/onboarding'
import { useProvidersStore } from '../../../stores/providers'
import { useModelsStore } from '../../../stores/models'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
  DialogStepper,
  type Step,
} from '../../common/Dialog'
import { WelcomeStep } from './steps/WelcomeStep'
import { ApiKeyStep } from './steps/ApiKeyStep'
import { ModelStep } from './steps/ModelStep'
import { DatabaseStep } from './steps/DatabaseStep'
import { SmtpStep } from './steps/SmtpStep'
import { PreferencesStep } from './steps/PreferencesStep'
import { CompleteStep } from './steps/CompleteStep'

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

export function OnboardingWizard() {
  const {
    isOpen,
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
      // smtp is always optional
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

  // Empty close handler — wizard must be completed or skipped
  const handleClose = () => {}

  return (
    <Dialog
      open={isOpen}
      onClose={handleClose}
      size="xl"
      closeOnBackdrop={false}
      closeOnEscape={false}
    >
      <DialogHeader
        title="Setup Wizard"
        subtitle={getStepSubtitle(stepId)}
        icon={<Rocket className="h-5 w-5 text-accent-500" />}
        onClose={handleClose}
      >
        <DialogStepper
          steps={WIZARD_STEPS}
          currentStep={stepId}
          completedSteps={completedSteps}
          variant="compact"
          className="mr-4"
        />
      </DialogHeader>

      <DialogContent scrollable maxHeight="max-h-[65vh]">
        {renderStep()}
      </DialogContent>

      <DialogFooter
        leftContent={
          isFirstStep ? (
            <button
              onClick={skipOnboarding}
              className="text-sm text-zinc-500 transition-colors hover:text-zinc-300"
            >
              Skip for now
            </button>
          ) : (
            <DialogButton variant="ghost" onClick={prevStep}>
              Back
            </DialogButton>
          )
        }
      >
        {isLastStep ? (
          <DialogButton variant="primary" onClick={completeOnboarding}>
            Get Started
          </DialogButton>
        ) : (
          <DialogButton
            variant="primary"
            onClick={nextStep}
            disabled={!canProceed()}
          >
            Continue
          </DialogButton>
        )}
      </DialogFooter>
    </Dialog>
  )
}

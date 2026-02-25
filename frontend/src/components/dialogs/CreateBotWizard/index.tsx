import { Sparkles } from 'lucide-react'
import { useCreationStore } from '../../../stores/creation'
import { useBotStore } from '../../../stores/bots'
import { useUIStore } from '../../../stores/ui'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
  DialogStepper,
  type Step,
} from '../../common/Dialog'
import { MethodSelectStep } from './steps/MethodSelectStep'
import { TemplateSelectStep } from './steps/TemplateSelectStep'
import { PurposeStep } from './steps/PurposeStep'
import { NamePickerStep } from './steps/NamePickerStep'
import { DetailsStep } from './steps/DetailsStep'
import { PersonalityStep } from './steps/PersonalityStep'
import { PromptReviewStep } from './steps/PromptReviewStep'
import { SetupStep } from './steps/SetupStep'
import { PreviewStep } from './steps/PreviewStep'
import { AppearanceStep } from './steps/AppearanceStep'
import { ConfirmStep } from './steps/ConfirmStep'
import { ImportStep } from './steps/ImportStep'
import { updateInstructions } from '../../../api/knowledge'
import { createTodo, createSchedule } from '../../../api/client'
import type { Bot as BotType } from '../../../types'

// Step definitions for the stepper
const WIZARD_STEPS: Record<string, Step[]> = {
  'ai-assisted': [
    { id: 'method-select', label: 'Start' },
    { id: 'purpose', label: 'Purpose' },
    { id: 'name-picker', label: 'Name' },
    { id: 'details', label: 'Details' },
    { id: 'personality', label: 'Style' },
    { id: 'prompt-review', label: 'Review' },
    { id: 'setup', label: 'Setup' },
    { id: 'preview', label: 'Test' },
    { id: 'appearance', label: 'Look' },
    { id: 'confirm', label: 'Create' },
  ],
  template: [
    { id: 'method-select', label: 'Method' },
    { id: 'template-select', label: 'Template' },
    { id: 'appearance', label: 'Design' },
    { id: 'confirm', label: 'Create' },
  ],
  blank: [
    { id: 'method-select', label: 'Method' },
    { id: 'appearance', label: 'Design' },
    { id: 'confirm', label: 'Create' },
  ],
  import: [
    { id: 'method-select', label: 'Method' },
    { id: 'import', label: 'Import' },
    { id: 'appearance', label: 'Design' },
    { id: 'confirm', label: 'Create' },
  ],
}

function getStepSubtitle(step: string): string {
  const subtitles: Record<string, string> = {
    'method-select': 'Choose how to create your bot',
    'template-select': 'Pick a template to start with',
    purpose: "What should your bot do?",
    'name-picker': 'Give your bot a meaningful name',
    details: 'Help us understand you better',
    personality: 'How should your bot communicate?',
    'prompt-review': 'Review your bot\'s personality',
    setup: 'Review what your bot knows about you',
    preview: 'Chat with your bot before creating',
    appearance: 'Customize the look',
    confirm: 'Ready to create your bot',
    import: 'Import a bot configuration',
  }
  return subtitles[step] || ''
}

export function CreateBotWizard() {
  const { setCreateBotOpen } = useUIStore()
  const { addBot, setActiveBot } = useBotStore()
  const {
    isOpen,
    currentStep,
    completedSteps,
    form,
    isGenerating,
    close,
    reset,
    nextStep,
    prevStep,
  } = useCreationStore()

  const handleClose = () => {
    close()
    setCreateBotOpen(false)
    // Reset after animation
    setTimeout(reset, 200)
  }

  const handleCreate = async () => {
    const botId = crypto.randomUUID()
    const newBot: BotType = {
      id: botId,
      name: form.name || 'New Bot',
      description: form.description || 'A new AI assistant',
      icon: form.icon,
      color: form.color,
      model: form.model,
      models: form.utilityModel
        ? { default: form.model, utility: form.utilityModel }
        : undefined,
      systemPrompt: form.systemPrompt,
      tools: form.tools,
      personality: form.method === 'ai-assisted'
        ? {
            purposeCategory: form.purposeCategory,
            purposeDescription: form.purposeDescription,
            communicationStyle: form.communicationStyle,
            useEmojis: form.useEmojis,
          }
        : undefined,
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
    }
    addBot(newBot)
    setActiveBot(newBot.id)

    // Save user context as Custom Instructions + create todos/schedules (fire-and-forget)
    if (form.method === 'ai-assisted') {
      // Save custom instructions
      if (form.userContext.trim()) {
        updateInstructions(botId, form.userContext).catch((err) =>
          console.warn('Failed to save custom instructions:', err)
        )
      }

      // Create enabled todos
      for (const todo of form.suggestedTodos) {
        if (todo.enabled) {
          createTodo(botId, { title: todo.title, notes: todo.notes || undefined }).catch(
            (err) => console.warn('Failed to create todo:', err)
          )
        }
      }

      // Create enabled schedules
      for (const schedule of form.suggestedSchedules) {
        if (schedule.enabled) {
          createSchedule(botId, {
            name: schedule.name,
            description: schedule.description || undefined,
          }).catch((err) => console.warn('Failed to create schedule:', err))
        }
      }
    }

    handleClose()
  }

  // Determine if we can proceed to next step
  const canProceed = (): boolean => {
    switch (currentStep) {
      case 'method-select':
        return form.method !== null
      case 'purpose':
        return form.purposeCategory !== '' && form.purposeDescription.trim() !== ''
      case 'name-picker':
        return form.name.trim() !== ''
      case 'details':
        return true // Optional to answer
      case 'personality':
        return form.communicationStyle !== ''
      case 'prompt-review':
        return form.systemPrompt.trim() !== ''
      case 'preview':
        return true
      case 'appearance':
        return form.name.trim() !== ''
      case 'confirm':
        return true
      default:
        return true
    }
  }

  // Get the steps for the current method
  const steps = form.method ? WIZARD_STEPS[form.method] : WIZARD_STEPS['ai-assisted']

  // Render the current step content
  const renderStep = () => {
    switch (currentStep) {
      case 'method-select':
        return <MethodSelectStep />
      case 'template-select':
        return <TemplateSelectStep />
      case 'purpose':
        return <PurposeStep />
      case 'name-picker':
        return <NamePickerStep />
      case 'details':
        return <DetailsStep />
      case 'personality':
        return <PersonalityStep />
      case 'prompt-review':
        return <PromptReviewStep />
      case 'setup':
        return <SetupStep />
      case 'preview':
        return <PreviewStep />
      case 'appearance':
        return <AppearanceStep />
      case 'confirm':
        return <ConfirmStep />
      case 'import':
        return <ImportStep />
      default:
        return <MethodSelectStep />
    }
  }

  const showBackButton = currentStep !== 'method-select'
  const isLastStep = currentStep === 'confirm'

  return (
    <Dialog open={isOpen} onClose={handleClose} size="xl">
      <DialogHeader
        title="Create New Bot"
        subtitle={getStepSubtitle(currentStep)}
        icon={<Sparkles className="h-5 w-5 text-cachi-500" />}
        onClose={handleClose}
      >
        {form.method && (
          <DialogStepper
            steps={steps}
            currentStep={currentStep}
            completedSteps={completedSteps}
            variant="compact"
            className="mr-4"
          />
        )}
      </DialogHeader>

      <DialogContent scrollable maxHeight="max-h-[65vh]">
        {renderStep()}
      </DialogContent>

      <DialogFooter
        leftContent={
          showBackButton ? (
            <DialogButton variant="ghost" onClick={prevStep}>
              Back
            </DialogButton>
          ) : null
        }
      >
        <DialogButton variant="ghost" onClick={handleClose}>
          Cancel
        </DialogButton>
        {isLastStep ? (
          <DialogButton
            variant="primary"
            onClick={handleCreate}
            disabled={!canProceed() || isGenerating}
          >
            Create Bot
          </DialogButton>
        ) : (
          <DialogButton
            variant="primary"
            onClick={nextStep}
            disabled={!canProceed() || isGenerating}
          >
            {isGenerating ? 'Generating...' : 'Continue'}
          </DialogButton>
        )}
      </DialogFooter>
    </Dialog>
  )
}

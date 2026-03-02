import { useEffect, useState } from 'react'
import { Sparkles, AlertTriangle } from 'lucide-react'
import { useCreationStore, resolveFlowKey } from '../../../stores/creation'
import type { FlowKey } from '../../../stores/creation'
import { useBotStore } from '../../../stores/bots'
import { useRoomStore } from '../../../stores/rooms'
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
import { PurposeStep } from './steps/PurposeStep'
import { ClassificationStep } from './steps/ClassificationStep'
import { NamePickerStep } from './steps/NamePickerStep'
import { DetailsStep } from './steps/DetailsStep'
import { PersonalityStep } from './steps/PersonalityStep'
import { PromptReviewStep } from './steps/PromptReviewStep'
import { SetupStep } from './steps/SetupStep'
import { PreviewStep } from './steps/PreviewStep'
import { AppearanceStep } from './steps/AppearanceStep'
import { ConfirmStep } from './steps/ConfirmStep'
import { ImportStep } from './steps/ImportStep'
import { ProjectDetailsStep } from './steps/ProjectDetailsStep'
import { ProjectProposalStep } from './steps/ProjectProposalStep'
import { ProjectConfirmStep } from './steps/ProjectConfirmStep'
import { updateInstructions } from '../../../api/knowledge'
import { createTodo, createSchedule, createProject } from '../../../api/client'
import type { Bot as BotType } from '../../../types'

// Step label definitions for each flow
const WIZARD_STEPS: Record<FlowKey, Step[]> = {
  'ai-assisted-single': [
    { id: 'method-select', label: 'Start' },
    { id: 'purpose', label: 'Purpose' },
    { id: 'classification', label: 'Type' },
    { id: 'name-picker', label: 'Name' },
    { id: 'details', label: 'Details' },
    { id: 'personality', label: 'Style' },
    { id: 'prompt-review', label: 'Review' },
    { id: 'appearance', label: 'Look' },
    { id: 'confirm', label: 'Create' },
  ],
  'ai-assisted-project': [
    { id: 'method-select', label: 'Start' },
    { id: 'purpose', label: 'Purpose' },
    { id: 'classification', label: 'Type' },
    { id: 'project-details', label: 'Details' },
    { id: 'project-proposal', label: 'Team' },
    { id: 'project-confirm', label: 'Create' },
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
    purpose: "What should your bot do?",
    classification: 'What kind of setup do you need?',
    'name-picker': 'Give your bot a meaningful name',
    details: 'Help us understand your needs',
    personality: 'How should your bot communicate?',
    'prompt-review': 'Review your bot\'s personality',
    setup: 'Review what your bot knows about you',
    preview: 'Chat with your bot before creating',
    appearance: 'Customize the look',
    confirm: 'Ready to create your bot',
    import: 'Import a bot configuration',
    'project-details': 'Tell us about your project',
    'project-proposal': 'Review your team',
    'project-confirm': 'Ready to create your project',
  }
  return subtitles[step] || ''
}

export function CreateBotWizard() {
  const { setCreateBotOpen } = useUIStore()
  const { addBot, setActiveBot } = useBotStore()
  const { setActiveRoom } = useRoomStore()
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

  const [showConfirmClose, setShowConfirmClose] = useState(false)
  const [isCreatingProject, setIsCreatingProject] = useState(false)

  // Steps where the user hasn't invested real effort yet — safe to close without confirmation
  const safeToDismiss = currentStep === 'method-select'

  const handleClose = () => {
    setShowConfirmClose(false)
    close()
    setCreateBotOpen(false)
    // Reset after animation
    setTimeout(reset, 200)
  }

  const requestClose = () => {
    if (safeToDismiss) {
      handleClose()
    } else {
      setShowConfirmClose(true)
    }
  }

  // When not safe to dismiss, Escape toggles the confirmation overlay
  useEffect(() => {
    if (!isOpen || safeToDismiss) return

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (showConfirmClose) {
          setShowConfirmClose(false)
        } else {
          setShowConfirmClose(true)
        }
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, safeToDismiss, showConfirmClose])

  // Single bot creation
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
      if (form.userContext.trim()) {
        updateInstructions(botId, form.userContext).catch((err) =>
          console.warn('Failed to save custom instructions:', err)
        )
      }

      for (const todo of form.suggestedTodos) {
        if (todo.enabled) {
          createTodo(botId, { title: todo.title, notes: todo.notes || undefined }).catch(
            (err) => console.warn('Failed to create todo:', err)
          )
        }
      }

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

  // Project creation — uses batch endpoint for atomic bot + room creation
  const handleCreateProject = async () => {
    const proposal = form.projectProposal
    if (!proposal) return

    setIsCreatingProject(true)
    try {
      // Call batch endpoint to create bots + rooms server-side
      const result = await createProject({
        bots: proposal.bots.map((b) => ({
          temp_id: b.tempId,
          name: b.name,
          description: b.description,
          icon: b.icon,
          color: b.color,
          system_prompt: b.systemPrompt,
          model: b.model,
          tone: b.tone,
          expertise_level: b.expertiseLevel,
          response_length: b.responseLength,
          personality_traits: b.personalityTraits,
        })),
        rooms: proposal.rooms.map((r) => ({
          name: r.name,
          description: r.description,
          response_mode: r.responseMode,
          bot_temp_ids: r.botTempIds,
          settings: r.settings,
        })),
      })

      // Add bots to local store using real IDs from the response
      const tempToRealId = new Map(result.bots.map((b) => [b.temp_id, b.bot_id]))

      for (const proposalBot of proposal.bots) {
        const realId = tempToRealId.get(proposalBot.tempId)
        if (!realId) continue

        const newBot: BotType = {
          id: realId,
          name: proposalBot.name,
          description: proposalBot.description,
          icon: proposalBot.icon,
          color: proposalBot.color,
          model: proposalBot.model,
          systemPrompt: proposalBot.systemPrompt,
          tools: ['file_read', 'file_write', 'file_list', 'file_edit', 'file_info', 'python_execute', 'task_complete'],
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        }
        addBot(newBot)
      }

      // Navigate to the first room created, or the first bot
      if (result.rooms.length > 0) {
        setActiveRoom(result.rooms[0].room_id)
      } else if (result.bots.length > 0) {
        setActiveBot(result.bots[0].bot_id)
      }

      handleClose()
    } catch (err) {
      console.error('Project creation failed:', err)
    } finally {
      setIsCreatingProject(false)
    }
  }

  // Determine if we can proceed to next step
  const canProceed = (): boolean => {
    switch (currentStep) {
      case 'method-select':
        return form.method !== null
      case 'purpose':
        return form.purposeDescription.trim() !== ''
      case 'classification':
        return form.creationPath !== null
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
      case 'project-details':
        return true // Optional to answer
      case 'project-proposal': {
        if (!form.projectProposal) return false
        const p = form.projectProposal
        if (p.bots.length < 2) return false
        if (p.rooms.length < 1) return false
        // Every room needs at least 2 bots
        return p.rooms.every((r) => r.botTempIds.length >= 2)
      }
      case 'project-confirm':
        return true
      default:
        return true
    }
  }

  // Get the flow key and steps for the stepper
  const flowKey = resolveFlowKey(form.method, form.creationPath)
  const steps = flowKey ? WIZARD_STEPS[flowKey] : WIZARD_STEPS['ai-assisted-single']

  // Render the current step content
  const renderStep = () => {
    switch (currentStep) {
      case 'method-select':
        return <MethodSelectStep />
      case 'purpose':
        return <PurposeStep />
      case 'classification':
        return <ClassificationStep />
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
      case 'project-details':
        return <ProjectDetailsStep />
      case 'project-proposal':
        return <ProjectProposalStep />
      case 'project-confirm':
        return <ProjectConfirmStep />
      default:
        return <MethodSelectStep />
    }
  }

  const showBackButton = currentStep !== 'method-select'
  const isLastStep = currentStep === 'confirm' || currentStep === 'project-confirm'
  const isProjectPath = form.creationPath === 'project'

  return (
    <Dialog
      open={isOpen}
      onClose={requestClose}
      closeOnBackdrop={safeToDismiss}
      closeOnEscape={safeToDismiss}
      size="xl"
      className="relative overflow-hidden"
    >
      <DialogHeader
        title={isProjectPath && currentStep !== 'method-select' && currentStep !== 'purpose' && currentStep !== 'classification'
          ? 'Create Project'
          : 'Create New Bot'}
        subtitle={getStepSubtitle(currentStep)}
        icon={<Sparkles className="h-5 w-5 text-cachi-500" />}
        onClose={requestClose}
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
        <DialogButton variant="ghost" onClick={requestClose}>
          Cancel
        </DialogButton>
        {isLastStep ? (
          currentStep === 'project-confirm' ? (
            <DialogButton
              variant="primary"
              onClick={handleCreateProject}
              disabled={!canProceed() || isCreatingProject}
            >
              {isCreatingProject ? 'Creating...' : 'Create Project'}
            </DialogButton>
          ) : (
            <DialogButton
              variant="primary"
              onClick={handleCreate}
              disabled={!canProceed() || isGenerating}
            >
              Create Bot
            </DialogButton>
          )
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

      {/* Confirm cancel overlay */}
      {showConfirmClose && (
        <div className="absolute inset-0 z-50 flex items-center justify-center rounded-2xl bg-black/60 backdrop-blur-sm">
          <div className="mx-6 w-full max-w-sm space-y-4 rounded-xl border border-[var(--color-border-primary)] bg-[var(--color-bg-dialog)] p-6 shadow-2xl">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-full bg-amber-500/10">
                <AlertTriangle className="h-5 w-5 text-amber-400" />
              </div>
              <div>
                <h3 className="text-sm font-semibold text-[var(--color-text-primary)]">
                  {isProjectPath ? 'Cancel project creation?' : 'Cancel bot creation?'}
                </h3>
                <p className="text-xs text-[var(--color-text-secondary)]">All your progress will be lost.</p>
              </div>
            </div>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfirmClose(false)}
                className="rounded-lg px-4 py-2 text-sm font-medium text-[var(--color-text-secondary)] transition-colors hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
              >
                Keep editing
              </button>
              <button
                onClick={handleClose}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-red-500"
              >
                Discard & close
              </button>
            </div>
          </div>
        </div>
      )}
    </Dialog>
  )
}

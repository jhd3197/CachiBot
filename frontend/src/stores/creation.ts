import { create } from 'zustand'
import type { BotIcon, RoomBotRole, RoomSettings } from '../types'

// Wizard step types
export type WizardMethod = 'ai-assisted' | 'blank' | 'import'

export type CreationPath = 'single' | 'project' | null

export type WizardStep =
  | 'method-select'
  | 'purpose'
  | 'classification'
  | 'name-picker'
  | 'details'
  | 'personality'
  | 'prompt-review'
  | 'setup'
  | 'preview'
  | 'appearance'
  | 'confirm'
  | 'import'
  | 'project-details'
  | 'project-proposal'
  | 'project-confirm'

// Structured personality types for project bots
export type BotTone = 'professional' | 'friendly' | 'casual' | 'concise' | 'playful' | 'witty'
export type BotExpertiseLevel = 'beginner' | 'intermediate' | 'expert' | 'authority'
export type BotResponseLength = 'brief' | 'moderate' | 'detailed' | 'comprehensive'
export type BotPersonalityTrait =
  | 'patient' | 'assertive' | 'creative' | 'analytical' | 'empathetic'
  | 'humorous' | 'encouraging' | 'direct' | 'methodical' | 'innovative'

export const TONE_OPTIONS: { value: BotTone; label: string }[] = [
  { value: 'professional', label: 'Professional' },
  { value: 'friendly', label: 'Friendly' },
  { value: 'casual', label: 'Casual' },
  { value: 'concise', label: 'Concise' },
  { value: 'playful', label: 'Playful' },
  { value: 'witty', label: 'Witty' },
]

export const EXPERTISE_LEVEL_OPTIONS: { value: BotExpertiseLevel; label: string }[] = [
  { value: 'beginner', label: 'Beginner' },
  { value: 'intermediate', label: 'Intermediate' },
  { value: 'expert', label: 'Expert' },
  { value: 'authority', label: 'Authority' },
]

export const RESPONSE_LENGTH_OPTIONS: { value: BotResponseLength; label: string }[] = [
  { value: 'brief', label: 'Brief' },
  { value: 'moderate', label: 'Moderate' },
  { value: 'detailed', label: 'Detailed' },
  { value: 'comprehensive', label: 'Comprehensive' },
]

export const PERSONALITY_TRAIT_OPTIONS: { value: BotPersonalityTrait; label: string }[] = [
  { value: 'patient', label: 'Patient' },
  { value: 'assertive', label: 'Assertive' },
  { value: 'creative', label: 'Creative' },
  { value: 'analytical', label: 'Analytical' },
  { value: 'empathetic', label: 'Empathetic' },
  { value: 'humorous', label: 'Humorous' },
  { value: 'encouraging', label: 'Encouraging' },
  { value: 'direct', label: 'Direct' },
  { value: 'methodical', label: 'Methodical' },
  { value: 'innovative', label: 'Innovative' },
]

// Project proposal types
export interface ProposalBot {
  tempId: string
  name: string
  description: string
  role: RoomBotRole
  icon: BotIcon
  color: string
  systemPrompt: string
  model: string
  tone: BotTone
  expertiseLevel: BotExpertiseLevel
  responseLength: BotResponseLength
  personalityTraits: BotPersonalityTrait[]
}

export interface ProposalRoom {
  tempId: string
  name: string
  description: string
  responseMode: RoomSettings['response_mode']
  botTempIds: string[]
  settings: Partial<RoomSettings>
}

export interface ProjectProposal {
  projectName: string
  projectDescription: string
  bots: ProposalBot[]
  rooms: ProposalRoom[]
}

export interface AIClassification {
  classification: 'single' | 'project'
  reason: string
  confidence: number
}

// Purpose categories for AI-assisted creation
export const PURPOSE_CATEGORIES = [
  // Lifestyle
  { id: 'fitness', label: 'Fitness & Health', description: 'Workouts, nutrition, gym routines, wellness' },
  { id: 'cooking', label: 'Cooking & Recipes', description: 'Meal planning, recipes, dietary tracking' },
  { id: 'finance', label: 'Finance & Budget', description: 'Budgeting, savings, expense tracking' },
  { id: 'travel', label: 'Travel & Planning', description: 'Trip planning, itineraries, recommendations' },
  // Work & Learning
  { id: 'coding', label: 'Coding & Dev', description: 'Programming help, debugging, code review' },
  { id: 'writing', label: 'Writing & Content', description: 'Blog posts, copywriting, editing' },
  { id: 'marketing', label: 'Marketing', description: 'Campaigns, SEO, social media, analytics' },
  { id: 'learning', label: 'Learning & Study', description: 'Tutoring, flashcards, explanations' },
  { id: 'productivity', label: 'Productivity', description: 'Task management, scheduling, goals' },
  // Creative & Personal
  { id: 'creative', label: 'Creative Projects', description: 'Art, music, design, brainstorming' },
  { id: 'gaming', label: 'Gaming & Hobbies', description: 'Game guides, tips, hobby tracking' },
  { id: 'social', label: 'Social & Dating', description: 'Conversation tips, profile help, advice' },
]

export const COMMUNICATION_STYLES = [
  { id: 'professional', label: 'Professional', description: 'Formal, precise, business-appropriate' },
  { id: 'friendly', label: 'Friendly', description: 'Warm, approachable, conversational' },
  { id: 'casual', label: 'Casual', description: 'Relaxed, informal, easy-going' },
  { id: 'concise', label: 'Concise', description: 'Brief, to-the-point, efficient' },
  { id: 'detailed', label: 'Detailed', description: 'Thorough, comprehensive, explanatory' },
  { id: 'playful', label: 'Playful', description: 'Fun, witty, entertaining' },
]

export type EmojiPreference = 'yes' | 'no' | 'sometimes'

// Name suggestion with meaning
export interface NameSuggestion {
  name: string
  meaning: string
}

// Follow-up question for details step
export interface FollowUpQuestion {
  id: string
  question: string
  placeholder: string
  answer: string
}

// Suggested items from creation analysis
export interface SuggestedTodoItem {
  title: string
  notes: string
  enabled: boolean
}

export interface SuggestedScheduleItem {
  name: string
  description: string
  frequency: string
  enabled: boolean
}

// Form data for bot creation
export interface BotFormData {
  // Method selection
  method: WizardMethod | null

  // Creation path (single bot vs project)
  creationPath: CreationPath
  aiClassification: AIClassification | null

  // Purpose (AI-assisted)
  purposeCategory: string
  purposeDescription: string

  // Name picker
  nameSuggestions: NameSuggestion[]
  selectedNameMeaning: string

  // Details - follow-up questions
  followUpQuestions: FollowUpQuestion[]

  // Project flow - follow-up questions
  projectFollowUpQuestions: FollowUpQuestion[]

  // Project proposal
  projectProposal: ProjectProposal | null

  // Personality (AI-assisted)
  communicationStyle: string
  useEmojis: EmojiPreference

  // Generated content
  generatedPrompt: string
  suggestedName: string
  suggestedDescription: string

  // Post-analysis setup
  userContext: string
  suggestedTodos: SuggestedTodoItem[]
  suggestedSchedules: SuggestedScheduleItem[]

  // Final bot config
  name: string
  description: string
  icon: BotIcon
  color: string
  model: string
  utilityModel: string
  systemPrompt: string
  tools: string[]
}

// Default form state
const defaultFormData: BotFormData = {
  method: null,
  creationPath: null,
  aiClassification: null,
  purposeCategory: '',
  purposeDescription: '',
  nameSuggestions: [],
  selectedNameMeaning: '',
  followUpQuestions: [],
  projectFollowUpQuestions: [],
  projectProposal: null,
  communicationStyle: 'friendly',
  useEmojis: 'sometimes',
  generatedPrompt: '',
  suggestedName: '',
  suggestedDescription: '',
  userContext: '',
  suggestedTodos: [],
  suggestedSchedules: [],
  name: '',
  description: '',
  icon: 'bot',
  color: '#3b82f6',
  model: '',
  utilityModel: '',
  systemPrompt: '',
  tools: ['file_read', 'file_write', 'file_list', 'file_edit', 'file_info', 'python_execute', 'task_complete'],
}

// Store state
interface CreationState {
  // Wizard state
  isOpen: boolean
  currentStep: WizardStep
  completedSteps: WizardStep[]

  // Form data
  form: BotFormData

  // AI generation state
  isGenerating: boolean
  generationError: string | null

  // Names already shown (to avoid duplicates on refresh)
  excludedNames: string[]

  // Preview chat state
  previewMessages: Array<{ role: 'user' | 'assistant'; content: string }>
  isPreviewLoading: boolean

  // Actions
  open: () => void
  close: () => void
  reset: () => void

  // Navigation
  setStep: (step: WizardStep) => void
  nextStep: () => void
  prevStep: () => void
  markStepCompleted: (step: WizardStep) => void
  getStepFlow: () => WizardStep[]

  // Form updates
  setMethod: (method: WizardMethod) => void
  updateForm: (updates: Partial<BotFormData>) => void

  // Creation path
  setCreationPath: (path: CreationPath) => void
  setAIClassification: (classification: AIClassification) => void

  // Project proposal
  setProjectProposal: (proposal: ProjectProposal) => void
  updateProposalBot: (tempId: string, updates: Partial<ProposalBot>) => void
  removeProposalBot: (tempId: string) => void
  addProposalBot: (bot: ProposalBot) => void
  updateProposalRoom: (tempId: string, updates: Partial<ProposalRoom>) => void
  removeProposalRoom: (tempId: string) => void
  addProposalRoom: (room: ProposalRoom) => void

  // AI generation
  setGenerating: (loading: boolean) => void
  setGenerationError: (error: string | null) => void
  setGeneratedContent: (prompt: string, name: string, description: string) => void

  // Name picker
  setNameSuggestions: (names: NameSuggestion[]) => void
  selectName: (name: string, meaning: string) => void
  getExcludedNames: () => string[]

  // Follow-up questions
  setFollowUpQuestions: (questions: FollowUpQuestion[]) => void
  updateFollowUpAnswer: (id: string, answer: string) => void

  // Project follow-up questions
  setProjectFollowUpQuestions: (questions: FollowUpQuestion[]) => void
  updateProjectFollowUpAnswer: (id: string, answer: string) => void

  // Preview
  addPreviewMessage: (role: 'user' | 'assistant', content: string) => void
  clearPreviewMessages: () => void
  setPreviewLoading: (loading: boolean) => void
}

// Step flow definitions — ai-assisted branches based on creationPath
export type FlowKey = 'ai-assisted-single' | 'ai-assisted-project' | 'blank' | 'import'

export const STEP_FLOWS: Record<FlowKey, WizardStep[]> = {
  'ai-assisted-single': [
    'method-select',
    'purpose',
    'classification',
    'name-picker',
    'details',
    'personality',
    'prompt-review',
    'appearance',
    'confirm',
  ],
  'ai-assisted-project': [
    'method-select',
    'purpose',
    'classification',
    'project-details',
    'project-proposal',
    'project-confirm',
  ],
  blank: ['method-select', 'appearance', 'confirm'],
  import: ['method-select', 'import', 'appearance', 'confirm'],
}

export function resolveFlowKey(method: WizardMethod | null, creationPath: CreationPath): FlowKey | null {
  if (!method) return null
  if (method === 'ai-assisted') {
    if (creationPath === 'project') return 'ai-assisted-project'
    return 'ai-assisted-single' // default to single (also covers null before classification)
  }
  return method as FlowKey
}

function getNextStep(method: WizardMethod | null, currentStep: WizardStep, creationPath: CreationPath): WizardStep | null {
  const key = resolveFlowKey(method, creationPath)
  if (!key) return null
  const flow = STEP_FLOWS[key]
  const currentIndex = flow.indexOf(currentStep)
  if (currentIndex === -1 || currentIndex === flow.length - 1) return null
  return flow[currentIndex + 1]
}

function getPrevStep(method: WizardMethod | null, currentStep: WizardStep, creationPath: CreationPath): WizardStep | null {
  const key = resolveFlowKey(method, creationPath)
  if (!key) return null
  const flow = STEP_FLOWS[key]
  const currentIndex = flow.indexOf(currentStep)
  if (currentIndex <= 0) return null
  return flow[currentIndex - 1]
}

export const useCreationStore = create<CreationState>((set, get) => ({
  // Initial state
  isOpen: false,
  currentStep: 'method-select',
  completedSteps: [],
  form: { ...defaultFormData },
  isGenerating: false,
  generationError: null,
  excludedNames: [],
  previewMessages: [],
  isPreviewLoading: false,

  // Actions
  open: () => set({ isOpen: true }),

  close: () => set({ isOpen: false }),

  reset: () =>
    set({
      isOpen: false,
      currentStep: 'method-select',
      completedSteps: [],
      form: { ...defaultFormData },
      isGenerating: false,
      generationError: null,
      excludedNames: [],
      previewMessages: [],
      isPreviewLoading: false,
    }),

  // Navigation
  setStep: (step) => set({ currentStep: step }),

  nextStep: () => {
    const { form, currentStep } = get()
    const next = getNextStep(form.method, currentStep, form.creationPath)
    if (next) {
      set((state) => ({
        currentStep: next,
        completedSteps: state.completedSteps.includes(currentStep)
          ? state.completedSteps
          : [...state.completedSteps, currentStep],
      }))
    }
  },

  prevStep: () => {
    const { form, currentStep } = get()
    const prev = getPrevStep(form.method, currentStep, form.creationPath)
    if (prev) {
      set({ currentStep: prev })
    }
  },

  markStepCompleted: (step) =>
    set((state) => ({
      completedSteps: state.completedSteps.includes(step)
        ? state.completedSteps
        : [...state.completedSteps, step],
    })),

  getStepFlow: () => {
    const { form } = get()
    const key = resolveFlowKey(form.method, form.creationPath)
    if (!key) return STEP_FLOWS['ai-assisted-single']
    return STEP_FLOWS[key]
  },

  // Form updates
  setMethod: (method) =>
    set((state) => ({
      form: { ...state.form, method },
    })),

  updateForm: (updates) =>
    set((state) => ({
      form: { ...state.form, ...updates },
    })),

  // Creation path
  setCreationPath: (creationPath) =>
    set((state) => ({
      form: { ...state.form, creationPath },
    })),

  setAIClassification: (aiClassification) =>
    set((state) => ({
      form: { ...state.form, aiClassification },
    })),

  // Project proposal
  setProjectProposal: (projectProposal) =>
    set((state) => ({
      form: { ...state.form, projectProposal },
    })),

  updateProposalBot: (tempId, updates) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            bots: state.form.projectProposal.bots.map((b) =>
              b.tempId === tempId ? { ...b, ...updates } : b
            ),
          },
        },
      }
    }),

  removeProposalBot: (tempId) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            bots: state.form.projectProposal.bots.filter((b) => b.tempId !== tempId),
            rooms: state.form.projectProposal.rooms.map((r) => ({
              ...r,
              botTempIds: r.botTempIds.filter((id) => id !== tempId),
            })),
          },
        },
      }
    }),

  addProposalBot: (bot) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            bots: [...state.form.projectProposal.bots, bot],
          },
        },
      }
    }),

  updateProposalRoom: (tempId, updates) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            rooms: state.form.projectProposal.rooms.map((r) =>
              r.tempId === tempId ? { ...r, ...updates } : r
            ),
          },
        },
      }
    }),

  removeProposalRoom: (tempId) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            rooms: state.form.projectProposal.rooms.filter((r) => r.tempId !== tempId),
          },
        },
      }
    }),

  addProposalRoom: (room) =>
    set((state) => {
      if (!state.form.projectProposal) return state
      return {
        form: {
          ...state.form,
          projectProposal: {
            ...state.form.projectProposal,
            rooms: [...state.form.projectProposal.rooms, room],
          },
        },
      }
    }),

  // AI generation
  setGenerating: (isGenerating) => set({ isGenerating }),

  setGenerationError: (generationError) => set({ generationError }),

  setGeneratedContent: (prompt, name, description) =>
    set((state) => ({
      form: {
        ...state.form,
        generatedPrompt: prompt,
        suggestedName: name,
        suggestedDescription: description,
        systemPrompt: prompt,
        name: state.form.name || name,
        description: state.form.description || description,
      },
    })),

  // Name picker
  setNameSuggestions: (names) =>
    set((state) => {
      // Add current suggestions to excluded list before replacing
      const currentNames = state.form.nameSuggestions.map((s) => s.name)
      const newExcluded = [...new Set([...state.excludedNames, ...currentNames])]
      return {
        excludedNames: newExcluded,
        form: {
          ...state.form,
          nameSuggestions: names,
        },
      }
    }),

  selectName: (name, meaning) =>
    set((state) => ({
      form: {
        ...state.form,
        name,
        selectedNameMeaning: meaning,
      },
    })),

  getExcludedNames: () => {
    const state = get()
    const currentNames = state.form.nameSuggestions.map((s) => s.name)
    return [...new Set([...state.excludedNames, ...currentNames])]
  },

  // Follow-up questions
  setFollowUpQuestions: (questions) =>
    set((state) => ({
      form: {
        ...state.form,
        followUpQuestions: questions,
      },
    })),

  updateFollowUpAnswer: (id, answer) =>
    set((state) => ({
      form: {
        ...state.form,
        followUpQuestions: state.form.followUpQuestions.map((q) =>
          q.id === id ? { ...q, answer } : q
        ),
      },
    })),

  // Project follow-up questions
  setProjectFollowUpQuestions: (questions) =>
    set((state) => ({
      form: {
        ...state.form,
        projectFollowUpQuestions: questions,
      },
    })),

  updateProjectFollowUpAnswer: (id, answer) =>
    set((state) => ({
      form: {
        ...state.form,
        projectFollowUpQuestions: state.form.projectFollowUpQuestions.map((q) =>
          q.id === id ? { ...q, answer } : q
        ),
      },
    })),

  // Preview
  addPreviewMessage: (role, content) =>
    set((state) => ({
      previewMessages: [...state.previewMessages, { role, content }],
    })),

  clearPreviewMessages: () => set({ previewMessages: [] }),

  setPreviewLoading: (isPreviewLoading) => set({ isPreviewLoading }),
}))

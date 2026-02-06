import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { CreationFlowStep, CreationFlowData } from '../types'
import { useBotStore } from './bots'

// =============================================================================
// CREATION FLOW STORE
// =============================================================================

interface CreationFlowState {
  // State
  step: CreationFlowStep
  data: CreationFlowData
  flowChatId: string | null
  isLoadingNames: boolean
  createdBotId: string | null

  // Actions
  startFlow: (chatId: string) => void
  setName: (name: string) => void
  setNameSuggestions: (names: string[]) => void
  setPurposeCategory: (category: string) => void
  setPurposeDescription: (description: string) => void
  setStyle: (style: string) => void
  setEmoji: (preference: 'yes' | 'no' | 'sometimes') => void
  setDetectedLanguage: (language: string | null) => void
  confirmAndCreate: () => CreationFlowData
  completeFlow: (botId?: string) => void
  cancelFlow: () => void
  setLoadingNames: (loading: boolean) => void
  getFlowData: () => CreationFlowData
}

const initialData: CreationFlowData = {
  name: null,
  nameSuggestions: [],
  purposeCategory: null,
  purposeDescription: null,
  communicationStyle: null,
  useEmojis: null,
  detectedLanguage: null,
}

export const useCreationFlowStore = create<CreationFlowState>()(
  persist(
    (set, get) => ({
      // Initial state
      step: 'idle',
      data: { ...initialData },
      flowChatId: null,
      isLoadingNames: false,
      createdBotId: null,

      // Start the creation flow
      startFlow: (chatId: string) => {
        set({
          step: 'name',
          data: { ...initialData },
          flowChatId: chatId,
          isLoadingNames: false,
        })
      },

      // Set the bot name (validates uniqueness)
      setName: (name: string) => {
        const bots = useBotStore.getState().bots
        const nameLower = name.toLowerCase().trim()
        const nameExists = bots.some(
          (bot) => bot.name.toLowerCase() === nameLower
        )

        if (nameExists) {
          throw new Error(`A bot named "${name}" already exists. Please choose a different name.`)
        }

        set((state) => ({
          step: 'purpose-category',
          data: { ...state.data, name: name.trim() },
        }))
      },

      // Store AI-generated name suggestions
      setNameSuggestions: (names: string[]) => {
        set((state) => ({
          data: { ...state.data, nameSuggestions: names },
        }))
      },

      // Set purpose category
      setPurposeCategory: (category: string) => {
        set((state) => ({
          step: 'purpose-description',
          data: { ...state.data, purposeCategory: category },
        }))
      },

      // Set purpose description
      setPurposeDescription: (description: string) => {
        set((state) => ({
          step: 'style',
          data: { ...state.data, purposeDescription: description },
        }))
      },

      // Set communication style
      setStyle: (style: string) => {
        set((state) => ({
          step: 'emoji',
          data: { ...state.data, communicationStyle: style },
        }))
      },

      // Set emoji preference
      setEmoji: (preference: 'yes' | 'no' | 'sometimes') => {
        set((state) => ({
          step: 'summary',
          data: { ...state.data, useEmojis: preference },
        }))
      },

      // Set detected language (from auto-detection)
      setDetectedLanguage: (language: string | null) => {
        set((state) => ({
          data: { ...state.data, detectedLanguage: language },
        }))
      },

      // Confirm creation and return data (called before completeFlow)
      confirmAndCreate: () => {
        const currentData = get().data
        return currentData
      },

      // Complete the flow and reset state for next /create
      completeFlow: (botId?: string) => {
        set({
          step: 'idle',
          data: { ...initialData },
          flowChatId: null,
          isLoadingNames: false,
          createdBotId: botId || null,
        })
      },

      // Cancel the flow and reset
      cancelFlow: () => {
        set({
          step: 'idle',
          data: { ...initialData },
          flowChatId: null,
          isLoadingNames: false,
          createdBotId: null,
        })
      },

      // Toggle loading state for name generation
      setLoadingNames: (loading: boolean) => {
        set({ isLoadingNames: loading })
      },

      // Get a copy of current flow data
      getFlowData: () => {
        return { ...get().data }
      },
    }),
    {
      name: 'cachibot-creation-flow',
      // Only persist step, data, and flowChatId (not loading states)
      partialize: (state) => ({
        step: state.step,
        data: state.data,
        flowChatId: state.flowChatId,
      }),
    }
  )
)

import { create } from 'zustand'
import type { Config } from '../types'

interface ConfigState {
  config: Config | null

  // Actions
  setConfig: (config: Config) => void
  updateConfig: (updates: Partial<Config['agent'] & Config['display']>) => void
}

export const useConfigStore = create<ConfigState>((set) => ({
  config: null,

  setConfig: (config) => set({ config }),

  updateConfig: (updates) =>
    set((state) => {
      if (!state.config) return state

      return {
        config: {
          ...state.config,
          agent: {
            ...state.config.agent,
            ...(updates.model !== undefined && { model: updates.model }),
            ...(updates.maxIterations !== undefined && { maxIterations: updates.maxIterations }),
            ...(updates.approveActions !== undefined && { approveActions: updates.approveActions }),
            ...(updates.temperature !== undefined && { temperature: updates.temperature }),
          },
          display: {
            ...state.config.display,
            ...(updates.showThinking !== undefined && { showThinking: updates.showThinking }),
            ...(updates.showCost !== undefined && { showCost: updates.showCost }),
          },
        },
      }
    }),
}))

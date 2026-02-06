import { create } from 'zustand'
import { getModels, getDefaultModel, setDefaultModel, type ModelsGrouped, type ModelInfo } from '../api/models'

interface ModelsState {
  groups: ModelsGrouped
  defaultModel: string
  loading: boolean
  error: string | null

  // Derived
  models: ModelInfo[]

  // Actions
  refresh: () => Promise<void>
  updateDefaultModel: (model: string) => Promise<void>
}

export const useModelsStore = create<ModelsState>((set, get) => ({
  groups: {},
  defaultModel: '',
  loading: true,
  error: null,

  get models() {
    return Object.values(get().groups).flat()
  },

  refresh: async () => {
    set({ loading: true, error: null })
    try {
      const [groups, defaultModel] = await Promise.all([
        getModels(),
        getDefaultModel(),
      ])
      set({
        groups,
        defaultModel,
        loading: false,
      })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load models',
        loading: false,
      })
    }
  },

  updateDefaultModel: async (model: string) => {
    try {
      await setDefaultModel(model)
      set({ defaultModel: model })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to update default model',
      })
    }
  },
}))

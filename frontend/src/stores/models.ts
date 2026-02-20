import { create } from 'zustand'
import { getModels, getDefaultModel, setDefaultModel, type ModelsGrouped, type ModelInfo } from '../api/models'

/** Filter a ModelsGrouped object to only models matching a predicate. */
function filterGroups(groups: ModelsGrouped, predicate: (m: ModelInfo) => boolean): ModelsGrouped {
  const result: ModelsGrouped = {}
  for (const [provider, items] of Object.entries(groups)) {
    const filtered = items.filter(predicate)
    if (filtered.length > 0) result[provider] = filtered
  }
  return result
}

interface ModelsState {
  groups: ModelsGrouped
  imageGroups: ModelsGrouped
  audioGroups: ModelsGrouped
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
  imageGroups: {},
  audioGroups: {},
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
        imageGroups: filterGroups(groups, (m) => m.supports_image_generation),
        audioGroups: filterGroups(groups, (m) => m.supports_audio),
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

import { create } from 'zustand'
import {
  getProviders,
  updateProvider,
  deleteProvider,
  type Provider,
} from '../api/providers'

interface ProvidersState {
  providers: Provider[]
  loading: boolean
  error: string | null

  refresh: () => Promise<void>
  update: (name: string, value: string) => Promise<void>
  remove: (name: string) => Promise<void>
}

export const useProvidersStore = create<ProvidersState>((set) => ({
  providers: [],
  loading: false,
  error: null,

  refresh: async () => {
    set({ loading: true, error: null })
    try {
      const providers = await getProviders()
      set({ providers, loading: false })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to load providers',
        loading: false,
      })
    }
  },

  update: async (name: string, value: string) => {
    try {
      await updateProvider(name, value)
      // Refresh to get updated masked values
      const providers = await getProviders()
      set({ providers })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to update provider',
      })
      throw err
    }
  },

  remove: async (name: string) => {
    try {
      await deleteProvider(name)
      const providers = await getProviders()
      set({ providers })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to remove provider',
      })
      throw err
    }
  },
}))

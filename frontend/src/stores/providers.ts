import { create } from 'zustand'
import {
  getProviders,
  updateProvider,
  deleteProvider,
  updateProviderKey,
  deleteProviderKey,
  type Provider,
} from '../api/providers'

interface ProvidersState {
  providers: Provider[]
  loading: boolean
  error: string | null

  refresh: () => Promise<void>
  update: (name: string, value: string) => Promise<void>
  remove: (name: string) => Promise<void>
  updateKey: (name: string, envKey: string, value: string) => Promise<void>
  removeKey: (name: string, envKey: string) => Promise<void>
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

  updateKey: async (name: string, envKey: string, value: string) => {
    try {
      await updateProviderKey(name, envKey, value)
      const providers = await getProviders()
      set({ providers })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to update key',
      })
      throw err
    }
  },

  removeKey: async (name: string, envKey: string) => {
    try {
      await deleteProviderKey(name, envKey)
      const providers = await getProviders()
      set({ providers })
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : 'Failed to remove key',
      })
      throw err
    }
  },
}))

/**
 * Zustand store for external plugin management.
 */

import { create } from 'zustand'
import type { ExternalPluginInfo } from '../types'
import {
  fetchExternalPlugins,
  enableExternalPlugin,
  disableExternalPlugin,
  reloadExternalPlugins,
  installExternalPlugin,
  uninstallExternalPlugin,
} from '../api/external-plugins'

interface PluginsState {
  plugins: ExternalPluginInfo[]
  loading: boolean
  error: string | null

  fetchPlugins: () => Promise<void>
  togglePlugin: (name: string, enable: boolean) => Promise<{ capabilityKey: string; enabled: boolean } | null>
  reloadPlugins: () => Promise<{ loaded: number; total: number; errors: Record<string, string> } | null>
  installPlugin: (file: File) => Promise<boolean>
  uninstallPlugin: (name: string) => Promise<boolean>
}

export const usePluginsStore = create<PluginsState>((set) => ({
  plugins: [],
  loading: false,
  error: null,

  fetchPlugins: async () => {
    set({ loading: true, error: null })
    try {
      const plugins = await fetchExternalPlugins()
      set({ plugins, loading: false })
    } catch (err) {
      set({ error: (err as Error).message, loading: false })
    }
  },

  togglePlugin: async (name: string, enable: boolean) => {
    try {
      const result = enable
        ? await enableExternalPlugin(name)
        : await disableExternalPlugin(name)
      return result
    } catch (err) {
      set({ error: (err as Error).message })
      return null
    }
  },

  reloadPlugins: async () => {
    set({ loading: true, error: null })
    try {
      const result = await reloadExternalPlugins()
      // Re-fetch the full plugin list after reload
      const plugins = await fetchExternalPlugins()
      set({ plugins, loading: false })
      return result
    } catch (err) {
      set({ error: (err as Error).message, loading: false })
      return null
    }
  },

  installPlugin: async (file: File) => {
    set({ error: null })
    try {
      await installExternalPlugin(file)
      // Re-fetch after install
      const plugins = await fetchExternalPlugins()
      set({ plugins })
      return true
    } catch (err) {
      set({ error: (err as Error).message })
      return false
    }
  },

  uninstallPlugin: async (name: string) => {
    set({ error: null })
    try {
      await uninstallExternalPlugin(name)
      // Re-fetch after uninstall
      const plugins = await fetchExternalPlugins()
      set({ plugins })
      return true
    } catch (err) {
      set({ error: (err as Error).message })
      return false
    }
  },
}))

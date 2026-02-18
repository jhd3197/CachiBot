/**
 * Platform Tool Config Store
 *
 * Global tool visibility state — lets admins disable capabilities and
 * skills platform-wide.
 */

import { create } from 'zustand'
import {
  getPlatformToolConfig,
  updatePlatformToolConfig,
} from '../api/platform-tools'
import type { PlatformToolConfig } from '../types'

interface PlatformToolsState {
  config: PlatformToolConfig | null
  loading: boolean
  error: string | null

  fetchConfig: () => Promise<void>
  toggleCapability: (key: string) => Promise<void>
  toggleSkill: (skillId: string) => Promise<void>

  /** Check if a capability is globally disabled. */
  isCapabilityDisabled: (key: string) => boolean
  /** Check if a skill is globally disabled. */
  isSkillDisabled: (skillId: string) => boolean
}

export const usePlatformToolsStore = create<PlatformToolsState>()((set, get) => ({
  config: null,
  loading: false,
  error: null,

  fetchConfig: async () => {
    set({ loading: true, error: null })
    try {
      const config = await getPlatformToolConfig()
      set({ config, loading: false })
    } catch (e) {
      set({ error: e instanceof Error ? e.message : 'Failed to load', loading: false })
    }
  },

  toggleCapability: async (key: string) => {
    const { config } = get()
    if (!config) return

    const current = config.disabledCapabilities
    const updated = current.includes(key)
      ? current.filter((k) => k !== key)
      : [...current, key]

    // Optimistic update
    set({ config: { ...config, disabledCapabilities: updated } })

    try {
      const result = await updatePlatformToolConfig({
        disabled_capabilities: updated,
      })
      set({ config: result })
    } catch (e) {
      // Revert on failure
      set({ config, error: e instanceof Error ? e.message : 'Failed to update' })
    }
  },

  toggleSkill: async (skillId: string) => {
    const { config } = get()
    if (!config) return

    const current = config.disabledSkills
    const updated = current.includes(skillId)
      ? current.filter((id) => id !== skillId)
      : [...current, skillId]

    // Optimistic update
    set({ config: { ...config, disabledSkills: updated } })

    try {
      const result = await updatePlatformToolConfig({
        disabled_skills: updated,
      })
      set({ config: result })
    } catch (e) {
      // Revert on failure
      set({ config, error: e instanceof Error ? e.message : 'Failed to update' })
    }
  },

  isCapabilityDisabled: (key: string) => {
    const { config } = get()
    return config?.disabledCapabilities.includes(key) ?? false
  },

  isSkillDisabled: (skillId: string) => {
    const { config } = get()
    return config?.disabledSkills.includes(skillId) ?? false
  },
}))

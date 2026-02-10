import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  checkForUpdate as apiCheckForUpdate,
  applyUpdate as apiApplyUpdate,
  restartServer as apiRestartServer,
  checkHealth,
} from '../api/client'
import type { UpdateCheckInfo, UpdateApplyResponse } from '../api/client'

const CHECK_INTERVAL = 3600_000 // 1 hour in ms

interface UpdateState {
  // Data
  checkResult: UpdateCheckInfo | null
  updateResult: UpdateApplyResponse | null

  // UI state
  isChecking: boolean
  isUpdating: boolean
  isRestarting: boolean
  showBanner: boolean
  showDialog: boolean

  // Persisted
  lastCheckAt: number
  skippedVersions: string[]
  optIntoBeta: boolean

  // Actions
  checkForUpdate: (force?: boolean) => Promise<void>
  performUpdate: (targetVersion?: string) => Promise<void>
  skipVersion: (version: string) => void
  restartServer: () => Promise<void>
  dismissBanner: () => void
  openDialog: () => void
  closeDialog: () => void
  setOptIntoBeta: (value: boolean) => void
}

export const useUpdateStore = create<UpdateState>()(
  persist(
    (set, get) => ({
      checkResult: null,
      updateResult: null,
      isChecking: false,
      isUpdating: false,
      isRestarting: false,
      showBanner: false,
      showDialog: false,
      lastCheckAt: 0,
      skippedVersions: [],
      optIntoBeta: false,

      checkForUpdate: async (force = false) => {
        const state = get()
        // Client-side rate limit
        if (!force && Date.now() - state.lastCheckAt < CHECK_INTERVAL) {
          return
        }
        if (state.isChecking) return

        set({ isChecking: true })
        try {
          const result = await apiCheckForUpdate(force)
          const latestVersion = result.latest_stable || result.latest_prerelease
          const isSkipped = latestVersion ? state.skippedVersions.includes(latestVersion) : false
          set({
            checkResult: result,
            lastCheckAt: Date.now(),
            showBanner: (result.update_available || result.prerelease_available) && !isSkipped,
          })
        } catch (err) {
          console.warn('Update check failed:', err)
        } finally {
          set({ isChecking: false })
        }
      },

      performUpdate: async (targetVersion?: string) => {
        const state = get()
        if (state.isUpdating) return

        set({ isUpdating: true })
        try {
          const result = await apiApplyUpdate({
            target_version: targetVersion,
            include_prerelease: state.optIntoBeta,
          })
          set({ updateResult: result })
        } catch (err) {
          set({
            updateResult: {
              success: false,
              old_version: state.checkResult?.current_version || 'unknown',
              new_version: state.checkResult?.current_version || 'unknown',
              message: err instanceof Error ? err.message : 'Update failed',
              restart_required: false,
              pip_output: '',
            },
          })
        } finally {
          set({ isUpdating: false })
        }
      },

      skipVersion: (version: string) => {
        set((state) => ({
          skippedVersions: [...state.skippedVersions, version],
          showBanner: false,
          showDialog: false,
        }))
      },

      restartServer: async () => {
        set({ isRestarting: true })
        try {
          await apiRestartServer()
        } catch {
          // Expected — the server is shutting down, so the request may fail
        }

        // Poll /api/health until the new server responds
        const maxAttempts = 30
        for (let i = 0; i < maxAttempts; i++) {
          await new Promise((r) => setTimeout(r, 2000))
          try {
            await checkHealth()
            // New server is up — reload page
            window.location.reload()
            return
          } catch {
            // Not ready yet
          }
        }

        // Give up after ~60 seconds
        set({ isRestarting: false })
      },

      dismissBanner: () => set({ showBanner: false }),
      openDialog: () => set({ showDialog: true }),
      closeDialog: () => set({ showDialog: false, updateResult: null }),
      setOptIntoBeta: (value: boolean) => set({ optIntoBeta: value }),
    }),
    {
      name: 'cachibot-update',
      partialize: (state) => ({
        skippedVersions: state.skippedVersions,
        optIntoBeta: state.optIntoBeta,
        lastCheckAt: state.lastCheckAt,
      }),
    }
  )
)

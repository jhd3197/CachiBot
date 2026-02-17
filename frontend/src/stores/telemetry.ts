import { create } from 'zustand'
import type { TelemetryStatus } from '../api/telemetry'

interface TelemetryState {
  status: TelemetryStatus | null
  loading: boolean

  setStatus: (status: TelemetryStatus) => void
  setLoading: (loading: boolean) => void
  refresh: () => Promise<void>
}

export const useTelemetryStore = create<TelemetryState>((set) => ({
  status: null,
  loading: false,

  setStatus: (status) => set({ status }),
  setLoading: (loading) => set({ loading }),

  refresh: async () => {
    set({ loading: true })
    try {
      const { getTelemetryStatus } = await import('../api/telemetry')
      const status = await getTelemetryStatus()
      set({ status, loading: false })
    } catch {
      set({ loading: false })
    }
  },
}))

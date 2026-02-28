import { create } from 'zustand'
import { getTelemetryStatus, type TelemetryStatus } from '../api/telemetry'

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
      const status = await getTelemetryStatus()
      set({ status, loading: false })
    } catch {
      set({ loading: false })
    }
  },
}))

/**
 * Computer store (C1).
 *
 * Holds the Docker probe summary (`status`) and, per bot, the live computer
 * state. The probe decides whether any computer UI may appear at all; the
 * per-bot records are fed by GET /api/bots/{id}/computer and kept live by
 * `computer_update` WebSocket events. Deliberately NOT persisted — the
 * server owns the state. No views consume this yet (they land in C4, hidden
 * while `status.available` is false).
 */

import { create } from 'zustand'
import {
  getBotComputer,
  getComputerStatus,
  sleepComputer,
  stopComputer,
  wakeComputer,
} from '../api/computer'
import type { BotComputer, ComputerUpdatePayload, DockerProbeSummary } from '../types'

interface ComputerStoreState {
  /** Docker probe summary; null until the first fetch. */
  status: DockerProbeSummary | null
  /** Whether the probe was fetched at least once (even if it failed). */
  statusLoaded: boolean
  /** botId -> latest computer state (REST response or WS event). */
  byBot: Record<string, BotComputer>
  /** botId -> a fetch is in flight (dedupes concurrent ensure calls). */
  loadingFor: Record<string, boolean>

  /** Fetch the Docker probe summary (call on app mount). */
  fetchStatus: () => Promise<void>
  /** Load one bot's computer state once (call where a C4 view mounts). */
  ensureForBot: (botId: string) => Promise<void>
  /** Insert or replace one record (from the API or a `computer_update`). */
  applyUpdate: (payload: ComputerUpdatePayload) => void

  wake: (botId: string) => Promise<BotComputer>
  sleep: (botId: string) => Promise<BotComputer>
  stop: (botId: string) => Promise<BotComputer>
}

export const useComputerStore = create<ComputerStoreState>()((set, get) => ({
  status: null,
  statusLoaded: false,
  byBot: {},
  loadingFor: {},

  fetchStatus: async () => {
    try {
      const status = await getComputerStatus()
      set({ status, statusLoaded: true })
    } catch {
      // Treat an unreachable probe as "no computer": views stay hidden.
      set({
        status: { available: false, reason: null, docker_version: null, server_os: null, arch: null },
        statusLoaded: true,
      })
    }
  },

  ensureForBot: async (botId) => {
    if (get().byBot[botId] || get().loadingFor[botId]) return
    set((state) => ({ loadingFor: { ...state.loadingFor, [botId]: true } }))
    try {
      const computer = await getBotComputer(botId)
      set((state) => ({
        byBot: { ...state.byBot, [botId]: computer },
        loadingFor: { ...state.loadingFor, [botId]: false },
      }))
    } catch {
      set((state) => ({ loadingFor: { ...state.loadingFor, [botId]: false } }))
    }
  },

  applyUpdate: (payload) =>
    set((state) => ({
      byBot: { ...state.byBot, [payload.botId]: payload },
    })),

  wake: async (botId) => {
    const computer = await wakeComputer(botId)
    get().applyUpdate({ botId, ...computer })
    return computer
  },

  sleep: async (botId) => {
    const computer = await sleepComputer(botId)
    get().applyUpdate({ botId, ...computer })
    return computer
  },

  stop: async (botId) => {
    const computer = await stopComputer(botId)
    get().applyUpdate({ botId, ...computer })
    return computer
  },
}))

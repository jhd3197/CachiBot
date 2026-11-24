/**
 * Computer store (C1 + C2).
 *
 * Holds the Docker probe summary (`status`) and, per bot, the live computer
 * state. The probe decides whether any computer UI may appear at all; the
 * per-bot records are fed by GET /api/bots/{id}/computer and kept live by
 * `computer_update` WebSocket events, which carry the C2 fields: activity,
 * windows count, watchers, driver (who is driving), the needs-you reason and
 * the preview revision (refetch the preview only when it changes). The
 * windows list itself (app + title) is fetched on demand into
 * `windowsByBot`. Deliberately NOT persisted — the server owns the state.
 * No views consume this yet (they land in C4, hidden while
 * `status.available` is false).
 */

import { create } from 'zustand'
import {
  getBotComputer,
  getComputerStatus,
  getComputerViews,
  handbackComputer,
  respondComputerNeedsYou,
  sleepComputer,
  stopComputer,
  takeoverComputer,
  wakeComputer,
} from '../api/computer'
import type {
  BotComputer,
  ComputerUpdatePayload,
  ComputerWindow,
  DockerProbeSummary,
} from '../types'

interface ComputerStoreState {
  /** Docker probe summary; null until the first fetch. */
  status: DockerProbeSummary | null
  /** Whether the probe was fetched at least once (even if it failed). */
  statusLoaded: boolean
  /** botId -> latest computer state (REST response or WS event). */
  byBot: Record<string, BotComputer>
  /** botId -> open windows (app + title), from GET .../computer/views. */
  windowsByBot: Record<string, ComputerWindow[]>
  /** botId -> a fetch is in flight (dedupes concurrent ensure calls). */
  loadingFor: Record<string, boolean>

  /** Fetch the Docker probe summary (call on app mount). */
  fetchStatus: () => Promise<void>
  /** Load one bot's computer state once (call where a C4 view mounts). */
  ensureForBot: (botId: string) => Promise<void>
  /** Load one bot's open windows + activity (call where a C4 view mounts). */
  fetchViews: (botId: string) => Promise<void>
  /** Insert or replace one record (from the API or a `computer_update`). */
  applyUpdate: (payload: ComputerUpdatePayload) => void

  wake: (botId: string) => Promise<BotComputer>
  sleep: (botId: string) => Promise<BotComputer>
  stop: (botId: string) => Promise<BotComputer>
  takeover: (botId: string) => Promise<BotComputer>
  handback: (botId: string) => Promise<BotComputer>
  respondNeedsYou: (botId: string, action: 'takeover' | 'skip') => Promise<BotComputer>
}

export const useComputerStore = create<ComputerStoreState>()((set, get) => ({
  status: null,
  statusLoaded: false,
  byBot: {},
  windowsByBot: {},
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

  fetchViews: async (botId) => {
    try {
      const views = await getComputerViews(botId)
      set((state) => ({ windowsByBot: { ...state.windowsByBot, [botId]: views.windows } }))
    } catch {
      // Asleep or unreachable: keep the last real list; never invent one.
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

  takeover: async (botId) => {
    const computer = await takeoverComputer(botId)
    get().applyUpdate({ botId, ...computer })
    return computer
  },

  handback: async (botId) => {
    const computer = await handbackComputer(botId)
    get().applyUpdate({ botId, ...computer })
    return computer
  },

  respondNeedsYou: async (botId, action) => {
    const computer = await respondComputerNeedsYou(botId, action)
    get().applyUpdate({ botId, ...computer })
    return computer
  },
}))

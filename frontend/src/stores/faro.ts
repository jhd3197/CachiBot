/**
 * Faro store.
 *
 * Holds the global bridge detection (`status`) and, per bot, the connection
 * state. The global status decides whether any Faro UI may appear; the
 * per-bot records are fed by GET /api/bots/{id}/faro and kept live by
 * `faro_update` WebSocket events, which carry the pending approvals while a
 * call is in flight and clear them the moment the call ends. Deliberately
 * NOT persisted — the server owns the state.
 */

import { create } from 'zustand'
import {
  connectFaro,
  denyFaroApproval,
  disconnectFaro,
  getBotFaro,
  getFaroStatus,
} from '../api/faro'
import type { BotFaroStatus, FaroIntegrationStatus, FaroUpdatePayload } from '../types'

interface FaroStoreState {
  /** Global bridge detection; null until the first fetch. */
  status: FaroIntegrationStatus | null
  /** Whether the global status was fetched at least once (even if failed). */
  statusLoaded: boolean
  /** botId -> latest per-bot state (REST response or WS event). */
  byBot: Record<string, BotFaroStatus>
  /** botId -> a fetch is in flight (dedupes concurrent ensure calls). */
  loadingFor: Record<string, boolean>

  /** Fetch the global bridge detection (call where the card may mount). */
  fetchStatus: () => Promise<void>
  /** Load one bot's Faro state once (call where the card mounts). */
  ensureForBot: (botId: string) => Promise<void>
  /** Insert or replace one record (from the API or a `faro_update`). */
  applyUpdate: (payload: FaroUpdatePayload) => void

  connect: (botId: string) => Promise<BotFaroStatus>
  disconnect: (botId: string) => Promise<BotFaroStatus>
  /** Deny one pending approval in Faro (the only answer from here). */
  denyApproval: (botId: string, requestId: string) => Promise<void>
}

export const useFaroStore = create<FaroStoreState>()((set, get) => ({
  status: null,
  statusLoaded: false,
  byBot: {},
  loadingFor: {},

  fetchStatus: async () => {
    try {
      const status = await getFaroStatus()
      set({ status, statusLoaded: true })
    } catch {
      // An unreachable status endpoint reads as "no Faro": views stay hidden.
      set({
        status: { available: false, reason: null, version: null, supportsApprovals: false },
        statusLoaded: true,
      })
    }
  },

  ensureForBot: async (botId) => {
    if (get().byBot[botId] || get().loadingFor[botId]) return
    set((state) => ({ loadingFor: { ...state.loadingFor, [botId]: true } }))
    try {
      const faro = await getBotFaro(botId)
      set((state) => ({
        byBot: { ...state.byBot, [botId]: faro },
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

  connect: async (botId) => {
    const faro = await connectFaro(botId)
    get().applyUpdate({ botId, ...faro })
    return faro
  },

  disconnect: async (botId) => {
    const faro = await disconnectFaro(botId)
    get().applyUpdate({ botId, ...faro })
    return faro
  },

  denyApproval: async (botId, requestId) => {
    await denyFaroApproval(botId, requestId)
    // The faro_update event settles the line; re-read now so the card
    // clears even if the socket is quiet.
    try {
      const faro = await getBotFaro(botId)
      get().applyUpdate({ botId, ...faro })
    } catch {
      // Keep the last real state; nothing is invented.
    }
  },
}))

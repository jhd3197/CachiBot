import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { UsageStats } from '../types'

// =============================================================================
// USAGE STORE
// =============================================================================

interface UsageState {
  stats: UsageStats

  // Actions
  recordUsage: (data: {
    botId: string
    model: string
    tokens: number
    cost: number
  }) => void
  resetStats: () => void
  clearBotStats: (botId: string) => void
}

const initialStats: UsageStats = {
  totalMessages: 0,
  totalTokens: 0,
  totalCost: 0,
  byModel: {},
  byBot: {},
  daily: [],
}

export const useUsageStore = create<UsageState>()(
  persist(
    (set) => ({
      stats: initialStats,

      recordUsage: ({ botId, model, tokens, cost }) =>
        set((state) => {
          const today = new Date().toISOString().split('T')[0]
          const existingDaily = state.stats.daily.find((d) => d.date === today)

          return {
            stats: {
              totalMessages: state.stats.totalMessages + 1,
              totalTokens: state.stats.totalTokens + tokens,
              totalCost: state.stats.totalCost + cost,
              byModel: {
                ...state.stats.byModel,
                [model]: {
                  tokens: (state.stats.byModel[model]?.tokens || 0) + tokens,
                  cost: (state.stats.byModel[model]?.cost || 0) + cost,
                  messages: (state.stats.byModel[model]?.messages || 0) + 1,
                },
              },
              byBot: {
                ...state.stats.byBot,
                [botId]: {
                  tokens: (state.stats.byBot[botId]?.tokens || 0) + tokens,
                  cost: (state.stats.byBot[botId]?.cost || 0) + cost,
                  messages: (state.stats.byBot[botId]?.messages || 0) + 1,
                },
              },
              daily: existingDaily
                ? state.stats.daily.map((d) =>
                    d.date === today
                      ? {
                          ...d,
                          tokens: d.tokens + tokens,
                          cost: d.cost + cost,
                          messages: d.messages + 1,
                        }
                      : d
                  )
                : [
                    ...state.stats.daily.slice(-29), // Keep last 30 days
                    { date: today, tokens, cost, messages: 1 },
                  ],
            },
          }
        }),

      resetStats: () => set({ stats: initialStats }),

      clearBotStats: (botId: string) =>
        set((state) => {
          const botStats = state.stats.byBot[botId]
          if (!botStats) return state

          // Remove the bot's contribution from totals
          const { [botId]: _removed, ...remainingByBot } = state.stats.byBot
          void _removed // Intentionally unused - we're just removing this key

          return {
            stats: {
              ...state.stats,
              totalMessages: Math.max(0, state.stats.totalMessages - botStats.messages),
              totalTokens: Math.max(0, state.stats.totalTokens - botStats.tokens),
              totalCost: Math.max(0, state.stats.totalCost - botStats.cost),
              byBot: remainingByBot,
            },
          }
        }),
    }),
    {
      name: 'cachibot-usage',
    }
  )
)

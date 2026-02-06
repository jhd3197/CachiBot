import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Connection, ConnectionPlatform, PlatformInfo, UsageStats } from '../types'

// =============================================================================
// PLATFORM INFORMATION
// =============================================================================

export const PLATFORMS: PlatformInfo[] = [
  {
    id: 'whatsapp',
    name: 'WhatsApp',
    description: 'Connect via WhatsApp Web API',
    icon: 'message-circle',
    library: '@whiskeysockets/baileys',
    docsUrl: 'https://github.com/WhiskeySockets/Baileys',
    free: true,
    setupSteps: [
      'Install Baileys: npm install @whiskeysockets/baileys',
      'Scan QR code with WhatsApp mobile app',
      'Session will persist automatically',
    ],
  },
  {
    id: 'telegram',
    name: 'Telegram',
    description: 'Connect via Telegram Bot API',
    icon: 'send',
    library: 'telegraf',
    docsUrl: 'https://telegraf.js.org',
    free: true,
    setupSteps: [
      'Create bot with @BotFather on Telegram',
      'Copy the bot token',
      'Install Telegraf: npm install telegraf',
    ],
  },
  {
    id: 'discord',
    name: 'Discord',
    description: 'Connect via Discord Bot',
    icon: 'gamepad-2',
    library: 'discord.js',
    docsUrl: 'https://discord.js.org',
    free: true,
    setupSteps: [
      'Create app at discord.com/developers',
      'Create a Bot and copy token',
      'Install Discord.js: npm install discord.js',
      'Invite bot to your server',
    ],
  },
  {
    id: 'slack',
    name: 'Slack',
    description: 'Connect via Slack Bolt',
    icon: 'hash',
    library: '@slack/bolt',
    docsUrl: 'https://slack.dev/bolt-js',
    free: true,
    setupSteps: [
      'Create Slack App at api.slack.com/apps',
      'Enable Socket Mode for free tier',
      'Install Bolt: npm install @slack/bolt',
      'Install app to workspace',
    ],
  },
  {
    id: 'messenger',
    name: 'Facebook Messenger',
    description: 'Connect via Messenger Platform',
    icon: 'facebook',
    library: 'messenger-platform',
    docsUrl: 'https://developers.facebook.com/docs/messenger-platform',
    free: true,
    setupSteps: [
      'Create Facebook App and Page',
      'Generate Page Access Token',
      'Set up webhook endpoint',
      'Subscribe to messaging events',
    ],
  },
  {
    id: 'matrix',
    name: 'Matrix',
    description: 'Open federated messaging protocol',
    icon: 'network',
    library: 'matrix-js-sdk',
    docsUrl: 'https://matrix.org/docs/develop/',
    free: true,
    setupSteps: [
      'Create account on any Matrix server',
      'Get access token from account settings',
      'Install SDK: npm install matrix-js-sdk',
    ],
  },
  {
    id: 'email',
    name: 'Email',
    description: 'IMAP/SMTP email integration',
    icon: 'mail',
    library: 'nodemailer + imap',
    docsUrl: 'https://nodemailer.com',
    free: true,
    setupSteps: [
      'Enable IMAP in email settings',
      'Generate app password if using Gmail/Outlook',
      'Install: npm install nodemailer imap',
    ],
  },
]

// =============================================================================
// CONNECTION STORE
// =============================================================================

interface ConnectionState {
  connections: Connection[]
  activeConnectionId: string | null

  // Actions
  addConnection: (connection: Connection) => void
  updateConnection: (id: string, updates: Partial<Connection>) => void
  deleteConnection: (id: string) => void
  setActiveConnection: (id: string | null) => void
  getConnectionsByBot: (botId: string) => Connection[]
  getConnectionsByPlatform: (platform: ConnectionPlatform) => Connection[]
}

export const useConnectionStore = create<ConnectionState>()(
  persist(
    (set, get) => ({
      connections: [],
      activeConnectionId: null,

      addConnection: (connection) =>
        set((state) => ({
          connections: [...state.connections, connection],
        })),

      updateConnection: (id, updates) =>
        set((state) => ({
          connections: state.connections.map((conn) =>
            conn.id === id ? { ...conn, ...updates } : conn
          ),
        })),

      deleteConnection: (id) =>
        set((state) => ({
          connections: state.connections.filter((conn) => conn.id !== id),
          activeConnectionId:
            state.activeConnectionId === id ? null : state.activeConnectionId,
        })),

      setActiveConnection: (id) => set({ activeConnectionId: id }),

      getConnectionsByBot: (botId) => {
        const state = get()
        return state.connections.filter((conn) => conn.botId === botId)
      },

      getConnectionsByPlatform: (platform) => {
        const state = get()
        return state.connections.filter((conn) => conn.platform === platform)
      },
    }),
    {
      name: 'cachibot-connections',
    }
  )
)

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

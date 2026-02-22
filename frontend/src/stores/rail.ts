import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { BotGroup, RailItem } from '../types'
import { useBotStore } from './bots'

interface RailState {
  railOrder: RailItem[]
  botGroups: BotGroup[]
  _initialized: boolean

  // Rail ordering
  moveItem: (fromIndex: number, toIndex: number) => void

  // Group management
  createGroup: (name: string, initialBotId?: string) => string
  deleteGroup: (groupId: string) => void
  renameGroup: (groupId: string, name: string) => void
  toggleGroupCollapse: (groupId: string) => void

  // Bot-in-group management
  addBotToGroup: (groupId: string, botId: string) => void
  removeBotFromGroup: (groupId: string, botId: string) => void
  moveBotWithinGroup: (groupId: string, fromIndex: number, toIndex: number) => void

  // Sync with bot store
  ensureBotInRail: (botId: string) => void
  removeBotFromRail: (botId: string) => void

  // Init
  initFromBots: () => void
}

export const useRailStore = create<RailState>()(
  persist(
    (set, get) => ({
      railOrder: [],
      botGroups: [],
      _initialized: false,

      moveItem: (fromIndex, toIndex) =>
        set((state) => {
          const items = [...state.railOrder]
          const [moved] = items.splice(fromIndex, 1)
          items.splice(toIndex, 0, moved)
          return { railOrder: items }
        }),

      createGroup: (name, initialBotId) => {
        const groupId = `group-${Date.now()}`
        set((state) => {
          const botIds: string[] = []
          let railOrder = [...state.railOrder]

          if (initialBotId) {
            // Remove bot from top-level rail
            railOrder = railOrder.filter(
              (item) => !(item.type === 'bot' && item.botId === initialBotId)
            )
            botIds.push(initialBotId)
          }

          // Insert group at the position of the removed bot, or at the end
          const insertIndex = initialBotId
            ? state.railOrder.findIndex(
                (item) => item.type === 'bot' && item.botId === initialBotId
              )
            : railOrder.length

          railOrder.splice(
            insertIndex >= 0 ? insertIndex : railOrder.length,
            0,
            { type: 'group', groupId }
          )

          return {
            railOrder,
            botGroups: [
              ...state.botGroups,
              { id: groupId, name, collapsed: false, botIds },
            ],
          }
        })
        return groupId
      },

      deleteGroup: (groupId) =>
        set((state) => {
          const group = state.botGroups.find((g) => g.id === groupId)
          if (!group) return state

          // Find where the group is in the rail order
          const groupIndex = state.railOrder.findIndex(
            (item) => item.type === 'group' && item.groupId === groupId
          )

          const railOrder = state.railOrder.filter(
            (item) => !(item.type === 'group' && item.groupId === groupId)
          )

          // Re-insert the group's bots at the group's former position
          const botsToInsert: RailItem[] = group.botIds.map((botId) => ({
            type: 'bot' as const,
            botId,
          }))
          if (groupIndex >= 0) {
            railOrder.splice(groupIndex, 0, ...botsToInsert)
          } else {
            railOrder.push(...botsToInsert)
          }

          return {
            railOrder,
            botGroups: state.botGroups.filter((g) => g.id !== groupId),
          }
        }),

      renameGroup: (groupId, name) =>
        set((state) => ({
          botGroups: state.botGroups.map((g) =>
            g.id === groupId ? { ...g, name } : g
          ),
        })),

      toggleGroupCollapse: (groupId) =>
        set((state) => ({
          botGroups: state.botGroups.map((g) =>
            g.id === groupId ? { ...g, collapsed: !g.collapsed } : g
          ),
        })),

      addBotToGroup: (groupId, botId) =>
        set((state) => {
          // Remove from top-level rail
          const railOrder = state.railOrder.filter(
            (item) => !(item.type === 'bot' && item.botId === botId)
          )

          // Also remove from any other group
          const botGroups = state.botGroups.map((g) => {
            if (g.id === groupId) {
              // Add to target group (if not already there)
              return g.botIds.includes(botId)
                ? g
                : { ...g, botIds: [...g.botIds, botId] }
            }
            // Remove from other groups
            return { ...g, botIds: g.botIds.filter((id) => id !== botId) }
          })

          return { railOrder, botGroups }
        }),

      removeBotFromGroup: (groupId, botId) =>
        set((state) => {
          const group = state.botGroups.find((g) => g.id === groupId)
          if (!group) return state

          // Find the group's position in rail order
          const groupIndex = state.railOrder.findIndex(
            (item) => item.type === 'group' && item.groupId === groupId
          )

          // Remove bot from the group
          const botGroups = state.botGroups.map((g) =>
            g.id === groupId
              ? { ...g, botIds: g.botIds.filter((id) => id !== botId) }
              : g
          )

          // Insert bot right after the group in the rail order
          const railOrder = [...state.railOrder]
          const insertAt = groupIndex >= 0 ? groupIndex + 1 : railOrder.length
          railOrder.splice(insertAt, 0, { type: 'bot', botId })

          return { railOrder, botGroups }
        }),

      moveBotWithinGroup: (groupId, fromIndex, toIndex) =>
        set((state) => ({
          botGroups: state.botGroups.map((g) => {
            if (g.id !== groupId) return g
            const botIds = [...g.botIds]
            const [moved] = botIds.splice(fromIndex, 1)
            botIds.splice(toIndex, 0, moved)
            return { ...g, botIds }
          }),
        })),

      ensureBotInRail: (botId) =>
        set((state) => {
          // Check if bot is already in the rail or in a group
          const inRail = state.railOrder.some(
            (item) => item.type === 'bot' && item.botId === botId
          )
          const inGroup = state.botGroups.some((g) => g.botIds.includes(botId))
          if (inRail || inGroup) return state

          return {
            railOrder: [...state.railOrder, { type: 'bot', botId }],
          }
        }),

      removeBotFromRail: (botId) =>
        set((state) => ({
          railOrder: state.railOrder.filter(
            (item) => !(item.type === 'bot' && item.botId === botId)
          ),
          botGroups: state.botGroups.map((g) => ({
            ...g,
            botIds: g.botIds.filter((id) => id !== botId),
          })),
        })),

      initFromBots: () => {
        const state = get()
        if (state._initialized && state.railOrder.length > 0) return

        const bots = useBotStore.getState().bots
        const railOrder: RailItem[] = bots.map((bot) => ({
          type: 'bot' as const,
          botId: bot.id,
        }))

        set({ railOrder, _initialized: true })
      },
    }),
    {
      name: 'cachibot-rail',
      partialize: (state) => ({
        railOrder: state.railOrder,
        botGroups: state.botGroups,
        _initialized: state._initialized,
      }),
    }
  )
)

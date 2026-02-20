import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Room, RoomMessage, ToolCall } from '../types'

export type BotRoomState = 'idle' | 'thinking' | 'responding'

interface RoomState {
  rooms: Room[]
  activeRoomId: string | null
  messages: Record<string, RoomMessage[]> // roomId -> messages
  onlineUsers: Record<string, string[]> // roomId -> user IDs
  typingUsers: Record<string, { userId: string; username: string }[]> // roomId -> typing users
  botStates: Record<string, Record<string, BotRoomState>> // roomId -> { botId -> state }
  activeToolCalls: Record<string, Record<string, ToolCall[]>> // roomId -> messageId -> ToolCall[]
  chainStep: Record<string, { step: number; totalSteps: number; botName: string } | null>
  routeDecision: Record<string, { botName: string; reason: string } | null>
  isLoading: boolean
  error: string | null

  // Room CRUD
  setRooms: (rooms: Room[]) => void
  addRoom: (room: Room) => void
  updateRoom: (roomId: string, updates: Partial<Room>) => void
  deleteRoom: (roomId: string) => void
  setActiveRoom: (roomId: string | null) => void

  // Messages
  addMessage: (roomId: string, message: RoomMessage) => void
  appendMessageContent: (roomId: string, messageId: string, content: string) => void
  setMessages: (roomId: string, messages: RoomMessage[]) => void
  clearMessages: (roomId: string) => void

  // Presence
  setOnlineUsers: (roomId: string, userIds: string[]) => void
  addOnlineUser: (roomId: string, userId: string) => void
  removeOnlineUser: (roomId: string, userId: string) => void

  // Typing
  setTyping: (roomId: string, userId: string, username: string, isTyping: boolean) => void

  // Bot states
  setBotState: (roomId: string, botId: string, state: BotRoomState) => void

  // Tool call tracking (transient — not persisted)
  addToolCall: (roomId: string, messageId: string, call: ToolCall) => void
  completeToolCall: (roomId: string, messageId: string, toolId: string, result: unknown, success: boolean) => void
  finalizeToolCalls: (roomId: string, messageId: string) => void
  updateMessageMetadata: (roomId: string, messageId: string, metadata: Record<string, unknown>) => void

  // Chain / Router
  setChainStep: (roomId: string, step: { step: number; totalSteps: number; botName: string } | null) => void
  setRouteDecision: (roomId: string, decision: { botName: string; reason: string } | null) => void

  // Selectors
  getRoomsForBot: (botId: string) => Room[]

  // Meta
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useRoomStore = create<RoomState>()(
  persist(
    (set, get) => ({
      rooms: [],
      activeRoomId: null,
      messages: {},
      onlineUsers: {},
      typingUsers: {},
      botStates: {},
      activeToolCalls: {},
      chainStep: {},
      routeDecision: {},
      isLoading: false,
      error: null,

      setRooms: (rooms) => set({ rooms }),

      addRoom: (room) =>
        set((state) => ({ rooms: [room, ...state.rooms] })),

      updateRoom: (roomId, updates) =>
        set((state) => ({
          rooms: state.rooms.map((r) => (r.id === roomId ? { ...r, ...updates } : r)),
        })),

      deleteRoom: (roomId) =>
        set((state) => ({
          rooms: state.rooms.filter((r) => r.id !== roomId),
          activeRoomId: state.activeRoomId === roomId ? null : state.activeRoomId,
          messages: (() => {
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { [roomId]: _removed, ...rest } = state.messages
            return rest
          })(),
        })),

      setActiveRoom: (roomId) => set({ activeRoomId: roomId }),

      addMessage: (roomId, message) =>
        set((state) => {
          const existing = state.messages[roomId] || []
          const existingIdx = existing.findIndex((m) => m.id === message.id)
          if (existingIdx >= 0) {
            if (message.senderType === 'bot') {
              // Append content for bot streaming deltas
              const updated = [...existing]
              updated[existingIdx] = {
                ...updated[existingIdx],
                content: updated[existingIdx].content + message.content,
              }
              return { messages: { ...state.messages, [roomId]: updated } }
            }
            // User/system: already have it, skip
            return state
          }

          // Deduplicate user messages: skip if same sender + content within 2 seconds
          if (message.senderType === 'user') {
            const msgTime = new Date(message.timestamp).getTime()
            const isDup = existing.some(
              (m) =>
                m.senderType === 'user' &&
                m.senderId === message.senderId &&
                m.content === message.content &&
                Math.abs(new Date(m.timestamp).getTime() - msgTime) < 2000
            )
            if (isDup) return state
          }

          return { messages: { ...state.messages, [roomId]: [...existing, message] } }
        }),

      appendMessageContent: (roomId, messageId, content) =>
        set((state) => {
          const existing = state.messages[roomId] || []
          const idx = existing.findIndex((m) => m.id === messageId)
          if (idx < 0) return state
          const updated = [...existing]
          updated[idx] = { ...updated[idx], content: updated[idx].content + content }
          return { messages: { ...state.messages, [roomId]: updated } }
        }),

      setMessages: (roomId, messages) =>
        set((state) => ({ messages: { ...state.messages, [roomId]: messages } })),

      clearMessages: (roomId) =>
        set((state) => ({ messages: { ...state.messages, [roomId]: [] } })),

      setOnlineUsers: (roomId, userIds) =>
        set((state) => ({ onlineUsers: { ...state.onlineUsers, [roomId]: userIds } })),

      addOnlineUser: (roomId, userId) =>
        set((state) => {
          const current = state.onlineUsers[roomId] || []
          if (current.includes(userId)) return state
          return { onlineUsers: { ...state.onlineUsers, [roomId]: [...current, userId] } }
        }),

      removeOnlineUser: (roomId, userId) =>
        set((state) => {
          const current = state.onlineUsers[roomId] || []
          return {
            onlineUsers: {
              ...state.onlineUsers,
              [roomId]: current.filter((id) => id !== userId),
            },
          }
        }),

      setTyping: (roomId, userId, username, isTyping) =>
        set((state) => {
          const current = state.typingUsers[roomId] || []
          if (isTyping) {
            if (current.some((t) => t.userId === userId)) return state
            return {
              typingUsers: {
                ...state.typingUsers,
                [roomId]: [...current, { userId, username }],
              },
            }
          }
          return {
            typingUsers: {
              ...state.typingUsers,
              [roomId]: current.filter((t) => t.userId !== userId),
            },
          }
        }),

      setBotState: (roomId, botId, botState) =>
        set((state) => ({
          botStates: {
            ...state.botStates,
            [roomId]: { ...(state.botStates[roomId] || {}), [botId]: botState },
          },
        })),

      addToolCall: (roomId, messageId, call) =>
        set((state) => {
          const roomCalls = state.activeToolCalls[roomId] || {}
          const msgCalls = roomCalls[messageId] || []
          return {
            activeToolCalls: {
              ...state.activeToolCalls,
              [roomId]: { ...roomCalls, [messageId]: [...msgCalls, call] },
            },
          }
        }),

      completeToolCall: (roomId, messageId, toolId, result, success) =>
        set((state) => {
          const roomCalls = state.activeToolCalls[roomId] || {}
          const msgCalls = roomCalls[messageId] || []
          return {
            activeToolCalls: {
              ...state.activeToolCalls,
              [roomId]: {
                ...roomCalls,
                [messageId]: msgCalls.map((c) =>
                  c.id === toolId ? { ...c, result, success, endTime: Date.now() } : c
                ),
              },
            },
          }
        }),

      finalizeToolCalls: (roomId, messageId) =>
        set((state) => {
          const roomCalls = state.activeToolCalls[roomId] || {}
          const calls = roomCalls[messageId]
          if (!calls || calls.length === 0) return state

          // Copy tool calls into the message
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state

          const updated = [...msgs]
          updated[idx] = { ...updated[idx], toolCalls: calls }

          // Clean up active tracking
          // eslint-disable-next-line @typescript-eslint/no-unused-vars
          const { [messageId]: _removed, ...restCalls } = roomCalls

          return {
            messages: { ...state.messages, [roomId]: updated },
            activeToolCalls: { ...state.activeToolCalls, [roomId]: restCalls },
          }
        }),

      updateMessageMetadata: (roomId, messageId, metadata) =>
        set((state) => {
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state

          const updated = [...msgs]
          updated[idx] = {
            ...updated[idx],
            metadata: { ...updated[idx].metadata, ...metadata },
          }
          return { messages: { ...state.messages, [roomId]: updated } }
        }),

      setChainStep: (roomId, step) =>
        set((state) => ({
          chainStep: { ...state.chainStep, [roomId]: step },
        })),

      setRouteDecision: (roomId, decision) =>
        set((state) => ({
          routeDecision: { ...state.routeDecision, [roomId]: decision },
        })),

      getRoomsForBot: (botId) =>
        get().rooms.filter((room) => room.bots.some((b) => b.botId === botId)),

      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
    }),
    {
      name: 'cachibot-rooms',
      partialize: (state) => ({
        rooms: state.rooms,
      }),
    }
  )
)

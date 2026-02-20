import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Room, RoomMessage } from '../types'

export type BotRoomState = 'idle' | 'thinking' | 'responding'

interface RoomState {
  rooms: Room[]
  activeRoomId: string | null
  messages: Record<string, RoomMessage[]> // roomId -> messages
  onlineUsers: Record<string, string[]> // roomId -> user IDs
  typingUsers: Record<string, { userId: string; username: string }[]> // roomId -> typing users
  botStates: Record<string, Record<string, BotRoomState>> // roomId -> { botId -> state }
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
          // Check for existing message with same ID (streaming updates)
          const existingIdx = existing.findIndex((m) => m.id === message.id)
          if (existingIdx >= 0) {
            // Append content to existing message
            const updated = [...existing]
            updated[existingIdx] = {
              ...updated[existingIdx],
              content: updated[existingIdx].content + message.content,
            }
            return { messages: { ...state.messages, [roomId]: updated } }
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

      getRoomsForBot: (botId) =>
        get().rooms.filter((room) => room.bots.some((b) => b.botId === botId)),

      setLoading: (loading) => set({ isLoading: loading }),
      setError: (error) => set({ error }),
    }),
    {
      name: 'cachibot-rooms',
      partialize: (state) => ({
        rooms: state.rooms,
        messages: state.messages,
      }),
    }
  )
)

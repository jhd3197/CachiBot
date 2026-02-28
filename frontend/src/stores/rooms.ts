import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Room, RoomMessage, ToolCall, PinnedMessage, BookmarkedMessage, RoomTask, RoomTaskEvent, Asset } from '../types'

export type BotRoomState = 'idle' | 'thinking' | 'responding'

interface RoomState {
  rooms: Room[]
  activeRoomId: string | null
  messages: Record<string, RoomMessage[]> // roomId -> messages
  onlineUsers: Record<string, string[]> // roomId -> user IDs
  typingUsers: Record<string, { userId: string; username: string }[]> // roomId -> typing users
  botStates: Record<string, Record<string, BotRoomState>> // roomId -> { botId -> state }
  botActivity: Record<string, Record<string, string>> // roomId -> { botId -> descriptive activity text }
  activeToolCalls: Record<string, Record<string, ToolCall[]>> // roomId -> messageId -> ToolCall[]
  thinkingContent: Record<string, Record<string, string>> // roomId -> botId -> text (transient)
  instructionDeltas: Record<string, Record<string, string>> // roomId -> toolId -> text (transient)
  chainStep: Record<string, { step: number; totalSteps: number; botName: string } | null>
  routeDecision: Record<string, { botName: string; reason: string } | null>
  pinnedMessages: Record<string, PinnedMessage[]> // roomId -> pinned messages
  bookmarkedMessageIds: Record<string, Set<string>> // roomId -> message IDs
  bookmarks: BookmarkedMessage[]
  viewMode: Record<string, 'chat' | 'cards' | 'timeline' | 'tasks' | 'assets'>
  roomTasks: Record<string, RoomTask[]>
  selectedTaskId: Record<string, string | null>
  taskEvents: Record<string, RoomTaskEvent[]>
  taskEventsLoading: Record<string, boolean>
  roomAssets: Record<string, Asset[]>
  botTimeline: Record<string, Array<{ botId: string; botName: string; startTime: number; endTime: number; tokens: number }>>
  consensusState: Record<string, { phase: 'collecting' | 'synthesizing'; collected: number; total: number; synthesizerName?: string } | null>
  interviewState: Record<string, { questionCount: number; maxQuestions: number; handoffTriggered: boolean } | null>
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
  setBotActivity: (roomId: string, botId: string, activity: string) => void
  clearBotActivity: (roomId: string, botId: string) => void

  // Tool call tracking (transient — not persisted)
  addToolCall: (roomId: string, messageId: string, call: ToolCall) => void
  completeToolCall: (roomId: string, messageId: string, toolId: string, result: unknown, success: boolean) => void
  finalizeToolCalls: (roomId: string, messageId: string) => void
  setMessageToolCalls: (roomId: string, messageId: string, toolCalls: ToolCall[]) => void
  updateMessageMetadata: (roomId: string, messageId: string, metadata: Record<string, unknown>) => void

  // Thinking content (transient — not persisted)
  setBotThinking: (roomId: string, botId: string, content: string) => void
  clearBotThinking: (roomId: string, botId: string) => void
  attachThinkingToMessage: (roomId: string, messageId: string, thinking: string) => void

  // Instruction deltas (transient — not persisted)
  appendInstructionDelta: (roomId: string, toolId: string, text: string) => void

  // Chain / Router
  setChainStep: (roomId: string, step: { step: number; totalSteps: number; botName: string } | null) => void
  setRouteDecision: (roomId: string, decision: { botName: string; reason: string } | null) => void

  // Reactions
  addReactionToMessage: (roomId: string, messageId: string, emoji: string, userId: string) => void
  removeReactionFromMessage: (roomId: string, messageId: string, emoji: string, userId: string) => void

  // Pins
  setPinnedMessages: (roomId: string, pins: PinnedMessage[]) => void
  addPinnedMessage: (roomId: string, pin: PinnedMessage) => void
  removePinnedMessage: (roomId: string, messageId: string) => void

  // Bookmarks
  setBookmarks: (bookmarks: BookmarkedMessage[]) => void
  addBookmarkedId: (roomId: string, messageId: string) => void
  removeBookmarkedId: (roomId: string, messageId: string) => void

  // View mode
  setViewMode: (roomId: string, mode: 'chat' | 'cards' | 'timeline' | 'tasks' | 'assets') => void

  // Room tasks
  setRoomTasks: (roomId: string, tasks: RoomTask[]) => void
  addRoomTask: (roomId: string, task: RoomTask) => void
  updateRoomTask: (roomId: string, taskId: string, updates: Partial<RoomTask>) => void
  deleteRoomTask: (roomId: string, taskId: string) => void
  setSelectedTask: (roomId: string, taskId: string | null) => void
  setTaskEvents: (taskId: string, events: RoomTaskEvent[]) => void
  setTaskEventsLoading: (taskId: string, loading: boolean) => void

  // Room assets
  setRoomAssets: (roomId: string, assets: Asset[]) => void
  addRoomAsset: (roomId: string, asset: Asset) => void
  deleteRoomAsset: (roomId: string, assetId: string) => void

  // Timeline
  addTimelineEntry: (roomId: string, entry: { botId: string; botName: string; startTime: number; endTime: number; tokens: number }) => void
  resetTimeline: (roomId: string) => void

  // Consensus
  setConsensusState: (roomId: string, state: { phase: 'collecting' | 'synthesizing'; collected: number; total: number; synthesizerName?: string } | null) => void

  // Interview
  setInterviewState: (roomId: string, state: { questionCount: number; maxQuestions: number; handoffTriggered: boolean } | null) => void

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
      botActivity: {},
      activeToolCalls: {},
      thinkingContent: {},
      instructionDeltas: {},
      chainStep: {},
      routeDecision: {},
      pinnedMessages: {},
      bookmarkedMessageIds: {},
      bookmarks: [],
      viewMode: {},
      roomTasks: {},
      selectedTaskId: {},
      taskEvents: {},
      taskEventsLoading: {},
      roomAssets: {},
      botTimeline: {},
      consensusState: {},
      interviewState: {},
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

      setBotActivity: (roomId, botId, activity) =>
        set((state) => ({
          botActivity: {
            ...state.botActivity,
            [roomId]: { ...(state.botActivity[roomId] || {}), [botId]: activity },
          },
        })),

      clearBotActivity: (roomId, botId) =>
        set((state) => {
          const room = { ...(state.botActivity[roomId] || {}) }
          delete room[botId]
          return { botActivity: { ...state.botActivity, [roomId]: room } }
        }),

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

          // Clean up instruction deltas for finalized tool calls
          const roomDeltas = { ...state.instructionDeltas[roomId] }
          for (const tc of calls) {
            delete roomDeltas[tc.id]
          }

          return {
            messages: { ...state.messages, [roomId]: updated },
            activeToolCalls: { ...state.activeToolCalls, [roomId]: restCalls },
            instructionDeltas: { ...state.instructionDeltas, [roomId]: roomDeltas },
          }
        }),

      setMessageToolCalls: (roomId, messageId, toolCalls) =>
        set((state) => {
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state
          const updated = [...msgs]
          updated[idx] = { ...updated[idx], toolCalls }
          return { messages: { ...state.messages, [roomId]: updated } }
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

      setBotThinking: (roomId, botId, content) =>
        set((state) => {
          const existing = state.thinkingContent[roomId]?.[botId] || ''
          return {
            thinkingContent: {
              ...state.thinkingContent,
              [roomId]: { ...(state.thinkingContent[roomId] || {}), [botId]: existing + content },
            },
          }
        }),

      clearBotThinking: (roomId, botId) =>
        set((state) => {
          const roomThinking = { ...(state.thinkingContent[roomId] || {}) }
          delete roomThinking[botId]
          return {
            thinkingContent: { ...state.thinkingContent, [roomId]: roomThinking },
          }
        }),

      attachThinkingToMessage: (roomId, messageId, thinking) =>
        set((state) => {
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state
          const updated = [...msgs]
          updated[idx] = { ...updated[idx], thinking }
          return { messages: { ...state.messages, [roomId]: updated } }
        }),

      appendInstructionDelta: (roomId, toolId, text) =>
        set((state) => {
          const roomDeltas = state.instructionDeltas[roomId] || {}
          return {
            instructionDeltas: {
              ...state.instructionDeltas,
              [roomId]: { ...roomDeltas, [toolId]: (roomDeltas[toolId] || '') + text },
            },
          }
        }),

      setChainStep: (roomId, step) =>
        set((state) => ({
          chainStep: { ...state.chainStep, [roomId]: step },
        })),

      setRouteDecision: (roomId, decision) =>
        set((state) => ({
          routeDecision: { ...state.routeDecision, [roomId]: decision },
        })),

      // Reactions
      addReactionToMessage: (roomId, messageId, emoji, userId) =>
        set((state) => {
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state
          const updated = [...msgs]
          const reactions = [...(updated[idx].reactions || [])]
          const existing = reactions.findIndex((r) => r.emoji === emoji)
          if (existing >= 0) {
            const r = reactions[existing]
            if (!r.userIds.includes(userId)) {
              reactions[existing] = { ...r, count: r.count + 1, userIds: [...r.userIds, userId] }
            }
          } else {
            reactions.push({ emoji, count: 1, userIds: [userId] })
          }
          updated[idx] = { ...updated[idx], reactions }
          return { messages: { ...state.messages, [roomId]: updated } }
        }),

      removeReactionFromMessage: (roomId, messageId, emoji, userId) =>
        set((state) => {
          const msgs = state.messages[roomId] || []
          const idx = msgs.findIndex((m) => m.id === messageId)
          if (idx < 0) return state
          const updated = [...msgs]
          let reactions = [...(updated[idx].reactions || [])]
          const existing = reactions.findIndex((r) => r.emoji === emoji)
          if (existing >= 0) {
            const r = reactions[existing]
            const newUserIds = r.userIds.filter((id) => id !== userId)
            if (newUserIds.length === 0) {
              reactions = reactions.filter((_, i) => i !== existing)
            } else {
              reactions[existing] = { ...r, count: newUserIds.length, userIds: newUserIds }
            }
          }
          updated[idx] = { ...updated[idx], reactions }
          return { messages: { ...state.messages, [roomId]: updated } }
        }),

      // Pins
      setPinnedMessages: (roomId, pins) =>
        set((state) => ({
          pinnedMessages: { ...state.pinnedMessages, [roomId]: pins },
        })),

      addPinnedMessage: (roomId, pin) =>
        set((state) => ({
          pinnedMessages: {
            ...state.pinnedMessages,
            [roomId]: [pin, ...(state.pinnedMessages[roomId] || [])],
          },
        })),

      removePinnedMessage: (roomId, messageId) =>
        set((state) => ({
          pinnedMessages: {
            ...state.pinnedMessages,
            [roomId]: (state.pinnedMessages[roomId] || []).filter((p) => p.messageId !== messageId),
          },
        })),

      // Bookmarks
      setBookmarks: (bookmarks) => set({ bookmarks }),

      addBookmarkedId: (roomId, messageId) =>
        set((state) => {
          const current = state.bookmarkedMessageIds[roomId] || new Set()
          const updated = new Set(current)
          updated.add(messageId)
          return { bookmarkedMessageIds: { ...state.bookmarkedMessageIds, [roomId]: updated } }
        }),

      removeBookmarkedId: (roomId, messageId) =>
        set((state) => {
          const current = state.bookmarkedMessageIds[roomId] || new Set()
          const updated = new Set(current)
          updated.delete(messageId)
          return { bookmarkedMessageIds: { ...state.bookmarkedMessageIds, [roomId]: updated } }
        }),

      // View mode
      setViewMode: (roomId, mode) =>
        set((state) => ({
          viewMode: { ...state.viewMode, [roomId]: mode },
        })),

      // Timeline
      addTimelineEntry: (roomId, entry) =>
        set((state) => ({
          botTimeline: {
            ...state.botTimeline,
            [roomId]: [...(state.botTimeline[roomId] || []), entry],
          },
        })),

      resetTimeline: (roomId) =>
        set((state) => ({
          botTimeline: { ...state.botTimeline, [roomId]: [] },
        })),

      // Consensus
      setConsensusState: (roomId, consensusState) =>
        set((state) => ({
          consensusState: { ...state.consensusState, [roomId]: consensusState },
        })),

      // Interview
      setInterviewState: (roomId, interviewState) =>
        set((state) => ({
          interviewState: { ...state.interviewState, [roomId]: interviewState },
        })),

      // Room tasks
      setRoomTasks: (roomId, tasks) =>
        set((state) => ({
          roomTasks: { ...state.roomTasks, [roomId]: tasks },
        })),

      addRoomTask: (roomId, task) =>
        set((state) => ({
          roomTasks: {
            ...state.roomTasks,
            [roomId]: [...(state.roomTasks[roomId] || []), task],
          },
        })),

      updateRoomTask: (roomId, taskId, updates) =>
        set((state) => ({
          roomTasks: {
            ...state.roomTasks,
            [roomId]: (state.roomTasks[roomId] || []).map((t) =>
              t.id === taskId ? { ...t, ...updates } : t
            ),
          },
        })),

      deleteRoomTask: (roomId, taskId) =>
        set((state) => ({
          roomTasks: {
            ...state.roomTasks,
            [roomId]: (state.roomTasks[roomId] || []).filter((t) => t.id !== taskId),
          },
        })),

      setSelectedTask: (roomId, taskId) =>
        set((state) => ({
          selectedTaskId: { ...state.selectedTaskId, [roomId]: taskId },
        })),

      setTaskEvents: (taskId, events) =>
        set((state) => ({
          taskEvents: { ...state.taskEvents, [taskId]: events },
        })),

      setTaskEventsLoading: (taskId, loading) =>
        set((state) => ({
          taskEventsLoading: { ...state.taskEventsLoading, [taskId]: loading },
        })),

      // Room assets
      setRoomAssets: (roomId, assets) =>
        set((state) => ({
          roomAssets: { ...state.roomAssets, [roomId]: assets },
        })),

      addRoomAsset: (roomId, asset) =>
        set((state) => ({
          roomAssets: {
            ...state.roomAssets,
            [roomId]: [asset, ...(state.roomAssets[roomId] || [])],
          },
        })),

      deleteRoomAsset: (roomId, assetId) =>
        set((state) => ({
          roomAssets: {
            ...state.roomAssets,
            [roomId]: (state.roomAssets[roomId] || []).filter((a) => a.id !== assetId),
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
      }),
    }
  )
)

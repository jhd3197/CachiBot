import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type {
  Bot,
  BotModels,
  Chat,
  Job,
  Task,
  BotView,
  ChatMessage,
  ToolCall,
  // Work management types
  Work,
  WorkTask,
  WorkJob,
  Todo,
  BotFunction,
  Schedule,
  WorkStatus,
  TodoStatus,
  Priority,
} from '../types'
import { syncBot, deleteBackendBot, getPlatformChats, getPlatformChatMessages, archivePlatformChat, unarchivePlatformChat } from '../api/client'

// Guard to prevent concurrent syncPlatformChats calls for the same bot
const syncingBotIds = new Set<string>()

// =============================================================================
// BOT STORE
// =============================================================================

interface BotState {
  bots: Bot[]
  activeBotId: string | null
  activeView: BotView

  // Actions
  addBot: (bot: Bot) => void
  updateBot: (id: string, updates: Partial<Bot>) => void
  deleteBot: (id: string) => void
  setActiveBot: (id: string | null) => void
  setActiveView: (view: BotView) => void
  getActiveBot: () => Bot | undefined
}

// Default bot settings (exported for reset functionality)
export const DEFAULT_BOT_SETTINGS: Pick<Bot, 'name' | 'description' | 'icon' | 'color' | 'model' | 'systemPrompt'> = {
  name: 'CachiBot',
  description: 'The Armored AI Agent - your general-purpose assistant',
  icon: 'shield' as const,
  color: '#22c55e',
  model: '',
  systemPrompt: `You are CachiBot, a helpful AI assistant created by Juan Almonte.

## About Your Name
CachiBot is named after the Venezuelan *cachicamo* (armadillo) - a resilient, armored creature known for its protective shell and methodical nature. Like the cachicamo, you approach tasks with care, protection, and thoroughness.

## Guidelines
- Be concise and helpful
- Use tools when actions are needed
- Explain what you're doing
- When asked about yourself, refer to the information above - do not claim to be created by any other company`,
}

/**
 * Get effective multi-model config for a bot, with fallback from bot.model.
 */
export function getEffectiveModels(bot: Bot): BotModels {
  return {
    default: bot.models?.default || bot.model || '',
    image: bot.models?.image || '',
    audio: bot.models?.audio || '',
    structured: bot.models?.structured || '',
  }
}

// Default bot for initial state
const defaultBot: Bot = {
  id: 'default',
  ...DEFAULT_BOT_SETTINGS,
  tools: ['file_read', 'file_write', 'file_list', 'file_edit', 'file_info', 'python_execute', 'task_complete'],
  createdAt: new Date().toISOString(),
  updatedAt: new Date().toISOString(),
}

// Helper to sync bot to backend (fire-and-forget, doesn't block UI)
function syncBotToBackend(bot: Bot) {
  // Only sync if bot has a system prompt (required for platform messages)
  if (!bot.systemPrompt) {
    return
  }

  syncBot({
    id: bot.id,
    name: bot.name,
    description: bot.description,
    icon: bot.icon,
    color: bot.color,
    model: bot.model,
    systemPrompt: bot.systemPrompt,
    capabilities: bot.capabilities as Record<string, boolean> | undefined,
    createdAt: bot.createdAt,
    updatedAt: bot.updatedAt,
  }).catch((err) => {
    console.warn('Failed to sync bot to backend:', err)
  })
}

export const useBotStore = create<BotState>()(
  persist(
    (set, get) => ({
      bots: [defaultBot],
      activeBotId: 'default',
      activeView: 'chats',

      addBot: (bot) => {
        set((state) => ({
          bots: [...state.bots, bot],
        }))
        // Sync to backend for platform connections
        syncBotToBackend(bot)
      },

      updateBot: (id, updates) => {
        set((state) => ({
          bots: state.bots.map((bot) =>
            bot.id === id
              ? { ...bot, ...updates, updatedAt: new Date().toISOString() }
              : bot
          ),
        }))
        // Sync updated bot to backend
        const updatedBot = get().bots.find((b) => b.id === id)
        if (updatedBot) {
          syncBotToBackend(updatedBot)
        }
      },

      deleteBot: (id) => {
        // Prevent deletion of the default bot
        if (id === 'default') return

        set((state) => ({
          bots: state.bots.filter((bot) => bot.id !== id),
          activeBotId: state.activeBotId === id ? state.bots[0]?.id ?? null : state.activeBotId,
        }))
        // Delete from backend
        deleteBackendBot(id).catch((err) => {
          console.warn('Failed to delete bot from backend:', err)
        })
      },

      setActiveBot: (id) => set({ activeBotId: id }),

      setActiveView: (view) => set({ activeView: view }),

      getActiveBot: () => {
        const state = get()
        return state.bots.find((bot) => bot.id === state.activeBotId)
      },
    }),
    {
      name: 'cachibot-bots',
    }
  )
)

// =============================================================================
// CHAT STORE (Enhanced)
// =============================================================================

interface ChatState {
  chats: Chat[]
  activeChatId: string | null
  messages: Record<string, ChatMessage[]> // chatId -> messages
  thinking: string | null
  toolCalls: ToolCall[]
  isLoading: boolean
  error: string | null
  replyToMessage: ChatMessage | null

  // Actions
  addChat: (chat: Chat) => void
  updateChat: (id: string, updates: Partial<Chat>) => void
  deleteChat: (id: string) => void
  setActiveChat: (id: string | null) => void
  getChatsByBot: (botId: string) => Chat[]

  // Platform chat sync
  syncPlatformChats: (botId: string) => Promise<void>
  loadPlatformChatMessages: (botId: string, chatId: string) => Promise<void>
  archiveChat: (botId: string, chatId: string) => Promise<void>
  unarchiveChat: (botId: string, chatId: string) => Promise<void>

  // Messages
  addMessage: (chatId: string, message: ChatMessage) => void
  updateMessage: (chatId: string, messageId: string, content: string) => void
  updateLastAssistantMessage: (chatId: string, updates: Partial<ChatMessage>) => void
  updateLastAssistantMessageMetadata: (chatId: string, metadata: Record<string, unknown>) => void
  getMessages: (chatId: string) => ChatMessage[]
  getMessageById: (chatId: string, messageId: string) => ChatMessage | undefined
  clearMessages: (chatId: string) => void

  // Reply state
  setReplyTo: (message: ChatMessage | null) => void

  // UI State
  setThinking: (content: string | null) => void
  appendThinking: (content: string) => void
  addToolCall: (call: Omit<ToolCall, 'startTime'>) => void
  updateToolCall: (id: string, result: unknown, success: boolean) => void
  clearToolCalls: () => void
  attachToolCallsToLastMessage: (chatId: string, toolCalls: ToolCall[]) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useChatStore = create<ChatState>()(
  persist(
    (set, get) => ({
      chats: [],
      activeChatId: null,
      messages: {},
      thinking: null,
      toolCalls: [],
      isLoading: false,
      error: null,
      replyToMessage: null,

      addChat: (chat) =>
        set((state) => ({
          chats: [chat, ...state.chats],
        })),

      updateChat: (id, updates) =>
        set((state) => ({
          chats: state.chats.map((chat) =>
            chat.id === id
              ? { ...chat, ...updates, updatedAt: new Date().toISOString() }
              : chat
          ),
        })),

      deleteChat: (id) =>
        set((state) => {
          const { [id]: _removed, ...remainingMessages } = state.messages
          void _removed // Intentionally unused - we're just removing this key
          return {
            chats: state.chats.filter((chat) => chat.id !== id),
            messages: remainingMessages,
            activeChatId: state.activeChatId === id ? null : state.activeChatId,
          }
        }),

      setActiveChat: (id) => set({ activeChatId: id }),

      getChatsByBot: (botId) => {
        const state = get()
        return state.chats
          .filter((chat) => chat.botId === botId)
          .sort((a, b) => {
            // Pinned first, then by date
            if (a.pinned && !b.pinned) return -1
            if (!a.pinned && b.pinned) return 1
            return new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime()
          })
      },

      syncPlatformChats: async (botId) => {
        if (syncingBotIds.has(botId)) return
        syncingBotIds.add(botId)
        try {
          const platformChats = await getPlatformChats(botId)
          set((state) => {
            // Merge platform chats with existing chats
            const existingIds = new Set(state.chats.map((c) => c.id))
            const newChats = platformChats
              .filter((pc) => !existingIds.has(pc.id))
              .map((pc) => ({
                id: pc.id,
                botId: pc.botId,
                title: pc.title,
                createdAt: pc.createdAt,
                updatedAt: pc.updatedAt,
                messageCount: 0,
                pinned: pc.pinned,
                platform: pc.platform as 'telegram' | 'discord' | null,
                platformChatId: pc.platformChatId,
              }))

            // Update existing platform chats
            const updatedChats = state.chats.map((chat) => {
              const platformChat = platformChats.find((pc) => pc.id === chat.id)
              if (platformChat) {
                return {
                  ...chat,
                  title: platformChat.title,
                  updatedAt: platformChat.updatedAt,
                  pinned: platformChat.pinned,
                }
              }
              return chat
            })

            return {
              chats: [...newChats, ...updatedChats],
            }
          })
        } catch (err) {
          console.warn('Failed to sync platform chats:', err)
        } finally {
          syncingBotIds.delete(botId)
        }
      },

      loadPlatformChatMessages: async (botId, chatId) => {
        try {
          const messages = await getPlatformChatMessages(botId, chatId)
          set((state) => ({
            messages: {
              ...state.messages,
              [chatId]: messages.map((m) => {
                // Extract toolCalls from metadata if present (persisted by message_processor)
                const toolCalls = m.metadata?.toolCalls as ToolCall[] | undefined
                const msg: ChatMessage = {
                  id: m.id,
                  role: m.role as 'user' | 'assistant' | 'system',
                  content: m.content,
                  timestamp: m.timestamp,
                  metadata: m.metadata,
                  replyToId: (m as unknown as Record<string, unknown>).replyToId as string | undefined,
                }
                if (toolCalls && toolCalls.length > 0) {
                  msg.toolCalls = toolCalls
                }
                return msg
              }),
            },
          }))
        } catch (err) {
          console.warn('Failed to load platform chat messages:', err)
        }
      },

      archiveChat: async (botId, chatId) => {
        try {
          await archivePlatformChat(botId, chatId)
          // Remove from local state (archived chats are hidden)
          set((state) => ({
            chats: state.chats.filter((c) => c.id !== chatId),
            activeChatId: state.activeChatId === chatId ? null : state.activeChatId,
          }))
        } catch (err) {
          console.error('Failed to archive chat:', err)
          throw err
        }
      },

      unarchiveChat: async (botId, chatId) => {
        try {
          await unarchivePlatformChat(botId, chatId)
          // Re-sync to get the unarchived chat back
          await get().syncPlatformChats(botId)
        } catch (err) {
          console.error('Failed to unarchive chat:', err)
          throw err
        }
      },

      addMessage: (chatId, message) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: [...(state.messages[chatId] || []), message],
          },
        })),

      updateMessage: (chatId, messageId, content) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: (state.messages[chatId] || []).map((m) =>
              m.id === messageId ? { ...m, content } : m
            ),
          },
        })),

      updateLastAssistantMessage: (chatId, updates) =>
        set((state) => {
          const chatMessages = state.messages[chatId] || []
          let lastAssistantIndex = -1
          for (let i = chatMessages.length - 1; i >= 0; i--) {
            if (chatMessages[i].role === 'assistant') {
              lastAssistantIndex = i
              break
            }
          }
          if (lastAssistantIndex === -1) return state
          return {
            messages: {
              ...state.messages,
              [chatId]: chatMessages.map((m, i) =>
                i === lastAssistantIndex ? { ...m, ...updates } : m
              ),
            },
          }
        }),

      updateLastAssistantMessageMetadata: (chatId, metadata) =>
        set((state) => {
          const chatMessages = state.messages[chatId] || []
          // Find the last assistant message
          let lastAssistantIndex = -1
          for (let i = chatMessages.length - 1; i >= 0; i--) {
            if (chatMessages[i].role === 'assistant') {
              lastAssistantIndex = i
              break
            }
          }
          if (lastAssistantIndex === -1) return state

          return {
            messages: {
              ...state.messages,
              [chatId]: chatMessages.map((m, i) =>
                i === lastAssistantIndex
                  ? { ...m, metadata: { ...m.metadata, ...metadata } }
                  : m
              ),
            },
          }
        }),

      getMessages: (chatId) => {
        const state = get()
        return state.messages[chatId] || []
      },

      getMessageById: (chatId, messageId) => {
        const state = get()
        return (state.messages[chatId] || []).find((m) => m.id === messageId)
      },

      setReplyTo: (message) => set({ replyToMessage: message }),

      clearMessages: (chatId) =>
        set((state) => ({
          messages: {
            ...state.messages,
            [chatId]: [],
          },
        })),

      setThinking: (thinking) => set({ thinking }),

      appendThinking: (content) =>
        set((state) => ({
          thinking: state.thinking ? state.thinking + content : content,
        })),

      addToolCall: (call) =>
        set((state) => ({
          toolCalls: [...state.toolCalls, { ...call, startTime: Date.now() }],
        })),

      updateToolCall: (id, result, success) =>
        set((state) => ({
          toolCalls: state.toolCalls.map((tc) =>
            tc.id === id ? { ...tc, result, success, endTime: Date.now() } : tc
          ),
        })),

      clearToolCalls: () => set({ toolCalls: [] }),

      attachToolCallsToLastMessage: (chatId, toolCalls) =>
        set((state) => {
          const chatMessages = state.messages[chatId] || []
          let lastAssistantIndex = -1
          for (let i = chatMessages.length - 1; i >= 0; i--) {
            if (chatMessages[i].role === 'assistant') {
              lastAssistantIndex = i
              break
            }
          }
          // If no assistant message exists (LLM went straight to tool call),
          // create a placeholder so tool calls aren't lost
          if (lastAssistantIndex === -1) {
            const placeholder: ChatMessage = {
              id: `msg-tools-${Date.now()}`,
              role: 'assistant',
              content: '',
              timestamp: new Date().toISOString(),
              toolCalls: [...toolCalls],
            }
            return {
              messages: {
                ...state.messages,
                [chatId]: [...chatMessages, placeholder],
              },
            }
          }
          return {
            messages: {
              ...state.messages,
              [chatId]: chatMessages.map((m, i) =>
                i === lastAssistantIndex
                  ? { ...m, toolCalls: [...toolCalls] }
                  : m
              ),
            },
          }
        }),

      setLoading: (isLoading) => set({ isLoading }),

      setError: (error) => set({ error }),
    }),
    {
      name: 'cachibot-chats',
      partialize: (state) => ({
        chats: state.chats,
        messages: state.messages,
        // replyToMessage excluded — transient UI state
      }),
    }
  )
)

// =============================================================================
// JOBS STORE
// =============================================================================

interface JobState {
  jobs: Job[]
  activeJobId: string | null

  // Actions
  addJob: (job: Job) => void
  updateJob: (id: string, updates: Partial<Job>) => void
  deleteJob: (id: string) => void
  setActiveJob: (id: string | null) => void
  getJobsByBot: (botId: string) => Job[]
  getActiveJobs: (botId: string) => Job[]
}

export const useJobStore = create<JobState>()(
  persist(
    (set, get) => ({
      jobs: [],
      activeJobId: null,

      addJob: (job) =>
        set((state) => ({
          jobs: [job, ...state.jobs],
        })),

      updateJob: (id, updates) =>
        set((state) => ({
          jobs: state.jobs.map((job) =>
            job.id === id ? { ...job, ...updates } : job
          ),
        })),

      deleteJob: (id) =>
        set((state) => ({
          jobs: state.jobs.filter((job) => job.id !== id),
          activeJobId: state.activeJobId === id ? null : state.activeJobId,
        })),

      setActiveJob: (id) => set({ activeJobId: id }),

      getJobsByBot: (botId) => {
        const state = get()
        return state.jobs
          .filter((job) => job.botId === botId)
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      },

      getActiveJobs: (botId) => {
        const state = get()
        return state.jobs.filter(
          (job) => job.botId === botId && ['pending', 'running'].includes(job.status)
        )
      },
    }),
    {
      name: 'cachibot-jobs',
    }
  )
)

// =============================================================================
// TASKS STORE
// =============================================================================

interface TaskState {
  tasks: Task[]
  activeTaskId: string | null
  filter: {
    status: Task['status'] | 'all'
    priority: Task['priority'] | 'all'
  }

  // Actions
  addTask: (task: Task) => void
  updateTask: (id: string, updates: Partial<Task>) => void
  deleteTask: (id: string) => void
  setActiveTask: (id: string | null) => void
  getTasksByBot: (botId: string) => Task[]
  setFilter: (filter: Partial<TaskState['filter']>) => void
}

export const useTaskStore = create<TaskState>()(
  persist(
    (set, get) => ({
      tasks: [],
      activeTaskId: null,
      filter: {
        status: 'all',
        priority: 'all',
      },

      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),

      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((task) =>
            task.id === id ? { ...task, ...updates } : task
          ),
        })),

      deleteTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((task) => task.id !== id),
          activeTaskId: state.activeTaskId === id ? null : state.activeTaskId,
        })),

      setActiveTask: (id) => set({ activeTaskId: id }),

      getTasksByBot: (botId) => {
        const state = get()
        let tasks = state.tasks.filter((task) => task.botId === botId)

        if (state.filter.status !== 'all') {
          tasks = tasks.filter((task) => task.status === state.filter.status)
        }
        if (state.filter.priority !== 'all') {
          tasks = tasks.filter((task) => task.priority === state.filter.priority)
        }

        // Sort: todo first, then in_progress, blocked, done
        const statusOrder = { todo: 0, in_progress: 1, blocked: 2, done: 3 }
        const priorityOrder = { high: 0, medium: 1, low: 2 }

        return tasks.sort((a, b) => {
          const statusDiff = statusOrder[a.status] - statusOrder[b.status]
          if (statusDiff !== 0) return statusDiff
          return priorityOrder[a.priority] - priorityOrder[b.priority]
        })
      },

      setFilter: (filter) =>
        set((state) => ({
          filter: { ...state.filter, ...filter },
        })),
    }),
    {
      name: 'cachibot-tasks',
    }
  )
)

// =============================================================================
// WORK STORE (New Work Management System)
// =============================================================================

interface WorkState {
  work: Work[]
  activeWorkId: string | null
  filter: {
    status: WorkStatus | 'all'
    priority: Priority | 'all'
  }

  // Actions
  addWork: (work: Work) => void
  updateWork: (id: string, updates: Partial<Work>) => void
  deleteWork: (id: string) => void
  setActiveWork: (id: string | null) => void
  getWorkByBot: (botId: string) => Work[]
  getActiveWork: (botId: string) => Work[]
  setFilter: (filter: Partial<WorkState['filter']>) => void
}

export const useWorkStore = create<WorkState>()(
  persist(
    (set, get) => ({
      work: [],
      activeWorkId: null,
      filter: {
        status: 'all',
        priority: 'all',
      },

      addWork: (work) =>
        set((state) => ({
          work: [work, ...state.work],
        })),

      updateWork: (id, updates) =>
        set((state) => ({
          work: state.work.map((w) =>
            w.id === id ? { ...w, ...updates } : w
          ),
        })),

      deleteWork: (id) =>
        set((state) => ({
          work: state.work.filter((w) => w.id !== id),
          activeWorkId: state.activeWorkId === id ? null : state.activeWorkId,
        })),

      setActiveWork: (id) => set({ activeWorkId: id }),

      getWorkByBot: (botId) => {
        const state = get()
        let items = state.work.filter((w) => w.botId === botId)

        if (state.filter.status !== 'all') {
          items = items.filter((w) => w.status === state.filter.status)
        }
        if (state.filter.priority !== 'all') {
          items = items.filter((w) => w.priority === state.filter.priority)
        }

        // Sort by priority, then by created date
        const priorityOrder = { urgent: 0, high: 1, normal: 2, low: 3 }
        return items.sort((a, b) => {
          const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
          if (priorityDiff !== 0) return priorityDiff
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        })
      },

      getActiveWork: (botId) => {
        const state = get()
        return state.work.filter(
          (w) => w.botId === botId && ['pending', 'in_progress'].includes(w.status)
        )
      },

      setFilter: (filter) =>
        set((state) => ({
          filter: { ...state.filter, ...filter },
        })),
    }),
    {
      name: 'cachibot-work',
    }
  )
)

// =============================================================================
// WORK TASKS STORE
// =============================================================================

interface WorkTaskState {
  tasks: WorkTask[]
  activeTaskId: string | null

  // Actions
  addTask: (task: WorkTask) => void
  addTasks: (tasks: WorkTask[]) => void
  updateTask: (id: string, updates: Partial<WorkTask>) => void
  deleteTask: (id: string) => void
  setActiveTask: (id: string | null) => void
  getTasksByWork: (workId: string) => WorkTask[]
  getReadyTasks: (workId: string) => WorkTask[]
  clearTasksForWork: (workId: string) => void
}

export const useWorkTaskStore = create<WorkTaskState>()(
  persist(
    (set, get) => ({
      tasks: [],
      activeTaskId: null,

      addTask: (task) =>
        set((state) => ({
          tasks: [...state.tasks, task],
        })),

      addTasks: (tasks) =>
        set((state) => ({
          tasks: [...state.tasks, ...tasks],
        })),

      updateTask: (id, updates) =>
        set((state) => ({
          tasks: state.tasks.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        })),

      deleteTask: (id) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.id !== id),
          activeTaskId: state.activeTaskId === id ? null : state.activeTaskId,
        })),

      setActiveTask: (id) => set({ activeTaskId: id }),

      getTasksByWork: (workId) => {
        const state = get()
        return state.tasks
          .filter((t) => t.workId === workId)
          .sort((a, b) => a.order - b.order)
      },

      getReadyTasks: (workId) => {
        const state = get()
        const allTasks = state.tasks.filter((t) => t.workId === workId)
        const completedIds = new Set(
          allTasks.filter((t) => t.status === 'completed').map((t) => t.id)
        )

        return allTasks.filter((t) => {
          if (t.status !== 'pending') return false
          return t.dependsOn.every((depId) => completedIds.has(depId))
        })
      },

      clearTasksForWork: (workId) =>
        set((state) => ({
          tasks: state.tasks.filter((t) => t.workId !== workId),
        })),
    }),
    {
      name: 'cachibot-work-tasks',
    }
  )
)

// =============================================================================
// WORK JOBS STORE
// =============================================================================

interface WorkJobState {
  jobs: WorkJob[]
  activeJobId: string | null

  // Actions
  addJob: (job: WorkJob) => void
  updateJob: (id: string, updates: Partial<WorkJob>) => void
  appendLog: (jobId: string, level: string, message: string, data?: unknown) => void
  deleteJob: (id: string) => void
  setActiveJob: (id: string | null) => void
  getJobsByTask: (taskId: string) => WorkJob[]
  getJobsByWork: (workId: string) => WorkJob[]
  getRunningJobs: (botId?: string) => WorkJob[]
  clearJobsForWork: (workId: string) => void
}

export const useWorkJobStore = create<WorkJobState>()(
  persist(
    (set, get) => ({
      jobs: [],
      activeJobId: null,

      addJob: (job) =>
        set((state) => ({
          jobs: [job, ...state.jobs],
        })),

      updateJob: (id, updates) =>
        set((state) => ({
          jobs: state.jobs.map((j) =>
            j.id === id ? { ...j, ...updates } : j
          ),
        })),

      appendLog: (jobId, level, message, data) =>
        set((state) => ({
          jobs: state.jobs.map((j) =>
            j.id === jobId
              ? {
                  ...j,
                  logs: [
                    ...j.logs,
                    {
                      timestamp: new Date().toISOString(),
                      level: level as 'debug' | 'info' | 'warn' | 'error',
                      message,
                      data,
                    },
                  ],
                }
              : j
          ),
        })),

      deleteJob: (id) =>
        set((state) => ({
          jobs: state.jobs.filter((j) => j.id !== id),
          activeJobId: state.activeJobId === id ? null : state.activeJobId,
        })),

      setActiveJob: (id) => set({ activeJobId: id }),

      getJobsByTask: (taskId) => {
        const state = get()
        return state.jobs
          .filter((j) => j.taskId === taskId)
          .sort((a, b) => a.attempt - b.attempt)
      },

      getJobsByWork: (workId) => {
        const state = get()
        return state.jobs
          .filter((j) => j.workId === workId)
          .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
      },

      getRunningJobs: (botId) => {
        const state = get()
        return state.jobs.filter((j) => {
          if (j.status !== 'running') return false
          if (botId && j.botId !== botId) return false
          return true
        })
      },

      clearJobsForWork: (workId) =>
        set((state) => ({
          jobs: state.jobs.filter((j) => j.workId !== workId),
        })),
    }),
    {
      name: 'cachibot-work-jobs',
    }
  )
)

// =============================================================================
// TODO STORE
// =============================================================================

interface TodoState {
  todos: Todo[]
  activeTodoId: string | null
  filter: {
    status: TodoStatus | 'all'
    priority: Priority | 'all'
  }

  // Actions
  addTodo: (todo: Todo) => void
  updateTodo: (id: string, updates: Partial<Todo>) => void
  deleteTodo: (id: string) => void
  setActiveTodo: (id: string | null) => void
  getTodosByBot: (botId: string) => Todo[]
  getOpenTodos: (botId: string) => Todo[]
  markDone: (id: string) => void
  markConverted: (id: string, workId?: string, taskId?: string) => void
  setFilter: (filter: Partial<TodoState['filter']>) => void
}

export const useTodoStore = create<TodoState>()(
  persist(
    (set, get) => ({
      todos: [],
      activeTodoId: null,
      filter: {
        status: 'all',
        priority: 'all',
      },

      addTodo: (todo) =>
        set((state) => ({
          todos: [todo, ...state.todos],
        })),

      updateTodo: (id, updates) =>
        set((state) => ({
          todos: state.todos.map((t) =>
            t.id === id ? { ...t, ...updates } : t
          ),
        })),

      deleteTodo: (id) =>
        set((state) => ({
          todos: state.todos.filter((t) => t.id !== id),
          activeTodoId: state.activeTodoId === id ? null : state.activeTodoId,
        })),

      setActiveTodo: (id) => set({ activeTodoId: id }),

      getTodosByBot: (botId) => {
        const state = get()
        let items = state.todos.filter((t) => t.botId === botId)

        if (state.filter.status !== 'all') {
          items = items.filter((t) => t.status === state.filter.status)
        }
        if (state.filter.priority !== 'all') {
          items = items.filter((t) => t.priority === state.filter.priority)
        }

        const priorityOrder = { urgent: 0, high: 1, normal: 2, low: 3 }
        return items.sort((a, b) => {
          const priorityDiff = priorityOrder[a.priority] - priorityOrder[b.priority]
          if (priorityDiff !== 0) return priorityDiff
          return new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        })
      },

      getOpenTodos: (botId) => {
        const state = get()
        return state.todos.filter((t) => t.botId === botId && t.status === 'open')
      },

      markDone: (id) =>
        set((state) => ({
          todos: state.todos.map((t) =>
            t.id === id
              ? { ...t, status: 'done' as TodoStatus, completedAt: new Date().toISOString() }
              : t
          ),
        })),

      markConverted: (id, workId, taskId) =>
        set((state) => ({
          todos: state.todos.map((t) =>
            t.id === id
              ? {
                  ...t,
                  status: 'done' as TodoStatus,
                  completedAt: new Date().toISOString(),
                  convertedToWorkId: workId,
                  convertedToTaskId: taskId,
                }
              : t
          ),
        })),

      setFilter: (filter) =>
        set((state) => ({
          filter: { ...state.filter, ...filter },
        })),
    }),
    {
      name: 'cachibot-todos',
    }
  )
)

// =============================================================================
// FUNCTION STORE (Reusable Templates)
// =============================================================================

interface FunctionState {
  functions: BotFunction[]
  activeFunctionId: string | null

  // Actions
  addFunction: (fn: BotFunction) => void
  updateFunction: (id: string, updates: Partial<BotFunction>) => void
  deleteFunction: (id: string) => void
  setActiveFunction: (id: string | null) => void
  getFunctionsByBot: (botId: string) => BotFunction[]
  incrementRunCount: (id: string, success: boolean) => void
}

export const useFunctionStore = create<FunctionState>()(
  persist(
    (set, get) => ({
      functions: [],
      activeFunctionId: null,

      addFunction: (fn) =>
        set((state) => ({
          functions: [...state.functions, fn],
        })),

      updateFunction: (id, updates) =>
        set((state) => ({
          functions: state.functions.map((f) =>
            f.id === id ? { ...f, ...updates, updatedAt: new Date().toISOString() } : f
          ),
        })),

      deleteFunction: (id) =>
        set((state) => ({
          functions: state.functions.filter((f) => f.id !== id),
          activeFunctionId: state.activeFunctionId === id ? null : state.activeFunctionId,
        })),

      setActiveFunction: (id) => set({ activeFunctionId: id }),

      getFunctionsByBot: (botId) => {
        const state = get()
        return state.functions
          .filter((f) => f.botId === botId)
          .sort((a, b) => a.name.localeCompare(b.name))
      },

      incrementRunCount: (id, success) =>
        set((state) => ({
          functions: state.functions.map((f) => {
            if (f.id !== id) return f
            const newCount = f.runCount + 1
            const oldSuccesses = f.runCount * f.successRate
            const newSuccesses = oldSuccesses + (success ? 1 : 0)
            const newRate = newSuccesses / newCount
            return {
              ...f,
              runCount: newCount,
              successRate: newRate,
              lastRunAt: new Date().toISOString(),
              updatedAt: new Date().toISOString(),
            }
          }),
        })),
    }),
    {
      name: 'cachibot-functions',
    }
  )
)

// =============================================================================
// SCHEDULE STORE (Cron/Timer Triggers)
// =============================================================================

interface ScheduleState {
  schedules: Schedule[]
  activeScheduleId: string | null

  // Actions
  addSchedule: (schedule: Schedule) => void
  updateSchedule: (id: string, updates: Partial<Schedule>) => void
  deleteSchedule: (id: string) => void
  setActiveSchedule: (id: string | null) => void
  getSchedulesByBot: (botId: string) => Schedule[]
  getEnabledSchedules: (botId?: string) => Schedule[]
  toggleEnabled: (id: string) => void
  recordRun: (id: string, nextRunAt?: string) => void
}

export const useScheduleStore = create<ScheduleState>()(
  persist(
    (set, get) => ({
      schedules: [],
      activeScheduleId: null,

      addSchedule: (schedule) =>
        set((state) => ({
          schedules: [...state.schedules, schedule],
        })),

      updateSchedule: (id, updates) =>
        set((state) => ({
          schedules: state.schedules.map((s) =>
            s.id === id ? { ...s, ...updates, updatedAt: new Date().toISOString() } : s
          ),
        })),

      deleteSchedule: (id) =>
        set((state) => ({
          schedules: state.schedules.filter((s) => s.id !== id),
          activeScheduleId: state.activeScheduleId === id ? null : state.activeScheduleId,
        })),

      setActiveSchedule: (id) => set({ activeScheduleId: id }),

      getSchedulesByBot: (botId) => {
        const state = get()
        return state.schedules
          .filter((s) => s.botId === botId)
          .sort((a, b) => a.name.localeCompare(b.name))
      },

      getEnabledSchedules: (botId) => {
        const state = get()
        return state.schedules.filter((s) => {
          if (!s.enabled) return false
          if (botId && s.botId !== botId) return false
          return true
        })
      },

      toggleEnabled: (id) =>
        set((state) => ({
          schedules: state.schedules.map((s) =>
            s.id === id
              ? { ...s, enabled: !s.enabled, updatedAt: new Date().toISOString() }
              : s
          ),
        })),

      recordRun: (id, nextRunAt) =>
        set((state) => ({
          schedules: state.schedules.map((s) =>
            s.id === id
              ? {
                  ...s,
                  runCount: s.runCount + 1,
                  lastRunAt: new Date().toISOString(),
                  nextRunAt: nextRunAt || s.nextRunAt,
                  updatedAt: new Date().toISOString(),
                }
              : s
          ),
        })),
    }),
    {
      name: 'cachibot-schedules',
    }
  )
)

/**
 * Side-task store (principle 9).
 *
 * Fed by GET /api/bots/{id}/side-tasks (per bot, optionally filtered by
 * parent chat) and kept live by `side_task_update` WebSocket events, which
 * carry the full record on every state change. Deliberately NOT persisted:
 * side tasks live on the server (they survive restarts there), so the store
 * re-fetches on demand and treats the WS events as the source of truth.
 */

import { create } from 'zustand'
import {
  discardSideTask,
  listSideTasks,
  retryMergeSideTask,
  startSideTask,
  stopSideTask,
} from '../api/side-tasks'
import type { SideTask } from '../types'

interface SideTasksState {
  /** All known side tasks, keyed by side-task id. */
  byId: Record<string, SideTask>
  /** botId -> the full list was loaded at least once. */
  loadedFor: Record<string, boolean>
  /** botId -> a fetch is in flight (dedupes concurrent ensure calls). */
  loadingFor: Record<string, boolean>

  /** Load the side-task list for a bot once (call on view mount). */
  ensureForBot: (botId: string) => Promise<void>
  /** Force a reload (e.g. after the WebSocket reconnects). */
  refreshForBot: (botId: string) => Promise<void>
  /** Insert or replace one record (from the API or a WS event). */
  upsert: (task: SideTask) => void

  start: (botId: string, chatId: string, prompt: string, title?: string) => Promise<SideTask>
  stop: (botId: string, sideTaskId: string) => Promise<void>
  retryMerge: (botId: string, sideTaskId: string) => Promise<void>
  discard: (botId: string, sideTaskId: string) => Promise<void>
}

export const useSideTasksStore = create<SideTasksState>()((set, get) => ({
  byId: {},
  loadedFor: {},
  loadingFor: {},

  ensureForBot: async (botId) => {
    if (get().loadedFor[botId] || get().loadingFor[botId]) return
    await get().refreshForBot(botId)
  },

  refreshForBot: async (botId) => {
    set((state) => ({ loadingFor: { ...state.loadingFor, [botId]: true } }))
    try {
      const tasks = await listSideTasks(botId)
      set((state) => {
        // Replace this bot's records; keep other bots' records untouched.
        const byId = { ...state.byId }
        for (const key of Object.keys(byId)) {
          if (byId[key].botId === botId) delete byId[key]
        }
        for (const task of tasks) byId[task.id] = task
        return {
          byId,
          loadedFor: { ...state.loadedFor, [botId]: true },
          loadingFor: { ...state.loadingFor, [botId]: false },
        }
      })
    } catch {
      set((state) => ({ loadingFor: { ...state.loadingFor, [botId]: false } }))
    }
  },

  upsert: (task) =>
    set((state) => ({
      byId: { ...state.byId, [task.id]: task },
      loadedFor: { ...state.loadedFor, [task.botId]: true },
    })),

  start: async (botId, chatId, prompt, title) => {
    const task = await startSideTask(botId, chatId, { prompt, title })
    get().upsert(task)
    return task
  },

  stop: async (botId, sideTaskId) => {
    await stopSideTask(botId, sideTaskId)
  },

  retryMerge: async (botId, sideTaskId) => {
    const task = await retryMergeSideTask(botId, sideTaskId)
    get().upsert(task)
  },

  discard: async (botId, sideTaskId) => {
    const task = await discardSideTask(botId, sideTaskId)
    get().upsert(task)
  },
}))

/** All side tasks of one parent chat, oldest first (stable card order). */
export function selectSideTasksByParent(state: SideTasksState, parentChatId: string): SideTask[] {
  return Object.values(state.byId)
    .filter((t) => t.parentChatId === parentChatId)
    .sort((a, b) => a.createdAt.localeCompare(b.createdAt))
}

/** The side task whose own chat is `chatId`, if any. */
export function selectSideTaskByChatId(state: SideTasksState, chatId: string): SideTask | undefined {
  return Object.values(state.byId).find((t) => t.chatId === chatId)
}

/**
 * Group helper records by their group id. Helpers created together by the
 * bot share one group; ungrouped records stay singles. The counts shown on
 * the group card use the same buckets as the backend's group summary:
 * done covers done + merged, waiting is waiting_for_slot.
 */
export function partitionSideTasks(tasks: SideTask[]): {
  singles: SideTask[]
  groups: Array<{ groupId: string; title: string | null; items: SideTask[] }>
} {
  const singles: SideTask[] = []
  const byGroup = new Map<string, SideTask[]>()
  for (const task of tasks) {
    if (task.kind === 'helper' && task.groupId) {
      const list = byGroup.get(task.groupId) ?? []
      list.push(task)
      byGroup.set(task.groupId, list)
    } else {
      singles.push(task)
    }
  }
  const groups = [...byGroup.entries()].map(([groupId, items]) => ({
    groupId,
    title: items[0]?.groupTitle ?? null,
    items: items.sort((a, b) => a.createdAt.localeCompare(b.createdAt)),
  }))
  groups.sort((a, b) => a.items[0].createdAt.localeCompare(b.items[0].createdAt))
  return { singles, groups }
}

/** "done" for group counts covers done + merged (matches the group endpoint). */
export function sideTaskDone(tasks: SideTask[]): number {
  return tasks.filter((t) => t.status === 'done' || t.status === 'merged').length
}

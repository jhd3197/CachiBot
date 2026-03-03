/**
 * Zustand store for workspace state management.
 *
 * Tracks the active workspace plugin, available workspaces for the current bot,
 * and workspace task progress from the agent's plan_tasks / update_task tools.
 * Only activeWorkspace and workspaceConfig are persisted; taskProgress is transient.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'

export interface WorkspaceInfo {
  pluginName: string
  capabilityKey: string | null
  displayName: string
  icon: string
  description: string
  toolbar: string[]
  accentColor: string
  defaultArtifactType: string | null
  autoOpenPanel: boolean
}

export interface TaskItem {
  description: string
  status: 'pending' | 'in_progress' | 'done' | 'failed'
}

export interface TaskProgress {
  tasks: TaskItem[]
  completedCount: number
  totalCount: number
}

export interface ProgressPayload {
  tasks?: TaskItem[]
  taskNumber?: number
  status?: string
}

interface WorkspaceState {
  activeWorkspace: string | null
  workspaceConfig: WorkspaceInfo | null
  taskProgress: TaskProgress | null
  availableWorkspaces: WorkspaceInfo[]

  setActiveWorkspace: (ws: WorkspaceInfo | null) => void
  clearWorkspace: () => void
  setAvailableWorkspaces: (list: WorkspaceInfo[]) => void
  applyProgress: (action: string, data: ProgressPayload) => void
  clearProgress: () => void
}

function countCompleted(tasks: TaskItem[]): number {
  return tasks.filter(t => t.status === 'done').length
}

export const useWorkspaceStore = create<WorkspaceState>()(
  persist(
    (set) => ({
      activeWorkspace: null,
      workspaceConfig: null,
      taskProgress: null,
      availableWorkspaces: [],

      setActiveWorkspace: (ws) =>
        set({
          activeWorkspace: ws?.pluginName ?? null,
          workspaceConfig: ws,
          taskProgress: null,
        }),

      clearWorkspace: () =>
        set({
          activeWorkspace: null,
          workspaceConfig: null,
          taskProgress: null,
        }),

      setAvailableWorkspaces: (list) =>
        set({ availableWorkspaces: list }),

      applyProgress: (action, data) =>
        set((state) => {
          if (action === 'plan' && data.tasks) {
            const tasks = data.tasks
            return {
              taskProgress: {
                tasks,
                completedCount: countCompleted(tasks),
                totalCount: tasks.length,
              },
            }
          }

          if (action === 'update' && data.taskNumber !== undefined && data.status && state.taskProgress) {
            const idx = data.taskNumber - 1 // 1-based to 0-based
            if (idx < 0 || idx >= state.taskProgress.tasks.length) return state
            const tasks = [...state.taskProgress.tasks]
            tasks[idx] = { ...tasks[idx], status: data.status as TaskItem['status'] }
            return {
              taskProgress: {
                tasks,
                completedCount: countCompleted(tasks),
                totalCount: tasks.length,
              },
            }
          }

          return state
        }),

      clearProgress: () =>
        set({ taskProgress: null }),
    }),
    {
      name: 'cachibot-workspace',
      partialize: (state) => ({
        activeWorkspace: state.activeWorkspace,
        workspaceConfig: state.workspaceConfig,
        // Don't persist taskProgress — it's transient per-session
      }),
    }
  )
)

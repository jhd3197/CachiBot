import { create } from 'zustand'
import type { Script, ScriptVersion } from '../api/automations'
import type { ExecutionLog } from '../api/execution-log'
import type { AutomationSection } from '../types'

interface AutomationsState {
  // Scripts
  scripts: Script[]
  activeScriptId: string | null
  scriptVersions: Record<string, ScriptVersion[]>

  // Execution logs
  executions: ExecutionLog[]
  activeExecutionId: string | null

  // UI
  section: AutomationSection
  loading: boolean
  error: string | null

  // Actions
  setScripts: (scripts: Script[]) => void
  addScript: (script: Script) => void
  updateScript: (id: string, updates: Partial<Script>) => void
  removeScript: (id: string) => void
  setActiveScript: (id: string | null) => void
  setScriptVersions: (scriptId: string, versions: ScriptVersion[]) => void

  setExecutions: (executions: ExecutionLog[]) => void
  addExecution: (execution: ExecutionLog) => void
  updateExecution: (id: string, updates: Partial<ExecutionLog>) => void
  setActiveExecution: (id: string | null) => void

  setSection: (section: AutomationSection) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
}

export const useAutomationsStore = create<AutomationsState>()((set) => ({
  scripts: [],
  activeScriptId: null,
  scriptVersions: {},

  executions: [],
  activeExecutionId: null,

  section: 'all',
  loading: false,
  error: null,

  setScripts: (scripts) => set({ scripts }),
  addScript: (script) => set((s) => ({ scripts: [script, ...s.scripts] })),
  updateScript: (id, updates) =>
    set((s) => ({
      scripts: s.scripts.map((sc) => (sc.id === id ? { ...sc, ...updates } : sc)),
    })),
  removeScript: (id) =>
    set((s) => ({
      scripts: s.scripts.filter((sc) => sc.id !== id),
      activeScriptId: s.activeScriptId === id ? null : s.activeScriptId,
    })),
  setActiveScript: (activeScriptId) => set({ activeScriptId }),
  setScriptVersions: (scriptId, versions) =>
    set((s) => ({
      scriptVersions: { ...s.scriptVersions, [scriptId]: versions },
    })),

  setExecutions: (executions) => set({ executions }),
  addExecution: (execution) => set((s) => ({ executions: [execution, ...s.executions] })),
  updateExecution: (id, updates) =>
    set((s) => ({
      executions: s.executions.map((e) => (e.id === id ? { ...e, ...updates } : e)),
    })),
  setActiveExecution: (activeExecutionId) => set({ activeExecutionId }),

  setSection: (section) => set({ section }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
}))

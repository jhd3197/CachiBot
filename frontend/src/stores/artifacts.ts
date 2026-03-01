/**
 * Zustand store for artifact state management.
 *
 * Tracks artifacts produced by tool skills, manages the active artifact
 * displayed in the side panel, and handles artifact updates.
 * Persisted to localStorage so artifacts survive page reloads.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import type { Artifact, ArtifactUpdatePayload } from '../types'

interface ArtifactsState {
  /** All artifacts indexed by ID */
  artifacts: Record<string, Artifact>
  /** Currently displayed artifact ID */
  activeArtifactId: string | null
  /** Whether the artifact panel is open */
  panelOpen: boolean
  /** Artifact panel width ratio (0-1), default 0.65 */
  panelWidthRatio: number

  /** Add a new artifact */
  addArtifact: (artifact: Artifact) => void
  /** Update an existing artifact (partial) */
  updateArtifact: (id: string, updates: Partial<Artifact>) => void
  /** Apply an artifact update payload from WS */
  applyArtifactUpdate: (update: ArtifactUpdatePayload) => void
  /** Set the active artifact and open the panel */
  setActive: (id: string | null) => void
  /** Close the panel */
  closePanel: () => void
  /** Clear all artifacts for a given chat */
  clearForChat: (chatId: string) => void
  /** Set panel width ratio */
  setPanelWidthRatio: (ratio: number) => void
  /** Get artifact by ID */
  getArtifact: (id: string) => Artifact | undefined
  /** Get all artifacts for a chat */
  getArtifactsForChat: (chatId: string) => Artifact[]
  /** Get all artifacts for a message */
  getArtifactsForMessage: (messageId: string) => Artifact[]
}

export const useArtifactsStore = create<ArtifactsState>()(
  persist(
    (set, get) => ({
      artifacts: {},
      activeArtifactId: null,
      panelOpen: false,
      panelWidthRatio: 0.65,

      addArtifact: (artifact) =>
        set((state) => ({
          artifacts: { ...state.artifacts, [artifact.id]: artifact },
          // Auto-open the panel when a new artifact arrives
          activeArtifactId: artifact.id,
          panelOpen: true,
        })),

      updateArtifact: (id, updates) =>
        set((state) => {
          const existing = state.artifacts[id]
          if (!existing) return state
          return {
            artifacts: {
              ...state.artifacts,
              [id]: { ...existing, ...updates },
            },
          }
        }),

      applyArtifactUpdate: (update) =>
        set((state) => {
          const existing = state.artifacts[update.id]
          if (!existing) return state
          const updated: Artifact = { ...existing }
          if (update.content !== undefined) updated.content = update.content
          if (update.title !== undefined) updated.title = update.title
          if (update.version !== undefined) updated.version = update.version
          if (update.metadata !== undefined) {
            updated.metadata = { ...updated.metadata, ...update.metadata }
          }
          return {
            artifacts: { ...state.artifacts, [update.id]: updated },
          }
        }),

      setActive: (id) =>
        set({
          activeArtifactId: id,
          panelOpen: id !== null,
        }),

      closePanel: () =>
        set({
          activeArtifactId: null,
          panelOpen: false,
        }),

      clearForChat: (chatId) =>
        set((state) => {
          const filtered: Record<string, Artifact> = {}
          for (const [id, artifact] of Object.entries(state.artifacts)) {
            if (artifact.chatId !== chatId) {
              filtered[id] = artifact
            }
          }
          return {
            artifacts: filtered,
            activeArtifactId:
              state.activeArtifactId && filtered[state.activeArtifactId]
                ? state.activeArtifactId
                : null,
            panelOpen:
              state.activeArtifactId && filtered[state.activeArtifactId]
                ? state.panelOpen
                : false,
          }
        }),

      setPanelWidthRatio: (ratio) =>
        set({ panelWidthRatio: Math.max(0.2, Math.min(0.7, ratio)) }),

      getArtifact: (id) => get().artifacts[id],

      getArtifactsForChat: (chatId) =>
        Object.values(get().artifacts).filter((a) => a.chatId === chatId),

      getArtifactsForMessage: (messageId) =>
        Object.values(get().artifacts).filter((a) => a.messageId === messageId),
    }),
    {
      name: 'cachibot-artifacts',
      partialize: (state) => ({
        artifacts: state.artifacts,
        panelWidthRatio: state.panelWidthRatio,
        // Don't persist panel open/active state — start closed on reload
      }),
    }
  )
)

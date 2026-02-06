/**
 * Knowledge Base Store
 *
 * Manages documents and custom instructions state per bot.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  knowledgeApi,
  type DocumentResponse,
} from '../api/knowledge'

export type { DocumentResponse } from '../api/knowledge'

// =============================================================================
// TYPES
// =============================================================================

export interface KnowledgeState {
  // Documents per bot: botId -> documents[]
  documents: Record<string, DocumentResponse[]>
  // Instructions per bot: botId -> content
  instructions: Record<string, string>
  // Loading states
  loadingDocuments: Record<string, boolean>
  loadingInstructions: Record<string, boolean>
  // Upload state
  uploadingBots: Set<string>
  // Error state
  error: string | null

  // Document actions
  loadDocuments: (botId: string) => Promise<void>
  uploadDocument: (botId: string, file: File) => Promise<string>
  deleteDocument: (botId: string, documentId: string) => Promise<void>
  refreshDocument: (botId: string, documentId: string) => Promise<void>
  getDocuments: (botId: string) => DocumentResponse[]

  // Instruction actions
  loadInstructions: (botId: string) => Promise<void>
  updateInstructions: (botId: string, content: string) => Promise<void>
  deleteInstructions: (botId: string) => Promise<void>
  getInstructions: (botId: string) => string

  // Utility
  clearError: () => void
}

// =============================================================================
// STORE
// =============================================================================

export const useKnowledgeStore = create<KnowledgeState>()(
  persist(
    (set, get) => ({
      documents: {},
      instructions: {},
      loadingDocuments: {},
      loadingInstructions: {},
      uploadingBots: new Set(),
      error: null,

      // ===== DOCUMENTS =====

      loadDocuments: async (botId: string) => {
        set((state) => ({
          loadingDocuments: { ...state.loadingDocuments, [botId]: true },
          error: null,
        }))

        try {
          const docs = await knowledgeApi.documents.list(botId)
          set((state) => ({
            documents: { ...state.documents, [botId]: docs },
            loadingDocuments: { ...state.loadingDocuments, [botId]: false },
          }))
        } catch (error) {
          set((state) => ({
            loadingDocuments: { ...state.loadingDocuments, [botId]: false },
            error: error instanceof Error ? error.message : 'Failed to load documents',
          }))
        }
      },

      uploadDocument: async (botId: string, file: File) => {
        set((state) => ({
          uploadingBots: new Set([...state.uploadingBots, botId]),
          error: null,
        }))

        try {
          const result = await knowledgeApi.documents.upload(botId, file)

          // Refresh document list
          await get().loadDocuments(botId)

          set((state) => {
            const newUploading = new Set(state.uploadingBots)
            newUploading.delete(botId)
            return { uploadingBots: newUploading }
          })

          return result.document_id
        } catch (error) {
          set((state) => {
            const newUploading = new Set(state.uploadingBots)
            newUploading.delete(botId)
            return {
              uploadingBots: newUploading,
              error: error instanceof Error ? error.message : 'Upload failed',
            }
          })
          throw error
        }
      },

      deleteDocument: async (botId: string, documentId: string) => {
        try {
          await knowledgeApi.documents.delete(botId, documentId)

          // Remove from local state
          set((state) => ({
            documents: {
              ...state.documents,
              [botId]: (state.documents[botId] || []).filter((d) => d.id !== documentId),
            },
          }))
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Delete failed',
          })
          throw error
        }
      },

      refreshDocument: async (botId: string, documentId: string) => {
        try {
          const doc = await knowledgeApi.documents.get(botId, documentId)

          set((state) => ({
            documents: {
              ...state.documents,
              [botId]: (state.documents[botId] || []).map((d) =>
                d.id === documentId ? doc : d
              ),
            },
          }))
        } catch {
          // Silently fail - document may have been deleted
        }
      },

      getDocuments: (botId: string) => {
        return get().documents[botId] || []
      },

      // ===== INSTRUCTIONS =====

      loadInstructions: async (botId: string) => {
        set((state) => ({
          loadingInstructions: { ...state.loadingInstructions, [botId]: true },
          error: null,
        }))

        try {
          const result = await knowledgeApi.instructions.get(botId)
          set((state) => ({
            instructions: { ...state.instructions, [botId]: result.content },
            loadingInstructions: { ...state.loadingInstructions, [botId]: false },
          }))
        } catch (error) {
          set((state) => ({
            loadingInstructions: { ...state.loadingInstructions, [botId]: false },
            error: error instanceof Error ? error.message : 'Failed to load instructions',
          }))
        }
      },

      updateInstructions: async (botId: string, content: string) => {
        try {
          await knowledgeApi.instructions.update(botId, content)
          set((state) => ({
            instructions: { ...state.instructions, [botId]: content },
          }))
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Update failed',
          })
          throw error
        }
      },

      deleteInstructions: async (botId: string) => {
        try {
          await knowledgeApi.instructions.delete(botId)
          set((state) => ({
            instructions: { ...state.instructions, [botId]: '' },
          }))
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Delete failed',
          })
          throw error
        }
      },

      getInstructions: (botId: string) => {
        return get().instructions[botId] || ''
      },

      // ===== UTILITY =====

      clearError: () => set({ error: null }),
    }),
    {
      name: 'cachibot-knowledge',
      // Only persist documents and instructions, not loading/error states
      partialize: (state) => ({
        documents: state.documents,
        instructions: state.instructions,
      }),
    }
  )
)

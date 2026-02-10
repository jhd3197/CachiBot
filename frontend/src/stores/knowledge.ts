/**
 * Knowledge Base Store
 *
 * Manages documents, custom instructions, notes, and KB stats per bot.
 */

import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  knowledgeApi,
  type DocumentResponse,
  type NoteResponse,
  type NoteCreate,
  type NoteUpdate,
  type KnowledgeStats,
  type SearchResult,
  type ChunkPreview,
} from '../api/knowledge'

export type { DocumentResponse, NoteResponse, KnowledgeStats, SearchResult, ChunkPreview } from '../api/knowledge'

// =============================================================================
// TYPES
// =============================================================================

export interface KnowledgeState {
  // Documents per bot: botId -> documents[]
  documents: Record<string, DocumentResponse[]>
  // Instructions per bot: botId -> content
  instructions: Record<string, string>
  // Notes per bot: botId -> notes[]
  notes: Record<string, NoteResponse[]>
  // All tags per bot: botId -> tags[]
  allTags: Record<string, string[]>
  // Stats per bot
  stats: Record<string, KnowledgeStats>
  // Search results
  searchResults: SearchResult[]
  // Document chunks: documentId -> chunks[]
  documentChunks: Record<string, ChunkPreview[]>
  // Loading states
  loadingDocuments: Record<string, boolean>
  loadingInstructions: Record<string, boolean>
  loadingNotes: Record<string, boolean>
  loadingStats: Record<string, boolean>
  loadingSearch: boolean
  loadingChunks: Record<string, boolean>
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
  retryDocument: (botId: string, documentId: string) => Promise<void>
  loadDocumentChunks: (botId: string, documentId: string) => Promise<void>

  // Instruction actions
  loadInstructions: (botId: string) => Promise<void>
  updateInstructions: (botId: string, content: string) => Promise<void>
  deleteInstructions: (botId: string) => Promise<void>
  getInstructions: (botId: string) => string

  // Notes actions
  loadNotes: (botId: string, tags?: string, search?: string) => Promise<void>
  createNote: (botId: string, data: NoteCreate) => Promise<NoteResponse>
  updateNote: (botId: string, noteId: string, data: NoteUpdate) => Promise<void>
  deleteNote: (botId: string, noteId: string) => Promise<void>
  loadTags: (botId: string) => Promise<void>

  // Stats & search
  loadStats: (botId: string) => Promise<void>
  searchKnowledge: (botId: string, query: string) => Promise<void>

  // Utility
  clearError: () => void
  clearSearchResults: () => void
}

// =============================================================================
// STORE
// =============================================================================

export const useKnowledgeStore = create<KnowledgeState>()(
  persist(
    (set, get) => ({
      documents: {},
      instructions: {},
      notes: {},
      allTags: {},
      stats: {},
      searchResults: [],
      documentChunks: {},
      loadingDocuments: {},
      loadingInstructions: {},
      loadingNotes: {},
      loadingStats: {},
      loadingSearch: false,
      loadingChunks: {},
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

      retryDocument: async (botId: string, documentId: string) => {
        try {
          await knowledgeApi.documents.retry(botId, documentId)
          // Refresh to show new status
          await get().loadDocuments(botId)
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Retry failed',
          })
          throw error
        }
      },

      loadDocumentChunks: async (botId: string, documentId: string) => {
        set((state) => ({
          loadingChunks: { ...state.loadingChunks, [documentId]: true },
        }))
        try {
          const chunks = await knowledgeApi.documents.getChunks(botId, documentId)
          set((state) => ({
            documentChunks: { ...state.documentChunks, [documentId]: chunks },
            loadingChunks: { ...state.loadingChunks, [documentId]: false },
          }))
        } catch (error) {
          set((state) => ({
            loadingChunks: { ...state.loadingChunks, [documentId]: false },
            error: error instanceof Error ? error.message : 'Failed to load chunks',
          }))
        }
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

      // ===== NOTES =====

      loadNotes: async (botId: string, tags?: string, search?: string) => {
        set((state) => ({
          loadingNotes: { ...state.loadingNotes, [botId]: true },
          error: null,
        }))

        try {
          const notes = await knowledgeApi.notes.list(botId, { tags, search })
          set((state) => ({
            notes: { ...state.notes, [botId]: notes },
            loadingNotes: { ...state.loadingNotes, [botId]: false },
          }))
        } catch (error) {
          set((state) => ({
            loadingNotes: { ...state.loadingNotes, [botId]: false },
            error: error instanceof Error ? error.message : 'Failed to load notes',
          }))
        }
      },

      createNote: async (botId: string, data: NoteCreate) => {
        try {
          const note = await knowledgeApi.notes.create(botId, data)
          set((state) => ({
            notes: {
              ...state.notes,
              [botId]: [note, ...(state.notes[botId] || [])],
            },
          }))
          return note
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to create note',
          })
          throw error
        }
      },

      updateNote: async (botId: string, noteId: string, data: NoteUpdate) => {
        try {
          const updated = await knowledgeApi.notes.update(botId, noteId, data)
          set((state) => ({
            notes: {
              ...state.notes,
              [botId]: (state.notes[botId] || []).map((n) =>
                n.id === noteId ? updated : n
              ),
            },
          }))
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to update note',
          })
          throw error
        }
      },

      deleteNote: async (botId: string, noteId: string) => {
        try {
          await knowledgeApi.notes.delete(botId, noteId)
          set((state) => ({
            notes: {
              ...state.notes,
              [botId]: (state.notes[botId] || []).filter((n) => n.id !== noteId),
            },
          }))
        } catch (error) {
          set({
            error: error instanceof Error ? error.message : 'Failed to delete note',
          })
          throw error
        }
      },

      loadTags: async (botId: string) => {
        try {
          const tags = await knowledgeApi.notes.getTags(botId)
          set((state) => ({
            allTags: { ...state.allTags, [botId]: tags },
          }))
        } catch {
          // Silently fail
        }
      },

      // ===== STATS & SEARCH =====

      loadStats: async (botId: string) => {
        set((state) => ({
          loadingStats: { ...state.loadingStats, [botId]: true },
        }))
        try {
          const stats = await knowledgeApi.stats(botId)
          set((state) => ({
            stats: { ...state.stats, [botId]: stats },
            loadingStats: { ...state.loadingStats, [botId]: false },
          }))
        } catch (error) {
          set((state) => ({
            loadingStats: { ...state.loadingStats, [botId]: false },
            error: error instanceof Error ? error.message : 'Failed to load stats',
          }))
        }
      },

      searchKnowledge: async (botId: string, query: string) => {
        set({ loadingSearch: true, error: null })
        try {
          const results = await knowledgeApi.search(botId, query)
          set({ searchResults: results, loadingSearch: false })
        } catch (error) {
          set({
            loadingSearch: false,
            error: error instanceof Error ? error.message : 'Search failed',
          })
        }
      },

      // ===== UTILITY =====

      clearError: () => set({ error: null }),
      clearSearchResults: () => set({ searchResults: [] }),
    }),
    {
      name: 'cachibot-knowledge',
      // Only persist documents, instructions, and notes, not loading/error states
      partialize: (state) => ({
        documents: state.documents,
        instructions: state.instructions,
        notes: state.notes,
      }),
    }
  )
)

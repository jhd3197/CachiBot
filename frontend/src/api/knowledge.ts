/**
 * Knowledge Base API Client
 *
 * Functions for document upload, management, and custom instructions.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api/bots'

// =============================================================================
// TYPES
// =============================================================================

export interface DocumentResponse {
  id: string
  filename: string
  file_type: string
  file_size: number
  chunk_count: number
  status: 'processing' | 'ready' | 'failed'
  uploaded_at: string
  processed_at: string | null
}

export interface UploadResponse {
  document_id: string
  status: string
  message: string
}

export interface InstructionsResponse {
  content: string
  updated_at: string | null
}

export interface NoteResponse {
  id: string
  bot_id: string
  title: string
  content: string
  tags: string[]
  source: 'user' | 'bot'
  created_at: string
  updated_at: string
}

export interface NoteCreate {
  title: string
  content: string
  tags?: string[]
}

export interface NoteUpdate {
  title?: string
  content?: string
  tags?: string[]
}

export interface KnowledgeStats {
  total_documents: number
  documents_ready: number
  documents_processing: number
  documents_failed: number
  total_chunks: number
  total_notes: number
  has_instructions: boolean
}

export interface SearchResult {
  type: 'document' | 'note'
  id: string
  title: string
  content: string
  score: number | null
  source: string | null
}

export interface ChunkPreview {
  id: string
  document_id: string
  chunk_index: number
  content: string
}

// =============================================================================
// AUTH HELPERS
// =============================================================================

function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const url = `${API_BASE}${endpoint}`

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      return request<T>(endpoint, options, false)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }

  return response.json()
}

// =============================================================================
// DOCUMENTS API
// =============================================================================

export async function uploadDocument(
  botId: string,
  file: File
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  // For FormData uploads, don't set Content-Type (browser sets it with boundary)
  const url = `${API_BASE}/${botId}/documents/`
  const response = await fetch(url, {
    method: 'POST',
    headers: { ...getAuthHeader() },
    body: formData,
  })

  if (response.status === 401) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      const retryResponse = await fetch(url, {
        method: 'POST',
        headers: { ...getAuthHeader() },
        body: formData,
      })
      if (!retryResponse.ok) {
        const error = await retryResponse.json().catch(() => ({ detail: 'Upload failed' }))
        throw new Error(error.detail || `Upload failed: ${retryResponse.status}`)
      }
      return retryResponse.json()
    }
  }

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `Upload failed: ${response.status}`)
  }

  return response.json()
}

export async function listDocuments(botId: string): Promise<DocumentResponse[]> {
  return request(`/${botId}/documents/`)
}

export async function getDocument(
  botId: string,
  documentId: string
): Promise<DocumentResponse> {
  return request(`/${botId}/documents/${documentId}`)
}

export async function deleteDocument(
  botId: string,
  documentId: string
): Promise<void> {
  return request(`/${botId}/documents/${documentId}`, {
    method: 'DELETE',
  })
}

// =============================================================================
// INSTRUCTIONS API
// =============================================================================

export async function getInstructions(botId: string): Promise<InstructionsResponse> {
  return request(`/${botId}/instructions/`)
}

export async function updateInstructions(
  botId: string,
  content: string
): Promise<InstructionsResponse> {
  return request(`/${botId}/instructions/`, {
    method: 'PUT',
    body: JSON.stringify({ content }),
  })
}

export async function deleteInstructions(botId: string): Promise<void> {
  return request(`/${botId}/instructions/`, {
    method: 'DELETE',
  })
}

// =============================================================================
// NOTES API
// =============================================================================

export async function listNotes(
  botId: string,
  params?: { tags?: string; search?: string; limit?: number; offset?: number }
): Promise<NoteResponse[]> {
  const searchParams = new URLSearchParams()
  if (params?.tags) searchParams.set('tags', params.tags)
  if (params?.search) searchParams.set('search', params.search)
  if (params?.limit) searchParams.set('limit', String(params.limit))
  if (params?.offset) searchParams.set('offset', String(params.offset))
  const qs = searchParams.toString()
  return request(`/${botId}/knowledge/notes${qs ? `?${qs}` : ''}`)
}

export async function createNote(
  botId: string,
  data: NoteCreate
): Promise<NoteResponse> {
  return request(`/${botId}/knowledge/notes`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getNote(
  botId: string,
  noteId: string
): Promise<NoteResponse> {
  return request(`/${botId}/knowledge/notes/${noteId}`)
}

export async function updateNote(
  botId: string,
  noteId: string,
  data: NoteUpdate
): Promise<NoteResponse> {
  return request(`/${botId}/knowledge/notes/${noteId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteNote(
  botId: string,
  noteId: string
): Promise<void> {
  return request(`/${botId}/knowledge/notes/${noteId}`, {
    method: 'DELETE',
  })
}

export async function getNoteTags(botId: string): Promise<string[]> {
  return request(`/${botId}/knowledge/notes/tags`)
}

// =============================================================================
// KNOWLEDGE UTILITY API
// =============================================================================

export async function getKnowledgeStats(botId: string): Promise<KnowledgeStats> {
  return request(`/${botId}/knowledge/stats`)
}

export async function searchKnowledge(
  botId: string,
  query: string,
  includeNotes = true,
  includeDocs = true,
  limit = 10
): Promise<SearchResult[]> {
  return request(`/${botId}/knowledge/search`, {
    method: 'POST',
    body: JSON.stringify({
      query,
      include_notes: includeNotes,
      include_documents: includeDocs,
      limit,
    }),
  })
}

export async function reindexDocuments(
  botId: string
): Promise<{ status: string; documents_queued: number }> {
  return request(`/${botId}/knowledge/reindex`, {
    method: 'POST',
  })
}

export async function retryDocument(
  botId: string,
  documentId: string
): Promise<{ status: string; document_id: string }> {
  return request(`/${botId}/knowledge/documents/${documentId}/retry`, {
    method: 'POST',
  })
}

export async function getDocumentChunks(
  botId: string,
  documentId: string
): Promise<ChunkPreview[]> {
  return request(`/${botId}/knowledge/documents/${documentId}/chunks`)
}

// =============================================================================
// COMBINED EXPORT
// =============================================================================

export const knowledgeApi = {
  documents: {
    upload: uploadDocument,
    list: listDocuments,
    get: getDocument,
    delete: deleteDocument,
    retry: retryDocument,
    reindex: reindexDocuments,
    getChunks: getDocumentChunks,
  },
  instructions: {
    get: getInstructions,
    update: updateInstructions,
    delete: deleteInstructions,
  },
  notes: {
    list: listNotes,
    create: createNote,
    get: getNote,
    update: updateNote,
    delete: deleteNote,
    getTags: getNoteTags,
  },
  stats: getKnowledgeStats,
  search: searchKnowledge,
}

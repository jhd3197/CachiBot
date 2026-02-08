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
// COMBINED EXPORT
// =============================================================================

export const knowledgeApi = {
  documents: {
    upload: uploadDocument,
    list: listDocuments,
    get: getDocument,
    delete: deleteDocument,
  },
  instructions: {
    get: getInstructions,
    update: updateInstructions,
    delete: deleteInstructions,
  },
}

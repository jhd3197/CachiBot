/**
 * Knowledge Base API Client
 *
 * Functions for document upload, management, and custom instructions.
 */

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
// DOCUMENTS API
// =============================================================================

export async function uploadDocument(
  botId: string,
  file: File
): Promise<UploadResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/${botId}/documents/`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Upload failed' }))
    throw new Error(error.detail || `Upload failed: ${response.status}`)
  }

  return response.json()
}

export async function listDocuments(botId: string): Promise<DocumentResponse[]> {
  const response = await fetch(`${API_BASE}/${botId}/documents/`)

  if (!response.ok) {
    throw new Error(`Failed to list documents: ${response.status}`)
  }

  return response.json()
}

export async function getDocument(
  botId: string,
  documentId: string
): Promise<DocumentResponse> {
  const response = await fetch(`${API_BASE}/${botId}/documents/${documentId}`)

  if (!response.ok) {
    throw new Error(`Failed to get document: ${response.status}`)
  }

  return response.json()
}

export async function deleteDocument(
  botId: string,
  documentId: string
): Promise<void> {
  const response = await fetch(`${API_BASE}/${botId}/documents/${documentId}`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status}`)
  }
}

// =============================================================================
// INSTRUCTIONS API
// =============================================================================

export async function getInstructions(botId: string): Promise<InstructionsResponse> {
  const response = await fetch(`${API_BASE}/${botId}/instructions/`)

  if (!response.ok) {
    throw new Error(`Failed to get instructions: ${response.status}`)
  }

  return response.json()
}

export async function updateInstructions(
  botId: string,
  content: string
): Promise<InstructionsResponse> {
  const response = await fetch(`${API_BASE}/${botId}/instructions/`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ content }),
  })

  if (!response.ok) {
    throw new Error(`Failed to update instructions: ${response.status}`)
  }

  return response.json()
}

export async function deleteInstructions(botId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${botId}/instructions/`, {
    method: 'DELETE',
  })

  if (!response.ok) {
    throw new Error(`Failed to delete instructions: ${response.status}`)
  }
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

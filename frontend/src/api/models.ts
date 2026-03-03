/**
 * Models API client
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

export interface ModelInfo {
  id: string
  provider: string
  context_window: number | null
  max_output_tokens: number | null
  supports_tool_use: boolean
  supports_vision: boolean
  supports_structured_output: boolean
  supports_image_generation: boolean
  supports_audio: boolean
  supports_embedding: boolean
  is_reasoning: boolean
  modalities_input: string[]
  modalities_output: string[]
  embedding_dimensions: number | null
  pricing: {
    input: number | null
    output: number | null
  } | null
}

export interface ModelsGrouped {
  [provider: string]: ModelInfo[]
}

export interface EmbeddingModelInfo {
  id: string
  provider: string
  dimensions: number | null
}

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

/**
 * Get all available models grouped by provider
 */
export async function getModels(): Promise<ModelsGrouped> {
  const data = await request<{ groups: ModelsGrouped }>('/models')
  return data.groups || {}
}

/**
 * Get all default model slots in a single request
 */
export async function getAllDefaults(): Promise<{
  default: string
  embedding: string
  utility: string
}> {
  return request('/models/defaults')
}

/**
 * Get the current default model
 */
export async function getDefaultModel(): Promise<string> {
  const data = await request<{ model: string }>('/models/default')
  return data.model
}

/**
 * Set the default model
 */
export async function setDefaultModel(model: string): Promise<void> {
  await request('/models/default', {
    method: 'PUT',
    body: JSON.stringify({ model }),
  })
}

/**
 * Get available embedding models
 */
export async function getEmbeddingModels(): Promise<EmbeddingModelInfo[]> {
  return request<EmbeddingModelInfo[]>('/models/embedding')
}

/**
 * Get the current default embedding model
 */
export async function getDefaultEmbeddingModel(): Promise<string> {
  const data = await request<{ model: string }>('/models/embedding/default')
  return data.model
}

/**
 * Set the default embedding model
 */
export async function setDefaultEmbeddingModel(model: string): Promise<void> {
  await request('/models/embedding/default', {
    method: 'PUT',
    body: JSON.stringify({ model }),
  })
}

/**
 * Get the current default utility model
 */
export async function getDefaultUtilityModel(): Promise<string> {
  const data = await request<{ model: string }>('/models/utility/default')
  return data.model
}

/**
 * Set the default utility model
 */
export async function setDefaultUtilityModel(model: string): Promise<void> {
  await request('/models/utility/default', {
    method: 'PUT',
    body: JSON.stringify({ model }),
  })
}

/**
 * REST API Client for Automations (Scripts & Versions)
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
    public data?: unknown
  ) {
    super(message)
    this.name = 'ApiError'
  }
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
    throw new ApiError(
      data.detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  return response.json()
}

// =============================================================================
// SCRIPT TYPES
// =============================================================================

export interface Script {
  id: string
  botId: string
  name: string
  description: string
  language: string
  sourceCode: string
  status: 'draft' | 'active' | 'disabled' | 'error'
  currentVersion: number
  runCount: number
  lastRunAt: string | null
  lastError: string | null
  createdAt: string
  updatedAt: string
}

export interface ScriptVersion {
  id: string
  scriptId: string
  version: number
  sourceCode: string
  changelog: string
  authorType: 'human' | 'bot'
  authorId: string | null
  approved: boolean
  approvedBy: string | null
  approvedAt: string | null
  createdAt: string
}

export interface CreateScriptRequest {
  name: string
  description?: string
  language?: string
  sourceCode: string
}

export interface UpdateScriptRequest {
  name?: string
  description?: string
  sourceCode?: string
  changelog?: string
}

export interface ScriptValidationResult {
  valid: boolean
  errors: string[]
  warnings: string[]
  riskLevel: string
}

// =============================================================================
// TIMELINE TYPES
// =============================================================================

export interface TimelineEvent {
  id: string
  botId: string
  sourceType: string
  sourceId: string
  eventType: string
  title: string
  description: string | null
  metadata: Record<string, unknown>
  createdAt: string
}

// =============================================================================
// SCRIPT API
// =============================================================================

export async function getScripts(botId: string): Promise<Script[]> {
  return request(`/bots/${botId}/scripts`)
}

export async function getScript(botId: string, scriptId: string): Promise<Script> {
  return request(`/bots/${botId}/scripts/${scriptId}`)
}

export async function createScript(botId: string, data: CreateScriptRequest): Promise<Script> {
  return request(`/bots/${botId}/scripts`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateScript(
  botId: string,
  scriptId: string,
  data: UpdateScriptRequest
): Promise<Script> {
  return request(`/bots/${botId}/scripts/${scriptId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteScript(botId: string, scriptId: string): Promise<void> {
  return request(`/bots/${botId}/scripts/${scriptId}`, { method: 'DELETE' })
}

export async function runScript(botId: string, scriptId: string): Promise<{ workId: string }> {
  return request(`/bots/${botId}/scripts/${scriptId}/run`, { method: 'POST' })
}

export async function activateScript(botId: string, scriptId: string): Promise<Script> {
  return request(`/bots/${botId}/scripts/${scriptId}/activate`, { method: 'POST' })
}

export async function disableScript(botId: string, scriptId: string): Promise<Script> {
  return request(`/bots/${botId}/scripts/${scriptId}/disable`, { method: 'POST' })
}

// =============================================================================
// SCRIPT VERSION API
// =============================================================================

export async function getScriptVersions(
  botId: string,
  scriptId: string
): Promise<ScriptVersion[]> {
  return request(`/bots/${botId}/scripts/${scriptId}/versions`)
}

export async function getScriptVersion(
  botId: string,
  scriptId: string,
  version: number
): Promise<ScriptVersion> {
  return request(`/bots/${botId}/scripts/${scriptId}/versions/${version}`)
}

export async function approveScriptVersion(
  botId: string,
  scriptId: string,
  version: number
): Promise<ScriptVersion> {
  return request(`/bots/${botId}/scripts/${scriptId}/versions/${version}/approve`, {
    method: 'POST',
  })
}

export async function rollbackScriptVersion(
  botId: string,
  scriptId: string,
  version: number
): Promise<Script> {
  return request(`/bots/${botId}/scripts/${scriptId}/versions/${version}/rollback`, {
    method: 'POST',
  })
}

// =============================================================================
// TIMELINE API
// =============================================================================

export async function getTimeline(
  botId: string,
  sourceType: string,
  sourceId: string,
  limit = 50,
  offset = 0
): Promise<TimelineEvent[]> {
  return request(
    `/bots/${botId}/timeline/${sourceType}/${sourceId}?limit=${limit}&offset=${offset}`
  )
}

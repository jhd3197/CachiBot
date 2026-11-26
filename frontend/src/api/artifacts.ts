/**
 * REST client for the server-side artifact store.
 *
 * Manual click-to-edit saves are PUT here (the server bumps the version and
 * writes website_builder pages back to disk), and a chat's artifacts are
 * listed when it opens so the localStorage cache converges on the server
 * state. Same auth-header + 401-refresh pattern as the other API modules;
 * failures throw ApiError — callers surface them, nothing is faked as saved.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { Artifact } from '../types'

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

async function request<T>(endpoint: string, options: RequestInit = {}, retry = true): Promise<T> {
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

/** What the client sends when saving an artifact (content is required). */
export interface SaveArtifactBody {
  content: string
  title?: string
  type?: string
  language?: string
  plugin?: string
  metadata?: Record<string, unknown>
  chatId?: string
  messageId?: string
  /** The client's current version — the server bumps its stored one. */
  version?: number
}

/** The artifact as the server stored it, plus the website write-back flag. */
export interface SaveArtifactResponse extends Artifact {
  websiteWritten: boolean
}

/** The bot's artifacts, optionally scoped to one chat (viewer+). */
export async function listArtifacts(botId: string, chatId?: string): Promise<Artifact[]> {
  const query = chatId ? `?chatId=${encodeURIComponent(chatId)}` : ''
  return request(`/bots/${botId}/artifacts${query}`)
}

/** Save edited artifact content (operator+); the response carries the new version. */
export async function saveArtifact(
  botId: string,
  artifactId: string,
  body: SaveArtifactBody
): Promise<SaveArtifactResponse> {
  return request(`/bots/${botId}/artifacts/${encodeURIComponent(artifactId)}`, {
    method: 'PUT',
    body: JSON.stringify(body),
  })
}

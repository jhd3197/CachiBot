/**
 * Connections API Client
 *
 * REST client for managing bot platform connections.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api/bots'

export type ConnectionPlatform = 'telegram' | 'discord'
export type ConnectionStatus = 'disconnected' | 'connecting' | 'connected' | 'error'

export interface Connection {
  id: string
  bot_id: string
  platform: ConnectionPlatform
  name: string
  status: ConnectionStatus
  message_count: number
  last_activity: string | null
  error: string | null
  created_at: string
  updated_at: string
  // Safe config values (excludes sensitive data like tokens)
  strip_markdown: boolean
}

export interface ConnectionCreate {
  platform: ConnectionPlatform
  name: string
  config: Record<string, string>
}

export interface ConnectionUpdate {
  name?: string
  config?: Record<string, string>
}

function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

async function request<T>(
  url: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  // Handle 401 by trying to refresh token
  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      return request<T>(url, options, false)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }

  return response.json()
}

async function requestNoBody(
  url: string,
  options: RequestInit = {},
  retry = true
): Promise<void> {
  const response = await fetch(url, {
    headers: {
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  // Handle 401 by trying to refresh token
  if (response.status === 401 && retry) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      return requestNoBody(url, options, false)
    }
  }

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }
}

/**
 * Get all connections for a bot.
 */
export async function getConnections(botId: string): Promise<Connection[]> {
  return request(`${API_BASE}/${botId}/connections`)
}

/**
 * Create a new connection.
 */
export async function createConnection(
  botId: string,
  data: ConnectionCreate
): Promise<Connection> {
  return request(`${API_BASE}/${botId}/connections`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Update an existing connection.
 */
export async function updateConnection(
  botId: string,
  connectionId: string,
  data: ConnectionUpdate
): Promise<Connection> {
  return request(`${API_BASE}/${botId}/connections/${connectionId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

/**
 * Delete a connection.
 */
export async function deleteConnection(botId: string, connectionId: string): Promise<void> {
  return requestNoBody(`${API_BASE}/${botId}/connections/${connectionId}`, {
    method: 'DELETE',
  })
}

/**
 * Start a platform connection.
 */
export async function connectPlatform(
  botId: string,
  connectionId: string
): Promise<Connection> {
  return request(`${API_BASE}/${botId}/connections/${connectionId}/connect`, {
    method: 'POST',
  })
}

/**
 * Stop a platform connection.
 */
export async function disconnectPlatform(
  botId: string,
  connectionId: string
): Promise<Connection> {
  return request(`${API_BASE}/${botId}/connections/${connectionId}/disconnect`, {
    method: 'POST',
  })
}

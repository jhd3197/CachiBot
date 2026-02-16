/**
 * Connections API Client
 *
 * REST client for managing bot platform connections.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api/bots'

export type ConnectionPlatform = string
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
  // Custom platform config (safe values only — no api_key)
  custom_config?: {
    base_url: string
    send_messages: boolean
    typing_indicator: boolean
    read_receipts: boolean
    message_status: boolean
  } | null
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

/** Metadata for a registered platform adapter. */
export interface PlatformMeta {
  name: string
  display_name: string
  required_config: string[]
  optional_config: Record<string, string>
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

// Module-level cache for platform metadata (static data that rarely changes)
let _platformsCache: Record<string, PlatformMeta> | null = null

/**
 * Fetch available platform adapters from the registry.
 */
export async function getPlatforms(): Promise<Record<string, PlatformMeta>> {
  if (_platformsCache) return _platformsCache
  const result = await request<Record<string, PlatformMeta>>('/api/platforms')
  _platformsCache = result
  return result
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

/** Custom platform API spec. */
export interface CustomPlatformSpec {
  inbound: {
    description: string
    method: string
    url_template: string
    headers: Record<string, string>
    body: Record<string, { type: string; required: boolean; description: string }>
    example: Record<string, unknown>
  }
  outbound: {
    endpoint: string
    capability: string
    default: boolean
    body: Record<string, unknown>
  }[]
}

/**
 * Fetch the Custom platform API contract / spec.
 */
export async function getCustomSpec(): Promise<CustomPlatformSpec> {
  return request('/api/platforms/custom/spec')
}

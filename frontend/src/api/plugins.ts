/**
 * Plugins API Client for CachiBot
 *
 * Fetches plugin and skill metadata from the backend.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { PluginInfo } from '../types'

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

/**
 * Get all plugins with their skills and metadata.
 */
export async function getPlugins(): Promise<PluginInfo[]> {
  const data = await request<{ plugins: PluginInfo[] }>('/plugins')
  return data.plugins
}

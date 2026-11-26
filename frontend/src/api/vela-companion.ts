/**
 * REST API client for the Vela companion integration.
 *
 * The server registers with a local Vela when one is present and serves its
 * desk widgets over a loopback endpoint. These calls only read the
 * integration's own status/toggle — the bearer token and the loopback port
 * are never exposed. The settings section feature-detects: when no Vela is
 * present (or the call fails), the UI renders nothing at all.
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
    throw new ApiError(data.detail || `Request failed: ${response.statusText}`, response.status, data)
  }

  return response.json()
}

export interface VelaCompanionStatus {
  /** A Vela home directory exists on this computer. */
  detected: boolean
  /** The integration is switched on (env var can force it off). */
  enabled: boolean
  /** The registration file is in place for Vela to find. */
  registered: boolean
  /** Last time Vela called our loopback server (ISO), or null. */
  lastSeenAt: string | null
}

export function getVelaCompanionStatus(): Promise<VelaCompanionStatus> {
  return request('/vela-companion/status')
}

export function updateVelaCompanionSettings(settings: {
  enabled: boolean
}): Promise<VelaCompanionStatus> {
  return request('/vela-companion/settings', {
    method: 'PUT',
    body: JSON.stringify(settings),
  })
}

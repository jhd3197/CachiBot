/**
 * Platform Tools API Client
 *
 * Global tool visibility configuration — disable capabilities and skills
 * platform-wide so they never appear in bot settings or at runtime.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { PlatformToolConfig, PlatformToolConfigUpdate } from '../types'

const API_BASE = '/api'

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

/** Get the current global tool visibility configuration. */
export async function getPlatformToolConfig(): Promise<PlatformToolConfig> {
  const raw = await request<{
    disabled_capabilities: string[]
    disabled_skills: string[]
  }>('/platform/tools')
  return {
    disabledCapabilities: raw.disabled_capabilities,
    disabledSkills: raw.disabled_skills,
  }
}

/** Update global tool visibility (admin only). */
export async function updatePlatformToolConfig(
  update: PlatformToolConfigUpdate
): Promise<PlatformToolConfig> {
  const raw = await request<{
    disabled_capabilities: string[]
    disabled_skills: string[]
  }>('/platform/tools', {
    method: 'PUT',
    body: JSON.stringify(update),
  })
  return {
    disabledCapabilities: raw.disabled_capabilities,
    disabledSkills: raw.disabled_skills,
  }
}

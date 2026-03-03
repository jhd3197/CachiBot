/**
 * API client for external plugin management.
 */

import type { ExternalPluginInfo } from '../types'
import { useAuthStore } from '../stores/auth'

const API_BASE = '/api'

function getAuthHeader(): Record<string, string> {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    return { Authorization: `Bearer ${accessToken}` }
  }
  return {}
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...getAuthHeader(),
      ...options.headers,
    },
    ...options,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchExternalPlugins(): Promise<ExternalPluginInfo[]> {
  const data = await request<{ plugins: ExternalPluginInfo[] }>('/plugins/external')
  return data.plugins
}

export async function enableExternalPlugin(
  name: string
): Promise<{ capabilityKey: string; enabled: boolean }> {
  return request(`/plugins/${name}/enable`, { method: 'POST' })
}

export async function disableExternalPlugin(
  name: string
): Promise<{ capabilityKey: string; enabled: boolean }> {
  return request(`/plugins/${name}/disable`, { method: 'POST' })
}

export async function reloadExternalPlugins(): Promise<{
  loaded: number
  total: number
  errors: Record<string, string>
}> {
  return request('/plugins/reload', { method: 'POST' })
}

export async function installExternalPlugin(
  file: File
): Promise<{
  name: string
  displayName: string
  version: string
  capabilityKey: string
  installed: boolean
}> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE}/plugins/install`, {
    method: 'POST',
    headers: { ...getAuthHeader() },
    body: formData,
  })

  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Install failed: ${response.statusText}`)
  }

  return response.json()
}

export async function uninstallExternalPlugin(name: string): Promise<{ name: string; uninstalled: boolean }> {
  return request(`/plugins/${name}`, { method: 'DELETE' })
}

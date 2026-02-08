/**
 * Providers API client
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

export interface Provider {
  name: string
  env_key: string
  type: 'api_key' | 'endpoint'
  configured: boolean
  masked_value: string
  default: string
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

export async function getProviders(): Promise<Provider[]> {
  const data = await request<{ providers: Provider[] }>('/providers')
  return data.providers
}

export async function updateProvider(name: string, value: string): Promise<void> {
  await request(`/providers/${name}`, {
    method: 'PUT',
    body: JSON.stringify({ value }),
  })
}

export async function deleteProvider(name: string): Promise<void> {
  await request(`/providers/${name}`, {
    method: 'DELETE',
  })
}

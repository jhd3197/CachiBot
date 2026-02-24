/**
 * Commands API client — fetches available /prefix:command entries for autocomplete.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { CommandDescriptor } from '../types'

const API_BASE = '/api'

async function authFetch<T>(endpoint: string): Promise<T> {
  const { accessToken } = useAuthStore.getState()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`

  let response = await fetch(`${API_BASE}${endpoint}`, { headers })

  if (response.status === 401) {
    const newToken = await tryRefreshToken()
    if (newToken) {
      headers.Authorization = `Bearer ${newToken}`
      response = await fetch(`${API_BASE}${endpoint}`, { headers })
    }
  }

  if (!response.ok) {
    throw new Error(`Failed to fetch commands: ${response.statusText}`)
  }

  return response.json()
}

export async function getAvailableCommands(botId?: string): Promise<CommandDescriptor[]> {
  const qs = botId ? `?bot_id=${encodeURIComponent(botId)}` : ''
  return authFetch<CommandDescriptor[]>(`/commands${qs}`)
}

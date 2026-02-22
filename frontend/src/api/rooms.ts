/**
 * REST API client for room operations.
 */

import type { Room, RoomMessage, CreateRoomRequest, RoomSettings, PinnedMessage, BookmarkedMessage, RoomAutomation } from '../types'
import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

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
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }

  if (response.status === 204) return undefined as T
  return response.json()
}

// Room CRUD
export async function createRoom(data: CreateRoomRequest): Promise<Room> {
  return request('/rooms', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getRooms(): Promise<Room[]> {
  return request('/rooms')
}

export async function getRoom(roomId: string): Promise<Room> {
  return request(`/rooms/${roomId}`)
}

export async function updateRoom(
  roomId: string,
  data: { title?: string; description?: string; settings?: RoomSettings }
): Promise<Room> {
  return request(`/rooms/${roomId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteRoom(roomId: string): Promise<void> {
  return request(`/rooms/${roomId}`, { method: 'DELETE' })
}

// Members
export async function inviteMember(
  roomId: string,
  username: string
): Promise<{ userId: string; username: string }> {
  return request(`/rooms/${roomId}/members`, {
    method: 'POST',
    body: JSON.stringify({ username }),
  })
}

export async function removeMember(roomId: string, userId: string): Promise<void> {
  return request(`/rooms/${roomId}/members/${userId}`, { method: 'DELETE' })
}

// Bots
export async function addRoomBot(
  roomId: string,
  botId: string
): Promise<{ botId: string; botName: string }> {
  return request(`/rooms/${roomId}/bots`, {
    method: 'POST',
    body: JSON.stringify({ bot_id: botId }),
  })
}

export async function removeRoomBot(roomId: string, botId: string): Promise<void> {
  return request(`/rooms/${roomId}/bots/${botId}`, { method: 'DELETE' })
}

// Bot role
export async function updateBotRole(
  roomId: string,
  botId: string,
  role: string
): Promise<{ botId: string; role: string }> {
  return request(`/rooms/${roomId}/bots/${botId}/role`, {
    method: 'PATCH',
    body: JSON.stringify({ role }),
  })
}

// Clear messages
export async function clearRoomMessages(roomId: string): Promise<{ deleted: number }> {
  return request(`/rooms/${roomId}/clear-messages`, { method: 'POST' })
}

// Messages
export async function getRoomMessages(
  roomId: string,
  limit = 50,
  before?: string
): Promise<RoomMessage[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (before) params.set('before', before)
  const raw = await request<RoomMessage[]>(`/rooms/${roomId}/messages?${params}`)
  return raw.map((msg) => ({
    ...msg,
    toolCalls: msg.toolCalls ?? (msg.metadata?.toolCalls as RoomMessage['toolCalls']) ?? undefined,
  }))
}

// =============================================================================
// REACTIONS
// =============================================================================

export async function addReaction(
  roomId: string,
  messageId: string,
  emoji: string
): Promise<{ id: string; emoji: string }> {
  return request(`/rooms/${roomId}/messages/${messageId}/reactions`, {
    method: 'POST',
    body: JSON.stringify({ emoji }),
  })
}

export async function removeReaction(
  roomId: string,
  messageId: string,
  emoji: string
): Promise<void> {
  return request(`/rooms/${roomId}/messages/${messageId}/reactions?emoji=${encodeURIComponent(emoji)}`, {
    method: 'DELETE',
  })
}

// =============================================================================
// PINNED MESSAGES
// =============================================================================

export async function pinMessage(
  roomId: string,
  messageId: string
): Promise<{ id: string; messageId: string }> {
  return request(`/rooms/${roomId}/pins/${messageId}`, { method: 'POST' })
}

export async function unpinMessage(
  roomId: string,
  messageId: string
): Promise<void> {
  return request(`/rooms/${roomId}/pins/${messageId}`, { method: 'DELETE' })
}

export async function getPinnedMessages(
  roomId: string
): Promise<PinnedMessage[]> {
  return request(`/rooms/${roomId}/pins`)
}

// =============================================================================
// BOOKMARKS
// =============================================================================

export async function addBookmark(
  roomId: string,
  messageId: string
): Promise<{ id: string; messageId: string }> {
  return request(`/rooms/${roomId}/bookmarks/${messageId}`, { method: 'POST' })
}

export async function removeBookmark(
  roomId: string,
  messageId: string
): Promise<void> {
  return request(`/rooms/${roomId}/bookmarks/${messageId}`, { method: 'DELETE' })
}

export async function getBookmarks(
  roomId?: string
): Promise<BookmarkedMessage[]> {
  const params = roomId ? `?room_id=${roomId}` : ''
  return request(`/rooms/bookmarks${params}`)
}

// Automations
export async function getAutomations(roomId: string): Promise<RoomAutomation[]> {
  return request(`/rooms/${roomId}/automations`)
}

export async function createAutomation(
  roomId: string,
  data: {
    name: string
    trigger_type: string
    trigger_config: Record<string, unknown>
    action_type: string
    action_config: Record<string, unknown>
  }
): Promise<RoomAutomation> {
  return request(`/rooms/${roomId}/automations`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateAutomation(
  roomId: string,
  automationId: string,
  data: Partial<{
    name: string
    enabled: boolean
    trigger_type: string
    trigger_config: Record<string, unknown>
    action_type: string
    action_config: Record<string, unknown>
  }>
): Promise<RoomAutomation> {
  return request(`/rooms/${roomId}/automations/${automationId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function deleteAutomation(
  roomId: string,
  automationId: string
): Promise<void> {
  return request(`/rooms/${roomId}/automations/${automationId}`, { method: 'DELETE' })
}

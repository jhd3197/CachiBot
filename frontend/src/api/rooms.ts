/**
 * REST API client for room operations.
 */

import type { Room, RoomMessage, CreateRoomRequest, RoomSettings } from '../types'
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

// Clear messages
export async function clearRoomMessages(roomId: string): Promise<{ deleted: number }> {
  return request(`/rooms/${roomId}/messages/_clear`, { method: 'POST' })
}

// Messages
export async function getRoomMessages(
  roomId: string,
  limit = 50,
  before?: string
): Promise<RoomMessage[]> {
  const params = new URLSearchParams({ limit: limit.toString() })
  if (before) params.set('before', before)
  return request(`/rooms/${roomId}/messages?${params}`)
}

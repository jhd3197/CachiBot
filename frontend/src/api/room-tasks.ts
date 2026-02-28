/**
 * REST API client for room task operations.
 */

import type { RoomTask, RoomTaskEvent, CreateRoomTaskRequest, UpdateRoomTaskRequest, RoomTaskStatus } from '../types'
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

export async function getRoomTasks(roomId: string, status?: RoomTaskStatus): Promise<RoomTask[]> {
  const params = status ? `?status=${status}` : ''
  return request(`/rooms/${roomId}/tasks${params}`)
}

export async function createRoomTask(roomId: string, data: CreateRoomTaskRequest): Promise<RoomTask> {
  return request(`/rooms/${roomId}/tasks`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getRoomTask(roomId: string, taskId: string): Promise<RoomTask> {
  return request(`/rooms/${roomId}/tasks/${taskId}`)
}

export async function updateRoomTask(
  roomId: string,
  taskId: string,
  data: UpdateRoomTaskRequest
): Promise<RoomTask> {
  return request(`/rooms/${roomId}/tasks/${taskId}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

export async function reorderRoomTask(
  roomId: string,
  taskId: string,
  status: RoomTaskStatus,
  position: number
): Promise<RoomTask> {
  return request(`/rooms/${roomId}/tasks/${taskId}/reorder`, {
    method: 'PATCH',
    body: JSON.stringify({ status, position }),
  })
}

export async function deleteRoomTask(roomId: string, taskId: string): Promise<void> {
  return request(`/rooms/${roomId}/tasks/${taskId}`, { method: 'DELETE' })
}

export async function getRoomTaskEvents(
  roomId: string,
  taskId: string,
  limit = 50,
  offset = 0
): Promise<RoomTaskEvent[]> {
  return request(`/rooms/${roomId}/tasks/${taskId}/events?limit=${limit}&offset=${offset}`)
}

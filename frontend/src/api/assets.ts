/**
 * REST API client for asset operations (rooms and chats).
 */

import type { Asset } from '../types'
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

// =============================================================================
// ROOM ASSETS
// =============================================================================

export async function getRoomAssets(roomId: string): Promise<Asset[]> {
  return request(`/rooms/${roomId}/assets`)
}

export async function uploadRoomAsset(roomId: string, file: File): Promise<Asset> {
  const formData = new FormData()
  formData.append('file', file)
  return request(`/rooms/${roomId}/assets`, {
    method: 'POST',
    body: formData,
    // Don't set Content-Type — browser sets multipart boundary automatically
  })
}

export async function downloadRoomAsset(roomId: string, assetId: string): Promise<Blob> {
  const url = `${API_BASE}/rooms/${roomId}/assets/${assetId}/download`
  const response = await fetch(url, {
    headers: getAuthHeader(),
  })
  if (!response.ok) throw new Error('Download failed')
  return response.blob()
}

export async function deleteRoomAsset(roomId: string, assetId: string): Promise<void> {
  return request(`/rooms/${roomId}/assets/${assetId}`, { method: 'DELETE' })
}

// =============================================================================
// CHAT ASSETS
// =============================================================================

export async function getChatAssets(botId: string, chatId: string): Promise<Asset[]> {
  return request(`/bots/${botId}/chats/${chatId}/assets`)
}

export async function uploadChatAsset(botId: string, chatId: string, file: File): Promise<Asset> {
  const formData = new FormData()
  formData.append('file', file)
  return request(`/bots/${botId}/chats/${chatId}/assets`, {
    method: 'POST',
    body: formData,
  })
}

export async function downloadChatAsset(botId: string, chatId: string, assetId: string): Promise<Blob> {
  const url = `${API_BASE}/bots/${botId}/chats/${chatId}/assets/${assetId}/download`
  const response = await fetch(url, {
    headers: getAuthHeader(),
  })
  if (!response.ok) throw new Error('Download failed')
  return response.blob()
}

export async function deleteChatAsset(botId: string, chatId: string, assetId: string): Promise<void> {
  return request(`/bots/${botId}/chats/${chatId}/assets/${assetId}`, { method: 'DELETE' })
}

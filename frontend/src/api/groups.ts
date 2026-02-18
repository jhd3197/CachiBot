/**
 * Groups & Bot Access API Client
 */

import type {
  Group,
  GroupWithMembers,
  CreateGroupRequest,
  UpdateGroupRequest,
  AddMemberRequest,
  GroupMember,
  BotAccessRecord,
  ShareBotRequest,
  UpdateAccessRequest,
} from '../types'
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

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true,
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

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as T
  }

  return response.json()
}

// =============================================================================
// GROUP ENDPOINTS
// =============================================================================

export async function listGroups(): Promise<Group[]> {
  return request('/groups')
}

export async function createGroup(data: CreateGroupRequest): Promise<Group> {
  return request('/groups', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function getGroup(groupId: string): Promise<GroupWithMembers> {
  return request(`/groups/${groupId}`)
}

export async function updateGroup(
  groupId: string,
  data: UpdateGroupRequest,
): Promise<Group> {
  return request(`/groups/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deleteGroup(groupId: string): Promise<void> {
  return request(`/groups/${groupId}`, { method: 'DELETE' })
}

export async function addMember(
  groupId: string,
  data: AddMemberRequest,
): Promise<GroupMember> {
  return request(`/groups/${groupId}/members`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function removeMember(
  groupId: string,
  userId: string,
): Promise<void> {
  return request(`/groups/${groupId}/members/${userId}`, {
    method: 'DELETE',
  })
}

// =============================================================================
// BOT ACCESS ENDPOINTS
// =============================================================================

export async function getBotAccess(botId: string): Promise<BotAccessRecord[]> {
  return request(`/bots/${botId}/access`)
}

export async function shareBotWithGroup(
  botId: string,
  data: ShareBotRequest,
): Promise<BotAccessRecord> {
  return request(`/bots/${botId}/access`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export async function updateBotAccess(
  botId: string,
  groupId: string,
  data: UpdateAccessRequest,
): Promise<{ status: string; access_level: string }> {
  return request(`/bots/${botId}/access/${groupId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function revokeBotAccess(
  botId: string,
  groupId: string,
): Promise<void> {
  return request(`/bots/${botId}/access/${groupId}`, {
    method: 'DELETE',
  })
}

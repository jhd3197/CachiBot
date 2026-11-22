/**
 * REST API client for side tasks (principle 9) and their backend chats.
 *
 * Side tasks are child chats of a parent chat that run in the background in
 * their own git worktree and merge back automatically. Viewers can list/read;
 * starting, stopping, retry-merge and discard require operator+ (the server
 * enforces it; the UI hides those controls below operator).
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type {
  BackendChat,
  BackendMessage,
  SideTask,
  SideTaskGroupSummary,
} from '../types'

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
    throw new ApiError(
      (data as { detail?: string }).detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  return response.json()
}

export async function listSideTasks(botId: string, parentChatId?: string): Promise<SideTask[]> {
  const qs = parentChatId ? `?parent_chat_id=${encodeURIComponent(parentChatId)}` : ''
  return request<SideTask[]>(`/bots/${botId}/side-tasks${qs}`)
}

export async function getSideTask(botId: string, sideTaskId: string): Promise<SideTask> {
  return request<SideTask>(`/bots/${botId}/side-tasks/${sideTaskId}`)
}

export async function startSideTask(
  botId: string,
  chatId: string,
  body: { prompt: string; title?: string }
): Promise<SideTask> {
  return request<SideTask>(`/bots/${botId}/chats/${chatId}/side-tasks`, {
    method: 'POST',
    body: JSON.stringify({ prompt: body.prompt, title: body.title || undefined }),
  })
}

export async function stopSideTask(
  botId: string,
  sideTaskId: string
): Promise<{ id: string; status: string }> {
  return request(`/bots/${botId}/side-tasks/${sideTaskId}/stop`, { method: 'POST' })
}

export async function retryMergeSideTask(botId: string, sideTaskId: string): Promise<SideTask> {
  return request<SideTask>(`/bots/${botId}/side-tasks/${sideTaskId}/retry-merge`, {
    method: 'POST',
  })
}

export async function discardSideTask(botId: string, sideTaskId: string): Promise<SideTask> {
  return request<SideTask>(`/bots/${botId}/side-tasks/${sideTaskId}/discard`, {
    method: 'POST',
  })
}

export async function getSideTaskGroup(
  botId: string,
  groupId: string
): Promise<SideTaskGroupSummary> {
  return request<SideTaskGroupSummary>(`/bots/${botId}/side-task-groups/${groupId}`)
}

export async function getChat(botId: string, chatId: string): Promise<BackendChat> {
  return request<BackendChat>(`/bots/${botId}/chats/${chatId}`)
}

export async function getChatMessages(
  botId: string,
  chatId: string,
  limit = 100
): Promise<BackendMessage[]> {
  return request<BackendMessage[]>(
    `/bots/${botId}/chats/${chatId}/messages?limit=${limit}`
  )
}

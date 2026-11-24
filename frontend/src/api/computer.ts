/**
 * REST API client for the bot's computer (Mini Vela).
 *
 * C1 exposes only status/state: the Docker probe summary, the per-bot
 * computer status, and wake/sleep/stop. Everything returns real backend
 * state — no placeholders — and the views (C4) stay hidden while
 * `DockerProbeSummary.available` is false.
 *
 * Access: viewers can read; wake/sleep/stop require operator-or-higher (the
 * server enforces it, matching the side-tasks pattern).
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { BotComputer, DockerProbeSummary } from '../types'

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
      data.detail || `Request failed: ${response.statusText}`,
      response.status,
      data
    )
  }

  return response.json()
}

/** Docker probe summary — the UI hides every computer surface when unavailable. */
export async function getComputerStatus(): Promise<DockerProbeSummary> {
  return request('/computer/status')
}

/** Current state of one bot's computer. */
export async function getBotComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer`)
}

/** Turn the computer on (background work; watch `computer_update` events). */
export async function wakeComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/wake`, { method: 'POST' })
}

/** Stop the container, keep the volumes. */
export async function sleepComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/sleep`, { method: 'POST' })
}

/** Stop the computer and mark it off (volumes kept). */
export async function stopComputer(botId: string): Promise<BotComputer> {
  return request(`/bots/${botId}/computer/stop`, { method: 'POST' })
}

/**
 * REST API client for the Faro Agent Bridge integration.
 *
 * The global status endpoint tells the UI whether any Faro surface may
 * appear at all; the per-bot endpoints carry the connection flag, the live
 * bridge status and the pending approvals (Deny only — approving happens in
 * Faro). No response ever carries the bridge token.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'
import type { BotFaroStatus, FaroIntegrationStatus } from '../types'

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

/** Global bridge detection — the UI hides every Faro surface when this says
 * unavailable and the bot is not connected. */
export async function getFaroStatus(): Promise<FaroIntegrationStatus> {
  return request('/integrations/faro/status')
}

/** One bot's Faro connection: flag + live status + pending approvals. */
export async function getBotFaro(botId: string): Promise<BotFaroStatus> {
  return request(`/bots/${botId}/faro`)
}

/** Connect this bot to Faro (editor+). Requires a running bridge. */
export async function connectFaro(botId: string): Promise<BotFaroStatus> {
  return request(`/bots/${botId}/faro/connect`, { method: 'POST' })
}

/** Disconnect this bot from Faro (anyone with bot access). */
export async function disconnectFaro(botId: string): Promise<BotFaroStatus> {
  return request(`/bots/${botId}/faro/disconnect`, { method: 'POST' })
}

/** Deny one pending approval in Faro (operator+). There is deliberately no
 * approve call: approving only ever happens in Faro's own window. */
export async function denyFaroApproval(botId: string, requestId: string): Promise<{ denied: boolean }> {
  return request(`/bots/${botId}/faro/approvals/${encodeURIComponent(requestId)}/deny`, {
    method: 'POST',
  })
}

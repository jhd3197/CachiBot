/**
 * Developer API Client
 *
 * API key management, webhook CRUD, and test delivery for per-bot developer access.
 */

import type { BotApiKey, BotApiKeyCreated, BotWebhook, WebhookEvent } from '../types'
import { useAuthStore } from '../stores/auth'

const API_BASE = '/api'

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const { accessToken } = useAuthStore.getState()
  const response = await fetch(`${API_BASE}${endpoint}`, {
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      ...options.headers,
    },
    ...options,
  })
  if (!response.ok) {
    const data = await response.json().catch(() => ({}))
    throw new Error(data.detail || `Request failed: ${response.statusText}`)
  }
  return response.json()
}

// =============================================================================
// API Keys
// =============================================================================

export function createApiKey(
  botId: string,
  name: string,
  expiresInDays?: number
): Promise<BotApiKeyCreated> {
  return request(`/bots/${botId}/developer/api-keys`, {
    method: 'POST',
    body: JSON.stringify({ name, expires_in_days: expiresInDays ?? null }),
  })
}

export function getApiKeys(botId: string): Promise<BotApiKey[]> {
  return request(`/bots/${botId}/developer/api-keys`)
}

export function revokeApiKey(botId: string, keyId: string): Promise<{ status: string }> {
  return request(`/bots/${botId}/developer/api-keys/${keyId}`, {
    method: 'DELETE',
  })
}

// =============================================================================
// Webhooks
// =============================================================================

export function createWebhook(
  botId: string,
  data: { name: string; url: string; events: WebhookEvent[]; secret?: string }
): Promise<BotWebhook> {
  return request(`/bots/${botId}/developer/webhooks`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

export function getWebhooks(botId: string): Promise<BotWebhook[]> {
  return request(`/bots/${botId}/developer/webhooks`)
}

export function updateWebhook(
  botId: string,
  webhookId: string,
  data: { name?: string; url?: string; events?: WebhookEvent[]; secret?: string; is_active?: boolean }
): Promise<BotWebhook> {
  return request(`/bots/${botId}/developer/webhooks/${webhookId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export function deleteWebhook(botId: string, webhookId: string): Promise<{ status: string }> {
  return request(`/bots/${botId}/developer/webhooks/${webhookId}`, {
    method: 'DELETE',
  })
}

export function testWebhook(
  botId: string,
  webhookId: string
): Promise<{ status: string; response_status?: number; error?: string }> {
  return request(`/bots/${botId}/developer/webhooks/${webhookId}/test`, {
    method: 'POST',
  })
}

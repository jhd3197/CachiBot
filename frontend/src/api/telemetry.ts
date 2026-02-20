/**
 * Telemetry API Client
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api'

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const url = `${API_BASE}${endpoint}`
  const { accessToken } = useAuthStore.getState()

  const response = await fetch(url, {
    headers: {
      'Content-Type': 'application/json',
      ...(accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
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

  return response.json()
}

// Types

export interface TelemetryStatus {
  enabled: boolean
  install_id: string
  last_sent: string
  terms_accepted: boolean
  terms_version: string
  terms_accepted_at: string
  latest_terms_version: string
}

export interface TelemetrySettingsUpdate {
  enabled?: boolean
  terms_accepted?: boolean
  terms_version?: string
}

export interface ConsentRequest {
  terms_accepted: boolean
  terms_version: string
  telemetry_enabled: boolean
}

// API functions

export async function getTelemetryStatus(): Promise<TelemetryStatus> {
  return request('/telemetry/status')
}

export async function getTelemetryPreview(): Promise<Record<string, unknown>> {
  return request('/telemetry/preview')
}

export async function updateTelemetrySettings(
  data: TelemetrySettingsUpdate
): Promise<TelemetryStatus> {
  return request('/telemetry/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function resetTelemetryId(): Promise<{ install_id: string }> {
  return request('/telemetry/reset-id', { method: 'POST' })
}

export async function acceptConsent(data: ConsentRequest): Promise<TelemetryStatus> {
  return request('/telemetry/consent', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

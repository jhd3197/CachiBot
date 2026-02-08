/**
 * Contacts API Client
 *
 * REST client for managing bot contacts.
 */

import { useAuthStore } from '../stores/auth'
import { tryRefreshToken } from './auth'

const API_BASE = '/api/bots'

export interface Contact {
  id: string
  bot_id: string
  name: string
  details: string | null
  created_at: string
  updated_at: string
}

export interface ContactCreate {
  name: string
  details?: string | null
}

export interface ContactUpdate {
  name: string
  details?: string | null
}

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
  retry = true
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

  return response.json()
}

/**
 * Get all contacts for a bot.
 */
export async function getContacts(botId: string): Promise<Contact[]> {
  return request(`/${botId}/contacts`)
}

/**
 * Create a new contact.
 */
export async function createContact(botId: string, data: ContactCreate): Promise<Contact> {
  return request(`/${botId}/contacts`, {
    method: 'POST',
    body: JSON.stringify(data),
  })
}

/**
 * Update an existing contact.
 */
export async function updateContact(
  botId: string,
  contactId: string,
  data: ContactUpdate
): Promise<Contact> {
  return request(`/${botId}/contacts/${contactId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

/**
 * Delete a contact.
 */
export async function deleteContact(botId: string, contactId: string): Promise<void> {
  return request(`/${botId}/contacts/${contactId}`, {
    method: 'DELETE',
  })
}

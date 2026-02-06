/**
 * Contacts API Client
 *
 * REST client for managing bot contacts.
 */

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

/**
 * Get all contacts for a bot.
 */
export async function getContacts(botId: string): Promise<Contact[]> {
  const response = await fetch(`${API_BASE}/${botId}/contacts`)
  if (!response.ok) {
    throw new Error(`Failed to get contacts: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Create a new contact.
 */
export async function createContact(botId: string, data: ContactCreate): Promise<Contact> {
  const response = await fetch(`${API_BASE}/${botId}/contacts`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to create contact: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Update an existing contact.
 */
export async function updateContact(
  botId: string,
  contactId: string,
  data: ContactUpdate
): Promise<Contact> {
  const response = await fetch(`${API_BASE}/${botId}/contacts/${contactId}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (!response.ok) {
    throw new Error(`Failed to update contact: ${response.statusText}`)
  }
  return response.json()
}

/**
 * Delete a contact.
 */
export async function deleteContact(botId: string, contactId: string): Promise<void> {
  const response = await fetch(`${API_BASE}/${botId}/contacts/${contactId}`, {
    method: 'DELETE',
  })
  if (!response.ok) {
    throw new Error(`Failed to delete contact: ${response.statusText}`)
  }
}

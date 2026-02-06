/**
 * Contacts Store
 *
 * Manages contacts state per bot.
 */

import { create } from 'zustand'
import type { Contact } from '../api/contacts'

interface ContactsState {
  // State: contacts keyed by botId
  contacts: Record<string, Contact[]>
  loading: Record<string, boolean>
  error: string | null

  // Actions
  setContacts: (botId: string, contacts: Contact[]) => void
  addContact: (botId: string, contact: Contact) => void
  updateContact: (botId: string, contact: Contact) => void
  removeContact: (botId: string, contactId: string) => void
  setLoading: (botId: string, loading: boolean) => void
  setError: (error: string | null) => void
  getContacts: (botId: string) => Contact[]
}

export const useContactsStore = create<ContactsState>()((set, get) => ({
  contacts: {},
  loading: {},
  error: null,

  setContacts: (botId, contacts) =>
    set((state) => ({
      contacts: { ...state.contacts, [botId]: contacts },
    })),

  addContact: (botId, contact) =>
    set((state) => ({
      contacts: {
        ...state.contacts,
        [botId]: [...(state.contacts[botId] || []), contact],
      },
    })),

  updateContact: (botId, contact) =>
    set((state) => ({
      contacts: {
        ...state.contacts,
        [botId]: (state.contacts[botId] || []).map((c) =>
          c.id === contact.id ? contact : c
        ),
      },
    })),

  removeContact: (botId, contactId) =>
    set((state) => ({
      contacts: {
        ...state.contacts,
        [botId]: (state.contacts[botId] || []).filter((c) => c.id !== contactId),
      },
    })),

  setLoading: (botId, loading) =>
    set((state) => ({
      loading: { ...state.loading, [botId]: loading },
    })),

  setError: (error) => set({ error }),

  getContacts: (botId) => get().contacts[botId] || [],
}))

/**
 * ContactsPanel Component
 *
 * UI for managing bot contacts with CRUD operations.
 */

import { useState, useEffect } from 'react'
import { Plus, Pencil, Trash2, X, Check, User } from 'lucide-react'
import { useContactsStore } from '../../stores/contacts'
import * as contactsApi from '../../api/contacts'
import type { Contact } from '../../api/contacts'

interface ContactsPanelProps {
  botId: string
}

export function ContactsPanel({ botId }: ContactsPanelProps) {
  const {
    setContacts,
    addContact,
    updateContact,
    removeContact,
    loading,
    setLoading,
    error,
    setError,
    getContacts,
  } = useContactsStore()

  const [editingId, setEditingId] = useState<string | null>(null)
  const [isAdding, setIsAdding] = useState(false)
  const [formName, setFormName] = useState('')
  const [formDetails, setFormDetails] = useState('')

  const botContacts = getContacts(botId)
  const isLoading = loading[botId] || false

  // Load contacts on mount
  useEffect(() => {
    const loadContacts = async () => {
      setLoading(botId, true)
      try {
        const data = await contactsApi.getContacts(botId)
        setContacts(botId, data)
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load contacts')
      } finally {
        setLoading(botId, false)
      }
    }
    loadContacts()
  }, [botId, setContacts, setLoading, setError])

  const handleAdd = async () => {
    if (!formName.trim()) return
    try {
      const contact = await contactsApi.createContact(botId, {
        name: formName.trim(),
        details: formDetails.trim() || null,
      })
      addContact(botId, contact)
      setFormName('')
      setFormDetails('')
      setIsAdding(false)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to create contact')
    }
  }

  const handleUpdate = async (contact: Contact) => {
    if (!formName.trim()) return
    try {
      const updated = await contactsApi.updateContact(botId, contact.id, {
        name: formName.trim(),
        details: formDetails.trim() || null,
      })
      updateContact(botId, updated)
      setEditingId(null)
      setFormName('')
      setFormDetails('')
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to update contact')
    }
  }

  const handleDelete = async (contactId: string) => {
    try {
      await contactsApi.deleteContact(botId, contactId)
      removeContact(botId, contactId)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete contact')
    }
  }

  const startEdit = (contact: Contact) => {
    setEditingId(contact.id)
    setFormName(contact.name)
    setFormDetails(contact.details || '')
    setIsAdding(false)
  }

  const startAdd = () => {
    setIsAdding(true)
    setEditingId(null)
    setFormName('')
    setFormDetails('')
  }

  const cancelForm = () => {
    setIsAdding(false)
    setEditingId(null)
    setFormName('')
    setFormDetails('')
  }

  if (isLoading) {
    return <div className="text-sm text-[var(--color-text-secondary)]">Loading contacts...</div>
  }

  return (
    <div className="space-y-4">
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Contact list */}
      <div className="space-y-2">
        {botContacts.map((contact) => (
          <div
            key={contact.id}
            className="flex items-center justify-between rounded-lg border border-[var(--color-border-primary)] p-3"
          >
            {editingId === contact.id ? (
              <div className="flex-1 space-y-2">
                <input
                  type="text"
                  value={formName}
                  onChange={(e) => setFormName(e.target.value)}
                  placeholder="Name"
                  className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
                  autoFocus
                />
                <input
                  type="text"
                  value={formDetails}
                  onChange={(e) => setFormDetails(e.target.value)}
                  placeholder="Details (email, phone, notes...)"
                  className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
                />
                <div className="flex gap-2">
                  <button
                    onClick={() => handleUpdate(contact)}
                    className="rounded bg-cachi-600 px-2 py-1 text-xs text-white hover:bg-cachi-500"
                  >
                    <Check className="h-3 w-3" />
                  </button>
                  <button
                    onClick={cancelForm}
                    className="rounded bg-[var(--color-hover-bg)] px-2 py-1 text-xs text-[var(--color-text-primary)] hover:bg-[var(--color-active-bg)]"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </div>
              </div>
            ) : (
              <>
                <div className="flex items-center gap-3">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[var(--color-bg-secondary)]">
                    <User className="h-4 w-4 text-[var(--color-text-secondary)]" />
                  </div>
                  <div>
                    <div className="font-medium text-[var(--color-text-primary)]">{contact.name}</div>
                    {contact.details && (
                      <div className="text-xs text-[var(--color-text-secondary)]">{contact.details}</div>
                    )}
                  </div>
                </div>
                <div className="flex gap-1">
                  <button
                    onClick={() => startEdit(contact)}
                    className="rounded p-1 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
                  >
                    <Pencil className="h-4 w-4" />
                  </button>
                  <button
                    onClick={() => handleDelete(contact.id)}
                    className="rounded p-1 text-[var(--color-text-secondary)] hover:bg-[var(--color-hover-bg)] hover:text-red-400"
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}
          </div>
        ))}
      </div>

      {/* Add form */}
      {isAdding ? (
        <div className="space-y-2 rounded-lg border border-[var(--color-border-secondary)] bg-[var(--card-bg)] p-3">
          <input
            type="text"
            value={formName}
            onChange={(e) => setFormName(e.target.value)}
            placeholder="Name"
            className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
            autoFocus
          />
          <input
            type="text"
            value={formDetails}
            onChange={(e) => setFormDetails(e.target.value)}
            placeholder="Details (email, phone, notes...)"
            className="w-full rounded border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-2 py-1 text-sm text-[var(--color-text-primary)]"
          />
          <div className="flex gap-2">
            <button
              onClick={handleAdd}
              disabled={!formName.trim()}
              className="rounded bg-cachi-600 px-3 py-1 text-xs text-white hover:bg-cachi-500 disabled:opacity-50"
            >
              Add Contact
            </button>
            <button
              onClick={cancelForm}
              className="rounded bg-[var(--color-hover-bg)] px-3 py-1 text-xs text-[var(--color-text-primary)] hover:bg-[var(--color-active-bg)]"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <button
          onClick={startAdd}
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-[var(--color-border-secondary)] p-3 text-sm text-[var(--color-text-secondary)] hover:border-[var(--color-border-secondary)] hover:text-[var(--color-text-secondary)]"
        >
          <Plus className="h-4 w-4" />
          Add Contact
        </button>
      )}

      {botContacts.length === 0 && !isAdding && (
        <p className="text-center text-sm text-[var(--color-text-secondary)]">
          No contacts yet. Add contacts that your bot can reference.
        </p>
      )}
    </div>
  )
}

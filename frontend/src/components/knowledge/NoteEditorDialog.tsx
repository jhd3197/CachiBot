/**
 * Note Editor Dialog
 *
 * Dialog for creating and editing knowledge base notes.
 * Supports title, content, and tag management with suggestions.
 */

import { useState, useEffect, useCallback, useRef, useMemo } from 'react'
import { X, Plus, Tag } from 'lucide-react'
import { Dialog, DialogHeader, DialogContent, DialogFooter, DialogButton } from '../common/Dialog'
import { useKnowledgeStore } from '../../stores/knowledge'

interface NoteEditorDialogProps {
  botId: string
  noteId: string | null
  open: boolean
  onClose: () => void
}

export function NoteEditorDialog({ botId, noteId, open, onClose }: NoteEditorDialogProps) {
  const { notes, allTags, createNote, updateNote, loadTags, loadNotes } = useKnowledgeStore()

  const [title, setTitle] = useState('')
  const [content, setContent] = useState('')
  const [tags, setTags] = useState<string[]>([])
  const [tagInput, setTagInput] = useState('')
  const [saving, setSaving] = useState(false)

  const tagInputRef = useRef<HTMLInputElement>(null)

  const isEditMode = noteId !== null
  const botTags = useMemo(() => allTags[botId] || [], [allTags, botId])
  const botNotes = useMemo(() => notes[botId] || [], [notes, botId])

  // Suggested tags: all known tags that are not already selected
  const suggestedTags = botTags.filter((t) => !tags.includes(t))

  // Load existing note data in edit mode, or reset for create mode
  useEffect(() => {
    if (!open) return

    if (isEditMode) {
      const existing = botNotes.find((n) => n.id === noteId)
      if (existing) {
        setTitle(existing.title)
        setContent(existing.content)
        setTags([...existing.tags])
      }
    } else {
      setTitle('')
      setContent('')
      setTags([])
    }

    setTagInput('')
    setSaving(false)
    loadTags(botId)
  }, [open, noteId, isEditMode, botId, botNotes, loadTags])

  const addTag = useCallback(
    (tag: string) => {
      const trimmed = tag.trim().toLowerCase()
      if (trimmed && !tags.includes(trimmed)) {
        setTags((prev) => [...prev, trimmed])
      }
      setTagInput('')
    },
    [tags]
  )

  const removeTag = useCallback((tag: string) => {
    setTags((prev) => prev.filter((t) => t !== tag))
  }, [])

  const handleTagKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault()
        if (tagInput.trim()) {
          addTag(tagInput)
        }
      } else if (e.key === 'Backspace' && !tagInput && tags.length > 0) {
        removeTag(tags[tags.length - 1])
      }
    },
    [tagInput, tags, addTag, removeTag]
  )

  const handleSave = useCallback(async () => {
    if (!title.trim() || !content.trim()) return

    setSaving(true)
    try {
      if (isEditMode && noteId) {
        await updateNote(botId, noteId, {
          title: title.trim(),
          content: content.trim(),
          tags,
        })
      } else {
        await createNote(botId, {
          title: title.trim(),
          content: content.trim(),
          tags,
        })
      }
      // Refresh notes list and tags after save
      await Promise.all([loadNotes(botId), loadTags(botId)])
      onClose()
    } catch {
      // Error is handled by the store
    } finally {
      setSaving(false)
    }
  }, [botId, noteId, isEditMode, title, content, tags, createNote, updateNote, loadNotes, loadTags, onClose])

  const canSave = title.trim().length > 0 && content.trim().length > 0 && !saving

  return (
    <Dialog open={open} onClose={onClose} size="lg">
      <DialogHeader
        title={isEditMode ? 'Edit Note' : 'New Note'}
        onClose={onClose}
      />
      <DialogContent scrollable maxHeight="max-h-[70vh]">
        <div className="space-y-5">
          {/* Title field */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Note title..."
              autoFocus
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500 transition-colors"
            />
          </div>

          {/* Content field */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300">Content</label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Write your note content..."
              rows={8}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500 transition-colors resize-y leading-relaxed"
            />
          </div>

          {/* Tags field */}
          <div className="space-y-2">
            <label className="text-sm font-medium text-zinc-300 flex items-center gap-1.5">
              <Tag className="h-3.5 w-3.5" />
              Tags
            </label>

            {/* Selected tags + input */}
            <div
              className="flex flex-wrap items-center gap-1.5 rounded-lg border border-zinc-700 bg-zinc-800 px-2 py-2 focus-within:border-cachi-500 transition-colors cursor-text"
              onClick={() => tagInputRef.current?.focus()}
            >
              {tags.map((tag) => (
                <span
                  key={tag}
                  className="inline-flex items-center gap-1 rounded-md bg-cachi-600/20 px-2 py-0.5 text-xs text-cachi-400"
                >
                  {tag}
                  <button
                    type="button"
                    onClick={(e) => {
                      e.stopPropagation()
                      removeTag(tag)
                    }}
                    className="rounded-sm p-0.5 hover:bg-cachi-600/30 hover:text-cachi-300 transition-colors"
                  >
                    <X className="h-3 w-3" />
                  </button>
                </span>
              ))}
              <input
                ref={tagInputRef}
                type="text"
                value={tagInput}
                onChange={(e) => setTagInput(e.target.value)}
                onKeyDown={handleTagKeyDown}
                placeholder={tags.length === 0 ? 'Type a tag and press Enter...' : 'Add tag...'}
                className="flex-1 min-w-[120px] bg-transparent text-sm text-zinc-100 placeholder-zinc-500 outline-none"
              />
            </div>

            {/* Tag suggestions */}
            {suggestedTags.length > 0 && (
              <div className="flex items-center gap-1.5 flex-wrap">
                <span className="text-xs text-zinc-500">Suggestions:</span>
                {suggestedTags.map((tag) => (
                  <button
                    key={tag}
                    type="button"
                    onClick={() => addTag(tag)}
                    className="inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-xs text-zinc-400 hover:border-cachi-500/50 hover:text-cachi-400 transition-colors"
                  >
                    <Plus className="h-3 w-3" />
                    {tag}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </DialogContent>
      <DialogFooter>
        <DialogButton variant="ghost" onClick={onClose}>
          Cancel
        </DialogButton>
        <DialogButton variant="primary" onClick={handleSave} disabled={!canSave}>
          {saving ? 'Saving...' : isEditMode ? 'Save Changes' : 'Create Note'}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}

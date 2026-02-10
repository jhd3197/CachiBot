/**
 * Notes Manager Component
 *
 * Manages notes for a bot's knowledge base with tag filtering,
 * search, create/edit/delete operations, and source badges.
 */

import { useEffect, useState, useMemo, useCallback } from 'react'
import {
  StickyNote,
  Plus,
  Search,
  Tag,
  Trash2,
  Pencil,
  Bot,
  User,
  RefreshCw,
} from 'lucide-react'
import { useKnowledgeStore, type NoteResponse } from '../../stores/knowledge'
import { cn } from '../../lib/utils'

interface NotesManagerProps {
  botId: string
  onEditNote: (noteId: string) => void
  onNewNote: () => void
}

function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffSec = Math.floor(diffMs / 1000)
  const diffMin = Math.floor(diffSec / 60)
  const diffHr = Math.floor(diffMin / 60)
  const diffDays = Math.floor(diffHr / 24)

  if (diffSec < 60) return 'just now'
  if (diffMin < 60) return `${diffMin}m ago`
  if (diffHr < 24) return `${diffHr}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  if (diffDays < 30) return `${Math.floor(diffDays / 7)}w ago`
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function truncateContent(content: string, maxLength = 150): string {
  if (content.length <= maxLength) return content
  return content.slice(0, maxLength).trimEnd() + '...'
}

// Deterministic color for tag pills based on tag string hash
const TAG_COLORS = [
  'bg-blue-500/20 text-blue-400',
  'bg-purple-500/20 text-purple-400',
  'bg-emerald-500/20 text-emerald-400',
  'bg-amber-500/20 text-amber-400',
  'bg-rose-500/20 text-rose-400',
  'bg-cyan-500/20 text-cyan-400',
  'bg-orange-500/20 text-orange-400',
  'bg-pink-500/20 text-pink-400',
]

function getTagColor(tag: string): string {
  let hash = 0
  for (let i = 0; i < tag.length; i++) {
    hash = ((hash << 5) - hash + tag.charCodeAt(i)) | 0
  }
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length]
}

function SourceBadge({ source }: { source: NoteResponse['source'] }) {
  if (source === 'bot') {
    return (
      <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded bg-cachi-500/20 text-cachi-400">
        <Bot className="h-3 w-3" />
        bot
      </span>
    )
  }
  return (
    <span className="inline-flex items-center gap-1 px-1.5 py-0.5 text-xs rounded bg-zinc-600/40 text-zinc-400">
      <User className="h-3 w-3" />
      user
    </span>
  )
}

export function NotesManager({ botId, onEditNote, onNewNote }: NotesManagerProps) {
  const {
    notes,
    allTags,
    loadNotes,
    loadTags,
    deleteNote,
    loadingNotes,
  } = useKnowledgeStore()

  const botNotes = useMemo(() => notes[botId] || [], [notes, botId])
  const botTags = useMemo(() => allTags[botId] || [], [allTags, botId])
  const isLoading = loadingNotes[botId]

  const [searchQuery, setSearchQuery] = useState('')
  const [selectedTags, setSelectedTags] = useState<Set<string>>(new Set())
  const [confirmingDelete, setConfirmingDelete] = useState<string | null>(null)

  // Load notes and tags on mount
  useEffect(() => {
    loadNotes(botId)
    loadTags(botId)
  }, [botId, loadNotes, loadTags])

  // Reload notes when tag or search filters change (debounced for search)
  useEffect(() => {
    const tagsParam = selectedTags.size > 0 ? Array.from(selectedTags).join(',') : undefined
    const searchParam = searchQuery.trim() || undefined

    const timeout = setTimeout(() => {
      loadNotes(botId, tagsParam, searchParam)
    }, searchParam ? 300 : 0)

    return () => clearTimeout(timeout)
  }, [botId, selectedTags, searchQuery, loadNotes])

  const toggleTag = useCallback((tag: string) => {
    setSelectedTags((prev) => {
      const next = new Set(prev)
      if (next.has(tag)) {
        next.delete(tag)
      } else {
        next.add(tag)
      }
      return next
    })
  }, [])

  const handleDelete = useCallback(async (noteId: string) => {
    try {
      await deleteNote(botId, noteId)
    } catch {
      // Error handled by store
    } finally {
      setConfirmingDelete(null)
    }
  }, [botId, deleteNote])

  // Filter notes locally for instant feedback (server also filters)
  const filteredNotes = useMemo(() => {
    return botNotes
  }, [botNotes])

  // Loading state
  if (isLoading && botNotes.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <RefreshCw className="h-5 w-5 animate-spin text-zinc-500" />
      </div>
    )
  }

  return (
    <div className="space-y-4">
      {/* Header: search + new note button */}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search notes..."
            className="w-full pl-9 pr-3 py-2 bg-zinc-800 border border-zinc-700 rounded-lg text-sm text-zinc-200 placeholder:text-zinc-500 focus:outline-none focus:border-cachi-500 transition-colors"
          />
        </div>
        <button
          onClick={onNewNote}
          className="flex items-center gap-1.5 px-3 py-2 bg-cachi-600 hover:bg-cachi-500 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap"
        >
          <Plus className="h-4 w-4" />
          New Note
        </button>
      </div>

      {/* Tag filter bar */}
      {botTags.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap">
          <Tag className="h-3.5 w-3.5 text-zinc-500 flex-shrink-0" />
          {botTags.map((tag) => (
            <button
              key={tag}
              onClick={() => toggleTag(tag)}
              className={cn(
                'px-2 py-0.5 text-xs rounded-full border transition-colors',
                selectedTags.has(tag)
                  ? 'bg-cachi-500/20 text-cachi-400 border-cachi-500/40'
                  : 'bg-zinc-800 text-zinc-400 border-zinc-700 hover:border-zinc-600'
              )}
            >
              {tag}
            </button>
          ))}
          {selectedTags.size > 0 && (
            <button
              onClick={() => setSelectedTags(new Set())}
              className="px-2 py-0.5 text-xs text-zinc-500 hover:text-zinc-300 transition-colors"
            >
              Clear
            </button>
          )}
        </div>
      )}

      {/* Notes list */}
      {filteredNotes.length === 0 ? (
        <div className="text-center py-12 text-zinc-500">
          <StickyNote className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">
            {searchQuery || selectedTags.size > 0
              ? 'No notes match your filters'
              : 'No notes yet'}
          </p>
          {!searchQuery && selectedTags.size === 0 && (
            <button
              onClick={onNewNote}
              className="mt-2 text-sm text-cachi-500 hover:text-cachi-400 transition-colors"
            >
              Create your first note
            </button>
          )}
        </div>
      ) : (
        <div className="space-y-2">
          {filteredNotes.map((note) => (
            <div
              key={note.id}
              className="group p-3 bg-zinc-800/50 rounded-lg border border-zinc-800 hover:border-zinc-700 transition-colors"
            >
              {/* Title row */}
              <div className="flex items-start justify-between gap-2">
                <button
                  onClick={() => onEditNote(note.id)}
                  className="text-sm font-medium text-zinc-200 hover:text-cachi-400 text-left transition-colors truncate flex-1"
                >
                  {note.title}
                </button>
                <div className="flex items-center gap-1 flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity">
                  <button
                    onClick={() => onEditNote(note.id)}
                    className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-cachi-400 transition-colors"
                    title="Edit note"
                  >
                    <Pencil className="h-3.5 w-3.5" />
                  </button>
                  {confirmingDelete === note.id ? (
                    <div className="flex items-center gap-1 text-xs">
                      <span className="text-zinc-400">Are you sure?</span>
                      <button
                        onClick={() => handleDelete(note.id)}
                        className="px-1.5 py-0.5 rounded bg-red-600 hover:bg-red-500 text-white transition-colors"
                      >
                        Confirm
                      </button>
                      <button
                        onClick={() => setConfirmingDelete(null)}
                        className="px-1.5 py-0.5 rounded bg-zinc-700 hover:bg-zinc-600 text-zinc-300 transition-colors"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <button
                      onClick={() => setConfirmingDelete(note.id)}
                      className="p-1 rounded hover:bg-zinc-700 text-zinc-400 hover:text-red-400 transition-colors"
                      title="Delete note"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Content preview */}
              <p className="mt-1 text-xs text-zinc-400 leading-relaxed">
                {truncateContent(note.content)}
              </p>

              {/* Footer: tags + source + timestamp */}
              <div className="mt-2 flex items-center justify-between gap-2">
                <div className="flex items-center gap-1.5 flex-wrap min-w-0">
                  {note.tags.map((tag) => (
                    <span
                      key={tag}
                      className={cn(
                        'px-1.5 py-0.5 text-[10px] rounded-full',
                        getTagColor(tag)
                      )}
                    >
                      {tag}
                    </span>
                  ))}
                </div>
                <div className="flex items-center gap-2 flex-shrink-0">
                  <SourceBadge source={note.source} />
                  <span className="text-[10px] text-zinc-500">
                    {formatRelativeTime(note.updated_at)}
                  </span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

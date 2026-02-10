/**
 * Knowledge Search Component
 *
 * Search across documents and notes with debounced input and result display.
 */

import { useState, useEffect, useRef } from 'react'
import { Search, FileText, StickyNote, RefreshCw, X } from 'lucide-react'
import { useKnowledgeStore, type SearchResult } from '../../stores/knowledge'

interface KnowledgeSearchProps {
  botId: string
}

function ResultTypeIcon({ type }: { type: SearchResult['type'] }) {
  if (type === 'document') {
    return <FileText className="h-4 w-4 text-blue-400 flex-shrink-0" />
  }
  return <StickyNote className="h-4 w-4 text-amber-400 flex-shrink-0" />
}

function truncate(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength).trimEnd() + '...'
}

export function KnowledgeSearch({ botId }: KnowledgeSearchProps) {
  const [query, setQuery] = useState('')
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined)
  const inputRef = useRef<HTMLInputElement>(null)

  const { searchKnowledge, clearSearchResults, searchResults, loadingSearch } =
    useKnowledgeStore()

  useEffect(() => {
    if (!query.trim()) {
      clearSearchResults()
      return
    }
    debounceRef.current = setTimeout(() => {
      searchKnowledge(botId, query)
    }, 300)
    return () => clearTimeout(debounceRef.current)
  }, [query, botId, searchKnowledge, clearSearchResults])

  // Clean up on unmount
  useEffect(() => {
    return () => {
      clearSearchResults()
      clearTimeout(debounceRef.current)
    }
  }, [clearSearchResults])

  const handleClear = () => {
    setQuery('')
    clearSearchResults()
    inputRef.current?.focus()
  }

  const hasQuery = query.trim().length > 0

  return (
    <div className="space-y-3">
      {/* Search input */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
        <input
          ref={inputRef}
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search knowledge base..."
          className="w-full pl-9 pr-9 py-2 bg-zinc-800 border border-zinc-700 rounded-lg
            text-sm text-zinc-200 placeholder:text-zinc-500
            focus:outline-none focus:ring-1 focus:ring-cachi-500 focus:border-cachi-500
            transition-colors"
        />
        {hasQuery && (
          <button
            onClick={handleClear}
            className="absolute right-2 top-1/2 -translate-y-1/2 p-1 rounded
              text-zinc-500 hover:text-zinc-300 hover:bg-zinc-700 transition-colors"
            title="Clear search"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      {/* Results panel - only shown after user has typed something */}
      {hasQuery && (
        <div className="rounded-lg border border-zinc-700 bg-zinc-800/50 overflow-hidden">
          {/* Loading state */}
          {loadingSearch && (
            <div className="flex items-center justify-center gap-2 py-6">
              <RefreshCw className="h-4 w-4 animate-spin text-cachi-500" />
              <span className="text-sm text-zinc-400">Searching...</span>
            </div>
          )}

          {/* Empty state */}
          {!loadingSearch && searchResults.length === 0 && (
            <div className="text-center py-6">
              <Search className="h-6 w-6 mx-auto mb-2 text-zinc-600" />
              <p className="text-sm text-zinc-500">No results found</p>
            </div>
          )}

          {/* Results list */}
          {!loadingSearch && searchResults.length > 0 && (
            <ul className="divide-y divide-zinc-700/50">
              {searchResults.map((result) => (
                <li
                  key={`${result.type}-${result.id}`}
                  className="px-4 py-3 hover:bg-zinc-700/30 transition-colors"
                >
                  <div className="flex items-start gap-3">
                    <div className="mt-0.5">
                      <ResultTypeIcon type={result.type} />
                    </div>

                    <div className="flex-1 min-w-0">
                      {/* Title row */}
                      <div className="flex items-center gap-2 mb-1">
                        <span className="text-sm font-medium text-zinc-200 truncate">
                          {result.title}
                        </span>
                        {result.score !== null && (
                          <span
                            className="flex-shrink-0 text-xs px-1.5 py-0.5 rounded
                              bg-cachi-500/15 text-cachi-400 font-mono"
                          >
                            {result.score.toFixed(2)}
                          </span>
                        )}
                      </div>

                      {/* Content preview */}
                      <p className="text-xs text-zinc-400 leading-relaxed">
                        {truncate(result.content, 200)}
                      </p>

                      {/* Source label */}
                      {result.source && (
                        <span className="inline-block mt-1.5 text-xs text-zinc-500">
                          {result.source}
                        </span>
                      )}
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

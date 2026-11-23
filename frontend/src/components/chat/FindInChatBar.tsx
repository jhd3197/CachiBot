/**
 * UI v2 "Find in chat" bar (design 03) — purely client-side search over the
 * messages of the active chat. Ctrl/Cmd+F opens it; Enter = next match,
 * Shift+Enter = previous; Escape closes.
 */

import { Search, ChevronUp, ChevronDown, X } from 'lucide-react'
import { useEffect, useRef } from 'react'

interface FindInChatBarProps {
  query: string
  onQueryChange: (query: string) => void
  /** 1-based index of the current match, 0 when there are no matches */
  current: number
  total: number
  onPrev: () => void
  onNext: () => void
  onClose: () => void
}

export function FindInChatBar({
  query,
  onQueryChange,
  current,
  total,
  onPrev,
  onNext,
  onClose,
}: FindInChatBarProps) {
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  return (
    <div className="v2-findbar">
      <Search className="v2-findbar__icon" />
      <input
        ref={inputRef}
        type="text"
        value={query}
        onChange={(e) => onQueryChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault()
            if (e.shiftKey) {
              onPrev()
            } else {
              onNext()
            }
          }
          if (e.key === 'Escape') {
            e.preventDefault()
            onClose()
          }
        }}
        placeholder="Find in chat"
        className="v2-findbar__input"
      />
      <span className="v2-findbar__count">
        {total === 0 ? (query ? 'No results' : '') : `${current} of ${total}`}
      </span>
      <div className="v2-findbar__btns">
        <button type="button" onClick={onPrev} className="v2-icon-action" title="Previous" aria-label="Previous match">
          <ChevronUp className="h-3.5 w-3.5" />
        </button>
        <button type="button" onClick={onNext} className="v2-icon-action" title="Next" aria-label="Next match">
          <ChevronDown className="h-3.5 w-3.5" />
        </button>
        <button type="button" onClick={onClose} className="v2-icon-action" title="Close" aria-label="Close search">
          <X className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  )
}

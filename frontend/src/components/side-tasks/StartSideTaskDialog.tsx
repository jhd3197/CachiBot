/**
 * "Start a side task" dialog (design 11c): opened from a message's
 * More › "Do this on the side" (prompt prefilled from that message) or the
 * composer's + › "Side task". Posts to the real start endpoint; the
 * backend's clear error (e.g. the workspace is not a git repository, or the
 * chat is unknown to the server) is shown inline and as a toast.
 */

import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { GitBranch } from 'lucide-react'
import { toast } from 'sonner'
import { useSideTasksStore } from '../../stores/side-tasks'

interface StartSideTaskDialogProps {
  botId: string
  /** The parent chat the side task belongs to. */
  chatId: string
  /** Prefilled prompt (from the message or the composer). */
  initialPrompt?: string
  onClose: () => void
}

export function StartSideTaskDialog({ botId, chatId, initialPrompt = '', onClose }: StartSideTaskDialogProps) {
  const navigate = useNavigate()
  const start = useSideTasksStore((s) => s.start)
  const [prompt, setPrompt] = useState(initialPrompt)
  const [error, setError] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
    inputRef.current?.select()
  }, [])

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const handleStart = async () => {
    const trimmed = prompt.trim()
    if (!trimmed || busy) return
    setBusy(true)
    setError(null)
    try {
      const task = await start(botId, chatId, trimmed)
      toast.success(`Side task "${task.title}" started`)
      onClose()
      // Open the side task's own chat so its progress is visible.
      navigate(`/${task.botId}/chats/${task.chatId}`)
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Could not start the side task'
      setError(message)
      toast.error(message)
      setBusy(false)
    }
  }

  return (
    <div className="side-task-dialog" onClick={onClose}>
      <div
        className="side-task-dialog__panel"
        role="dialog"
        aria-modal="true"
        aria-label="Start a side task"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="side-task-dialog__title">
          <GitBranch size={15} strokeWidth={1.8} style={{ marginRight: 8, verticalAlign: -2 }} />
          Start a side task
        </h2>
        <p className="side-task-dialog__hint">
          Runs in its own copy of the files and reports back here when it is done.
        </p>
        <textarea
          ref={inputRef}
          className="side-task-dialog__input"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault()
              void handleStart()
            }
          }}
          placeholder="What should it do?"
          rows={4}
        />
        {error && <p className="side-task-dialog__error">{error}</p>}
        <div className="side-task-dialog__actions">
          <button type="button" className="v2-mini-btn" onClick={onClose}>
            Cancel
          </button>
          <button
            type="button"
            className="v2-mini-btn v2-mini-btn--primary"
            disabled={!prompt.trim() || busy}
            onClick={() => void handleStart()}
          >
            {busy ? 'Starting…' : 'Start side task'}
          </button>
        </div>
      </div>
    </div>
  )
}

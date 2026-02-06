import { useState, useRef, useEffect, type KeyboardEvent } from 'react'
import { Send, Square } from 'lucide-react'
import { Button } from '../common/Button'
import { cn } from '../../lib/utils'

interface InputAreaProps {
  onSend: (message: string) => void
  onCancel: () => void
  isLoading: boolean
  disabled: boolean
}

export function InputArea({ onSend, onCancel, isLoading, disabled }: InputAreaProps) {
  const [input, setInput] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Auto-resize textarea
  useEffect(() => {
    const textarea = textareaRef.current
    if (textarea) {
      textarea.style.height = 'auto'
      textarea.style.height = `${Math.min(textarea.scrollHeight, 200)}px`
    }
  }, [input])

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleSend = () => {
    const message = input.trim()
    if (!message || isLoading || disabled) return

    onSend(message)
    setInput('')
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  return (
    <div className="relative">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? 'Connecting...' : 'Type a message...'}
        disabled={disabled || isLoading}
        rows={1}
        className={cn(
          'w-full resize-none rounded-xl border border-zinc-200 bg-white px-4 py-3 pr-24 text-sm',
          'placeholder:text-zinc-400',
          'focus:border-cachi-500 focus:outline-none focus:ring-2 focus:ring-cachi-500/20',
          'disabled:cursor-not-allowed disabled:opacity-50',
          'dark:border-zinc-700 dark:bg-zinc-900 dark:text-zinc-100'
        )}
      />

      <div className="absolute bottom-2 right-2 flex items-center gap-1">
        {isLoading ? (
          <Button
            variant="danger"
            size="sm"
            onClick={onCancel}
            title="Cancel"
          >
            <Square className="h-4 w-4" />
          </Button>
        ) : (
          <Button
            variant="primary"
            size="sm"
            onClick={handleSend}
            disabled={!input.trim() || disabled}
            title="Send (Enter)"
          >
            <Send className="h-4 w-4" />
          </Button>
        )}
      </div>

      <p className="mt-2 text-center text-xs text-zinc-400">
        Press <kbd className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">Enter</kbd> to send,{' '}
        <kbd className="rounded bg-zinc-100 px-1.5 py-0.5 dark:bg-zinc-800">Shift+Enter</kbd> for new line
      </p>
    </div>
  )
}

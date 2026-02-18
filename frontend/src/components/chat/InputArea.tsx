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
    <div className="chat-input-wrap">
      <textarea
        ref={textareaRef}
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={disabled ? 'Connecting...' : 'Type a message...'}
        disabled={disabled || isLoading}
        rows={1}
        className={cn(
          'chat-input',
          'disabled:cursor-not-allowed disabled:opacity-50'
        )}
      />

      <div className="chat-input-actions">
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

      <p className="chat-input-help">
        Press <kbd className="chat-input-kbd">Enter</kbd> to send,{' '}
        <kbd className="chat-input-kbd">Shift+Enter</kbd> for new line
      </p>
    </div>
  )
}

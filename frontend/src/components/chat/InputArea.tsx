import { useState, useRef, useEffect, useCallback, type KeyboardEvent } from 'react'
import { Send, Square, Paperclip } from 'lucide-react'
import { cn } from '../../lib/utils'
import type { RoomBot } from '../../types'

interface InputAreaProps {
  onSend: (message: string) => void
  onCancel?: () => void
  onTyping?: (isTyping: boolean) => void
  isLoading?: boolean
  disabled?: boolean
  isConnected: boolean
  placeholder?: string
  model?: string
  bots?: RoomBot[]
}

export function InputArea({
  onSend,
  onCancel,
  onTyping,
  isLoading,
  disabled,
  isConnected,
  placeholder,
  model,
  bots,
}: InputAreaProps) {
  const [input, setInput] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionFilter, setMentionFilter] = useState('')
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const typingTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  // Focus textarea on mount
  useEffect(() => {
    textareaRef.current?.focus()
  }, [])

  const handleInputChange = useCallback(
    (value: string) => {
      setInput(value)

      // @mention detection (only when bots are provided)
      if (bots && bots.length > 0) {
        const lastAtIndex = value.lastIndexOf('@')
        if (lastAtIndex >= 0) {
          const afterAt = value.slice(lastAtIndex + 1)
          const beforeAt = lastAtIndex > 0 ? value[lastAtIndex - 1] : ' '
          if (beforeAt === ' ' || lastAtIndex === 0) {
            if (!afterAt.includes(' ') || afterAt.length < 20) {
              setShowMentions(true)
              setMentionFilter(afterAt.toLowerCase())
            } else {
              setShowMentions(false)
            }
          }
        } else {
          setShowMentions(false)
        }
      }

      // Debounced typing indicator
      if (onTyping) {
        onTyping(true)
        if (typingTimeout.current) clearTimeout(typingTimeout.current)
        typingTimeout.current = setTimeout(() => onTyping(false), 3000)
      }
    },
    [bots, onTyping]
  )

  const handleSend = useCallback(() => {
    const message = input.trim()
    if (!message || isLoading || disabled || !isConnected) return

    onSend(message)
    setInput('')
    setShowMentions(false)
    if (onTyping) {
      onTyping(false)
      if (typingTimeout.current) clearTimeout(typingTimeout.current)
    }
  }, [input, isLoading, disabled, isConnected, onSend, onTyping])

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault()
        handleSend()
      }
    },
    [handleSend]
  )

  const insertMention = useCallback(
    (botName: string) => {
      const lastAtIndex = input.lastIndexOf('@')
      if (lastAtIndex >= 0) {
        const before = input.slice(0, lastAtIndex)
        setInput(`${before}@${botName} `)
      }
      setShowMentions(false)
      textareaRef.current?.focus()
    },
    [input]
  )

  // Filter bots for mention popup
  const showAll = bots && 'all'.includes(mentionFilter)
  const filteredBots = bots?.filter((b) =>
    b.botName.toLowerCase().includes(mentionFilter)
  ) || []
  const hasMentionPopup = bots && showMentions && (showAll || filteredBots.length > 0)

  const defaultPlaceholder = bots
    ? 'Type a message... Use @BotName or @all to mention bots'
    : 'Type a message...'

  return (
    <div className="chat-panel__input-area">
      <div className="chat-panel__input-inner">
        <div className="chat-input-container">
          {/* @mention popup */}
          {hasMentionPopup && (
            <div className="chat-input-mention-popup">
              {showAll && (
                <button
                  onClick={() => insertMention('all')}
                  className="chat-input-mention-item"
                >
                  <span style={{ fontWeight: 500 }}>@all</span>
                  <span style={{ opacity: 0.6, marginLeft: 8, fontSize: '0.85em' }}>
                    Everyone in the room
                  </span>
                </button>
              )}
              {filteredBots.map((bot) => (
                <button
                  key={bot.botId}
                  onClick={() => insertMention(bot.botName)}
                  className="chat-input-mention-item"
                >
                  <span style={{ fontWeight: 500 }}>@{bot.botName}</span>
                </button>
              ))}
            </div>
          )}

          {/* Textarea */}
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => handleInputChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={!isConnected ? 'Reconnecting...' : placeholder || defaultPlaceholder}
            disabled={!isConnected || isLoading || disabled}
            rows={1}
            className="chat-textarea"
          />

          {/* Buttons */}
          <div className="chat-input-btns">
            <button
              type="button"
              className="chat-input-btn chat-input-btn--attach"
              title="Attach file"
              disabled={!isConnected || disabled}
            >
              <Paperclip className="h-4 w-4" />
            </button>

            {isLoading && onCancel ? (
              <button
                type="button"
                onClick={onCancel}
                className="chat-input-btn chat-input-btn--stop"
                title="Stop"
              >
                <Square className="h-4 w-4" />
              </button>
            ) : (
              <button
                type="button"
                onClick={handleSend}
                disabled={!input.trim() || !isConnected || disabled}
                className="chat-input-btn chat-input-btn--send"
                title="Send message"
              >
                <Send className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>

        {/* Status bar */}
        <div className="chat-status-bar">
          <div className="chat-status-bar__left">
            <span className="chat-status-bar__indicator">
              <span
                className={cn(
                  'chat-status-bar__dot',
                  isConnected ? 'chat-status-bar__dot--connected' : 'chat-status-bar__dot--disconnected'
                )}
              />
              <span className="chat-status-bar__label">
                {isConnected ? 'Connected' : 'Disconnected'}
              </span>
            </span>
            {model && <span className="chat-status-bar__model">{model}</span>}
          </div>
          <span className="chat-status-bar__hint">Press Enter to send, Shift+Enter for new line</span>
        </div>
      </div>
    </div>
  )
}

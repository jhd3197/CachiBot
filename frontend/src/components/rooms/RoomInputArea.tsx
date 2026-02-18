import { useState, useRef, useEffect, useCallback } from 'react'
import { Send } from 'lucide-react'
import type { RoomBot } from '../../types'

interface RoomInputAreaProps {
  onSend: (message: string) => void
  onTyping: (isTyping: boolean) => void
  bots: RoomBot[]
  disabled?: boolean
}

export function RoomInputArea({ onSend, onTyping, bots, disabled }: RoomInputAreaProps) {
  const [input, setInput] = useState('')
  const [showMentions, setShowMentions] = useState(false)
  const [mentionFilter, setMentionFilter] = useState('')
  const inputRef = useRef<HTMLTextAreaElement>(null)
  const typingTimeout = useRef<ReturnType<typeof setTimeout> | null>(null)

  const handleInputChange = useCallback(
    (value: string) => {
      setInput(value)

      // Check for @mention trigger
      const lastAtIndex = value.lastIndexOf('@')
      if (lastAtIndex >= 0) {
        const afterAt = value.slice(lastAtIndex + 1)
        // Only show if @ is at start or preceded by a space
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

      // Debounced typing indicator
      onTyping(true)
      if (typingTimeout.current) clearTimeout(typingTimeout.current)
      typingTimeout.current = setTimeout(() => onTyping(false), 3000)
    },
    [onTyping]
  )

  const handleSend = useCallback(() => {
    const trimmed = input.trim()
    if (!trimmed || disabled) return
    onSend(trimmed)
    setInput('')
    setShowMentions(false)
    onTyping(false)
    if (typingTimeout.current) clearTimeout(typingTimeout.current)
  }, [input, disabled, onSend, onTyping])

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
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
      inputRef.current?.focus()
    },
    [input]
  )

  // Filter bots for mention popup
  const filteredBots = bots.filter((b) =>
    b.botName.toLowerCase().includes(mentionFilter)
  )

  // Auto-resize textarea
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = 'auto'
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 120) + 'px'
    }
  }, [input])

  return (
    <div className="room-input">
      {/* @mention popup */}
      {showMentions && filteredBots.length > 0 && (
        <div className="room-input__mention-popup">
          {filteredBots.map((bot) => (
            <button
              key={bot.botId}
              onClick={() => insertMention(bot.botName)}
              className="room-input__mention-item"
            >
              <span style={{ fontWeight: 500 }}>@{bot.botName}</span>
            </button>
          ))}
        </div>
      )}

      <div className="room-input__inner">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... Use @BotName to mention a specific bot"
          disabled={disabled}
          rows={1}
          className="room-input__textarea"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="room-input__send"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  )
}

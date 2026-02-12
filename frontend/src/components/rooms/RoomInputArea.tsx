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
    <div className="relative border-t border-zinc-300 px-4 py-3 dark:border-zinc-800">
      {/* @mention popup */}
      {showMentions && filteredBots.length > 0 && (
        <div className="absolute bottom-full left-4 right-4 z-10 mb-1 rounded-lg border border-zinc-300 bg-white py-1 shadow-lg dark:border-zinc-700 dark:bg-zinc-800">
          {filteredBots.map((bot) => (
            <button
              key={bot.botId}
              onClick={() => insertMention(bot.botName)}
              className="flex w-full items-center gap-2 px-3 py-1.5 text-left text-sm text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-700"
            >
              <span className="font-medium">@{bot.botName}</span>
            </button>
          ))}
        </div>
      )}

      <div className="mx-auto flex max-w-3xl items-end gap-2">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Type a message... Use @BotName to mention a specific bot"
          disabled={disabled}
          rows={1}
          className="max-h-[120px] min-h-[40px] flex-1 resize-none rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 placeholder-zinc-500 outline-none focus:border-accent-500 focus:ring-1 focus:ring-accent-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
        />
        <button
          onClick={handleSend}
          disabled={!input.trim() || disabled}
          className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-lg bg-accent-600 text-white transition-colors hover:bg-accent-500 disabled:opacity-50"
        >
          <Send className="h-4 w-4" />
        </button>
      </div>
    </div>
  )
}

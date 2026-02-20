import { useEffect, useRef, useState } from 'react'
import { User, Copy, CheckCircle } from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { cn, darkenColor } from '../../lib/utils'
import type { RoomMessage } from '../../types'

interface RoomMessageListProps {
  messages: RoomMessage[]
}

export function RoomMessageList({ messages }: RoomMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  // Scroll on new messages AND on streaming content appends (same ID, growing content)
  const lastMsg = messages[messages.length - 1]
  const scrollKey = `${messages.length}-${lastMsg?.content.length ?? 0}`

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [scrollKey])

  if (messages.length === 0) {
    return (
      <div className="room-panel__empty" style={{ flex: 1 }}>
        No messages yet. Start the conversation!
      </div>
    )
  }

  return (
    <div className="room-panel__messages">
      <div className="room-panel__messages-inner">
        {messages.map((msg) => (
          <MessageBubble key={`${msg.id}-${msg.content.length}`} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: RoomMessage }) {
  const [copied, setCopied] = useState(false)
  const bots = useBotStore((s) => s.bots)
  const { accentColor, customHex } = useUIStore()

  if (message.senderType === 'system') {
    return (
      <div className="room-message room-message--system">
        {message.content}
      </div>
    )
  }

  const isBot = message.senderType === 'bot'
  const isUser = !isBot

  // Look up per-bot color/icon
  const bot = isBot ? bots.find((b) => b.id === message.senderId) : undefined
  const botColor = bot?.color
  const botIcon = bot?.icon

  // User accent color
  const userColor = accentColor === 'custom'
    ? generatePalette(customHex)[600]
    : accentColors[accentColor].palette[600]

  const handleCopy = () => {
    navigator.clipboard.writeText(message.content)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={cn(
      'room-message',
      isUser ? 'room-message--user' : 'room-message--bot'
    )}>
      {/* Avatar */}
      <div
        className={cn(
          'room-message__avatar',
          isUser ? 'room-message__avatar--user' : 'room-message__avatar--bot'
        )}
        style={
          isBot && botColor
            ? { backgroundColor: botColor + '20', color: botColor }
            : isUser
              ? { backgroundColor: userColor }
              : undefined
        }
      >
        {isBot ? (
          <BotIconRenderer icon={botIcon || 'bot'} size={16} />
        ) : (
          <User size={16} />
        )}
      </div>

      {/* Content */}
      <div className={cn(
        'room-message__content',
        isUser ? 'room-message__content--user' : 'room-message__content--bot'
      )}>
        <div className="room-message__header">
          <span
            className={cn(
              'room-message__sender',
              isUser ? 'room-message__sender--user' : 'room-message__sender--bot'
            )}
            style={isBot && botColor ? { color: botColor } : undefined}
          >
            {message.senderName}
          </span>
          <span className="room-message__time">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <div
          className={cn(
            'room-message__bubble',
            isUser ? 'room-message__bubble--user' : 'room-message__bubble--bot'
          )}
          style={isUser ? { background: `linear-gradient(135deg, ${userColor}, ${darkenColor(userColor, 15)})` } : undefined}
        >
          {isBot ? (
            <MarkdownRenderer content={message.content} />
          ) : (
            <div className="whitespace-pre-wrap">{message.content}</div>
          )}
        </div>

        {/* Actions (hover-reveal) */}
        <div className="room-message__actions">
          <button onClick={handleCopy} className="chat-message__action-btn">
            {copied ? <CheckCircle className="h-3 w-3" /> : <Copy className="h-3 w-3" />}
            {copied ? 'Copied' : 'Copy'}
          </button>
        </div>
      </div>
    </div>
  )
}

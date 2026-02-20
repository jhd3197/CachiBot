import { useEffect, useRef } from 'react'
import { User, Bot } from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { MessageBubble } from './MessageBubble'
import type { ChatMessage, RoomMessage } from '../../types'
import { cn, formatTime } from '../../lib/utils'

// =============================================================================
// Chat MessageList (1:1 chat)
// =============================================================================

interface MessageListProps {
  messages: ChatMessage[]
}

export function MessageList({ messages }: MessageListProps) {
  return (
    <div className="space-y-4">
      {messages.map((message) => (
        <MessageItem key={message.id} message={message} />
      ))}
    </div>
  )
}

interface MessageItemProps {
  message: ChatMessage
}

function MessageItem({ message }: MessageItemProps) {
  const isUser = message.role === 'user'

  return (
    <div
      className={cn(
        'chat-message',
        isUser ? 'chat-message--user' : 'chat-message--bot'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'chat-message__avatar',
          isUser ? 'chat-message__avatar--user' : 'chat-message__avatar--bot'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div
        className={cn(
          'chat-message__content',
          isUser ? 'chat-message__content--user' : 'chat-message__content--bot'
        )}
      >
        <div
          className={cn(
            'chat-message__bubble',
            isUser ? 'chat-message__bubble--user' : 'chat-message__bubble--bot'
          )}
        >
          <MessageContent content={message.content} />
        </div>
        <span className="chat-message__time">
          {formatTime(message.timestamp)}
        </span>
      </div>
    </div>
  )
}

interface MessageContentProps {
  content: string
}

function MessageContent({ content }: MessageContentProps) {
  // Simple markdown-like rendering for code blocks
  const parts = content.split(/(```[\s\S]*?```)/g)

  return (
    <div className="space-y-2 text-sm">
      {parts.map((part, index) => {
        if (part.startsWith('```')) {
          // Code block
          const match = part.match(/```(\w+)?\n?([\s\S]*?)```/)
          if (match) {
            const [, , code] = match
            return (
              <pre
                key={index}
                className="chat-message__code-block"
              >
                <code>{code.trim()}</code>
              </pre>
            )
          }
        }

        // Regular text - handle inline code
        const inlineParts = part.split(/(`[^`]+`)/g)
        return (
          <p key={index} className="whitespace-pre-wrap">
            {inlineParts.map((inlinePart, inlineIndex) => {
              if (inlinePart.startsWith('`') && inlinePart.endsWith('`')) {
                return (
                  <code
                    key={inlineIndex}
                    className="chat-message__inline-code"
                  >
                    {inlinePart.slice(1, -1)}
                  </code>
                )
              }
              return inlinePart
            })}
          </p>
        )
      })}
    </div>
  )
}

// =============================================================================
// Room MessageList (multi-bot rooms)
// =============================================================================

interface RoomMessageListProps {
  messages: RoomMessage[]
}

export function RoomMessageList({ messages }: RoomMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const bots = useBotStore((s) => s.bots)
  const { accentColor, customHex } = useUIStore()

  const userColor = accentColor === 'custom'
    ? generatePalette(customHex)[600]
    : accentColors[accentColor].palette[600]

  // Scroll on new messages AND on streaming content appends
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
        {messages.map((msg) => {
          const bot = msg.senderType === 'bot' ? bots.find((b) => b.id === msg.senderId) : undefined

          return (
            <MessageBubble
              key={`${msg.id}-${msg.content.length}`}
              message={{
                id: msg.id,
                content: msg.content,
                timestamp: msg.timestamp,
                isUser: msg.senderType === 'user',
                isSystem: msg.senderType === 'system',
                senderName: msg.senderName,
                toolCalls: msg.toolCalls,
                metadata: msg.metadata,
              }}
              botIcon={bot?.icon}
              botColor={bot?.color}
              userColor={userColor}
              showSenderName
            />
          )
        })}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

import { useEffect, useRef } from 'react'
import { Bot, User } from 'lucide-react'
import type { RoomMessage } from '../../types'

interface RoomMessageListProps {
  messages: RoomMessage[]
}

export function RoomMessageList({ messages }: RoomMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages.length])

  if (messages.length === 0) {
    return (
      <div className="room-panel__empty" style={{ flex: 1 }}>
        No messages yet. Start the conversation!
      </div>
    )
  }

  return (
    <div className="room-panel__messages">
      <div className="room-panel__messages-inner" style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
        {messages.map((msg) => (
          <MessageBubble key={`${msg.id}-${msg.content.length}`} message={msg} />
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

function MessageBubble({ message }: { message: RoomMessage }) {
  if (message.senderType === 'system') {
    return (
      <div className="room-message room-message--system">
        {message.content}
      </div>
    )
  }

  const isBot = message.senderType === 'bot'

  return (
    <div className="room-message">
      {/* Avatar */}
      <div className={`room-message__avatar room-message__avatar--${isBot ? 'bot' : 'user'}`}>
        {isBot ? <Bot size={16} /> : <User size={16} />}
      </div>

      {/* Content */}
      <div className="room-message__content">
        <div className="room-message__header">
          <span className={`room-message__sender room-message__sender--${isBot ? 'bot' : 'user'}`}>
            {message.senderName}
          </span>
          <span className="room-message__time">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <div className="room-message__text">
          {message.content}
        </div>
      </div>
    </div>
  )
}

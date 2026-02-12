import { useEffect, useRef } from 'react'
import { Bot, User } from 'lucide-react'
import { cn } from '../../lib/utils'
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
      <div className="flex flex-1 items-center justify-center text-sm text-zinc-500">
        No messages yet. Start the conversation!
      </div>
    )
  }

  return (
    <div className="flex-1 overflow-y-auto px-4 py-4">
      <div className="mx-auto max-w-3xl space-y-3">
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
      <div className="py-1 text-center text-xs text-zinc-500">
        {message.content}
      </div>
    )
  }

  const isBot = message.senderType === 'bot'

  return (
    <div className="flex items-start gap-3">
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full',
          isBot
            ? 'bg-accent-600/20 text-accent-600 dark:text-accent-400'
            : 'bg-blue-600/20 text-blue-600 dark:text-blue-400'
        )}
      >
        {isBot ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div className="min-w-0 flex-1">
        <div className="flex items-baseline gap-2">
          <span
            className={cn(
              'text-sm font-semibold',
              isBot ? 'text-accent-600 dark:text-accent-400' : 'text-blue-600 dark:text-blue-400'
            )}
          >
            {message.senderName}
          </span>
          <span className="text-xs text-zinc-500">
            {new Date(message.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>
        <div className="mt-0.5 whitespace-pre-wrap text-sm text-zinc-800 dark:text-zinc-200">
          {message.content}
        </div>
      </div>
    </div>
  )
}

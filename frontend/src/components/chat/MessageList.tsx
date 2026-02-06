import { User, Bot } from 'lucide-react'
import type { ChatMessage } from '../../types'
import { cn, formatTime } from '../../lib/utils'

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
        'flex gap-3',
        isUser ? 'flex-row-reverse' : 'flex-row'
      )}
    >
      {/* Avatar */}
      <div
        className={cn(
          'flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full',
          isUser
            ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400'
            : 'bg-cachi-100 text-cachi-600 dark:bg-cachi-900/30 dark:text-cachi-400'
        )}
      >
        {isUser ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
      </div>

      {/* Content */}
      <div
        className={cn(
          'flex max-w-[80%] flex-col',
          isUser ? 'items-end' : 'items-start'
        )}
      >
        <div
          className={cn(
            'rounded-2xl px-4 py-2',
            isUser
              ? 'bg-blue-600 text-white'
              : 'bg-zinc-100 text-zinc-900 dark:bg-zinc-800 dark:text-zinc-100'
          )}
        >
          <MessageContent content={message.content} />
        </div>
        <span className="mt-1 text-xs text-zinc-400">
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
                className="overflow-x-auto rounded-lg bg-zinc-900 p-3 text-xs text-zinc-100"
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
                    className="rounded bg-zinc-200 px-1.5 py-0.5 text-xs dark:bg-zinc-700"
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

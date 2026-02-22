import { useEffect, useRef, useCallback, type ReactNode } from 'react'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { useRoomStore } from '../../stores/rooms'
import { MessageBubble } from './MessageBubble'
import { pinMessage, unpinMessage, addBookmark, removeBookmark } from '../../api/rooms'
import type { ChatMessage, RoomMessage } from '../../types'

// =============================================================================
// Chat MessageList (1:1 chat)
// =============================================================================

interface MessageListProps {
  messages: ChatMessage[]
  chatId?: string
  onReply?: (msg: ChatMessage) => void
}

export function MessageList({ messages, chatId, onReply }: MessageListProps) {
  const activeBot = useBotStore((s) => s.getActiveBot())
  const activeChatId = useChatStore((s) => s.activeChatId)
  const resolvedChatId = chatId || activeChatId || ''

  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <MessageBubble
          key={msg.id}
          message={{
            id: msg.id,
            content: msg.content,
            timestamp: msg.timestamp,
            isUser: msg.role === 'user',
            isSystem: msg.role === 'system',
            toolCalls: msg.toolCalls,
            metadata: msg.metadata,
            replyToId: msg.replyToId,
            thinking: msg.thinking,
          }}
          botIcon={activeBot?.icon}
          botColor={activeBot?.color}
          chatId={resolvedChatId}
          onReply={onReply ? () => onReply(msg) : undefined}
        />
      ))}
    </div>
  )
}

// =============================================================================
// Room MessageList (multi-bot rooms)
// =============================================================================

interface RoomMessageListProps {
  messages: RoomMessage[]
  roomId?: string
  children?: ReactNode
}

export function RoomMessageList({ messages, roomId, children }: RoomMessageListProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const bots = useBotStore((s) => s.bots)
  const { accentColor, customHex } = useUIStore()
  const roomActiveToolCalls = useRoomStore((s) => roomId ? s.activeToolCalls[roomId] : undefined)
  const roomBotStates = useRoomStore((s) => roomId ? s.botStates[roomId] : undefined)
  const pinnedMessages = useRoomStore((s) => roomId ? s.pinnedMessages[roomId] : undefined)
  const bookmarkedIds = useRoomStore((s) => roomId ? s.bookmarkedMessageIds[roomId] : undefined)
  const { removePinnedMessage: removePin, addBookmarkedId, removeBookmarkedId } = useRoomStore()

  const pinnedSet = new Set(pinnedMessages?.map((p) => p.messageId) || [])

  const handlePin = useCallback(async (messageId: string) => {
    if (!roomId) return
    const isPinned = pinnedSet.has(messageId)
    try {
      if (isPinned) {
        await unpinMessage(roomId, messageId)
        removePin(roomId, messageId)
      } else {
        await pinMessage(roomId, messageId)
        // WS broadcast will add it to store
      }
    } catch { /* handled by WS */ }
  }, [roomId, pinnedSet, removePin])

  const handleBookmark = useCallback(async (messageId: string) => {
    if (!roomId) return
    const isBookmarked = bookmarkedIds?.has(messageId) ?? false
    try {
      if (isBookmarked) {
        await removeBookmark(roomId, messageId)
        removeBookmarkedId(roomId, messageId)
      } else {
        await addBookmark(roomId, messageId)
        addBookmarkedId(roomId, messageId)
      }
    } catch { /* handled */ }
  }, [roomId, bookmarkedIds, addBookmarkedId, removeBookmarkedId])

  const userColor = accentColor === 'custom'
    ? generatePalette(customHex)[600]
    : accentColors[accentColor].palette[600]

  // Scroll on new messages, streaming content appends, and tool call changes
  const lastMsg = messages[messages.length - 1]
  const activeCallCount = roomActiveToolCalls ? Object.values(roomActiveToolCalls).flat().length : 0
  const scrollKey = `${messages.length}-${lastMsg?.content.length ?? 0}-${activeCallCount}`

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [scrollKey, children])

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
          // Merge finalized tool calls with active (in-flight) tool calls
          const toolCalls = msg.toolCalls ?? roomActiveToolCalls?.[msg.id] ?? undefined
          // Bot is still streaming if it's in thinking/responding state
          const botState = msg.senderType === 'bot' && roomBotStates ? roomBotStates[msg.senderId] : undefined
          const isBotStreaming = botState === 'thinking' || botState === 'responding'

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
                toolCalls,
                metadata: msg.metadata,
                thinking: msg.thinking,
                reactions: msg.reactions,
              }}
              botIcon={bot?.icon}
              botColor={bot?.color}
              userColor={userColor}
              showSenderName
              isStreaming={isBotStreaming}
              roomId={roomId}
              onPin={() => handlePin(msg.id)}
              onBookmark={() => handleBookmark(msg.id)}
              isPinned={pinnedSet.has(msg.id)}
              isBookmarked={bookmarkedIds?.has(msg.id) ?? false}
            />
          )
        })}
        {children}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}

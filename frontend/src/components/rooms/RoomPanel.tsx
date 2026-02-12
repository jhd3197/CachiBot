import { useEffect, useState } from 'react'
import { Settings, Users, Bot, Loader2 } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { useRoomWebSocket } from '../../hooks/useRoomWebSocket'
import { getRoomMessages, getRoom } from '../../api/rooms'
import { RoomMessageList } from './RoomMessageList'
import { RoomInputArea } from './RoomInputArea'
import { RoomSettingsDialog } from './RoomSettingsDialog'
import { cn } from '../../lib/utils'
import { useAuthStore } from '../../stores/auth'
import type { Room } from '../../types'

interface RoomPanelProps {
  roomId: string
}

export function RoomPanel({ roomId }: RoomPanelProps) {
  const { messages, botStates, typingUsers, onlineUsers, setMessages, updateRoom } = useRoomStore()
  const { isConnected, sendMessage, sendTyping } = useRoomWebSocket(roomId)
  const [room, setRoom] = useState<Room | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [loading, setLoading] = useState(true)
  const user = useAuthStore((s) => s.user)

  const roomMessages = messages[roomId] || []
  const roomBotStates = botStates[roomId] || {}
  const roomTyping = typingUsers[roomId] || []
  const roomOnline = onlineUsers[roomId] || []

  // Load room data and transcript
  useEffect(() => {
    let cancelled = false

    async function load() {
      setLoading(true)
      try {
        const [roomData, msgs] = await Promise.all([
          getRoom(roomId),
          getRoomMessages(roomId),
        ])
        if (cancelled) return
        setRoom(roomData)
        setMessages(roomId, msgs)
      } catch {
        // Handled by error state
      } finally {
        if (!cancelled) setLoading(false)
      }
    }

    load()
    return () => { cancelled = true }
  }, [roomId, setMessages])

  const handleSettingsUpdate = (updated: Room) => {
    setRoom(updated)
    updateRoom(roomId, updated)
  }

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-zinc-500" />
      </div>
    )
  }

  if (!room) {
    return (
      <div className="flex h-full items-center justify-center text-sm text-zinc-500">
        Room not found
      </div>
    )
  }

  // Active bot statuses
  const activeBots = Object.entries(roomBotStates).filter(
    ([, state]) => state !== 'idle'
  )

  // Is current user the creator?
  const isCreator = user?.id === room.creatorId

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-zinc-300 px-4 dark:border-zinc-800">
        <div className="flex items-center gap-3">
          <h2 className="text-sm font-semibold text-zinc-900 dark:text-zinc-100">
            {room.title}
          </h2>
          {!isConnected && (
            <span className="rounded bg-yellow-500/20 px-1.5 py-0.5 text-[10px] font-medium text-yellow-600 dark:text-yellow-400">
              Reconnecting...
            </span>
          )}
        </div>

        <div className="flex items-center gap-2">
          {/* Online members */}
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Users className="h-3.5 w-3.5" />
            <span>{roomOnline.length}/{room.members.length}</span>
          </div>

          {/* Bot count */}
          <div className="flex items-center gap-1 text-xs text-zinc-500">
            <Bot className="h-3.5 w-3.5" />
            <span>{room.bots.length}</span>
          </div>

          {/* Settings button */}
          {isCreator && (
            <button
              onClick={() => setShowSettings(true)}
              className="flex h-7 w-7 items-center justify-center rounded text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-800"
            >
              <Settings className="h-4 w-4" />
            </button>
          )}
        </div>
      </div>

      {/* Bot status bar */}
      {activeBots.length > 0 && (
        <div className="flex items-center gap-2 border-b border-zinc-300 px-4 py-1.5 dark:border-zinc-800">
          {activeBots.map(([botId, state]) => {
            const bot = room.bots.find((b) => b.botId === botId)
            return (
              <span
                key={botId}
                className={cn(
                  'flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium',
                  state === 'thinking'
                    ? 'bg-amber-500/20 text-amber-600 dark:text-amber-400'
                    : 'bg-accent-500/20 text-accent-600 dark:text-accent-400'
                )}
              >
                <Loader2 className="h-3 w-3 animate-spin" />
                {bot?.botName || botId} is {state === 'thinking' ? 'thinking' : 'responding'}...
              </span>
            )
          })}
        </div>
      )}

      {/* Messages */}
      <RoomMessageList messages={roomMessages} />

      {/* Typing indicators */}
      {roomTyping.length > 0 && (
        <div className="px-4 py-1 text-xs text-zinc-500">
          {roomTyping.map((t) => t.username).join(', ')}
          {roomTyping.length === 1 ? ' is' : ' are'} typing...
        </div>
      )}

      {/* Input */}
      <RoomInputArea
        onSend={sendMessage}
        onTyping={sendTyping}
        bots={room.bots}
        disabled={!isConnected}
      />

      {/* Settings dialog */}
      {showSettings && room && (
        <RoomSettingsDialog
          room={room}
          onClose={() => setShowSettings(false)}
          onUpdate={handleSettingsUpdate}
        />
      )}
    </div>
  )
}

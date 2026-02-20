import { useEffect, useState } from 'react'
import { Settings, Users, Bot, Loader2 } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { useRoomWebSocket } from '../../hooks/useRoomWebSocket'
import { getRoomMessages, getRoom } from '../../api/rooms'
import { RoomMessageList } from '../chat/MessageList'
import { InputArea } from '../chat/InputArea'
import { RoomSettingsDialog } from './RoomSettingsDialog'
import { useAuthStore } from '../../stores/auth'
import type { Room } from '../../types'

interface RoomPanelProps {
  roomId: string
}

export function RoomPanel({ roomId }: RoomPanelProps) {
  const { messages, botStates, typingUsers, onlineUsers, setMessages, updateRoom, deleteRoom, setActiveRoom, chainStep, routeDecision } = useRoomStore()
  const [room, setRoom] = useState<Room | null>(null)
  const [showSettings, setShowSettings] = useState(false)
  const [loading, setLoading] = useState(true)

  // Connect WebSocket only after the initial REST load finishes so that
  // setMessages() from the REST response cannot overwrite messages that
  // arrived via WebSocket in the meantime.
  const { isConnected, sendMessage, sendTyping } = useRoomWebSocket(loading ? null : roomId)
  const user = useAuthStore((s) => s.user)

  const roomMessages = messages[roomId] || []
  const roomBotStates = botStates[roomId] || {}
  const roomTyping = typingUsers[roomId] || []
  const roomOnline = onlineUsers[roomId] || []
  const roomChainStep = chainStep[roomId] || null
  const roomRouteDecision = routeDecision[roomId] || null

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

  const handleDeleteRoom = () => {
    deleteRoom(roomId)
    setActiveRoom(null)
  }

  if (loading) {
    return (
      <div className="room-panel__loading">
        <Loader2 size={24} className="animate-spin" style={{ color: 'var(--color-text-secondary)' }} />
      </div>
    )
  }

  if (!room) {
    return (
      <div className="room-panel__empty">
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
    <div className="room-panel">
      {/* Header */}
      <div className="room-panel__header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
          <h2 className="room-panel__title">
            {room.title}
          </h2>
          {!isConnected && (
            <span className="room-panel__reconnecting">
              Reconnecting...
            </span>
          )}
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* Online members */}
          <div className="room-panel__counter">
            <Users size={14} />
            <span>{roomOnline.length}/{room.members.length}</span>
          </div>

          {/* Bot count */}
          <div className="room-panel__counter">
            <Bot size={14} />
            <span>{room.bots.length}</span>
          </div>

          {/* Settings button */}
          {isCreator && (
            <button
              onClick={() => setShowSettings(true)}
              className="room-panel__icon-btn"
            >
              <Settings size={16} />
            </button>
          )}
        </div>
      </div>

      {/* Chain step indicator */}
      {roomChainStep && (
        <div className="room-panel__chain-step">
          Step {roomChainStep.step}/{roomChainStep.totalSteps}: {roomChainStep.botName}
        </div>
      )}

      {/* Route decision indicator */}
      {roomRouteDecision && (
        <div className="room-panel__route-decision">
          Routed to {roomRouteDecision.botName} — {roomRouteDecision.reason}
        </div>
      )}

      {/* Bot status bar */}
      {activeBots.length > 0 && (
        <div className="room-panel__status-bar">
          {activeBots.map(([botId, state]) => {
            const bot = room.bots.find((b) => b.botId === botId)
            return (
              <span
                key={botId}
                className={`room-panel__bot-status room-panel__bot-status--${state === 'thinking' ? 'thinking' : 'responding'}`}
              >
                <Loader2 size={12} className="animate-spin" />
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
        <div className="room-panel__typing">
          {roomTyping.map((t) => t.username).join(', ')}
          {roomTyping.length === 1 ? ' is' : ' are'} typing...
        </div>
      )}

      {/* Input */}
      <InputArea
        onSend={sendMessage}
        onTyping={sendTyping}
        bots={room.bots}
        isConnected={isConnected}
      />

      {/* Settings dialog */}
      {showSettings && room && (
        <RoomSettingsDialog
          room={room}
          onClose={() => setShowSettings(false)}
          onUpdate={handleSettingsUpdate}
          onDelete={handleDeleteRoom}
        />
      )}
    </div>
  )
}

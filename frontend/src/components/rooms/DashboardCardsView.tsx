import { useMemo } from 'react'
import { Loader2 } from 'lucide-react'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import type { RoomMessage, RoomBot } from '../../types'

interface DashboardCardsViewProps {
  roomId: string
  messages: RoomMessage[]
  roomBots: RoomBot[]
}

export function DashboardCardsView({ roomId, messages, roomBots }: DashboardCardsViewProps) {
  const bots = useBotStore((s) => s.bots)
  const botStates = useRoomStore((s) => s.botStates[roomId] || {})
  const botActivity = useRoomStore((s) => s.botActivity[roomId] || {})
  const activeToolCalls = useRoomStore((s) => s.activeToolCalls[roomId] || {})

  // Group messages by bot
  const botMessages = useMemo(() => {
    const grouped: Record<string, RoomMessage[]> = {}
    for (const rb of roomBots) {
      grouped[rb.botId] = []
    }
    for (const msg of messages) {
      if (msg.senderType === 'bot' && grouped[msg.senderId]) {
        grouped[msg.senderId].push(msg)
      }
    }
    return grouped
  }, [messages, roomBots])

  if (roomBots.length === 0) {
    return (
      <div className="room-panel__empty" style={{ flex: 1 }}>
        No bots in this room.
      </div>
    )
  }

  return (
    <div className="room-cards-view">
      {roomBots.map((rb) => {
        const bot = bots.find((b) => b.id === rb.botId)
        const msgs = botMessages[rb.botId] || []
        const lastMsg = msgs[msgs.length - 1]
        const state = botStates[rb.botId]
        const activity = botActivity[rb.botId]
        const toolCalls = Object.values(activeToolCalls[rb.botId] || {})
        const isActive = state === 'thinking' || state === 'responding'

        return (
          <div key={rb.botId} className={`room-card-bot ${isActive ? 'room-card-bot--active' : ''}`}>
            <div className="room-card-bot__header">
              <BotIconRenderer icon={bot?.icon || 'bot'} size={20} />
              <span className="room-card-bot__name">{rb.botName}</span>
              <span className="room-card-bot__role">{rb.role}</span>
              {isActive && (
                <Loader2 size={12} className="animate-spin" style={{ marginLeft: 'auto', color: 'var(--accent-500)' }} />
              )}
            </div>

            <div className="room-card-bot__content">
              {isActive && !lastMsg?.content && (
                <span className="form-field__help">
                  {activity ? `Calling ${activity}...` : state === 'thinking' ? 'Thinking...' : 'Responding...'}
                </span>
              )}
              {lastMsg?.content ? (
                <MarkdownRenderer content={lastMsg.content} />
              ) : (
                !isActive && <span className="form-field__help">No responses yet</span>
              )}
            </div>

            <div className="room-card-bot__meta">
              <span>{msgs.length} message{msgs.length !== 1 ? 's' : ''}</span>
              {toolCalls.length > 0 && (
                <span>{toolCalls.length} active tool call{toolCalls.length !== 1 ? 's' : ''}</span>
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}

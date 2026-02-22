import { useEffect, useState } from 'react'
import { Pin, ChevronDown, X } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { getPinnedMessages, unpinMessage } from '../../api/rooms'
import { scrollToMessage } from '../chat/MessageBubble'
import type { PinnedMessage } from '../../types'

interface PinnedMessagesBarProps {
  roomId: string
}

export function PinnedMessagesBar({ roomId }: PinnedMessagesBarProps) {
  const [expanded, setExpanded] = useState(false)
  const { pinnedMessages, setPinnedMessages, removePinnedMessage } = useRoomStore()
  const pins = pinnedMessages[roomId] || []

  useEffect(() => {
    async function load() {
      try {
        const data = await getPinnedMessages(roomId) as PinnedMessage[]
        setPinnedMessages(roomId, data)
      } catch {
        // Silently fail
      }
    }
    load()
  }, [roomId, setPinnedMessages])

  if (pins.length === 0) return null

  const handleUnpin = async (messageId: string) => {
    try {
      await unpinMessage(roomId, messageId)
      removePinnedMessage(roomId, messageId)
    } catch {
      // Silently fail
    }
  }

  return (
    <div className="pinned-bar">
      <button
        className="pinned-bar__toggle"
        onClick={() => setExpanded(!expanded)}
      >
        <Pin size={12} />
        <span>{pins.length} pinned message{pins.length !== 1 ? 's' : ''}</span>
        <ChevronDown
          size={12}
          style={{ transform: expanded ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}
        />
      </button>

      {expanded && (
        <div className="pinned-bar__list">
          {pins.map((pin) => (
            <div key={pin.messageId} className="pinned-bar__item">
              <button
                className="pinned-bar__content"
                onClick={() => scrollToMessage(pin.messageId)}
              >
                <span className="pinned-bar__sender">{pin.senderName || 'Unknown'}</span>
                <span className="pinned-bar__text">
                  {pin.content || 'Jump to message'}
                </span>
              </button>
              <button
                className="pinned-bar__unpin"
                onClick={() => handleUnpin(pin.messageId)}
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

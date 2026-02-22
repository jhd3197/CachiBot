import { useState } from 'react'
import { SmilePlus } from 'lucide-react'
import { useAuthStore } from '../../stores/auth'
import { addReaction, removeReaction } from '../../api/rooms'
import type { ReactionSummary } from '../../types'

const ALLOWED_EMOJIS = ['👍', '👎', '❤️', '😂', '🤔', '🎉']

interface ReactionBarProps {
  roomId: string
  messageId: string
  reactions: ReactionSummary[]
}

export function ReactionBar({ roomId, messageId, reactions }: ReactionBarProps) {
  const [showPicker, setShowPicker] = useState(false)
  const userId = useAuthStore((s) => s.user?.id)

  const handleToggleReaction = async (emoji: string) => {
    if (!userId) return
    const existing = reactions.find((r) => r.emoji === emoji)
    const hasReacted = existing?.userIds.includes(userId)

    try {
      if (hasReacted) {
        await removeReaction(roomId, messageId, emoji)
      } else {
        await addReaction(roomId, messageId, emoji)
      }
    } catch {
      // Handled by WS broadcast
    }
    setShowPicker(false)
  }

  return (
    <div className="reaction-bar">
      {/* Existing reactions as pills */}
      {reactions.map((r) => {
        const hasReacted = userId ? r.userIds.includes(userId) : false
        return (
          <button
            key={r.emoji}
            className={`reaction-bar__pill${hasReacted ? ' reaction-bar__pill--active' : ''}`}
            onClick={() => handleToggleReaction(r.emoji)}
          >
            <span>{r.emoji}</span>
            <span className="reaction-bar__count">{r.count}</span>
          </button>
        )
      })}

      {/* Add reaction button */}
      <div className="reaction-bar__picker-wrap">
        <button
          className="reaction-bar__add"
          onClick={() => setShowPicker(!showPicker)}
        >
          <SmilePlus size={14} />
        </button>

        {showPicker && (
          <div className="reaction-bar__picker">
            {ALLOWED_EMOJIS.map((emoji) => (
              <button
                key={emoji}
                className="reaction-bar__picker-btn"
                onClick={() => handleToggleReaction(emoji)}
              >
                {emoji}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

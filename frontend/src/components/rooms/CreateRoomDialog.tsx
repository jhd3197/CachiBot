import { useState } from 'react'
import { X, Plus, Minus } from 'lucide-react'
import { toast } from 'sonner'
import { createRoom } from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'

interface CreateRoomDialogProps {
  onClose: () => void
}

export function CreateRoomDialog({ onClose }: CreateRoomDialogProps) {
  const { bots } = useBotStore()
  const { addRoom, setActiveRoom } = useRoomStore()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [selectedBotIds, setSelectedBotIds] = useState<string[]>([])
  const [cooldown, setCooldown] = useState(5)
  const [autoRelevance, setAutoRelevance] = useState(true)
  const [creating, setCreating] = useState(false)

  const toggleBot = (botId: string) => {
    setSelectedBotIds((prev) =>
      prev.includes(botId)
        ? prev.filter((id) => id !== botId)
        : prev.length < 4
          ? [...prev, botId]
          : prev
    )
  }

  const handleCreate = async () => {
    if (!title.trim()) {
      toast.error('Title is required')
      return
    }
    if (selectedBotIds.length < 2) {
      toast.error('Select at least 2 bots')
      return
    }

    setCreating(true)
    try {
      const room = await createRoom({
        title: title.trim(),
        description: description.trim() || undefined,
        bot_ids: selectedBotIds,
        settings: {
          cooldown_seconds: cooldown,
          auto_relevance: autoRelevance,
          response_mode: 'parallel',
        },
      })
      addRoom(room)
      setActiveRoom(room.id)
      toast.success('Room created')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create room')
    } finally {
      setCreating(false)
    }
  }

  return (
    <div className="dialog__backdrop">
      <div className="dialog__panel dialog__panel--sm">
        {/* Header */}
        <div className="dialog__header">
          <h3 className="room-panel__title" style={{ fontSize: '1rem' }}>
            Create Room
          </h3>
          <button onClick={onClose} className="btn-close">
            <X size={16} />
          </button>
        </div>

        {/* Body */}
        <div className="room-settings__section">
          {/* Title */}
          <div className="form-field">
            <label className="form-field__label">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Room name"
              className="input"
            />
          </div>

          {/* Description */}
          <div className="form-field">
            <label className="form-field__label">Description (optional)</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What's this room for?"
              className="input"
            />
          </div>

          {/* Bot selection */}
          <div className="form-field">
            <label className="form-field__label">Select Bots (2-4)</label>
            <div className="room-create__bot-list">
              {bots.map((bot) => {
                const selected = selectedBotIds.includes(bot.id)
                return (
                  <button
                    key={bot.id}
                    onClick={() => toggleBot(bot.id)}
                    className={`room-create__bot-option${selected ? ' room-create__bot-option--selected' : ''}`}
                  >
                    <div
                      className="room-create__bot-icon"
                      style={{ backgroundColor: (bot.color || '#666') + '20' }}
                    >
                      <BotIconRenderer icon={bot.icon} size={14} />
                    </div>
                    <span style={{ flex: 1 }}>{bot.name}</span>
                    {selected ? (
                      <Minus size={14} style={{ color: 'var(--color-danger-text)' }} />
                    ) : selectedBotIds.length < 4 ? (
                      <Plus size={14} style={{ color: 'var(--color-text-tertiary)' }} />
                    ) : null}
                  </button>
                )
              })}
            </div>
            <p className="room-create__bot-count">
              {selectedBotIds.length}/4 bots selected
            </p>
          </div>

          {/* Settings */}
          <div className="room-create__setting-row">
            <div style={{ flex: 1 }}>
              <label className="form-field__label">Cooldown (seconds)</label>
              <input
                type="number"
                value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
                min={1}
                max={30}
                className="input"
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', paddingTop: '1rem' }}>
              <input
                id="auto-relevance"
                type="checkbox"
                checked={autoRelevance}
                onChange={(e) => setAutoRelevance(e.target.checked)}
                className="consent__checkbox"
              />
              <label htmlFor="auto-relevance" className="form-field__help">
                Auto-respond
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="dialog__footer">
          <button onClick={onClose} className="btn btn--ghost btn--sm">
            Cancel
          </button>
          <button
            onClick={handleCreate}
            disabled={creating || selectedBotIds.length < 2 || !title.trim()}
            className="btn btn--primary btn--sm"
          >
            {creating ? 'Creating...' : 'Create Room'}
          </button>
        </div>
      </div>
    </div>
  )
}

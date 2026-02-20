import { useState } from 'react'
import { X, UserPlus, UserMinus, Plus, Minus, RotateCcw, Trash2 } from 'lucide-react'
import { toast } from 'sonner'
import {
  updateRoom as updateRoomApi,
  deleteRoom as deleteRoomApi,
  inviteMember,
  removeMember,
  addRoomBot,
  removeRoomBot,
  clearRoomMessages,
} from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import type { Room } from '../../types'

interface RoomSettingsDialogProps {
  room: Room
  onClose: () => void
  onUpdate: (room: Room) => void
  onDelete?: () => void
}

export function RoomSettingsDialog({ room, onClose, onUpdate, onDelete }: RoomSettingsDialogProps) {
  const { bots: allBots } = useBotStore()
  const { clearMessages } = useRoomStore()
  const [title, setTitle] = useState(room.title)
  const [description, setDescription] = useState(room.description || '')
  const [cooldown, setCooldown] = useState(room.settings.cooldown_seconds)
  const [autoRelevance, setAutoRelevance] = useState(room.settings.auto_relevance)
  const [responseMode, setResponseMode] = useState<'parallel' | 'sequential'>(room.settings.response_mode || 'parallel')
  const [inviteUsername, setInviteUsername] = useState('')
  const [saving, setSaving] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateRoomApi(room.id, {
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        settings: { cooldown_seconds: cooldown, auto_relevance: autoRelevance, response_mode: responseMode },
      })
      onUpdate(updated)
      toast.success('Room updated')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setSaving(false)
    }
  }

  const handleInvite = async () => {
    if (!inviteUsername.trim()) return
    try {
      await inviteMember(room.id, inviteUsername.trim())
      toast.success(`Invited ${inviteUsername}`)
      setInviteUsername('')
      // Refresh room data
      const { getRoom } = await import('../../api/rooms')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to invite')
    }
  }

  const handleRemoveMember = async (userId: string, username: string) => {
    try {
      await removeMember(room.id, userId)
      toast.success(`Removed ${username}`)
      const { getRoom } = await import('../../api/rooms')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove')
    }
  }

  const handleAddBot = async (botId: string) => {
    try {
      await addRoomBot(room.id, botId)
      toast.success('Bot added')
      const { getRoom } = await import('../../api/rooms')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add bot')
    }
  }

  const handleRemoveBot = async (botId: string) => {
    try {
      await removeRoomBot(room.id, botId)
      toast.success('Bot removed')
      const { getRoom } = await import('../../api/rooms')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove bot')
    }
  }

  const roomBotIds = new Set(room.bots.map((b) => b.botId))
  const availableBots = allBots.filter((b) => !roomBotIds.has(b.id))

  return (
    <div className="dialog__backdrop">
      <div className="dialog__panel dialog__panel--sm room-settings__panel">
        {/* Header */}
        <div className="dialog__header">
          <h3 className="room-panel__title" style={{ fontSize: '1rem' }}>
            Room Settings
          </h3>
          <button onClick={onClose} className="btn-close">
            <X size={16} />
          </button>
        </div>

        <div className="room-settings__section">
          {/* Title & description */}
          <div className="form-field">
            <label className="form-field__label">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="input"
            />
          </div>
          <div className="form-field">
            <label className="form-field__label">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input"
            />
          </div>

          {/* Members */}
          <div className="form-field">
            <label className="form-field__label">
              Members ({room.members.length})
            </label>
            <div className="room-settings__member-list">
              {room.members.map((m) => (
                <div key={m.userId} className="room-settings__member-item">
                  <span className="room-settings__member-name">
                    {m.username}
                    {m.role === 'creator' && (
                      <span className="room-settings__member-role">(creator)</span>
                    )}
                  </span>
                  {m.role !== 'creator' && (
                    <button
                      onClick={() => handleRemoveMember(m.userId, m.username)}
                      className="room-settings__bot-remove"
                    >
                      <UserMinus size={14} />
                    </button>
                  )}
                </div>
              ))}
              <div className="room-settings__invite-row">
                <input
                  type="text"
                  value={inviteUsername}
                  onChange={(e) => setInviteUsername(e.target.value)}
                  placeholder="Invite by username"
                  className="room-settings__invite-input"
                  onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
                />
                <button
                  onClick={handleInvite}
                  disabled={!inviteUsername.trim()}
                  className="room-settings__invite-btn"
                >
                  <UserPlus size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Bots */}
          <div className="form-field">
            <label className="form-field__label">
              Bots ({room.bots.length}/4)
            </label>
            <div className="room-settings__member-list">
              {room.bots.map((rb) => (
                <div key={rb.botId} className="room-settings__member-item">
                  <span className="room-settings__member-name">{rb.botName}</span>
                  {room.bots.length > 2 && (
                    <button
                      onClick={() => handleRemoveBot(rb.botId)}
                      className="room-settings__bot-remove"
                    >
                      <Minus size={14} />
                    </button>
                  )}
                </div>
              ))}
              {room.bots.length < 4 && availableBots.length > 0 && (
                <div style={{ marginTop: '0.5rem' }}>
                  <p className="form-field__help" style={{ marginBottom: '0.25rem' }}>Add a bot:</p>
                  {availableBots.slice(0, 5).map((bot) => (
                    <button
                      key={bot.id}
                      onClick={() => handleAddBot(bot.id)}
                      className="room-settings__bot-item"
                    >
                      <BotIconRenderer icon={bot.icon} size={14} />
                      <span>{bot.name}</span>
                      <Plus size={14} style={{ marginLeft: 'auto', color: 'var(--color-text-tertiary)' }} />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Cooldown & auto-relevance */}
          <div className="room-settings__setting-row">
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
                id="settings-auto-relevance"
                type="checkbox"
                checked={autoRelevance}
                onChange={(e) => setAutoRelevance(e.target.checked)}
                className="consent__checkbox"
              />
              <label htmlFor="settings-auto-relevance" className="form-field__help">
                Auto-respond
              </label>
            </div>
          </div>

          {/* Response mode */}
          <div className="form-field">
            <label className="form-field__label">Response Mode</label>
            <div className="room-settings__mode-toggle">
              <button
                type="button"
                onClick={() => setResponseMode('parallel')}
                className={`room-settings__mode-btn ${responseMode === 'parallel' ? 'room-settings__mode-btn--active' : ''}`}
              >
                Parallel
              </button>
              <button
                type="button"
                onClick={() => setResponseMode('sequential')}
                className={`room-settings__mode-btn ${responseMode === 'sequential' ? 'room-settings__mode-btn--active' : ''}`}
              >
                One by one
              </button>
            </div>
            <p className="form-field__help">
              {responseMode === 'parallel'
                ? 'All bots respond at the same time'
                : 'Bots take turns responding one after another'}
            </p>
          </div>
        </div>

        {/* Start Over & Delete */}
        <div className="room-settings__section" style={{ borderTop: '1px solid var(--color-border-primary)' }}>
          {showResetConfirm ? (
            <div className="room-settings__reset-confirm">
              <p className="form-field__help" style={{ margin: 0 }}>
                Clear all messages in this room? This can't be undone.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="btn btn--ghost btn--sm"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      await clearRoomMessages(room.id)
                      clearMessages(room.id)
                      setShowResetConfirm(false)
                      toast.success('Chat cleared')
                    } catch {
                      toast.error('Failed to clear messages')
                    }
                  }}
                  className="btn btn--danger btn--sm"
                >
                  Clear Messages
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowResetConfirm(true)}
              className="btn btn--ghost btn--sm"
              style={{ color: 'var(--color-text-secondary)', width: '100%', justifyContent: 'center', gap: '0.5rem' }}
            >
              <RotateCcw size={14} />
              Start Over
            </button>
          )}

          {showDeleteConfirm ? (
            <div className="room-settings__reset-confirm" style={{ marginTop: '0.5rem' }}>
              <p className="form-field__help" style={{ margin: 0 }}>
                Permanently delete this room and all its messages? This can't be undone.
              </p>
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }}>
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="btn btn--ghost btn--sm"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      await deleteRoomApi(room.id)
                      toast.success('Room deleted')
                      onDelete?.()
                    } catch {
                      toast.error('Failed to delete room')
                    }
                  }}
                  className="btn btn--danger btn--sm"
                >
                  Delete Room
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="btn btn--ghost btn--sm"
              style={{ color: 'var(--color-danger)', width: '100%', justifyContent: 'center', gap: '0.5rem', marginTop: '0.5rem' }}
            >
              <Trash2 size={14} />
              Delete Room
            </button>
          )}
        </div>

        {/* Footer */}
        <div className="dialog__footer">
          <button onClick={onClose} className="btn btn--ghost btn--sm">
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="btn btn--primary btn--sm"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

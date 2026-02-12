import { useState } from 'react'
import { X, UserPlus, UserMinus, Plus, Minus } from 'lucide-react'
import { toast } from 'sonner'
import {
  updateRoom as updateRoomApi,
  inviteMember,
  removeMember,
  addRoomBot,
  removeRoomBot,
} from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { BotIconRenderer } from '../common/BotIconRenderer'
import type { Room } from '../../types'

interface RoomSettingsDialogProps {
  room: Room
  onClose: () => void
  onUpdate: (room: Room) => void
}

export function RoomSettingsDialog({ room, onClose, onUpdate }: RoomSettingsDialogProps) {
  const { bots: allBots } = useBotStore()
  const [title, setTitle] = useState(room.title)
  const [description, setDescription] = useState(room.description || '')
  const [cooldown, setCooldown] = useState(room.settings.cooldown_seconds)
  const [autoRelevance, setAutoRelevance] = useState(room.settings.auto_relevance)
  const [inviteUsername, setInviteUsername] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSave = async () => {
    setSaving(true)
    try {
      const updated = await updateRoomApi(room.id, {
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        settings: { cooldown_seconds: cooldown, auto_relevance: autoRelevance },
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 max-h-[80vh] w-full max-w-md overflow-y-auto rounded-xl border border-zinc-300 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-300 px-4 py-3 dark:border-zinc-800">
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Room Settings
          </h3>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="space-y-4 p-4">
          {/* Title & description */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
            />
          </div>
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Description
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
            />
          </div>

          {/* Members */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Members ({room.members.length})
            </label>
            <div className="space-y-1 rounded-lg border border-zinc-300 p-2 dark:border-zinc-700">
              {room.members.map((m) => (
                <div
                  key={m.userId}
                  className="flex items-center justify-between rounded px-2 py-1 text-sm"
                >
                  <span className="text-zinc-700 dark:text-zinc-300">
                    {m.username}
                    {m.role === 'creator' && (
                      <span className="ml-1 text-xs text-zinc-500">(creator)</span>
                    )}
                  </span>
                  {m.role !== 'creator' && (
                    <button
                      onClick={() => handleRemoveMember(m.userId, m.username)}
                      className="text-red-400 hover:text-red-300"
                    >
                      <UserMinus className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
              <div className="mt-2 flex gap-2">
                <input
                  type="text"
                  value={inviteUsername}
                  onChange={(e) => setInviteUsername(e.target.value)}
                  placeholder="Invite by username"
                  className="flex-1 rounded border border-zinc-300 px-2 py-1 text-sm outline-none dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
                  onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
                />
                <button
                  onClick={handleInvite}
                  disabled={!inviteUsername.trim()}
                  className="rounded bg-accent-600 px-2 py-1 text-xs text-white hover:bg-accent-500 disabled:opacity-50"
                >
                  <UserPlus className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </div>

          {/* Bots */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Bots ({room.bots.length}/4)
            </label>
            <div className="space-y-1 rounded-lg border border-zinc-300 p-2 dark:border-zinc-700">
              {room.bots.map((rb) => (
                <div
                  key={rb.botId}
                  className="flex items-center justify-between rounded px-2 py-1 text-sm"
                >
                  <span className="text-zinc-700 dark:text-zinc-300">{rb.botName}</span>
                  {room.bots.length > 2 && (
                    <button
                      onClick={() => handleRemoveBot(rb.botId)}
                      className="text-red-400 hover:text-red-300"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>
              ))}
              {room.bots.length < 4 && availableBots.length > 0 && (
                <div className="mt-2">
                  <p className="mb-1 text-xs text-zinc-500">Add a bot:</p>
                  {availableBots.slice(0, 5).map((bot) => (
                    <button
                      key={bot.id}
                      onClick={() => handleAddBot(bot.id)}
                      className="flex w-full items-center gap-2 rounded px-2 py-1 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
                    >
                      <BotIconRenderer icon={bot.icon} size={14} />
                      <span>{bot.name}</span>
                      <Plus className="ml-auto h-3.5 w-3.5 text-zinc-400" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Cooldown & auto-relevance */}
          <div className="flex items-center gap-4">
            <div className="flex-1">
              <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
                Cooldown (seconds)
              </label>
              <input
                type="number"
                value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
                min={1}
                max={30}
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm outline-none dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
              />
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                id="settings-auto-relevance"
                type="checkbox"
                checked={autoRelevance}
                onChange={(e) => setAutoRelevance(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-300"
              />
              <label htmlFor="settings-auto-relevance" className="text-xs text-zinc-600 dark:text-zinc-400">
                Auto-respond
              </label>
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="flex justify-end gap-2 border-t border-zinc-300 px-4 py-3 dark:border-zinc-800">
          <button
            onClick={onClose}
            className="rounded-lg px-3 py-1.5 text-sm text-zinc-600 hover:bg-zinc-100 dark:text-zinc-400 dark:hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            className="rounded-lg bg-accent-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-500 disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}

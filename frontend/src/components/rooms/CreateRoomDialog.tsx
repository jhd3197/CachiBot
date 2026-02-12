import { useState } from 'react'
import { X, Plus, Minus } from 'lucide-react'
import { toast } from 'sonner'
import { createRoom } from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'

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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div className="mx-4 w-full max-w-md rounded-xl border border-zinc-300 bg-white shadow-2xl dark:border-zinc-700 dark:bg-zinc-900">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-zinc-300 px-4 py-3 dark:border-zinc-800">
          <h3 className="text-base font-semibold text-zinc-900 dark:text-zinc-100">
            Create Room
          </h3>
          <button
            onClick={onClose}
            className="flex h-7 w-7 items-center justify-center rounded text-zinc-500 hover:bg-zinc-200 dark:hover:bg-zinc-800"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 p-4">
          {/* Title */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Title
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Room name"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-accent-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
            />
          </div>

          {/* Description */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Description (optional)
            </label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What's this room for?"
              className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none focus:border-accent-500 dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
            />
          </div>

          {/* Bot selection */}
          <div>
            <label className="mb-1 block text-xs font-medium text-zinc-600 dark:text-zinc-400">
              Select Bots (2-4)
            </label>
            <div className="max-h-48 space-y-1 overflow-y-auto rounded-lg border border-zinc-300 p-2 dark:border-zinc-700">
              {bots.map((bot) => {
                const selected = selectedBotIds.includes(bot.id)
                return (
                  <button
                    key={bot.id}
                    onClick={() => toggleBot(bot.id)}
                    className={cn(
                      'flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm transition-colors',
                      selected
                        ? 'bg-accent-600/20 text-accent-600 dark:text-accent-400'
                        : 'text-zinc-700 hover:bg-zinc-100 dark:text-zinc-300 dark:hover:bg-zinc-800'
                    )}
                  >
                    <div
                      className="flex h-6 w-6 items-center justify-center rounded"
                      style={{ backgroundColor: (bot.color || '#666') + '20' }}
                    >
                      <BotIconRenderer icon={bot.icon} size={14} />
                    </div>
                    <span className="flex-1">{bot.name}</span>
                    {selected ? (
                      <Minus className="h-3.5 w-3.5 text-red-400" />
                    ) : selectedBotIds.length < 4 ? (
                      <Plus className="h-3.5 w-3.5 text-zinc-400" />
                    ) : null}
                  </button>
                )
              })}
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              {selectedBotIds.length}/4 bots selected
            </p>
          </div>

          {/* Settings */}
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
                className="w-full rounded-lg border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 outline-none dark:border-zinc-700 dark:bg-zinc-800/50 dark:text-zinc-100"
              />
            </div>
            <div className="flex items-center gap-2 pt-4">
              <input
                id="auto-relevance"
                type="checkbox"
                checked={autoRelevance}
                onChange={(e) => setAutoRelevance(e.target.checked)}
                className="h-4 w-4 rounded border-zinc-300 text-accent-600"
              />
              <label
                htmlFor="auto-relevance"
                className="text-xs text-zinc-600 dark:text-zinc-400"
              >
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
            onClick={handleCreate}
            disabled={creating || selectedBotIds.length < 2 || !title.trim()}
            className="rounded-lg bg-accent-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-accent-500 disabled:opacity-50"
          >
            {creating ? 'Creating...' : 'Create Room'}
          </button>
        </div>
      </div>
    </div>
  )
}

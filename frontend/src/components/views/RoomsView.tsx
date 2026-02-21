import { useEffect, useState } from 'react'
import { DoorOpen, Plus, Loader2 } from 'lucide-react'
import { useRoomStore } from '../../stores/rooms'
import { useBotStore } from '../../stores/bots'
import { getRooms } from '../../api/rooms'
import { RoomPanel } from '../rooms/RoomPanel'
import { CreateRoomDialog } from '../rooms/CreateRoomDialog'
import { BotIconRenderer } from '../common/BotIconRenderer'

export function RoomsView() {
  const { activeBotId } = useBotStore()
  const activeBot = useBotStore((s) => s.getActiveBot())
  const { setRooms, activeRoomId, getRoomsForBot } = useRoomStore()
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)

  // Load rooms on mount
  useEffect(() => {
    async function load() {
      setLoading(true)
      try {
        const data = await getRooms()
        setRooms(data)
      } catch {
        // Rooms not available
      } finally {
        setLoading(false)
      }
    }
    load()
  }, [setRooms])

  // If a room is active, show the panel
  if (activeRoomId) {
    return <RoomPanel roomId={activeRoomId} />
  }

  const botRooms = getRoomsForBot(activeBotId ?? '')

  // Welcome / empty state (rooms are listed in the sidebar — no need to duplicate here)
  return (
    <div className="chat-view">
      <div className="flex flex-1 items-center justify-center p-8">
        <div className="max-w-md text-center">
          {loading ? (
            <Loader2 className="mx-auto h-8 w-8 animate-spin text-[var(--color-text-secondary)]" />
          ) : (
            <>
              <div
                className="chat-empty__icon mx-auto"
                style={{ backgroundColor: (activeBot?.color || '#22c55e') + '30' }}
              >
                {botRooms.length === 0 ? (
                  <DoorOpen className="h-12 w-12 text-[var(--color-text-primary)]" />
                ) : (
                  <BotIconRenderer
                    icon={activeBot?.icon || 'shield'}
                    size={48}
                    className="text-[var(--color-text-primary)]"
                  />
                )}
              </div>
              <h2 className="chat-empty__title">
                {botRooms.length === 0
                  ? 'No rooms yet'
                  : `${activeBot?.name || 'CachiBot'} Rooms`}
              </h2>
              <p className="chat-empty__description">
                {botRooms.length === 0
                  ? 'Create a room and add bots to start a multi-bot conversation.'
                  : 'Select a room from the sidebar to continue, or create a new one.'}
              </p>
              <button
                onClick={() => setShowCreate(true)}
                className="mt-6 inline-flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500"
              >
                <Plus className="h-4 w-4" />
                Create a Room
              </button>
            </>
          )}
        </div>
      </div>

      {showCreate && <CreateRoomDialog onClose={() => setShowCreate(false)} />}
    </div>
  )
}

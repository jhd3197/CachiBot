import { useEffect, useState } from 'react'
import { Plus, Users, Bot, Trash2, MoreHorizontal, Loader2 } from 'lucide-react'
import { toast } from 'sonner'
import { useRoomStore } from '../../stores/rooms'
import { getRooms, deleteRoom as deleteRoomApi } from '../../api/rooms'
import { RoomPanel } from '../rooms/RoomPanel'
import { CreateRoomDialog } from '../rooms/CreateRoomDialog'
import { cn } from '../../lib/utils'
import type { Room } from '../../types'

export function RoomsView() {
  const { rooms, setRooms, activeRoomId, setActiveRoom, deleteRoom } = useRoomStore()
  const [showCreate, setShowCreate] = useState(false)
  const [loading, setLoading] = useState(true)
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

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

  const handleDeleteRoom = async (roomId: string) => {
    try {
      await deleteRoomApi(roomId)
      deleteRoom(roomId)
      toast.success('Room deleted')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
    }
    setMenuOpen(null)
  }

  // If a room is active, show the panel
  if (activeRoomId) {
    return <RoomPanel roomId={activeRoomId} />
  }

  // Room list view
  return (
    <div className="rooms-view">
      {/* Header */}
      <div className="rooms-view__header">
        <h1 className="rooms-view__title">Rooms</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="flex items-center gap-1.5 rounded-lg bg-accent-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-accent-500"
        >
          <Plus className="h-4 w-4" />
          Create Room
        </button>
      </div>

      {/* Room list */}
      <div className="rooms-view__content">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-[var(--color-text-secondary)]" />
          </div>
        ) : rooms.length === 0 ? (
          <div className="rooms-view__empty">
            <Users className="mx-auto h-12 w-12 text-[var(--color-text-secondary)]" />
            <p className="mt-3 text-sm text-[var(--color-text-secondary)]">No rooms yet</p>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              Create a room to start a multi-bot conversation
            </p>
            <button
              onClick={() => setShowCreate(true)}
              className="mt-4 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500"
            >
              Create Your First Room
            </button>
          </div>
        ) : (
          <div className="mx-auto max-w-2xl space-y-2">
            {rooms.map((room) => (
              <RoomCard
                key={room.id}
                room={room}
                active={false}
                menuOpen={menuOpen === room.id}
                onSelect={() => setActiveRoom(room.id)}
                onMenuToggle={() => setMenuOpen(menuOpen === room.id ? null : room.id)}
                onDelete={() => handleDeleteRoom(room.id)}
              />
            ))}
          </div>
        )}
      </div>

      {showCreate && <CreateRoomDialog onClose={() => setShowCreate(false)} />}
    </div>
  )
}

function RoomCard({
  room,
  active,
  menuOpen,
  onSelect,
  onMenuToggle,
  onDelete,
}: {
  room: Room
  active: boolean
  menuOpen: boolean
  onSelect: () => void
  onMenuToggle: () => void
  onDelete: () => void
}) {
  return (
    <div className="group relative">
      <button
        onClick={onSelect}
        className={cn(
          'room-card',
          active && 'room-card--active'
        )}
      >
        <div className="room-card__icon">
          <Users className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="room-card__name">{room.title}</h3>
          {room.description && (
            <p className="room-card__description">{room.description}</p>
          )}
          <div className="room-card__stats">
            <span className="flex items-center gap-1">
              <Users className="h-3 w-3" /> {room.members.length} members
            </span>
            <span className="flex items-center gap-1">
              <Bot className="h-3 w-3" /> {room.bots.length} bots
            </span>
            <span>{room.messageCount} messages</span>
          </div>
        </div>
      </button>

      {/* Menu button */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onMenuToggle()
        }}
        className={cn(
          'room-card__menu-btn',
          menuOpen && 'room-card__menu-btn--open'
        )}
      >
        <MoreHorizontal className="h-4 w-4" />
      </button>

      {menuOpen && (
        <div className="room-card-menu">
          <button
            onClick={(e) => {
              e.stopPropagation()
              onDelete()
            }}
            className="room-card-menu__item room-card-menu__item--danger"
          >
            <Trash2 className="h-4 w-4" />
            Delete Room
          </button>
        </div>
      )}
    </div>
  )
}

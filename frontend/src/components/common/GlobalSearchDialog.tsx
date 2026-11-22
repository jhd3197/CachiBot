import { useState, useEffect, useMemo, useRef } from 'react'
import { MessageSquare, DoorOpen, CheckSquare, Search, Bot } from 'lucide-react'
import { useBotStore, useChatStore, useTaskStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { useUIStore } from '../../stores/ui'

type SearchResult =
  | { type: 'bot'; id: string; title: string; meta: string }
  | { type: 'chat'; id: string; title: string; meta: string }
  | { type: 'room'; id: string; title: string; meta: string }
  | { type: 'task'; id: string; title: string; meta: string }

interface GlobalSearchDialogProps {
  /** Bot whose chats/tasks are searched; falls back to the active/first bot */
  botId?: string | null
  onNavigate: (path: string) => void
  onClose: () => void
}

/**
 * Search over bots, the bot's chats and tasks, and all rooms.
 * Opens from the sidebar search icon or Ctrl/Cmd+K anywhere (design 12/13).
 */
export function GlobalSearchDialog({ botId, onNavigate, onClose }: GlobalSearchDialogProps) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const { activeBotId, bots } = useBotStore()
  const { getChatsByBot } = useChatStore()
  const { rooms } = useRoomStore()
  const { getTasksByBot } = useTaskStore()

  // Effective bot: explicit prop, else active, else first (bots group + chats)
  const effectiveBotId = botId ?? activeBotId ?? bots[0]?.id ?? null

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  // Close on Escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  const q = query.toLowerCase().trim()

  const results = useMemo<SearchResult[]>(() => {
    if (!q) return []
    const out: SearchResult[] = []

    for (const bot of bots) {
      if (bot.name.toLowerCase().includes(q) || bot.description?.toLowerCase().includes(q)) {
        const chats = getChatsByBot(bot.id)
        out.push({
          type: 'bot',
          id: bot.id,
          title: bot.name,
          meta: bot.description || `${chats.length} chats`,
        })
      }
    }

    if (effectiveBotId) {
      for (const chat of getChatsByBot(effectiveBotId)) {
        if (chat.title.toLowerCase().includes(q) || chat.lastMessage?.toLowerCase().includes(q)) {
          out.push({
            type: 'chat',
            id: chat.id,
            title: chat.title,
            meta: chat.platform ? `${chat.platform} chat` : formatRelativeTime(chat.updatedAt),
          })
        }
      }

      for (const task of getTasksByBot(effectiveBotId)) {
        if (task.title.toLowerCase().includes(q)) {
          out.push({ type: 'task', id: task.id, title: task.title, meta: task.status })
        }
      }
    }

    for (const room of rooms) {
      if (room.title.toLowerCase().includes(q)) {
        out.push({
          type: 'room',
          id: room.id,
          title: room.title,
          meta: `${room.bots.length} bots · ${room.messageCount ?? 0} msgs`,
        })
      }
    }

    return out
  }, [q, bots, effectiveBotId, getChatsByBot, rooms, getTasksByBot])

  const handleSelect = (result: SearchResult) => {
    switch (result.type) {
      case 'bot': {
        // Same rule as the sidebar row: open the bot's latest chat
        const bot = bots.find((b) => b.id === result.id)
        if (!bot) return
        const chats = getChatsByBot(bot.id)
        const latest = chats[0]
        useChatStore.getState().setActiveChat(latest?.id ?? null)
        onNavigate(latest ? `/${bot.id}/chats/${latest.platform ?? latest.id}` : `/${bot.id}/chats`)
        break
      }
      case 'chat':
        useChatStore.getState().setActiveChat(result.id)
        onNavigate(`/${effectiveBotId}/chats/${result.id}`)
        break
      case 'room': {
        const room = rooms.find((r) => r.id === result.id)
        const botIdForRoom = room?.bots[0]?.botId ?? effectiveBotId
        if (!botIdForRoom) return
        useRoomStore.getState().setActiveRoom(result.id)
        onNavigate(`/${botIdForRoom}/rooms/${result.id}`)
        break
      }
      case 'task':
        useUIStore.getState().setWorkSection('quick-tasks')
        onNavigate(`/${effectiveBotId}/work`)
        break
    }
  }

  const iconFor = (type: SearchResult['type']) => {
    switch (type) {
      case 'bot': return <Bot className="h-4 w-4" />
      case 'chat': return <MessageSquare className="h-4 w-4" />
      case 'room': return <DoorOpen className="h-4 w-4" />
      case 'task': return <CheckSquare className="h-4 w-4" />
    }
  }

  const grouped = useMemo(() => {
    const groups: Record<string, SearchResult[]> = {}
    for (const r of results) {
      ;(groups[r.type] ??= []).push(r)
    }
    return groups
  }, [results])

  const groupLabel: Record<string, string> = { bot: 'Bots', chat: 'Chats', room: 'Rooms', task: 'Tasks' }

  return (
    <div className="v2-sheet-backdrop" onClick={onClose}>
      <div
        className="v2-sheet"
        style={{ alignSelf: 'flex-start', marginTop: '2vh' }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label="Search"
      >
        <div className="v2-search" style={{ margin: '8px 8px 0' }}>
          <Search size={16} strokeWidth={1.8} aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search bots, chats, rooms, tasks..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="v2-search__input"
          />
        </div>

        <div className="v2-sheet__body">
          {!q && (
            <div className="v2-sheet__empty">
              Type to search across your bots, conversations, rooms, and tasks.
            </div>
          )}
          {q && results.length === 0 && (
            <div className="v2-sheet__empty">No results for &ldquo;{query}&rdquo;</div>
          )}
          {Object.entries(grouped).map(([type, items]) => (
            <div key={type}>
              <div className="global-search__group-label">{groupLabel[type] ?? type}</div>
              {items.map((item) => (
                <button
                  key={`${item.type}-${item.id}`}
                  className="v2-chat-item"
                  onClick={() => handleSelect(item)}
                >
                  <div className={`global-search__item-icon global-search__item-icon--${item.type}`}>
                    {iconFor(item.type)}
                  </div>
                  <div className="v2-chat-item__main">
                    <span className="v2-chat-item__name">{item.title}</span>
                    <span className="v2-chat-item__preview">{item.meta}</span>
                  </div>
                </button>
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

function formatRelativeTime(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const minutes = Math.floor(diff / 60000)
  if (minutes < 1) return 'just now'
  if (minutes < 60) return `${minutes}m ago`
  const hours = Math.floor(minutes / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.floor(hours / 24)
  return `${days}d ago`
}

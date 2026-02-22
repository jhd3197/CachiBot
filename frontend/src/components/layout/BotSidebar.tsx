import {
  MessageSquare,
  CheckSquare,
  Wrench,
  Settings,
  Plus,
  Search,
  MoreHorizontal,
  Pin,
  Trash2,
  Archive,
  Bot,
  BookOpen,
  Sparkles,
  Plug,
  AlertTriangle,
  MessageCircle,
  FolderKanban,
  CalendarClock,
  Play,
  Blocks,
  CheckCircle2,
  History,
  Pause,
  Eraser,
  Mic,
  DoorOpen,
  Key,
  Code2,
  X,
  Download,
} from 'lucide-react'
import { useState, useEffect, useMemo, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useBotStore, useChatStore, useTaskStore, useWorkStore, useScheduleStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { getRooms } from '../../api/rooms'
import { useUIStore, type SettingsSection, type WorkSection, type ScheduleSection, type AutomationSection } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { ToolIconRenderer } from '../common/ToolIconRenderer'
import { clearChatMessages } from '../../api/client'
import { cn, downloadJson, slugify } from '../../lib/utils'
import { useBotAccess } from '../../hooks/useBotAccess'
import type { BotView, Chat, Task } from '../../types'

type MinAccessLevel = 'viewer' | 'operator' | 'editor'

const navItems: { id: BotView; label: string; icon: React.ComponentType<{ className?: string }>; minLevel: MinAccessLevel }[] = [
  { id: 'chats', label: 'Chats', icon: MessageSquare, minLevel: 'viewer' },
  { id: 'rooms', label: 'Rooms', icon: DoorOpen, minLevel: 'viewer' },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare, minLevel: 'viewer' },
  { id: 'work', label: 'Work', icon: FolderKanban, minLevel: 'operator' },
  { id: 'schedules', label: 'Schedules', icon: CalendarClock, minLevel: 'operator' },
]

const gearMenuItems: { id: BotView; label: string; icon: React.ComponentType<{ className?: string }>; minLevel: MinAccessLevel }[] = [
  { id: 'automations', label: 'Automations', icon: Blocks, minLevel: 'operator' },
  { id: 'tools', label: 'Tools', icon: Wrench, minLevel: 'editor' },
  { id: 'voice', label: 'Voice', icon: Mic, minLevel: 'operator' },
  { id: 'developer', label: 'Developer', icon: Code2, minLevel: 'editor' },
  { id: 'settings', label: 'Settings', icon: Settings, minLevel: 'editor' },
]

const GEAR_VIEW_IDS = new Set<BotView>(gearMenuItems.map((item) => item.id))

const LEVEL_RANK: Record<string, number> = { viewer: 1, operator: 2, editor: 3, owner: 4, admin: 4 }

interface BotSidebarProps {
  onNavigate?: () => void
}

export function BotSidebar({ onNavigate }: BotSidebarProps) {
  const navigate = useNavigate()
  const { getActiveBot, activeView, setActiveView, activeBotId } = useBotStore()
  const { addChat, setActiveChat } = useChatStore()
  const { sidebarCollapsed } = useUIStore()
  const activeBot = getActiveBot()
  const { accessLevel } = useBotAccess(activeBotId)
  const [openMenu, setOpenMenu] = useState<'gear' | null>(null)
  const [showSearch, setShowSearch] = useState(false)
  const [showCreatePicker, setShowCreatePicker] = useState(false)
  const [showCreateRoom, setShowCreateRoom] = useState(false)

  // Close any open dropdown on click outside
  useEffect(() => {
    if (!openMenu) return
    const handler = () => setOpenMenu(null)
    document.addEventListener('click', handler)
    return () => document.removeEventListener('click', handler)
  }, [openMenu])

  if (!activeBot) return null

  const userRank = LEVEL_RANK[accessLevel ?? 'owner'] ?? 4
  const visibleNavItems = navItems.filter((item) => userRank >= LEVEL_RANK[item.minLevel])
  const visibleGearItems = gearMenuItems.filter((item) => userRank >= LEVEL_RANK[item.minLevel])
  const gearActive = GEAR_VIEW_IDS.has(activeView)
  const toolCount = activeBot.tools?.length ?? 0

  const handleNavClick = (viewId: typeof activeView) => {
    setActiveView(viewId)
    navigate(`/${activeBotId}/${viewId}`)
  }

  const handleNewChat = () => {
    const newChat: Chat = {
      id: crypto.randomUUID(),
      botId: activeBot.id,
      title: 'New Chat',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0,
    }
    addChat(newChat)
    setActiveChat(newChat.id)
    setActiveView('chats')
    navigate(`/${activeBotId}/chats/${newChat.id}`)
    onNavigate?.()
  }

  const toggleMenu = (menu: 'gear') => (e: React.MouseEvent) => {
    e.stopPropagation()
    setOpenMenu(openMenu === menu ? null : menu)
  }

  const gearDropdown = (
    <div className="bot-sidebar__gear-menu">
      {visibleGearItems.map((item) => (
        <button
          key={item.id}
          onClick={() => { handleNavClick(item.id); setOpenMenu(null) }}
          className={cn('context-menu__item', activeView === item.id && 'context-menu__item--active')}
        >
          <item.icon className="h-4 w-4" />
          <span style={{ flex: 1 }}>{item.label}</span>
          {item.id === 'tools' && toolCount > 0 && (
            <span className="sidebar-section-btn__count">{toolCount}</span>
          )}
        </button>
      ))}
    </div>
  )

  return (
    <aside
      className={cn(
        'bot-sidebar',
        sidebarCollapsed ? 'bot-sidebar--collapsed' : 'bot-sidebar--expanded'
      )}
    >
      {/* Bot header */}
      <div className="bot-sidebar__header">
        <div
          className="bot-sidebar__bot-avatar"
          style={{ backgroundColor: activeBot.color + '20' }}
        >
          <BotIconRenderer icon={activeBot.icon} size={18} />
        </div>
        {!sidebarCollapsed && (
          <>
            <h2 className="bot-sidebar__bot-name">{activeBot.name}</h2>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.25rem', alignItems: 'center' }}>
              <button
                onClick={() => setShowCreatePicker(true)}
                title="New"
                className="nav-btn"
              >
                <Plus className="h-4 w-4" />
              </button>
              <button
                onClick={() => setShowSearch(true)}
                title="Search"
                className="nav-btn"
              >
                <Search className="h-4 w-4" />
              </button>
              <div className="relative">
                <button
                  onClick={toggleMenu('gear')}
                  title="More"
                  className={cn('nav-btn', gearActive && 'nav-btn--active')}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </button>
                {openMenu === 'gear' && gearDropdown}
              </div>
            </div>
          </>
        )}
        {sidebarCollapsed && (
          <>
            <button
              onClick={() => setShowCreatePicker(true)}
              title="New"
              className="nav-btn"
            >
              <Plus className="h-4 w-4" />
            </button>
            <button
              onClick={() => setShowSearch(true)}
              title="Search"
              className="nav-btn"
            >
              <Search className="h-4 w-4" />
            </button>
            <div className="relative">
              <button
                onClick={toggleMenu('gear')}
                title="More"
                className={cn('nav-btn', gearActive && 'nav-btn--active')}
              >
                <MoreHorizontal className="h-4 w-4" />
              </button>
              {openMenu === 'gear' && gearDropdown}
            </div>
          </>
        )}
      </div>

      {/* Navigation tabs */}
      <nav className="bot-sidebar__nav">
        {visibleNavItems.map((item) => (
          <NavButton
            key={item.id}
            icon={item.icon}
            label={item.label}
            active={activeView === item.id}
            onClick={() => handleNavClick(item.id)}
          />
        ))}
      </nav>

      {/* Content based on active view */}
      <div className="bot-sidebar__content">
        {activeView === 'chats' && <ChatList botId={activeBot.id} mode="chats" onNavigate={onNavigate} />}
        {activeView === 'rooms' && <ChatList botId={activeBot.id} mode="rooms" onNavigate={onNavigate} />}
        {activeView === 'tasks' && <TaskList botId={activeBot.id} collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'work' && <WorkSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'schedules' && <SchedulesSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'automations' && <AutomationsSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'tools' && <ToolsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'developer' && <DeveloperSectionsList collapsed={sidebarCollapsed} />}
        {activeView === 'settings' && <SettingsList collapsed={sidebarCollapsed} />}
      </div>

      {showCreatePicker && (
        <CreatePickerDialog
          onPickChat={() => { setShowCreatePicker(false); handleNewChat() }}
          onPickRoom={() => { setShowCreatePicker(false); setShowCreateRoom(true) }}
          onClose={() => setShowCreatePicker(false)}
        />
      )}
      {showCreateRoom && <CreateRoomDialogWrapper onClose={() => setShowCreateRoom(false)} />}
      {showSearch && (
        <GlobalSearchDialog
          botId={activeBot.id}
          onNavigate={(path) => { setShowSearch(false); navigate(path); onNavigate?.() }}
          onClose={() => setShowSearch(false)}
        />
      )}
    </aside>
  )
}

interface NavButtonProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  active: boolean
  onClick: () => void
}

function NavButton({ icon: Icon, label, active, onClick }: NavButtonProps) {
  return (
    <button
      onClick={onClick}
      title={label}
      className={cn(
        'nav-btn group',
        active && 'nav-btn--active'
      )}
    >
      <Icon className="h-4 w-4" />
      {/* Tooltip */}
      <span className="bot-sidebar__nav-tooltip">
        {label}
      </span>
    </button>
  )
}

// =============================================================================
// HELPERS
// =============================================================================

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

// =============================================================================
// CHAT LIST
// =============================================================================

function ChatList({ botId, mode, onNavigate }: { botId: string; mode: 'chats' | 'rooms'; onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { activeBotId } = useBotStore()
  const { getChatsByBot, activeChatId, setActiveChat, updateChat, deleteChat, clearMessages, syncPlatformChats, loadPlatformChatMessages, archiveChat } = useChatStore()
  const { setRooms, activeRoomId, setActiveRoom, getRoomsForBot } = useRoomStore()
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  // Sync platform chats (Telegram, Discord) from backend — only in chats mode
  useEffect(() => {
    if (mode !== 'chats') return
    syncPlatformChats(botId)
    const interval = setInterval(() => syncPlatformChats(botId), 60000)
    return () => clearInterval(interval)
  }, [botId, mode, syncPlatformChats])

  // Load rooms — only in rooms mode
  useEffect(() => {
    if (mode !== 'rooms') return
    getRooms().then(setRooms).catch(() => {})
  }, [mode, setRooms])

  // Get the appropriate icon for a chat
  const getChatIcon = (chat: Chat) => {
    if (chat.platform === 'telegram') {
      return <MessageCircle className="sidebar-chat-item__icon sidebar-chat-item__icon--telegram" size={16} />
    }
    if (chat.platform === 'discord') {
      return <MessageCircle className="sidebar-chat-item__icon sidebar-chat-item__icon--discord" size={16} />
    }
    return <MessageSquare className="sidebar-chat-item__icon sidebar-chat-item__icon--default" size={16} />
  }

  const handleChatClick = async (chat: Chat) => {
    setActiveChat(chat.id)
    if (chat.platform) {
      await loadPlatformChatMessages(botId, chat.id)
    }
    const chatPath = chat.platform ? chat.platform : chat.id
    navigate(`/${botId}/chats/${chatPath}`)
    onNavigate?.()
  }

  const handleRoomClick = (roomId: string) => {
    setActiveRoom(roomId)
    navigate(`/${activeBotId}/rooms/${roomId}`)
    onNavigate?.()
  }

  // ── Chats mode ──
  if (mode === 'chats') {
    const chats = getChatsByBot(botId)
      .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())

    return (
      <div className="flex h-full flex-col">
        <div className="sidebar-list">
          {chats.length === 0 ? (
            <div className="sidebar-list__empty">
              No chats yet
            </div>
          ) : (
            <div className="space-y-1">
              {chats.map((chat) => (
                <div key={chat.id} className="group relative">
                  <button
                    onClick={() => handleChatClick(chat)}
                    className={cn(
                      'sidebar-chat-item',
                      activeChatId === chat.id && 'sidebar-chat-item--active'
                    )}
                  >
                    {getChatIcon(chat)}
                    <div className="min-w-0 flex-1">
                      <div className="sidebar-chat-item__title-row">
                        <span className="sidebar-chat-item__name">{chat.title}</span>
                        {chat.pinned && <Pin className="sidebar-chat-item__pin" size={12} />}
                        {chat.platform && (
                          <span className="sidebar-chat-item__platform-badge">
                            {chat.platform}
                          </span>
                        )}
                        <span className="sidebar-chat-item__time">{formatRelativeTime(chat.updatedAt)}</span>
                      </div>
                      {chat.lastMessage && (
                        <p className="sidebar-chat-item__preview">{chat.lastMessage}</p>
                      )}
                    </div>
                  </button>

                  {/* Context menu trigger */}
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      setMenuOpen(menuOpen === chat.id ? null : chat.id)
                    }}
                    className={cn(
                      'sidebar-chat-item__menu-btn',
                      menuOpen === chat.id && 'sidebar-chat-item__menu-btn--open'
                    )}
                  >
                    <MoreHorizontal size={14} />
                  </button>

                  {/* Context menu */}
                  {menuOpen === chat.id && (
                    <div className="context-menu absolute right-0 top-8 z-10 w-48">
                      <button
                        onClick={() => {
                          updateChat(chat.id, { pinned: !chat.pinned })
                          setMenuOpen(null)
                        }}
                        className="context-menu__item"
                      >
                        <Pin className="h-4 w-4" />
                        {chat.pinned ? 'Unpin' : 'Pin'}
                      </button>

                      <button
                        onClick={() => {
                          const msgs = useChatStore.getState().getMessages(chat.id)
                          const date = new Date().toISOString().slice(0, 10)
                          downloadJson({
                            chat: { id: chat.id, title: chat.title, botId: chat.botId, createdAt: chat.createdAt, updatedAt: chat.updatedAt },
                            messages: msgs,
                            exportedAt: new Date().toISOString(),
                          }, `chat-${slugify(chat.title)}-${date}.json`)
                          setMenuOpen(null)
                        }}
                        className="context-menu__item"
                      >
                        <Download className="h-4 w-4" />
                        Export JSON
                      </button>

                      {chat.platform ? (
                        <>
                          <button
                            onClick={async () => {
                              setMenuOpen(null)
                              try {
                                await clearChatMessages(botId, chat.id)
                                clearMessages(chat.id)
                                toast.success('Messages cleared')
                              } catch {
                                toast.error('Failed to clear messages')
                              }
                            }}
                            className="context-menu__item"
                          >
                            <Eraser className="h-4 w-4" />
                            Clear Messages
                          </button>
                          <button
                            onClick={async () => {
                              setMenuOpen(null)
                              try {
                                await archiveChat(botId, chat.id)
                                toast.success('Chat archived')
                              } catch {
                                toast.error('Failed to archive chat')
                              }
                            }}
                            className="context-menu__item"
                          >
                            <Archive className="h-4 w-4" />
                            Archive Chat
                          </button>
                        </>
                      ) : (
                        <>
                          <button
                            onClick={() => {
                              updateChat(chat.id, { archived: true })
                              setMenuOpen(null)
                            }}
                            className="context-menu__item"
                          >
                            <Archive className="h-4 w-4" />
                            Archive
                          </button>
                          <div className="context-menu__divider" />
                          <button
                            onClick={() => {
                              deleteChat(chat.id)
                              setMenuOpen(null)
                            }}
                            className="context-menu__item context-menu__item--danger"
                          >
                            <Trash2 className="h-4 w-4" />
                            Delete
                          </button>
                        </>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    )
  }

  // ── Rooms mode ──
  const botRooms = getRoomsForBot(botId)
    .sort((a, b) => new Date(b.updatedAt).getTime() - new Date(a.updatedAt).getTime())

  return (
    <div className="flex h-full flex-col">
      <div className="sidebar-list">
        {botRooms.length === 0 ? (
          <div className="sidebar-list__empty">
            No rooms for this bot
          </div>
        ) : (
          <div className="space-y-1">
            {botRooms.map((room) => (
              <div key={room.id} className="group relative">
                <button
                  onClick={() => handleRoomClick(room.id)}
                  className={cn(
                    'sidebar-chat-item',
                    activeRoomId === room.id && 'sidebar-chat-item--active'
                  )}
                >
                  <DoorOpen className="sidebar-chat-item__icon sidebar-chat-item__icon--default" size={16} />
                  <div className="min-w-0 flex-1">
                    <div className="sidebar-chat-item__title-row">
                      <span className="sidebar-chat-item__name">{room.title}</span>
                      <span className="sidebar-chat-item__time">{formatRelativeTime(room.updatedAt)}</span>
                    </div>
                    <p className="sidebar-chat-item__preview">
                      {room.bots.length} bots · {room.messageCount ?? 0} msgs
                    </p>
                  </div>
                </button>

              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// GLOBAL SEARCH DIALOG
// =============================================================================

type SearchResult =
  | { type: 'chat'; id: string; title: string; meta: string }
  | { type: 'room'; id: string; title: string; meta: string }
  | { type: 'task'; id: string; title: string; meta: string }

function GlobalSearchDialog({
  botId,
  onNavigate,
  onClose,
}: {
  botId: string
  onNavigate: (path: string) => void
  onClose: () => void
}) {
  const [query, setQuery] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)
  const { activeBotId } = useBotStore()
  const { getChatsByBot } = useChatStore()
  const { rooms } = useRoomStore()
  const { getTasksByBot } = useTaskStore()

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

    // Chats
    for (const chat of getChatsByBot(botId)) {
      if (chat.title.toLowerCase().includes(q)) {
        out.push({
          type: 'chat',
          id: chat.id,
          title: chat.title,
          meta: chat.platform ? `${chat.platform} chat` : formatRelativeTime(chat.updatedAt),
        })
      }
    }

    // Rooms (all rooms, not just bot-filtered — global search)
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

    // Tasks
    for (const task of getTasksByBot(botId)) {
      if (task.title.toLowerCase().includes(q)) {
        out.push({
          type: 'task',
          id: task.id,
          title: task.title,
          meta: task.status,
        })
      }
    }

    return out
  }, [q, botId, getChatsByBot, rooms, getTasksByBot])

  const handleSelect = (result: SearchResult) => {
    switch (result.type) {
      case 'chat':
        onNavigate(`/${activeBotId}/chats/${result.id}`)
        break
      case 'room':
        onNavigate(`/${activeBotId}/rooms/${result.id}`)
        break
      case 'task':
        onNavigate(`/${activeBotId}/tasks`)
        break
    }
  }

  const iconFor = (type: SearchResult['type']) => {
    switch (type) {
      case 'chat': return <MessageSquare className="h-4 w-4" />
      case 'room': return <DoorOpen className="h-4 w-4" />
      case 'task': return <CheckSquare className="h-4 w-4" />
    }
  }

  // Group results by type
  const grouped = useMemo(() => {
    const groups: Record<string, SearchResult[]> = {}
    for (const r of results) {
      ;(groups[r.type] ??= []).push(r)
    }
    return groups
  }, [results])

  const groupLabel: Record<string, string> = { chat: 'Chats', room: 'Rooms', task: 'Tasks' }

  return (
    <div className="dialog__backdrop" onClick={onClose}>
      <div
        className="dialog__panel dialog__panel--sm"
        onClick={(e) => e.stopPropagation()}
        style={{ marginTop: '10vh' , alignSelf: 'flex-start' }}
      >
        {/* Search input */}
        <div className="global-search__input-wrap">
          <Search className="global-search__icon" />
          <input
            ref={inputRef}
            type="text"
            placeholder="Search chats, rooms, tasks..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="global-search__input"
          />
        </div>

        {/* Results */}
        <div className="global-search__body">
          {!q && (
            <div className="global-search__hint">
              Type to search across all your conversations, rooms, and tasks.
            </div>
          )}
          {q && results.length === 0 && (
            <div className="global-search__empty">
              No results for &ldquo;{query}&rdquo;
            </div>
          )}
          {Object.entries(grouped).map(([type, items]) => (
            <div key={type}>
              <div className="global-search__group-label">{groupLabel[type] ?? type}</div>
              {items.map((item) => (
                <button
                  key={`${item.type}-${item.id}`}
                  className="global-search__item"
                  onClick={() => handleSelect(item)}
                >
                  <div className={`global-search__item-icon global-search__item-icon--${item.type}`}>
                    {iconFor(item.type)}
                  </div>
                  <div className="global-search__item-info">
                    <span className="global-search__item-name">{item.title}</span>
                    <span className="global-search__item-meta">{item.meta}</span>
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

// =============================================================================
// CREATE PICKER DIALOG
// =============================================================================

function CreatePickerDialog({
  onPickChat,
  onPickRoom,
  onClose,
}: {
  onPickChat: () => void
  onPickRoom: () => void
  onClose: () => void
}) {
  return (
    <div className="dialog__backdrop" onClick={onClose}>
      <div
        className="dialog__panel dialog__panel--sm"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="dialog__header">
          <h2 style={{ fontSize: 'var(--text-base)', fontWeight: 600 }}>Create New</h2>
          <button onClick={onClose} className="nav-btn">
            <X className="h-4 w-4" />
          </button>
        </div>
        <div className="dialog__body-base">
          <div className="create-picker__grid">
            <button className="create-picker__card" onClick={onPickChat}>
              <div className="create-picker__icon create-picker__icon--chat">
                <MessageSquare className="h-6 w-6" />
              </div>
              <div className="create-picker__label">Chat</div>
              <p className="create-picker__desc">
                A private conversation between you and a single bot. Great for questions, brainstorming, or one-on-one tasks.
              </p>
            </button>
            <button className="create-picker__card" onClick={onPickRoom}>
              <div className="create-picker__icon create-picker__icon--room">
                <DoorOpen className="h-6 w-6" />
              </div>
              <div className="create-picker__label">Room</div>
              <p className="create-picker__desc">
                A shared space where multiple bots and people can collaborate together in real time.
              </p>
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

/** Lazy-load CreateRoomDialog to avoid circular imports */
function CreateRoomDialogWrapper({ onClose }: { onClose: () => void }) {
  const [Dialog, setDialog] = useState<React.ComponentType<{ onClose: () => void }> | null>(null)

  useEffect(() => {
    import('../rooms/CreateRoomDialog').then((mod) => {
      setDialog(() => mod.CreateRoomDialog)
    })
  }, [])

  if (!Dialog) return null
  return <Dialog onClose={onClose} />
}

// =============================================================================
// TASK LIST
// =============================================================================

function TaskList({ botId, collapsed, onNavigate }: { botId: string; collapsed: boolean; onNavigate?: () => void }) {
  const { getTasksByBot, activeTaskId, setActiveTask, addTask, updateTask } = useTaskStore()
  const tasks = getTasksByBot(botId)

  const getStatusClass = (status: Task['status']) => {
    switch (status) {
      case 'todo': return 'sidebar-task-item--todo'
      case 'in_progress': return 'sidebar-task-item--in_progress'
      case 'done': return 'sidebar-task-item--done'
      case 'blocked': return 'sidebar-task-item--blocked'
    }
  }

  const handleNewTask = () => {
    const newTask: Task = {
      id: crypto.randomUUID(),
      botId,
      title: 'New Task',
      status: 'todo',
      priority: 'medium',
      tags: [],
      createdAt: new Date().toISOString(),
    }
    addTask(newTask)
    setActiveTask(newTask.id)
    onNavigate?.()
  }

  if (collapsed) {
    const todoCount = tasks.filter((t) => t.status === 'todo').length
    return (
      <div className="flex flex-col items-center gap-2 p-2">
        <button
          onClick={handleNewTask}
          className="sidebar-add-btn sidebar-add-btn--lg"
        >
          <Plus className="h-4 w-4" />
        </button>
        {todoCount > 0 && (
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-bg-secondary)] text-xs font-bold text-[var(--color-text-primary)]">
            {todoCount}
          </div>
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Add task button */}
      <div className="p-3">
        <button
          onClick={handleNewTask}
          className="btn btn--dashed w-full"
        >
          <Plus className="h-4 w-4" />
          Add Task
        </button>
      </div>

      {/* Task list */}
      <div className="sidebar-list">
        {tasks.length === 0 ? (
          <div className="sidebar-list__empty">No tasks yet</div>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <button
                key={task.id}
                onClick={() => { setActiveTask(task.id); onNavigate?.() }}
                className={cn(
                  'sidebar-task-item',
                  activeTaskId === task.id && 'ring-1 ring-cachi-500',
                  getStatusClass(task.status)
                )}
              >
                {/* Checkbox */}
                <button
                  onClick={(e) => {
                    e.stopPropagation()
                    updateTask(task.id, {
                      status: task.status === 'done' ? 'todo' : 'done',
                      completedAt: task.status === 'done' ? undefined : new Date().toISOString(),
                    })
                  }}
                  className={cn(
                    'sidebar-task-item__checkbox',
                    task.status === 'done' && 'sidebar-task-item__checkbox--done'
                  )}
                >
                  {task.status === 'done' && '✓'}
                </button>

                <div className="min-w-0 flex-1">
                  <span
                    className={cn(
                      'text-sm',
                      task.status === 'done' ? 'text-[var(--color-text-secondary)] line-through' : 'text-[var(--color-text-primary)]'
                    )}
                  >
                    {task.title}
                  </span>
                  {task.tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {task.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-[var(--color-hover-bg)] px-1.5 py-0.5 text-xs text-[var(--color-text-secondary)]"
                        >
                          {tag}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

// =============================================================================
// WORK SECTIONS LIST (navigation for Work view - like SettingsList)
// =============================================================================

const workSections: { id: WorkSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'overview', label: 'Overview', icon: FolderKanban },
  { id: 'active', label: 'Active', icon: Play },
  { id: 'completed', label: 'Completed', icon: CheckCircle2 },
  { id: 'history', label: 'History', icon: History },
]

function WorkSectionsList({ botId, collapsed }: { botId: string; collapsed: boolean }) {
  const { workSection, setWorkSection } = useUIStore()
  const { getWorkByBot, getActiveWork } = useWorkStore()
  const allWork = getWorkByBot(botId)
  const activeWork = getActiveWork(botId)

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        {workSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setWorkSection(section.id)}
            className={cn(
              'sidebar-section-btn-icon',
              workSection === section.id && 'sidebar-section-btn-icon--active sidebar-section-btn--blue'
            )}
            title={section.label}
          >
            <section.icon className="h-5 w-5" />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-1">
        {workSections.map((section) => {
          // Show count badges for relevant sections
          let count: number | undefined
          if (section.id === 'active') count = activeWork.length
          if (section.id === 'completed') count = allWork.filter((w) => w.status === 'completed').length
          if (section.id === 'history') count = allWork.length

          return (
            <button
              key={section.id}
              onClick={() => setWorkSection(section.id)}
              className={cn(
                'sidebar-section-btn',
                workSection === section.id && 'sidebar-section-btn--active sidebar-section-btn--blue'
              )}
            >
              <section.icon className="h-5 w-5" />
              <span className="label">{section.label}</span>
              {count !== undefined && count > 0 && (
                <span className="sidebar-section-btn__count">
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// =============================================================================
// SCHEDULES SECTIONS LIST (navigation for Schedules view - like SettingsList)
// =============================================================================

const scheduleSections: { id: ScheduleSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'all', label: 'All Schedules', icon: CalendarClock },
  { id: 'enabled', label: 'Enabled', icon: Play },
  { id: 'disabled', label: 'Disabled', icon: Pause },
  { id: 'create', label: 'Create New', icon: Plus },
]

function SchedulesSectionsList({ botId, collapsed }: { botId: string; collapsed: boolean }) {
  const { scheduleSection, setScheduleSection } = useUIStore()
  const { getSchedulesByBot, getEnabledSchedules } = useScheduleStore()
  const allSchedules = getSchedulesByBot(botId)
  const enabledSchedules = getEnabledSchedules(botId)

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        {scheduleSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setScheduleSection(section.id)}
            className={cn(
              'sidebar-section-btn-icon',
              scheduleSection === section.id && 'sidebar-section-btn-icon--active sidebar-section-btn--purple'
            )}
            title={section.label}
          >
            <section.icon className="h-5 w-5" />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-1">
        {scheduleSections.map((section) => {
          // Show count badges for relevant sections
          let count: number | undefined
          if (section.id === 'all') count = allSchedules.length
          if (section.id === 'enabled') count = enabledSchedules.length
          if (section.id === 'disabled') count = allSchedules.length - enabledSchedules.length

          return (
            <button
              key={section.id}
              onClick={() => setScheduleSection(section.id)}
              className={cn(
                'sidebar-section-btn',
                scheduleSection === section.id && 'sidebar-section-btn--active sidebar-section-btn--purple'
              )}
            >
              <section.icon className="h-5 w-5" />
              <span className="label">{section.label}</span>
              {count !== undefined && count > 0 && (
                <span className="sidebar-section-btn__count">
                  {count}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

// =============================================================================
// AUTOMATIONS SECTIONS LIST
// =============================================================================

const automationSections: { id: AutomationSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'all', label: 'All Automations', icon: Blocks },
  { id: 'functions', label: 'Functions', icon: FolderKanban },
  { id: 'scripts', label: 'Scripts', icon: Code2 },
  { id: 'schedules', label: 'Schedules', icon: CalendarClock },
]

function AutomationsSectionsList({ collapsed }: { botId: string; collapsed: boolean }) {
  const { automationSection, setAutomationSection } = useUIStore()

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        {automationSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setAutomationSection(section.id)}
            className={cn(
              'sidebar-section-btn-icon',
              automationSection === section.id && 'sidebar-section-btn-icon--active sidebar-section-btn--accent'
            )}
            title={section.label}
          >
            <section.icon className="h-5 w-5" />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-1">
        {automationSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setAutomationSection(section.id)}
            className={cn(
              'sidebar-section-btn',
              automationSection === section.id && 'sidebar-section-btn--active sidebar-section-btn--accent'
            )}
          >
            <section.icon className="h-5 w-5" />
            <span className="label">{section.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// TOOLS LIST
// =============================================================================

function ToolsList({ collapsed }: { botId: string; collapsed: boolean }) {
  const { getActiveBot } = useBotStore()
  const activeBot = getActiveBot()

  const tools = activeBot?.tools || []

  if (collapsed) {
    return (
      <div className="flex flex-col items-center p-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-[var(--color-bg-secondary)] text-sm font-bold text-[var(--color-text-secondary)]">
          {tools.length}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-2">
        {tools.map((toolId) => (
          <div
            key={toolId}
            className="sidebar-tool-item"
          >
            <ToolIconRenderer toolId={toolId} className="h-5 w-5 text-[var(--color-text-secondary)]" />
            <span className="text-sm capitalize text-[var(--color-text-primary)]">{toolId.replace(/_/g, ' ')}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// DEVELOPER SECTIONS LIST
// =============================================================================

type DeveloperSection = 'api-keys' | 'api-docs' | 'webhooks'

const developerSections: { id: DeveloperSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'api-keys', label: 'API Keys', icon: Key },
  { id: 'api-docs', label: 'API Docs', icon: Code2 },
  { id: 'webhooks', label: 'Webhooks', icon: Plug },
]

function DeveloperSectionsList({ collapsed }: { collapsed: boolean }) {
  const { setSettingsSection } = useUIStore()
  const [devSection, setDevSection] = useState<DeveloperSection>('api-keys')

  // Ensure we're in developer settings section
  useEffect(() => {
    setSettingsSection('developer')
  }, [setSettingsSection])

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        {developerSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setDevSection(section.id)}
            className={cn(
              'sidebar-section-btn-icon',
              devSection === section.id && 'sidebar-section-btn-icon--active sidebar-section-btn--accent'
            )}
            title={section.label}
          >
            <section.icon className="h-5 w-5" />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-1">
        {developerSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setDevSection(section.id)}
            className={cn(
              'sidebar-section-btn',
              devSection === section.id && 'sidebar-section-btn--active sidebar-section-btn--accent'
            )}
          >
            <section.icon className="h-5 w-5" />
            <span className="label">{section.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

// =============================================================================
// SETTINGS LIST
// =============================================================================

const settingsSections: { id: SettingsSection; label: string; icon: React.ComponentType<{ className?: string }>; danger?: boolean }[] = [
  { id: 'general', label: 'General', icon: Bot },
  { id: 'knowledge', label: 'Knowledge', icon: BookOpen },
  { id: 'skills', label: 'Skills', icon: Sparkles },
  { id: 'connections', label: 'Connections', icon: Plug },
  { id: 'environment', label: 'Environment', icon: Key },
  { id: 'danger', label: 'Danger Zone', icon: AlertTriangle, danger: true },
]

function SettingsList({ collapsed }: { collapsed: boolean }) {
  const { settingsSection, setSettingsSection } = useUIStore()

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-1 p-2">
        {settingsSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setSettingsSection(section.id)}
            className={cn(
              'sidebar-section-btn-icon',
              settingsSection === section.id
                ? section.danger
                  ? 'sidebar-section-btn-icon--active sidebar-section-btn--danger'
                  : 'sidebar-section-btn-icon--active sidebar-section-btn--accent'
                : section.danger
                ? 'sidebar-section-btn--danger'
                : ''
            )}
            title={section.label}
          >
            <section.icon className="h-5 w-5" />
          </button>
        ))}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col p-3">
      <div className="space-y-1">
        {settingsSections.map((section) => (
          <button
            key={section.id}
            onClick={() => setSettingsSection(section.id)}
            className={cn(
              'sidebar-section-btn',
              settingsSection === section.id
                ? section.danger
                  ? 'sidebar-section-btn--active sidebar-section-btn--danger'
                  : 'sidebar-section-btn--active sidebar-section-btn--accent'
                : section.danger
                ? 'sidebar-section-btn--danger'
                : ''
            )}
          >
            <section.icon className="h-5 w-5" />
            <span className="label">{section.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}

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
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useBotStore, useChatStore, useTaskStore, useWorkStore, useScheduleStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { getRooms } from '../../api/rooms'
import { useUIStore, type SettingsSection, type WorkSection, type ScheduleSection, type AutomationSection } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { ToolIconRenderer } from '../common/ToolIconRenderer'
import { clearChatMessages } from '../../api/client'
import { cn } from '../../lib/utils'
import { useBotAccess } from '../../hooks/useBotAccess'
import type { BotView, Chat, Task } from '../../types'

type MinAccessLevel = 'viewer' | 'operator' | 'editor'

const navItems: { id: BotView; label: string; icon: React.ComponentType<{ className?: string }>; minLevel: MinAccessLevel }[] = [
  { id: 'chats', label: 'Chats', icon: MessageSquare, minLevel: 'viewer' },
  { id: 'rooms', label: 'Rooms', icon: DoorOpen, minLevel: 'viewer' },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare, minLevel: 'viewer' },
  { id: 'work', label: 'Work', icon: FolderKanban, minLevel: 'operator' },
  { id: 'schedules', label: 'Schedules', icon: CalendarClock, minLevel: 'operator' },
  { id: 'automations', label: 'Automations', icon: Blocks, minLevel: 'operator' },
  { id: 'voice', label: 'Voice', icon: Mic, minLevel: 'operator' },
  { id: 'tools', label: 'Tools', icon: Wrench, minLevel: 'editor' },
  { id: 'settings', label: 'Settings', icon: Settings, minLevel: 'editor' },
]

const LEVEL_RANK: Record<string, number> = { viewer: 1, operator: 2, editor: 3, owner: 4, admin: 4 }

interface BotSidebarProps {
  onNavigate?: () => void
}

export function BotSidebar({ onNavigate }: BotSidebarProps) {
  const navigate = useNavigate()
  const { getActiveBot, activeView, setActiveView, activeBotId } = useBotStore()
  const { sidebarCollapsed } = useUIStore()
  const activeBot = getActiveBot()
  const { accessLevel } = useBotAccess(activeBotId)

  if (!activeBot) return null

  const userRank = LEVEL_RANK[accessLevel ?? 'owner'] ?? 4
  const visibleNavItems = navItems.filter((item) => userRank >= LEVEL_RANK[item.minLevel])

  const handleNavClick = (viewId: typeof activeView) => {
    setActiveView(viewId)
    navigate(`/${activeBotId}/${viewId}`)
  }

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
          <div className="bot-sidebar__bot-info">
            <h2 className="name">
              {activeBot.name}
            </h2>
            <p className="model">{activeBot.model}</p>
          </div>
        )}
      </div>

      {/* Navigation tabs - compact icon-only style */}
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
        {activeView === 'chats' && <ChatList botId={activeBot.id} collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'rooms' && <RoomList collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'tasks' && <TaskList botId={activeBot.id} collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'work' && <WorkSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'schedules' && <SchedulesSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'automations' && <AutomationsSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'tools' && <ToolsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'settings' && <SettingsList collapsed={sidebarCollapsed} />}
      </div>
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
// CHAT LIST
// =============================================================================

function ChatList({ botId, collapsed, onNavigate }: { botId: string; collapsed: boolean; onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { getChatsByBot, activeChatId, setActiveChat, addChat, updateChat, deleteChat, clearMessages, syncPlatformChats, loadPlatformChatMessages, archiveChat } = useChatStore()
  const [search, setSearch] = useState('')
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  // Sync platform chats (Telegram, Discord) from backend
  // Real-time updates now come via WebSocket, but keep polling as fallback
  useEffect(() => {
    syncPlatformChats(botId)
    // Poll every 60 seconds as fallback (real-time updates via WebSocket)
    const interval = setInterval(() => syncPlatformChats(botId), 60000)
    return () => clearInterval(interval)
  }, [botId, syncPlatformChats])

  const chats = getChatsByBot(botId).filter(
    (chat) => !search || chat.title.toLowerCase().includes(search.toLowerCase())
  )

  // Get the appropriate icon for the chat
  const getChatIcon = (chat: Chat) => {
    if (chat.platform === 'telegram') {
      return <MessageCircle className="sidebar-chat-item__icon sidebar-chat-item__icon--telegram mt-0.5 h-4 w-4 flex-shrink-0" />
    }
    if (chat.platform === 'discord') {
      return <MessageCircle className="sidebar-chat-item__icon sidebar-chat-item__icon--discord mt-0.5 h-4 w-4 flex-shrink-0" />
    }
    return <MessageSquare className="sidebar-chat-item__icon sidebar-chat-item__icon--default mt-0.5 h-4 w-4 flex-shrink-0" />
  }

  const handleNewChat = () => {
    const newChat: Chat = {
      id: crypto.randomUUID(),
      botId,
      title: 'New Chat',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0,
    }
    addChat(newChat)
    setActiveChat(newChat.id)
    navigate(`/${botId}/chats/${newChat.id}`)
    onNavigate?.()
  }

  const handleChatClick = async (chat: Chat) => {
    setActiveChat(chat.id)
    // If it's a platform chat, load messages from backend
    if (chat.platform) {
      await loadPlatformChatMessages(botId, chat.id)
    }
    // Use platform name in URL for platform chats (e.g., /default/chats/telegram)
    const chatPath = chat.platform ? chat.platform : chat.id
    navigate(`/${botId}/chats/${chatPath}`)
    onNavigate?.()
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 p-2">
        <button
          onClick={handleNewChat}
          className="sidebar-add-btn sidebar-add-btn--lg"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search and new chat */}
      <div className="sidebar-search">
        <div className="sidebar-search__wrap">
          <Search className="sidebar-search__icon h-4 w-4" />
          <input
            type="text"
            placeholder="Search chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sidebar-search__input"
          />
        </div>
        <button
          onClick={handleNewChat}
          className="sidebar-add-btn"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Chat list */}
      <div className="sidebar-list">
        {chats.length === 0 ? (
          <div className="sidebar-list__empty">
            {search ? 'No chats found' : 'No chats yet'}
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
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium">{chat.title}</span>
                      {chat.pinned && (
                        <Pin className="h-3 w-3 flex-shrink-0 text-cachi-500" />
                      )}
                      {chat.platform && (
                        <span className="sidebar-chat-item__platform-badge">
                          {chat.platform}
                        </span>
                      )}
                    </div>
                    {chat.lastMessage && (
                      <p className="truncate text-xs text-[var(--color-text-secondary)]">{chat.lastMessage}</p>
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
                    'absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded text-[var(--color-text-secondary)] opacity-0 transition-opacity hover:bg-zinc-200 group-hover:opacity-100 dark:text-[var(--color-text-secondary)] dark:hover:bg-[var(--color-hover-bg)]',
                    menuOpen === chat.id && 'opacity-100'
                  )}
                >
                  <MoreHorizontal className="h-4 w-4" />
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

                    {/* Platform chats: Clear Messages + Archive options */}
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

// =============================================================================
// ROOM LIST
// =============================================================================

function RoomList({ collapsed, onNavigate }: { collapsed: boolean; onNavigate?: () => void }) {
  const navigate = useNavigate()
  const { activeBotId } = useBotStore()
  const { rooms, setRooms, activeRoomId, setActiveRoom } = useRoomStore()
  const [search, setSearch] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  // Load rooms on mount
  useEffect(() => {
    getRooms()
      .then(setRooms)
      .catch(() => {})
  }, [setRooms])

  const filtered = rooms.filter(
    (r) => !search || r.title.toLowerCase().includes(search.toLowerCase())
  )

  const handleRoomClick = (roomId: string) => {
    setActiveRoom(roomId)
    navigate(`/${activeBotId}/rooms/${roomId}`)
    onNavigate?.()
  }

  const handleNewRoom = () => {
    setShowCreate(true)
  }

  if (collapsed) {
    return (
      <div className="flex flex-col items-center gap-2 p-2">
        <button
          onClick={handleNewRoom}
          className="sidebar-add-btn sidebar-add-btn--lg"
        >
          <Plus className="h-4 w-4" />
        </button>
        {rooms.length > 0 && (
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-[var(--color-bg-secondary)] text-xs font-bold text-[var(--color-text-primary)]">
            {rooms.length}
          </div>
        )}
        {showCreate && (
          <CreateRoomDialogWrapper onClose={() => setShowCreate(false)} />
        )}
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search and new room */}
      <div className="sidebar-search">
        <div className="sidebar-search__wrap">
          <Search className="sidebar-search__icon h-4 w-4" />
          <input
            type="text"
            placeholder="Search rooms..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="sidebar-search__input"
          />
        </div>
        <button
          onClick={handleNewRoom}
          className="sidebar-add-btn"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Room list */}
      <div className="sidebar-list">
        {filtered.length === 0 ? (
          <div className="sidebar-list__empty">
            {search ? 'No rooms found' : 'No rooms yet'}
          </div>
        ) : (
          <div className="space-y-1">
            {filtered.map((room) => (
              <button
                key={room.id}
                onClick={() => handleRoomClick(room.id)}
                className={cn(
                  'sidebar-chat-item',
                  activeRoomId === room.id && 'sidebar-chat-item--active'
                )}
              >
                <DoorOpen className="sidebar-chat-item__icon sidebar-chat-item__icon--default mt-0.5 h-4 w-4 flex-shrink-0" />
                <div className="min-w-0 flex-1">
                  <span className="truncate text-sm font-medium">{room.title}</span>
                  <div className="flex items-center gap-2 text-xs text-[var(--color-text-secondary)]">
                    <span>{room.bots.length} bots</span>
                    <span>{room.messageCount ?? 0} msgs</span>
                  </div>
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {showCreate && (
        <CreateRoomDialogWrapper onClose={() => setShowCreate(false)} />
      )}
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

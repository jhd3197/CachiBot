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
  Sliders,
  AlertTriangle,
  MessageCircle,
  FolderKanban,
  CalendarClock,
  Play,
  CheckCircle2,
  History,
  Pause,
  Eraser,
} from 'lucide-react'
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { toast } from 'sonner'
import { useBotStore, useChatStore, useTaskStore, useWorkStore, useScheduleStore } from '../../stores/bots'
import { useUIStore, type SettingsSection, type WorkSection, type ScheduleSection } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { ToolIconRenderer } from '../common/ToolIconRenderer'
import { clearChatMessages } from '../../api/client'
import { cn } from '../../lib/utils'
import type { BotView, Chat, Task } from '../../types'

const navItems: { id: BotView; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'chats', label: 'Chats', icon: MessageSquare },
  { id: 'tasks', label: 'Tasks', icon: CheckSquare },
  { id: 'work', label: 'Work', icon: FolderKanban },
  { id: 'schedules', label: 'Schedules', icon: CalendarClock },
  { id: 'tools', label: 'Tools', icon: Wrench },
  { id: 'settings', label: 'Settings', icon: Settings },
]

interface BotSidebarProps {
  onNavigate?: () => void
}

export function BotSidebar({ onNavigate }: BotSidebarProps) {
  const navigate = useNavigate()
  const { getActiveBot, activeView, setActiveView, activeBotId } = useBotStore()
  const { sidebarCollapsed } = useUIStore()
  const activeBot = getActiveBot()

  if (!activeBot) return null

  const handleNavClick = (viewId: typeof activeView) => {
    setActiveView(viewId)
    navigate(`/${activeBotId}/${viewId}`)
  }

  return (
    <aside
      className={cn(
        'flex h-full flex-col border-r border-zinc-300 bg-zinc-50 transition-all duration-300 dark:border-zinc-800 dark:bg-zinc-900/50',
        sidebarCollapsed ? 'w-16' : 'w-72'
      )}
    >
      {/* Bot header */}
      <div className="flex h-14 items-center gap-3 border-b border-zinc-300 px-4 dark:border-zinc-800">
        <div
          className="flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg"
          style={{ backgroundColor: activeBot.color + '20' }}
        >
          <BotIconRenderer icon={activeBot.icon} size={18} />
        </div>
        {!sidebarCollapsed && (
          <div className="min-w-0 flex-1">
            <h2 className="truncate text-sm font-semibold text-zinc-900 dark:text-zinc-100">
              {activeBot.name}
            </h2>
            <p className="truncate text-xs text-zinc-500">{activeBot.model}</p>
          </div>
        )}
      </div>

      {/* Navigation tabs - compact icon-only style */}
      <nav className="flex items-center justify-center gap-1 border-b border-zinc-300 px-3 py-2 dark:border-zinc-800">
        {navItems.map((item) => (
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
      <div className="flex-1 overflow-hidden">
        {activeView === 'chats' && <ChatList botId={activeBot.id} collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'tasks' && <TaskList botId={activeBot.id} collapsed={sidebarCollapsed} onNavigate={onNavigate} />}
        {activeView === 'work' && <WorkSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
        {activeView === 'schedules' && <SchedulesSectionsList botId={activeBot.id} collapsed={sidebarCollapsed} />}
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
        'group relative flex h-8 w-8 items-center justify-center rounded-lg transition-all',
        active
          ? 'bg-accent-600/20 text-accent-600 dark:text-accent-400'
          : 'text-zinc-500 hover:bg-zinc-200 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-200'
      )}
    >
      <Icon className="h-4 w-4" />
      {/* Tooltip */}
      <span className="pointer-events-none absolute -bottom-8 left-1/2 z-50 -translate-x-1/2 whitespace-nowrap rounded-md bg-zinc-700 px-2 py-1 text-xs font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-zinc-800">
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
      return <MessageCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-blue-400" />
    }
    if (chat.platform === 'discord') {
      return <MessageCircle className="mt-0.5 h-4 w-4 flex-shrink-0 text-indigo-400" />
    }
    return <MessageSquare className="mt-0.5 h-4 w-4 flex-shrink-0 text-zinc-500" />
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
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-cachi-600 text-white hover:bg-cachi-500"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>
    )
  }

  return (
    <div className="flex h-full flex-col">
      {/* Search and new chat */}
      <div className="flex gap-2 p-3">
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search chats..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-9 pr-3 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-cachi-500 focus:ring-1 focus:ring-cachi-500"
          />
        </div>
        <button
          onClick={handleNewChat}
          className="flex h-9 w-9 items-center justify-center rounded-lg bg-cachi-600 text-white hover:bg-cachi-500"
        >
          <Plus className="h-4 w-4" />
        </button>
      </div>

      {/* Chat list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {chats.length === 0 ? (
          <div className="py-8 text-center text-sm text-zinc-500">
            {search ? 'No chats found' : 'No chats yet'}
          </div>
        ) : (
          <div className="space-y-1">
            {chats.map((chat) => (
              <div key={chat.id} className="group relative">
                <button
                  onClick={() => handleChatClick(chat)}
                  className={cn(
                    'flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition-colors',
                    activeChatId === chat.id
                      ? 'bg-zinc-800 text-zinc-100'
                      : 'text-zinc-300 hover:bg-zinc-800/50'
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
                        <span className="rounded bg-zinc-700 px-1 py-0.5 text-[10px] uppercase text-zinc-400">
                          {chat.platform}
                        </span>
                      )}
                    </div>
                    {chat.lastMessage && (
                      <p className="truncate text-xs text-zinc-500">{chat.lastMessage}</p>
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
                    'absolute right-2 top-2 flex h-6 w-6 items-center justify-center rounded text-zinc-400 opacity-0 transition-opacity hover:bg-zinc-700 group-hover:opacity-100',
                    menuOpen === chat.id && 'opacity-100'
                  )}
                >
                  <MoreHorizontal className="h-4 w-4" />
                </button>

                {/* Context menu */}
                {menuOpen === chat.id && (
                  <div className="absolute right-0 top-8 z-10 w-48 rounded-lg border border-zinc-700 bg-zinc-800 py-1 shadow-xl">
                    <button
                      onClick={() => {
                        updateChat(chat.id, { pinned: !chat.pinned })
                        setMenuOpen(null)
                      }}
                      className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
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
                            } catch (err) {
                              toast.error('Failed to clear messages')
                            }
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
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
                            } catch (err) {
                              toast.error('Failed to archive chat')
                            }
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
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
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-zinc-300 hover:bg-zinc-700"
                        >
                          <Archive className="h-4 w-4" />
                          Archive
                        </button>
                        <div className="my-1 h-px bg-zinc-700" />
                        <button
                          onClick={() => {
                            deleteChat(chat.id)
                            setMenuOpen(null)
                          }}
                          className="flex w-full items-center gap-2 px-3 py-1.5 text-sm text-red-400 hover:bg-zinc-700"
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
// JOB LIST
// =============================================================================

// =============================================================================
// TASK LIST
// =============================================================================

function TaskList({ botId, collapsed, onNavigate }: { botId: string; collapsed: boolean; onNavigate?: () => void }) {
  const { getTasksByBot, activeTaskId, setActiveTask, addTask, updateTask } = useTaskStore()
  const tasks = getTasksByBot(botId)

  const getStatusStyle = (status: Task['status']) => {
    switch (status) {
      case 'todo': return 'border-zinc-600 bg-zinc-800'
      case 'in_progress': return 'border-blue-500 bg-blue-500/10'
      case 'done': return 'border-green-500 bg-green-500/10'
      case 'blocked': return 'border-red-500 bg-red-500/10'
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
          className="flex h-10 w-10 items-center justify-center rounded-lg bg-cachi-600 text-white hover:bg-cachi-500"
        >
          <Plus className="h-4 w-4" />
        </button>
        {todoCount > 0 && (
          <div className="flex h-6 w-6 items-center justify-center rounded-full bg-zinc-800 text-xs font-bold text-zinc-300">
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
          className="flex w-full items-center justify-center gap-2 rounded-lg border border-dashed border-zinc-700 py-2 text-sm text-zinc-400 transition-colors hover:border-cachi-500 hover:text-cachi-400"
        >
          <Plus className="h-4 w-4" />
          Add Task
        </button>
      </div>

      {/* Task list */}
      <div className="flex-1 overflow-y-auto px-2 pb-2">
        {tasks.length === 0 ? (
          <div className="py-8 text-center text-sm text-zinc-500">No tasks yet</div>
        ) : (
          <div className="space-y-2">
            {tasks.map((task) => (
              <button
                key={task.id}
                onClick={() => { setActiveTask(task.id); onNavigate?.() }}
                className={cn(
                  'flex w-full items-start gap-3 rounded-lg border p-3 text-left transition-colors',
                  activeTaskId === task.id && 'ring-1 ring-cachi-500',
                  getStatusStyle(task.status)
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
                    'mt-0.5 flex h-4 w-4 flex-shrink-0 items-center justify-center rounded border transition-colors',
                    task.status === 'done'
                      ? 'border-green-500 bg-green-500 text-white'
                      : 'border-zinc-500 hover:border-cachi-500'
                  )}
                >
                  {task.status === 'done' && '✓'}
                </button>

                <div className="min-w-0 flex-1">
                  <span
                    className={cn(
                      'text-sm',
                      task.status === 'done' ? 'text-zinc-500 line-through' : 'text-zinc-200'
                    )}
                  >
                    {task.title}
                  </span>
                  {task.tags.length > 0 && (
                    <div className="mt-1 flex flex-wrap gap-1">
                      {task.tags.map((tag) => (
                        <span
                          key={tag}
                          className="rounded bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-400"
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
              'flex h-10 w-10 items-center justify-center rounded-lg transition-colors',
              workSection === section.id
                ? 'bg-blue-600/20 text-blue-400'
                : 'text-zinc-400 hover:bg-zinc-800'
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
                'flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors',
                workSection === section.id
                  ? 'bg-blue-600/20 text-blue-400'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
              )}
            >
              <section.icon className="h-5 w-5" />
              <span className="flex-1 text-sm">{section.label}</span>
              {count !== undefined && count > 0 && (
                <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
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
              'flex h-10 w-10 items-center justify-center rounded-lg transition-colors',
              scheduleSection === section.id
                ? 'bg-purple-600/20 text-purple-400'
                : 'text-zinc-400 hover:bg-zinc-800'
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
                'flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors',
                scheduleSection === section.id
                  ? 'bg-purple-600/20 text-purple-400'
                  : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
              )}
            >
              <section.icon className="h-5 w-5" />
              <span className="flex-1 text-sm">{section.label}</span>
              {count !== undefined && count > 0 && (
                <span className="rounded-full bg-zinc-700 px-2 py-0.5 text-xs text-zinc-400">
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
// TOOLS LIST
// =============================================================================

function ToolsList({ collapsed }: { botId: string; collapsed: boolean }) {
  const { getActiveBot } = useBotStore()
  const activeBot = getActiveBot()

  const tools = activeBot?.tools || []

  if (collapsed) {
    return (
      <div className="flex flex-col items-center p-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-zinc-800 text-sm font-bold text-zinc-400">
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
            className="flex items-center gap-3 rounded-lg border border-zinc-700 bg-zinc-800/30 p-3"
          >
            <ToolIconRenderer toolId={toolId} className="h-5 w-5 text-zinc-400" />
            <span className="text-sm capitalize text-zinc-300">{toolId.replace(/_/g, ' ')}</span>
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
  { id: 'advanced', label: 'Advanced', icon: Sliders },
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
              'flex h-10 w-10 items-center justify-center rounded-lg transition-colors',
              settingsSection === section.id
                ? 'bg-cachi-600/20 text-cachi-400'
                : section.danger
                ? 'text-red-400/70 hover:bg-red-500/10'
                : 'text-zinc-400 hover:bg-zinc-800'
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
              'flex w-full items-center gap-3 rounded-lg p-3 text-left transition-colors',
              settingsSection === section.id
                ? 'bg-cachi-600/20 text-cachi-400'
                : section.danger
                ? 'text-red-400/70 hover:bg-red-500/10 hover:text-red-400'
                : 'text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200'
            )}
          >
            <section.icon className="h-5 w-5" />
            <span className="text-sm">{section.label}</span>
          </button>
        ))}
      </div>
    </div>
  )
}


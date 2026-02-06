import { Plus, Settings, LayoutDashboard, Brain, Github } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'
import type { Bot } from '../../types'

// App-level paths (not bot views)
const appPaths = ['/dashboard', '/models', '/settings']

interface BotRailProps {
  onNavigate?: () => void
}

export function BotRail({ onNavigate }: BotRailProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { bots, activeBotId, setActiveBot } = useBotStore()
  const { setActiveChat } = useChatStore()
  const { setCreateBotOpen } = useUIStore()

  // Derive current app view from URL
  const currentPath = location.pathname
  const isAppView = appPaths.includes(currentPath)

  const handleBotClick = (botId: string) => {
    setActiveBot(botId)
    setActiveChat(null) // Clear active chat for blank slate
    navigate(`/${botId}/chats`)
    onNavigate?.()
  }

  const handleAppViewClick = (path: string) => {
    // Toggle: if already on this path, go home
    if (currentPath === path) {
      navigate('/')
    } else {
      navigate(path)
    }
    onNavigate?.()
  }

  return (
    <div className="flex h-full w-[72px] flex-col items-center bg-zinc-200 py-3 dark:bg-zinc-950">
      {/* App-level navigation */}
      <div className="flex flex-col items-center gap-2 pb-3">
        {/* Dashboard */}
        <button
          onClick={() => handleAppViewClick('/dashboard')}
          className={cn(
            'group relative flex h-12 w-12 items-center justify-center rounded-[24px] transition-all duration-200 hover:rounded-[16px]',
            currentPath === '/dashboard'
              ? 'rounded-[16px] bg-accent-600 text-white'
              : 'bg-zinc-300 text-zinc-600 hover:bg-accent-600/80 hover:text-white dark:bg-zinc-800 dark:text-zinc-400'
          )}
        >
          <LayoutDashboard className="h-5 w-5" />
          <Tooltip>Dashboard</Tooltip>
        </button>

        {/* Models */}
        <button
          onClick={() => handleAppViewClick('/models')}
          className={cn(
            'group relative flex h-12 w-12 items-center justify-center rounded-[24px] transition-all duration-200 hover:rounded-[16px]',
            currentPath === '/models'
              ? 'rounded-[16px] bg-accent-600 text-white'
              : 'bg-zinc-300 text-zinc-600 hover:bg-accent-600/80 hover:text-white dark:bg-zinc-800 dark:text-zinc-400'
          )}
        >
          <Brain className="h-5 w-5" />
          <Tooltip>Models</Tooltip>
        </button>

        <Divider />
      </div>

      {/* Bot avatars */}
      <div className="flex flex-1 flex-col items-center gap-2 overflow-y-auto scrollbar-none">
        {bots.map((bot) => (
          <BotAvatar
            key={bot.id}
            bot={bot}
            active={bot.id === activeBotId && !isAppView && currentPath.startsWith(`/${bot.id}/`)}
            onClick={() => handleBotClick(bot.id)}
          />
        ))}

        {/* Add bot button */}
        <button
          onClick={() => setCreateBotOpen(true)}
          className="group relative flex h-12 w-12 items-center justify-center rounded-[24px] bg-zinc-300 text-zinc-600 transition-all duration-200 hover:rounded-[16px] hover:bg-accent-600 hover:text-white dark:bg-zinc-800 dark:text-zinc-400"
        >
          <Plus className="h-5 w-5" />
          <Tooltip>Create Bot</Tooltip>
        </button>
      </div>

      {/* Bottom actions */}
      <div className="mt-auto flex flex-col items-center gap-2 pt-3">
        <Divider />

        {/* GitHub */}
        <a
          href="https://github.com/jhd3197/CachiBot"
          target="_blank"
          rel="noopener noreferrer"
          className="group relative flex h-12 w-12 items-center justify-center rounded-full text-zinc-600 transition-colors hover:bg-zinc-300 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
        >
          <Github className="h-5 w-5" />
          <Tooltip>GitHub</Tooltip>
        </a>

        {/* Settings */}
        <button
          onClick={() => handleAppViewClick('/settings')}
          className={cn(
            'group relative flex h-12 w-12 items-center justify-center rounded-full transition-colors',
            currentPath === '/settings'
              ? 'bg-accent-600/20 text-accent-600 dark:text-accent-400'
              : 'text-zinc-600 hover:bg-zinc-300 hover:text-zinc-800 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200'
          )}
        >
          <Settings className="h-5 w-5" />
          <Tooltip>Settings</Tooltip>
        </button>
      </div>
    </div>
  )
}

interface BotAvatarProps {
  bot: Bot
  active: boolean
  onClick: () => void
}

function BotAvatar({ bot, active, onClick }: BotAvatarProps) {
  return (
    <button
      onClick={onClick}
      className="group relative"
    >
      {/* Active indicator */}
      <div
        className={cn(
          'absolute -left-3 top-1/2 h-2 w-1 -translate-y-1/2 rounded-r-full bg-zinc-900 transition-all duration-200 dark:bg-white',
          active ? 'h-10' : 'h-0 group-hover:h-5'
        )}
      />

      {/* Avatar */}
      <div
        className={cn(
          'flex h-12 w-12 items-center justify-center transition-all duration-200',
          active
            ? 'rounded-[16px]'
            : 'rounded-[24px] group-hover:rounded-[16px]'
        )}
        style={{ backgroundColor: bot.color + '30' }}
      >
        <BotIconRenderer
          icon={bot.icon}
          className="h-6 w-6"
          size={24}
        />
      </div>

      <Tooltip>{bot.name}</Tooltip>
    </button>
  )
}

function Tooltip({ children }: { children: React.ReactNode }) {
  return (
    <div className="pointer-events-none absolute left-full top-1/2 z-50 ml-4 -translate-y-1/2 whitespace-nowrap rounded-md bg-zinc-800 px-3 py-2 text-sm font-medium text-white opacity-0 shadow-lg transition-opacity group-hover:opacity-100 dark:bg-zinc-900">
      {children}
      <div className="absolute -left-1 top-1/2 h-2 w-2 -translate-y-1/2 rotate-45 bg-zinc-800 dark:bg-zinc-900" />
    </div>
  )
}

function Divider() {
  return <div className="h-px w-8 bg-zinc-300 dark:bg-zinc-800" />
}

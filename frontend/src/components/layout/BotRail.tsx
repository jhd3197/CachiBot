import { Plus, Settings, LayoutDashboard, Github, Activity } from 'lucide-react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'
import type { Bot } from '../../types'

// App-level paths (not bot views)
const appPaths = ['/dashboard', '/settings', '/admin/logs']

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
  const isAppView = appPaths.some((p) => currentPath === p || currentPath.startsWith(p + '/'))

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
    <div className="bot-rail">
      {/* App-level navigation */}
      <div className="bot-rail__section">
        {/* Dashboard */}
        <button
          onClick={() => handleAppViewClick('/dashboard')}
          className={cn(
            'bot-rail__avatar-btn',
            currentPath === '/dashboard' && 'bot-rail__avatar-btn--active'
          )}
        >
          <LayoutDashboard className="h-5 w-5" />
          <Tooltip>Dashboard</Tooltip>
        </button>

        <div className="bot-rail__divider" />
      </div>

      {/* Bot avatars */}
      <div className="bot-rail__scroll">
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
          className="bot-rail__avatar-btn"
        >
          <Plus className="h-5 w-5" />
          <Tooltip>Create Bot</Tooltip>
        </button>
      </div>

      {/* Bottom actions */}
      <div className="bot-rail__bottom">
        <div className="bot-rail__divider" />

        {/* Admin Logs */}
        <button
          onClick={() => handleAppViewClick('/admin/logs')}
          className={cn(
            'bot-rail__action-btn',
            currentPath === '/admin/logs' && 'bot-rail__action-btn--active'
          )}
        >
          <Activity className="h-5 w-5" />
          <Tooltip>Exec Logs</Tooltip>
        </button>

        {/* GitHub */}
        <a
          href="https://github.com/jhd3197/CachiBot"
          target="_blank"
          rel="noopener noreferrer"
          className="bot-rail__action-btn"
        >
          <Github className="h-5 w-5" />
          <Tooltip>GitHub</Tooltip>
        </a>

        {/* Settings */}
        <button
          onClick={() => handleAppViewClick('/settings')}
          className={cn(
            'bot-rail__action-btn',
            (currentPath === '/settings' || currentPath.startsWith('/settings/')) && 'bot-rail__action-btn--active'
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
  const accessLevel = (bot as unknown as Record<string, unknown>).access_level as string | undefined
  const isShared = accessLevel && accessLevel !== 'owner'

  return (
    <button
      onClick={onClick}
      className="group relative"
    >
      {/* Active indicator */}
      <div
        className={cn(
          'bot-rail__active-indicator',
          active && 'bot-rail__active-indicator--active'
        )}
      />

      {/* Avatar */}
      <div
        className={cn(
          'bot-rail__avatar-btn',
          active && 'bot-rail__avatar-btn--active'
        )}
        style={{ backgroundColor: bot.color + '30' }}
      >
        <BotIconRenderer
          icon={bot.icon}
          className="h-6 w-6"
          size={24}
        />
      </div>

      {/* Shared bot indicator */}
      {isShared && (
        <div
          className={cn(
            'bot-rail__shared-dot',
            accessLevel === 'viewer' ? 'bot-rail__shared-dot--viewer' :
            accessLevel === 'operator' ? 'bot-rail__shared-dot--operator' :
            'bot-rail__shared-dot--editor'
          )}
          title={`Shared (${accessLevel})`}
        />
      )}

      <Tooltip>{bot.name}{isShared ? ` (${accessLevel})` : ''}</Tooltip>
    </button>
  )
}

function Tooltip({ children }: { children: React.ReactNode }) {
  return (
    <div className="bot-rail__tooltip">
      {children}
      <div className="bot-rail__tooltip-arrow" />
    </div>
  )
}

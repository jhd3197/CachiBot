import { useState, useMemo } from 'react'
import {
  Plus,
  Search,
  LayoutGrid,
  DoorOpen,
  Mic,
  FolderKanban,
  Blocks,
  Wrench,
  Puzzle,
  Code2,
  Settings,
  SlidersHorizontal,
  Activity,
  Github,
  Search as SearchIcon,
} from 'lucide-react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useRailStore } from '../../stores/rail'
import { useUIStore } from '../../stores/ui'
import { usePluginsStore } from '../../stores/plugins'
import { useBotAccess } from '../../hooks/useBotAccess'
import { resolveIconName } from '../common/ToolIconRenderer'
import { BotAvatar } from '../common/Avatar'
import { GlobalSearchDialog } from '../common/GlobalSearchDialog'
import { cn } from '../../lib/utils'
import type { Bot } from '../../types'

const LEVEL_RANK: Record<string, number> = { viewer: 1, operator: 2, editor: 3, owner: 4, admin: 4 }

interface BotListSidebarProps {
  onNavigate?: () => void
}

/**
 * UI v2 bot-first sidebar (design views 01/02): one row per bot,
 * search, new-bot, compact workspace links and the Workspace button.
 */
export function BotListSidebar({ onNavigate }: BotListSidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { botId: urlBotId } = useParams<{ botId?: string }>()
  const { bots, activeBotId, setActiveBot, setActiveView, getActiveBot } = useBotStore()
  const { getChatsByBot, setActiveChat } = useChatStore()
  const { setCreateBotOpen } = useUIStore()
  const { railOrder } = useRailStore()
  const [query, setQuery] = useState('')
  const [showGlobalSearch, setShowGlobalSearch] = useState(false)
  const activeBot = getActiveBot()
  const { accessLevel } = useBotAccess(activeBotId)
  const userRank = LEVEL_RANK[accessLevel ?? 'owner'] ?? 4

  // Order bots by the v1 rail order (groups flattened), unknown bots last
  const orderedBots = useMemo(() => {
    const ids: string[] = []
    for (const item of railOrder) {
      if (item.type === 'bot') ids.push(item.botId)
      else {
        const group = useRailStore.getState().botGroups.find((g) => g.id === item.groupId)
        if (group) ids.push(...group.botIds)
      }
    }
    const seen = new Set(ids)
    return [
      ...ids.map((id) => bots.find((b) => b.id === id)).filter((b): b is Bot => !!b),
      ...bots.filter((b) => !seen.has(b.id)),
    ]
  }, [railOrder, bots])

  const filteredBots = useMemo(() => {
    const q = query.trim().toLowerCase()
    if (!q) return orderedBots
    return orderedBots.filter(
      (b) => b.name.toLowerCase().includes(q) || b.description?.toLowerCase().includes(q)
    )
  }, [orderedBots, query])

  const handleBotClick = (bot: Bot) => {
    setActiveBot(bot.id)
    setActiveView('chats')
    const chats = getChatsByBot(bot.id)
    const latest = chats[0]
    if (latest) {
      setActiveChat(latest.id)
      navigate(`/${bot.id}/chats/${latest.platform ?? latest.id}`)
    } else {
      setActiveChat(null)
      navigate(`/${bot.id}/chats`)
    }
    onNavigate?.()
  }

  const handleWorkspaceClick = () => {
    navigate('/dashboard')
    onNavigate?.()
  }

  // ── Compact workspace menu (access-filtered legacy destinations) ──
  const botLinks = [
    { id: 'rooms', label: 'Rooms', icon: DoorOpen, minLevel: 'viewer', path: `/${activeBotId}/rooms`, view: 'rooms' as const },
    { id: 'voice', label: 'Voice', icon: Mic, minLevel: 'operator', path: `/${activeBotId}/voice`, view: 'voice' as const },
    { id: 'work', label: 'Work', icon: FolderKanban, minLevel: 'operator', path: `/${activeBotId}/work`, view: 'work' as const },
    { id: 'automations', label: 'Automations', icon: Blocks, minLevel: 'operator', path: `/${activeBotId}/automations`, view: 'automations' as const },
    { id: 'tools', label: 'Tools', icon: Wrench, minLevel: 'editor', path: `/${activeBotId}/tools`, view: 'tools' as const },
    { id: 'plugins', label: 'Plugins', icon: Puzzle, minLevel: 'editor', path: `/${activeBotId}/plugins`, view: 'plugins' as const },
    { id: 'developer', label: 'Developer', icon: Code2, minLevel: 'editor', path: `/${activeBotId}/developer`, view: 'developer' as const },
    { id: 'settings', label: 'Bot settings', icon: SlidersHorizontal, minLevel: 'editor', path: `/${activeBotId}/settings`, view: 'settings' as const },
  ].filter((item) => activeBot && userRank >= LEVEL_RANK[item.minLevel])

  // Dynamic view-type external plugins (same behavior as the v1 gear menu)
  const { plugins: externalPlugins } = usePluginsStore()
  const capabilities = (activeBot?.capabilities ?? {}) as Record<string, boolean>
  const pluginLinks = externalPlugins
    .filter((p) => p.type === 'view' && p.view && p.loaded && capabilities[p.capabilityKey] === true)
    .map((p) => ({
      name: p.name,
      label: p.view!.navLabel,
      icon: resolveIconName(p.view!.navIcon),
      route: p.view!.route,
    }))

  const appLinks = [
    { id: 'search', label: 'Search', icon: SearchIcon, path: null as string | null },
    { id: 'logs', label: 'Exec logs', icon: Activity, path: '/admin/logs' },
    { id: 'app-settings', label: 'Settings', icon: Settings, path: '/settings' },
    { id: 'github', label: 'GitHub', icon: Github, path: 'https://github.com/jhd3197/CachiBot' },
  ]

  const isBotRoute = (path: string) => location.pathname.startsWith(path)

  const handleMenuNav = (path: string, view?: string) => {
    if (view) setActiveView(view as Parameters<typeof setActiveView>[0])
    navigate(path)
    onNavigate?.()
  }

  const isWorkspaceActive = location.pathname === '/dashboard' || location.pathname === '/dashboard/usage'

  return (
    <aside className="v2-nav" aria-label="Bots">
      {/* Top actions: new bot (notifications omitted — no notifications backend yet) */}
      <div className="v2-nav__top">
        <button
          type="button"
          className="v2-icon-btn"
          aria-label="New bot"
          title="New bot"
          onClick={() => setCreateBotOpen(true)}
        >
          <Plus size={18} strokeWidth={1.8} />
        </button>
      </div>

      {/* Search filters real bots */}
      <label className="v2-search">
        <Search size={16} strokeWidth={1.8} aria-hidden="true" />
        <span className="sr-only">Search</span>
        <input
          type="search"
          className="v2-search__input"
          placeholder="Search"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
      </label>

      {/* Bot rows */}
      <div className="v2-nav__list" role="list">
        {filteredBots.length === 0 ? (
          <div className="v2-nav__empty">
            {bots.length === 0 ? 'No bots yet' : 'No bots match your search'}
          </div>
        ) : (
          filteredBots.map((bot) => {
            const chats = getChatsByBot(bot.id)
            const latest = chats[0]
            const active = !isWorkspaceActive && !!urlBotId && bot.id === urlBotId
            return (
              <button
                key={bot.id}
                type="button"
                role="listitem"
                className={cn('v2-bot-row', active && 'v2-bot-row--active')}
                onClick={() => handleBotClick(bot)}
              >
                <BotAvatar color={bot.color} name={bot.name} size={40} />
                <span className="v2-bot-row__main">
                  <span className="v2-bot-row__name-row">
                    <span className="v2-bot-row__name">{bot.name}</span>
                    {latest && <span className="v2-bot-row__time">{formatListTime(latest.updatedAt)}</span>}
                  </span>
                  {bot.description && <span className="v2-bot-row__chip">{bot.description}</span>}
                  {latest && (
                    <span className="v2-bot-row__preview">
                      {latest.lastMessage || latest.title}
                    </span>
                  )}
                </span>
              </button>
            )
          })
        )}
      </div>

      {/* Bottom: compact workspace links + Workspace */}
      <div className="v2-nav__bottom">
        <div className="v2-nav__menu" aria-label="Workspace links">
          {botLinks.map((item) => (
            <button
              key={item.id}
              type="button"
              className={cn('v2-icon-btn', isBotRoute(item.path) && 'v2-icon-btn--active')}
              title={item.label}
              aria-label={item.label}
              onClick={() => handleMenuNav(item.path, item.view)}
            >
              <item.icon size={17} strokeWidth={1.8} />
            </button>
          ))}
          {pluginLinks.map((p) => (
            <button
              key={`ext-${p.name}`}
              type="button"
              className={cn('v2-icon-btn', location.pathname === `/${activeBotId}/plugins/${p.name}` && 'v2-icon-btn--active')}
              title={p.label}
              aria-label={p.label}
              onClick={() => handleMenuNav(`/${activeBotId}/plugins/${p.name}`, 'plugins')}
            >
              <p.icon size={17} strokeWidth={1.8} />
            </button>
          ))}
          {appLinks.map((item) =>
            item.id === 'search' ? (
              <button
                key={item.id}
                type="button"
                className="v2-icon-btn"
                title={item.label}
                aria-label={item.label}
                onClick={() => setShowGlobalSearch(true)}
              >
                <item.icon size={17} strokeWidth={1.8} />
              </button>
            ) : item.path!.startsWith('http') ? (
              <a
                key={item.id}
                href={item.path!}
                target="_blank"
                rel="noopener noreferrer"
                className="v2-icon-btn"
                title={item.label}
                aria-label={item.label}
              >
                <item.icon size={17} strokeWidth={1.8} />
              </a>
            ) : (
              <button
                key={item.id}
                type="button"
                className={cn('v2-icon-btn', location.pathname.startsWith(item.path!) && 'v2-icon-btn--active')}
                title={item.label}
                aria-label={item.label}
                onClick={() => handleMenuNav(item.path!)}
              >
                <item.icon size={17} strokeWidth={1.8} />
              </button>
            )
          )}
        </div>

        <button
          type="button"
          className={cn('v2-workspace-btn', isWorkspaceActive && 'v2-workspace-btn--active')}
          onClick={handleWorkspaceClick}
        >
          <span className="v2-workspace-btn__icon-tile">
            <LayoutGrid size={16} strokeWidth={1.8} />
          </span>
          Workspace
        </button>
      </div>

      {showGlobalSearch && activeBot && (
        <GlobalSearchDialog
          botId={activeBot.id}
          onNavigate={(path) => { setShowGlobalSearch(false); navigate(path); onNavigate?.() }}
          onClose={() => setShowGlobalSearch(false)}
        />
      )}
    </aside>
  )
}

/**
 * Sidebar list timestamp per design: "9:14 AM", "Yesterday", "Mon".
 * Only shown when backed by a real chat's updatedAt.
 */
function formatListTime(iso: string): string {
  const d = new Date(iso)
  const now = new Date()
  const dayStart = (x: Date) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime()
  const diffDays = Math.round((dayStart(now) - dayStart(d)) / 86400000)
  if (diffDays <= 0) {
    return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
  }
  if (diffDays === 1) return 'Yesterday'
  if (diffDays < 7) return d.toLocaleDateString(undefined, { weekday: 'short' })
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

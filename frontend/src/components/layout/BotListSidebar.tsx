import { useState, useMemo, useEffect } from 'react'
import {
  Plus,
  Search,
  LayoutGrid,
  CircleUser,
  Settings,
  Clock,
  ListOrdered,
  Users,
  BookOpen,
  LogOut,
  GitBranch,
  Check,
  Square,
  XCircle,
  Hand,
} from 'lucide-react'
import { useNavigate, useLocation, useParams } from 'react-router-dom'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useSideTasksStore, partitionSideTasks } from '../../stores/side-tasks'
import { useRailStore } from '../../stores/rail'
import { useUIStore } from '../../stores/ui'
import { useRoomStore } from '../../stores/rooms'
import { useAuthStore } from '../../stores/auth'
import { getRooms } from '../../api/rooms'
import { listUsers } from '../../api/auth'
import { BotAvatar } from '../common/Avatar'
import { Spinner } from '../common/Spinner'
import { V2Menu, V2MenuItem, V2MenuLabel, V2MenuDivider } from '../common/V2Menu'
import { CreateRoomDialog } from '../rooms/CreateRoomDialog'
import { cn, parseApiDate } from '../../lib/utils'
import type { Bot, Room, SideTask, SideTaskStatus } from '../../types'

interface BotListSidebarProps {
  onNavigate?: () => void
  /** Opens the global search dialog (search icon + Ctrl/Cmd K) */
  onOpenSearch: () => void
}

/**
 * UI v2 bot-first sidebar (design views 13/02): "Bots" heading row with
 * search + new bot, one row per bot, a Rooms group under the bots, and
 * Workspace + Account at the bottom. The old bottom icon row is gone —
 * every destination moved per view 12 (search → here/Ctrl K, settings →
 * the account menu, work/automations/tools/plugins/developer → the chat
 * header More menu, exec logs/GitHub → account menu / settings).
 */
export function BotListSidebar({ onNavigate, onOpenSearch }: BotListSidebarProps) {
  const navigate = useNavigate()
  const location = useLocation()
  const { botId: urlBotId, roomId: urlRoomId } = useParams<{ botId?: string; roomId?: string }>()
  const { bots, activeBotId, setActiveBot, setActiveView } = useBotStore()
  const { getChatsByBot, setActiveChat, activeChatId } = useChatStore()
  const { setCreateBotOpen } = useUIStore()
  const { railOrder } = useRailStore()
  const { rooms, setRooms } = useRoomStore()
  const { user, logout } = useAuthStore()
  const [showCreateRoom, setShowCreateRoom] = useState(false)
  const [accountOpen, setAccountOpen] = useState(false)
  const [peopleCount, setPeopleCount] = useState<number | null>(null)
  const isAdmin = user?.role === 'admin'

  // Rooms for the sidebar group ( RoomsView also refreshes this store )
  useEffect(() => {
    let cancelled = false
    getRooms()
      .then((data) => { if (!cancelled) setRooms(data) })
      .catch(() => { /* rooms unavailable — group stays empty */ })
    return () => { cancelled = true }
  }, [setRooms])

  // Real user count for the admin "People" entry (admins only)
  useEffect(() => {
    if (!isAdmin || !accountOpen) return
    let cancelled = false
    listUsers(1, 0)
      .then((res) => { if (!cancelled) setPeopleCount(res.total) })
      .catch(() => { if (!cancelled) setPeopleCount(null) })
    return () => { cancelled = true }
  }, [isAdmin, accountOpen])

  // Side tasks (principle 9) for the sidebar tree — one level under the bot's
  // latest chat row. The list endpoint feeds the store; live state changes
  // arrive as side_task_update events.
  const sideTasksById = useSideTasksStore((s) => s.byId)
  const ensureSideTasks = useSideTasksStore((s) => s.ensureForBot)
  useEffect(() => {
    for (const bot of bots) void ensureSideTasks(bot.id)
  }, [bots, ensureSideTasks])

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

  const handleRoomClick = (room: Room) => {
    const botId = room.bots[0]?.botId ?? activeBotId ?? bots[0]?.id
    if (!botId) return
    setActiveBot(botId)
    setActiveView('rooms')
    useRoomStore.getState().setActiveRoom(room.id)
    navigate(`/${botId}/rooms/${room.id}`)
    onNavigate?.()
  }

  const handleWorkspaceClick = () => {
    navigate('/dashboard')
    onNavigate?.()
  }

  const handleNav = (path: string) => {
    setAccountOpen(false)
    navigate(path)
    onNavigate?.()
  }

  const handleSignOut = () => {
    setAccountOpen(false)
    logout()
    navigate('/login')
    onNavigate?.()
  }

  const isWorkspaceActive = location.pathname === '/dashboard' || location.pathname === '/dashboard/usage'
  const initial = (user?.username || user?.email || '?').trim().charAt(0).toUpperCase()

  return (
    <aside className="v2-nav" aria-label="Bots">
      {/* Heading row: title + search + new bot (notifications omitted — no source) */}
      <div className="v2-nav__heading">
        <span className="v2-nav__heading-title">Bots</span>
        <span className="v2-nav__heading-actions">
          <button
            type="button"
            className="v2-icon-btn"
            aria-label="Search (Ctrl K)"
            title="Search (Ctrl K)"
            onClick={onOpenSearch}
          >
            <Search size={17} strokeWidth={1.8} />
          </button>
          <button
            type="button"
            className="v2-icon-btn"
            aria-label="New bot"
            title="New bot"
            onClick={() => setCreateBotOpen(true)}
          >
            <Plus size={18} strokeWidth={1.8} />
          </button>
        </span>
      </div>

      {/* Bot rows + Rooms group */}
      <div className="v2-nav__list" role="list">
        {orderedBots.length === 0 ? (
          <div className="v2-nav__empty">No bots yet</div>
        ) : (
          orderedBots.map((bot) => {
            const chats = getChatsByBot(bot.id)
            const latest = chats[0]
            const active = !isWorkspaceActive && !urlRoomId && !!urlBotId && bot.id === urlBotId
            // Side tasks of the bot's latest chat (design 11a "Side-task
            // replies"): the tree stays quiet — active + needs-you + failed
            // rows only, one muted "N finished" row for the rest; the only
            // accent color is the amber on needs-you. Computed inline (no
            // memo hook inside the map): the row re-renders with any
            // sideTasksById change anyway, and the lists are small.
            const { singles: sideSingles, groups: sideGroups } = latest
              ? partitionSideTasks(
                  Object.values(sideTasksById).filter((t) => t.parentChatId === latest.id)
                )
              : { singles: [] as SideTask[], groups: [] as Array<{ groupId: string; title: string | null; items: SideTask[] }> }
            const treeVisible = (t: SideTask) =>
              t.status === 'running' ||
              t.status === 'waiting_for_slot' ||
              t.status === 'needs_you' ||
              t.status === 'failed'
            const treeFinished = (t: SideTask) => !treeVisible(t)
            const visibleSingles = sideSingles.filter(treeVisible)
            const finishedSingles = sideSingles.filter(treeFinished)
            const activeGroups = sideGroups.filter((g) => g.items.some(treeVisible))
            const finishedCount =
              finishedSingles.length +
              sideGroups
                .filter((g) => !activeGroups.includes(g))
                .reduce((n, g) => n + g.items.length, 0)
            const hasSideTree =
              visibleSingles.length > 0 || activeGroups.length > 0 || finishedCount > 0
            return (
              <div key={bot.id}>
                <button
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
                {hasSideTree && (
                  <div className="side-tree" role="group" aria-label={`Side tasks of ${bot.name}`}>
                    {visibleSingles.map((task) => (
                      <SideTreeRow key={task.id} task={task} activeChatId={activeChatId} />
                    ))}
                    {activeGroups.map((group) => (
                      <SideTreeGroupRow key={group.groupId} group={group} activeChatId={activeChatId} />
                    ))}
                    {finishedCount > 0 && (
                      <div className="side-tree__finished">
                        {finishedCount} finished
                      </div>
                    )}
                  </div>
                )}
              </div>
            )
          })
        )}

        {/* Rooms group (design 13) — always visible so "+" stays reachable */}
        <div className="v2-rooms">
          <div className="v2-rooms__heading">
            <span className="v2-rooms__heading-label">Rooms</span>
            <span className="v2-rooms__heading-actions">
              <button
                type="button"
                className="v2-icon-btn"
                aria-label="New room"
                title="New room"
                onClick={() => setShowCreateRoom(true)}
              >
                <Plus size={15} strokeWidth={1.8} />
              </button>
            </span>
          </div>
          {rooms.map((room) => {
            const active = !!urlRoomId && room.id === urlRoomId
            const last = room.lastMessage
            return (
              <button
                key={room.id}
                type="button"
                className={cn('v2-room-row', active && 'v2-room-row--active')}
                onClick={() => handleRoomClick(room)}
              >
                <span className="v2-room-row__avatars">
                  {room.bots.slice(0, 4).map((b) => (
                    <BotAvatar key={b.botId} color={botColor(b.botId)} name={b.botName || 'Bot'} size={22} />
                  ))}
                </span>
                <span className="v2-room-row__main">
                  <span className="v2-room-row__name">{room.title}</span>
                  <span className="v2-room-row__subtitle">
                    {last ? `${last.senderName}: ${last.content}` : `${room.bots.length} bots`}
                  </span>
                </span>
              </button>
            )
          })}
        </div>
      </div>

      {/* Bottom: Workspace + Account (design 13) */}
      <div className="v2-nav__bottom">
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

        <div className="v2-account-wrap">
          <button
            type="button"
            className="v2-account"
            aria-haspopup="menu"
            aria-expanded={accountOpen}
            onClick={(e) => { e.stopPropagation(); setAccountOpen((o) => !o) }}
          >
            <span className="v2-account__avatar">{initial}</span>
            <span className="v2-account__name">{user?.username || user?.email || 'Account'}</span>
            <Settings size={16} strokeWidth={1.8} className="v2-account__gear" />
          </button>
          {accountOpen && (
            <V2Menu className="v2-account__menu" onClose={() => setAccountOpen(false)}>
              <V2MenuItem icon={<CircleUser size={16} strokeWidth={1.8} />} onClick={() => handleNav('/settings/account')}>
                Your account
              </V2MenuItem>
              <V2MenuItem icon={<Settings size={16} strokeWidth={1.8} />} onClick={() => handleNav('/settings/general')}>
                Settings
              </V2MenuItem>
              <V2MenuItem
                icon={<Clock size={16} strokeWidth={1.8} />}
                suffix="this month"
                onClick={() => handleNav('/dashboard/usage')}
              >
                Usage
              </V2MenuItem>
              {isAdmin && (
                <>
                  <V2MenuDivider />
                  <V2MenuLabel>Admin</V2MenuLabel>
                  <V2MenuItem
                    icon={<ListOrdered size={16} strokeWidth={1.8} />}
                    onClick={() => handleNav('/admin/logs')}
                  >
                    Activity log
                  </V2MenuItem>
                  <V2MenuItem
                    icon={<Users size={16} strokeWidth={1.8} />}
                    suffix={peopleCount ?? undefined}
                    onClick={() => handleNav('/users')}
                  >
                    People
                  </V2MenuItem>
                </>
              )}
              <V2MenuDivider />
              <V2MenuItem icon={<BookOpen size={16} strokeWidth={1.8} />} onClick={() => handleNav('/settings/about')}>
                About and help
              </V2MenuItem>
              <V2MenuItem icon={<LogOut size={16} strokeWidth={1.8} />} onClick={handleSignOut}>
                Sign out
              </V2MenuItem>
            </V2Menu>
          )}
        </div>
      </div>

      {showCreateRoom && <CreateRoomDialog onClose={() => setShowCreateRoom(false)} />}
    </aside>
  )
}

// Bot colors for the stacked room avatars (deterministic per bot)
function botColor(botId: string): string {
  const bot = useBotStore.getState().bots.find((b) => b.id === botId)
  return bot?.color || '#4ade80'
}

function sideTaskStatusLabel(task: SideTask): { text: string; tone?: 'needs-you' } {
  switch (task.status) {
    case 'waiting_for_slot':
      return { text: 'Waiting' }
    case 'running':
      return { text: 'Running' }
    case 'needs_you':
      return { text: 'Needs you', tone: 'needs-you' }
    case 'merged':
      return { text: 'Brought in' }
    case 'failed':
      return { text: 'Failed' }
    case 'stopped':
      return { text: 'Stopped' }
    default:
      return { text: 'Done' }
  }
}

function SideTreeStatusIcon({ status }: { status: SideTaskStatus }) {
  const cls = 'side-tree__row-icon'
  switch (status) {
    case 'running':
      return <Spinner size="sm" label="" aria-hidden="true" className={cls} />
    case 'needs_you':
      return <Hand className={cn(cls, 'side-tree__row-icon--needs-you')} strokeWidth={1.8} />
    case 'failed':
      return <XCircle className={cls} strokeWidth={1.8} />
    case 'stopped':
      return <Square className={cls} strokeWidth={1.8} />
    case 'waiting_for_slot':
      return <Clock className={cls} strokeWidth={1.8} />
    default:
      return <Check className={cls} strokeWidth={1.8} />
  }
}

/**
 * One side-task row in the sidebar tree (design 11a/11c): icon by status,
 * title, right-hand status label. Opens the side task's own chat.
 */
function SideTreeRow({ task, activeChatId }: { task: SideTask; activeChatId: string | null }) {
  const navigate = useNavigate()
  const { text, tone } = sideTaskStatusLabel(task)
  return (
    <button
      type="button"
      className={cn('side-tree__row', activeChatId === task.chatId && 'side-tree__row--active')}
      onClick={() => navigate(`/${task.botId}/chats/${task.chatId}`)}
    >
      <SideTreeStatusIcon status={task.status} />
      <span className="side-tree__row-title">{task.title}</span>
      <span
        className={cn(
          'side-tree__row-status',
          tone === 'needs-you' && 'side-tree__row-status--needs-you'
        )}
      >
        {text}
      </span>
    </button>
  )
}

/**
 * One helper-group row in the sidebar tree: "Test on Python 3.11–3.13 · 1 of 3".
 * Opens the most attention-worthy helper's chat.
 */
function SideTreeGroupRow({
  group,
  activeChatId,
}: {
  group: { groupId: string; title: string | null; items: SideTask[] }
  activeChatId: string | null
}) {
  const navigate = useNavigate()
  const { items } = group
  const done = items.filter((t) => t.status === 'done' || t.status === 'merged').length
  const headline = (['needs_you', 'failed', 'running', 'waiting_for_slot'] as SideTaskStatus[])
    .map((s) => items.find((t) => t.status === s))
    .find(Boolean)
  const active = items.some((t) => t.chatId === activeChatId)
  const anyNeedsYou = items.some((t) => t.status === 'needs_you')

  const open = () => {
    const target = headline ?? items[0]
    if (target) navigate(`/${target.botId}/chats/${target.chatId}`)
  }

  return (
    <button
      type="button"
      className={cn('side-tree__row', active && 'side-tree__row--active')}
      onClick={open}
    >
      <GitBranch className="side-tree__row-icon" strokeWidth={1.8} />
      <span className="side-tree__row-title">{group.title ?? `${items.length} helpers`}</span>
      <span
        className={cn(
          'side-tree__row-status',
          anyNeedsYou && 'side-tree__row-status--needs-you'
        )}
      >
        {done} of {items.length}
      </span>
    </button>
  )
}

/**
 * Sidebar list timestamp per design: "9:14 AM", "Yesterday", "Mon".
 * Only shown when backed by a real chat's updatedAt.
 */
function formatListTime(iso: string): string {
  // Chat rows come from the local chat store (offset-bearing ISO strings),
  // so this is unchanged in practice; parseApiDate keeps it correct if a
  // naive-UTC API timestamp ever reaches it.
  const d = parseApiDate(iso)
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

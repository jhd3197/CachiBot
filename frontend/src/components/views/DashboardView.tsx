import { useState } from 'react'
import {
  BarChart3,
  Bot,
  MessageSquare,
  Zap,
  DollarSign,
  Activity,
  Plug,
  ArrowUpRight,
  Cpu,
  Target,
} from 'lucide-react'
import { useBotStore, useChatStore, useJobStore, useTaskStore } from '../../stores/bots'
import { useUsageStore } from '../../stores/connections'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { cn } from '../../lib/utils'

type TimeRange = '24h' | '7d' | '30d' | 'all'

export function DashboardView() {
  const [timeRange, setTimeRange] = useState<TimeRange>('7d')
  const { bots } = useBotStore()
  const { chats, messages } = useChatStore()
  const { jobs } = useJobStore()
  const { tasks } = useTaskStore()
  const { stats } = useUsageStore()
  const { rooms, messages: roomMessages } = useRoomStore()

  // Calculate totals (include both regular chat and room messages)
  const chatMessageCount = Object.values(messages).reduce((acc, msgs) => acc + msgs.length, 0)
  const roomMessageCount = Object.values(roomMessages).reduce((acc, msgs) => acc + msgs.length, 0)
  const totalMessages = chatMessageCount + roomMessageCount
  const activeJobs = jobs.filter((j) => j.status === 'running').length
  const completedTasks = tasks.filter((t) => t.status === 'done').length
  const pendingTasks = tasks.filter((t) => t.status === 'todo').length
  const totalChats = chats.length
  const totalConnections = totalChats + rooms.length

  // Bot stats
  const botStats = bots.map((bot) => {
    const botChats = chats.filter((c) => c.botId === bot.id)
    const botChatMessages = botChats.reduce(
      (acc, chat) => acc + (messages[chat.id]?.length || 0),
      0
    )
    // Count room messages where this bot is a sender
    const botRoomMessages = Object.values(roomMessages).reduce(
      (acc, msgs) => acc + msgs.filter((m) => m.senderId === bot.id).length,
      0
    )
    const botRooms = rooms.filter((r) => r.bots.some((b) => b.botId === bot.id))
    const botJobs = jobs.filter((j) => j.botId === bot.id)
    const botTasks = tasks.filter((t) => t.botId === bot.id)
    const usage = stats.byBot[bot.id] || { tokens: 0, cost: 0, messages: 0 }

    return {
      bot,
      chats: botChats.length,
      messages: botChatMessages + botRoomMessages,
      jobs: botJobs.length,
      activeJobs: botJobs.filter((j) => j.status === 'running').length,
      tasks: botTasks.length,
      completedTasks: botTasks.filter((t) => t.status === 'done').length,
      connections: botChats.length + botRooms.length,
      tokens: usage.tokens,
      cost: usage.cost,
    }
  })

  return (
    <div className="dashboard">
      {/* Header */}
      <div className="dashboard-header">
        <div>
          <h1 className="dashboard-header__title">Dashboard</h1>
          <p className="dashboard-header__subtitle">Overview of your bots and activity</p>
        </div>

        {/* Time range selector */}
        <div className="dashboard-time-range">
          {(['24h', '7d', '30d', 'all'] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={cn(
                'dashboard-time-range__btn',
                timeRange === range && 'dashboard-time-range__btn--active'
              )}
            >
              {range === 'all' ? 'All Time' : range}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="dashboard-content">
        <div className="dashboard-content__inner space-y-6">
          {/* Stats Grid */}
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              icon={Bot}
              label="Active Bots"
              value={bots.length}
              trend="+0"
              trendUp
              color="green"
            />
            <StatCard
              icon={MessageSquare}
              label="Total Messages"
              value={totalMessages.toLocaleString()}
              subValue={`${totalChats} chats · ${rooms.length} rooms`}
              color="blue"
            />
            <StatCard
              icon={Zap}
              label="Tokens Used"
              value={formatNumber(stats.totalTokens)}
              subValue={`${stats.totalMessages} API calls`}
              color="purple"
            />
            <StatCard
              icon={DollarSign}
              label="Total Cost"
              value={`$${stats.totalCost.toFixed(4)}`}
              subValue="estimated"
              color="amber"
            />
          </div>

          {/* Secondary Stats */}
          <div className="grid gap-4 sm:grid-cols-3">
            <StatCard
              icon={Activity}
              label="Active Jobs"
              value={activeJobs}
              subValue={`${jobs.length} total`}
              color="blue"
              small
            />
            <StatCard
              icon={Target}
              label="Tasks Completed"
              value={completedTasks}
              subValue={`${pendingTasks} pending`}
              color="green"
              small
            />
            <StatCard
              icon={Plug}
              label="Connections"
              value={totalConnections}
              subValue={`${totalChats} chats · ${rooms.length} rooms`}
              color="cyan"
              small
            />
          </div>

          {/* Bot Cards */}
          <section>
            <h2 className="dashboard-section-title">
              <Bot className="h-5 w-5 dashboard-section-title__icon" />
              Bot Performance
            </h2>
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {botStats.map(({ bot, chats, messages, activeJobs, completedTasks, tokens, cost, connections }) => (
                <BotCard
                  key={bot.id}
                  bot={bot}
                  chats={chats}
                  messages={messages}
                  activeJobs={activeJobs}
                  completedTasks={completedTasks}
                  tokens={tokens}
                  cost={cost}
                  connections={connections}
                />
              ))}
            </div>
          </section>

          {/* Usage Chart */}
          <section>
            <h2 className="dashboard-section-title">
              <BarChart3 className="h-5 w-5 dashboard-section-title__icon" />
              Usage Over Time
            </h2>
            <div className="dashboard-chart">
              {stats.daily.length > 0 ? (
                <div className="space-y-4">
                  <div className="dashboard-chart__bars" style={{ height: 120 }}>
                    {stats.daily.slice(-14).map((day) => {
                      const maxTokens = Math.max(...stats.daily.map((d) => d.tokens))
                      const heightPx = maxTokens > 0 ? Math.max((day.tokens / maxTokens) * 120, 5) : 5
                      return (
                        <div
                          key={day.date}
                          className="dashboard-chart__bar-wrapper"
                        >
                          <div
                            className="dashboard-chart__bar"
                            style={{ height: heightPx }}
                          />
                          <div className="dashboard-chart__bar-tooltip">
                            {formatNumber(day.tokens)} tokens
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <div className="dashboard-chart__date-range">
                    <span>{stats.daily[Math.max(0, stats.daily.length - 14)]?.date}</span>
                    <span>{stats.daily[stats.daily.length - 1]?.date}</span>
                  </div>
                </div>
              ) : (
                <div className="dashboard-chart__empty">
                  <div className="text-center">
                    <BarChart3 className="mx-auto mb-2 h-8 w-8 dashboard-chart__empty-icon" />
                    <p>No usage data yet</p>
                    <p className="dashboard-chart__empty-sub">Start chatting to see analytics</p>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Model Usage */}
          {Object.keys(stats.byModel).length > 0 && (
            <section>
              <h2 className="dashboard-section-title">
                <Cpu className="h-5 w-5 dashboard-section-title__icon" />
                Model Usage
              </h2>
              <div className="dashboard-model-list">
                {Object.entries(stats.byModel)
                  .sort((a, b) => b[1].tokens - a[1].tokens)
                  .map(([model, usage]) => (
                    <div
                      key={model}
                      className="dashboard-model-list__item"
                    >
                      <div>
                        <h4 className="dashboard-model-list__model-name">{model}</h4>
                        <p className="dashboard-model-list__model-msgs">{usage.messages} messages</p>
                      </div>
                      <div className="text-right">
                        <p className="dashboard-model-list__model-tokens">
                          {formatNumber(usage.tokens)}
                        </p>
                        <p className="dashboard-model-list__model-cost">${usage.cost.toFixed(4)}</p>
                      </div>
                    </div>
                  ))}
              </div>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// COMPONENTS
// =============================================================================

interface StatCardProps {
  icon: React.ComponentType<{ className?: string }>
  label: string
  value: string | number
  subValue?: string
  trend?: string
  trendUp?: boolean
  color: 'green' | 'blue' | 'purple' | 'amber' | 'cyan' | 'red'
  small?: boolean
}

function StatCard({
  icon: Icon,
  label,
  value,
  subValue,
  trend,
  trendUp,
  color,
  small,
}: StatCardProps) {
  return (
    <div className={cn('dashboard-stat', small && 'dashboard-stat--small')}>
      <div className="dashboard-stat__top">
        <div
          className={cn(
            'dashboard-stat__icon',
            `dashboard-stat__icon--${color}`,
            small && 'dashboard-stat__icon--small'
          )}
        >
          <Icon className={small ? 'h-4 w-4' : 'h-5 w-5'} />
        </div>
        {trend && (
          <div
            className={cn(
              'dashboard-stat__trend',
              trendUp ? 'dashboard-stat__trend--up' : 'dashboard-stat__trend--down'
            )}
          >
            {trend}
            <ArrowUpRight
              className={cn('h-3 w-3', !trendUp && 'rotate-90')}
            />
          </div>
        )}
      </div>
      <div className={cn('dashboard-stat__body', small && 'dashboard-stat__body--small')}>
        <h3 className="dashboard-stat__label">
          {label}
        </h3>
        <p className={cn('dashboard-stat__value', small && 'dashboard-stat__value--small')}>
          {value}
        </p>
        {subValue && <p className="dashboard-stat__sub">{subValue}</p>}
      </div>
    </div>
  )
}

interface BotCardProps {
  bot: { id: string; name: string; icon: string; color: string; model: string }
  chats: number
  messages: number
  activeJobs: number
  completedTasks: number
  tokens: number
  cost: number
  connections: number
}

function BotCard({
  bot,
  chats,
  messages,
  activeJobs,
  completedTasks,
  tokens,
  cost,
  connections,
}: BotCardProps) {
  return (
    <div className="dashboard-bot-card">
      <div className="dashboard-bot-card__header">
        <div
          className="dashboard-bot-card__avatar"
          style={{ backgroundColor: bot.color + '20' }}
        >
          <BotIconRenderer icon={bot.icon} size={22} color={bot.color} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="dashboard-bot-card__name">{bot.name}</h3>
          <p className="dashboard-bot-card__model">{bot.model}</p>
        </div>
      </div>

      <div className="dashboard-bot-card__stats">
        <MiniStat icon={MessageSquare} value={messages} label="messages" />
        <MiniStat icon={Zap} value={formatNumber(tokens)} label="tokens" />
        <MiniStat icon={Activity} value={activeJobs} label="active jobs" />
        <MiniStat icon={Target} value={completedTasks} label="completed" />
      </div>

      <div className="dashboard-bot-card__footer">
        <div className="flex items-center gap-3">
          <span>{chats} chats</span>
          <span className="flex items-center gap-1">
            <Plug className="h-3 w-3" />
            {connections}
          </span>
        </div>
        <div>
          ${cost.toFixed(4)}
        </div>
      </div>
    </div>
  )
}

function MiniStat({
  icon: Icon,
  value,
  label,
}: {
  icon: React.ComponentType<{ className?: string }>
  value: string | number
  label: string
}) {
  return (
    <div className="dashboard-mini-stat">
      <Icon className="h-3.5 w-3.5 dashboard-mini-stat__icon" />
      <div>
        <span className="dashboard-mini-stat__value">{value}</span>
        <span className="dashboard-mini-stat__label">{label}</span>
      </div>
    </div>
  )
}

function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toString()
}

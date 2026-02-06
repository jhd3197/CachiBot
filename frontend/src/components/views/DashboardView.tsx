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

  // Calculate totals
  const totalMessages = Object.values(messages).reduce((acc, msgs) => acc + msgs.length, 0)
  const activeJobs = jobs.filter((j) => j.status === 'running').length
  const completedTasks = tasks.filter((t) => t.status === 'done').length
  const pendingTasks = tasks.filter((t) => t.status === 'todo').length
  const totalChats = chats.length

  // Bot stats
  const botStats = bots.map((bot) => {
    const botChats = chats.filter((c) => c.botId === bot.id)
    const botMessages = botChats.reduce(
      (acc, chat) => acc + (messages[chat.id]?.length || 0),
      0
    )
    const botJobs = jobs.filter((j) => j.botId === bot.id)
    const botTasks = tasks.filter((t) => t.botId === bot.id)
    const usage = stats.byBot[bot.id] || { tokens: 0, cost: 0, messages: 0 }

    return {
      bot,
      chats: botChats.length,
      messages: botMessages,
      jobs: botJobs.length,
      activeJobs: botJobs.filter((j) => j.status === 'running').length,
      tasks: botTasks.length,
      completedTasks: botTasks.filter((t) => t.status === 'done').length,
      connections: botChats.length, // Use chats as connections
      tokens: usage.tokens,
      cost: usage.cost,
    }
  })

  return (
    <div className="flex h-full flex-col bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-4">
        <div>
          <h1 className="text-xl font-bold text-zinc-100">Dashboard</h1>
          <p className="text-sm text-zinc-500">Overview of your bots and activity</p>
        </div>

        {/* Time range selector */}
        <div className="flex items-center gap-1 rounded-lg bg-zinc-900 p-1">
          {(['24h', '7d', '30d', 'all'] as TimeRange[]).map((range) => (
            <button
              key={range}
              onClick={() => setTimeRange(range)}
              className={cn(
                'rounded-md px-3 py-1.5 text-sm font-medium transition-colors',
                timeRange === range
                  ? 'bg-cachi-600 text-white'
                  : 'text-zinc-400 hover:text-zinc-200'
              )}
            >
              {range === 'all' ? 'All Time' : range}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-6xl space-y-6">
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
              subValue={`${chats.length} chats`}
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
              value={totalChats}
              subValue={`${bots.length} bots`}
              color="cyan"
              small
            />
          </div>

          {/* Bot Cards */}
          <section>
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
              <Bot className="h-5 w-5 text-zinc-400" />
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
            <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
              <BarChart3 className="h-5 w-5 text-zinc-400" />
              Usage Over Time
            </h2>
            <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-6">
              {stats.daily.length > 0 ? (
                <div className="space-y-4">
                  <div className="flex items-end gap-1" style={{ height: 120 }}>
                    {stats.daily.slice(-14).map((day) => {
                      const maxTokens = Math.max(...stats.daily.map((d) => d.tokens))
                      const heightPx = maxTokens > 0 ? Math.max((day.tokens / maxTokens) * 120, 5) : 5
                      return (
                        <div
                          key={day.date}
                          className="group relative h-full flex-1"
                        >
                          <div
                            className="absolute bottom-0 left-0 right-0 rounded-t bg-green-600 transition-all hover:bg-green-500"
                            style={{ height: heightPx }}
                          />
                          <div className="pointer-events-none absolute -top-8 left-1/2 z-10 -translate-x-1/2 whitespace-nowrap rounded bg-zinc-800 px-2 py-1 text-xs text-zinc-300 opacity-0 transition-opacity group-hover:opacity-100">
                            {formatNumber(day.tokens)} tokens
                          </div>
                        </div>
                      )
                    })}
                  </div>
                  <div className="flex justify-between text-xs text-zinc-600">
                    <span>{stats.daily[Math.max(0, stats.daily.length - 14)]?.date}</span>
                    <span>{stats.daily[stats.daily.length - 1]?.date}</span>
                  </div>
                </div>
              ) : (
                <div className="flex h-32 items-center justify-center text-zinc-500">
                  <div className="text-center">
                    <BarChart3 className="mx-auto mb-2 h-8 w-8 text-zinc-600" />
                    <p>No usage data yet</p>
                    <p className="text-xs text-zinc-600">Start chatting to see analytics</p>
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* Model Usage */}
          {Object.keys(stats.byModel).length > 0 && (
            <section>
              <h2 className="mb-4 flex items-center gap-2 text-lg font-semibold text-zinc-200">
                <Cpu className="h-5 w-5 text-zinc-400" />
                Model Usage
              </h2>
              <div className="rounded-xl border border-zinc-800 bg-zinc-900/50">
                <div className="divide-y divide-zinc-800">
                  {Object.entries(stats.byModel)
                    .sort((a, b) => b[1].tokens - a[1].tokens)
                    .map(([model, usage]) => (
                      <div
                        key={model}
                        className="flex items-center justify-between px-5 py-3"
                      >
                        <div>
                          <h4 className="font-medium text-zinc-200">{model}</h4>
                          <p className="text-xs text-zinc-500">{usage.messages} messages</p>
                        </div>
                        <div className="text-right">
                          <p className="font-mono text-sm text-zinc-200">
                            {formatNumber(usage.tokens)}
                          </p>
                          <p className="text-xs text-zinc-500">${usage.cost.toFixed(4)}</p>
                        </div>
                      </div>
                    ))}
                </div>
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
  const colorStyles = {
    green: 'bg-green-500/10 text-green-400',
    blue: 'bg-blue-500/10 text-blue-400',
    purple: 'bg-purple-500/10 text-purple-400',
    amber: 'bg-amber-500/10 text-amber-400',
    cyan: 'bg-cyan-500/10 text-cyan-400',
    red: 'bg-red-500/10 text-red-400',
  }

  return (
    <div
      className={cn(
        'rounded-xl border border-zinc-800 bg-zinc-900/50',
        small ? 'p-4' : 'p-5'
      )}
    >
      <div className="flex items-start justify-between">
        <div
          className={cn(
            'flex items-center justify-center rounded-lg',
            colorStyles[color],
            small ? 'h-9 w-9' : 'h-10 w-10'
          )}
        >
          <Icon className={small ? 'h-4 w-4' : 'h-5 w-5'} />
        </div>
        {trend && (
          <div
            className={cn(
              'flex items-center gap-0.5 text-xs font-medium',
              trendUp ? 'text-green-400' : 'text-red-400'
            )}
          >
            {trend}
            <ArrowUpRight
              className={cn('h-3 w-3', !trendUp && 'rotate-90')}
            />
          </div>
        )}
      </div>
      <div className={small ? 'mt-3' : 'mt-4'}>
        <h3 className="text-xs font-medium uppercase tracking-wide text-zinc-500">
          {label}
        </h3>
        <p
          className={cn(
            'font-bold text-zinc-100',
            small ? 'mt-0.5 text-xl' : 'mt-1 text-2xl'
          )}
        >
          {value}
        </p>
        {subValue && <p className="mt-0.5 text-xs text-zinc-500">{subValue}</p>}
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
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
      <div className="flex items-center gap-3">
        <div
          className="flex h-11 w-11 items-center justify-center rounded-xl"
          style={{ backgroundColor: bot.color + '20' }}
        >
          <BotIconRenderer icon={bot.icon} size={22} color={bot.color} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="truncate font-semibold text-zinc-100">{bot.name}</h3>
          <p className="truncate text-xs text-zinc-500">{bot.model}</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-3">
        <MiniStat icon={MessageSquare} value={messages} label="messages" />
        <MiniStat icon={Zap} value={formatNumber(tokens)} label="tokens" />
        <MiniStat icon={Activity} value={activeJobs} label="active jobs" />
        <MiniStat icon={Target} value={completedTasks} label="completed" />
      </div>

      <div className="mt-3 flex items-center justify-between border-t border-zinc-800 pt-3">
        <div className="flex items-center gap-3 text-xs text-zinc-500">
          <span>{chats} chats</span>
          <span className="flex items-center gap-1">
            <Plug className="h-3 w-3" />
            {connections}
          </span>
        </div>
        <div className="text-xs font-medium text-zinc-400">
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
    <div className="flex items-center gap-2">
      <Icon className="h-3.5 w-3.5 text-zinc-600" />
      <div>
        <span className="font-medium text-zinc-200">{value}</span>
        <span className="ml-1 text-xs text-zinc-600">{label}</span>
      </div>
    </div>
  )
}

function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toString()
}

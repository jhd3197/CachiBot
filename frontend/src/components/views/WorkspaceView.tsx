import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { ChevronRight, Clock } from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore, useChatStore } from '../../stores/bots'
import { useRailStore } from '../../stores/rail'
import { useUsageStore } from '../../stores/connections'
import { useApprovalsStore } from '../../stores/approvals'
import { useUIStore } from '../../stores/ui'
import { getSchedules } from '../../api/client'
import {
  getExecutions,
  getRunningExecutions,
  cancelExecution,
  type ExecutionLog,
} from '../../api/execution-log'
import { getConnections, type Connection } from '../../api/connections'
import { BotAvatar } from '../common/Avatar'
import { cn, parseApiDate } from '../../lib/utils'
import { botAccessRank } from '../../hooks/useBotAccess'
import { useAuthStore } from '../../stores/auth'
import type { Bot, Schedule } from '../../types'

/**
 * Workspace "Your bots" page (design view 01).
 *
 * Data sources (all real, no placeholders):
 * - "Needs you": pending tool approvals recorded from live `approval_needed`
 *   WS payloads (stores/approvals.ts); failed runs this week and stuck runs
 *   (running > 1h) from GET /api/bots/{id}/executions; platform connections
 *   in error state from GET /api/bots/{id}/connections.
 * - "Bots": status = approvals + running executions + the in-flight chat run
 *   (activeRun); next routine + routine count from GET /api/bots/{id}/schedules;
 *   weekly messages counted from the local chat store (the chat UI's own
 *   message history) over the last 7 days.
 * - "This week": messages from the chat store (7d); tokens/cost from the
 *   usage store's daily slice (populated by real `usage` WS payloads).
 */

const WEEK_MS = 7 * 24 * 60 * 60 * 1000
/** A run still "running" after an hour is stuck (routine timeouts default to 5 min). */
const STUCK_MS = 60 * 60 * 1000

interface BotWorkspaceData {
  /** null = the API couldn't be reached, so the figure is hidden (never faked as 0) */
  failedRuns: number | null
  running: ExecutionLog[] | null
  stuck: ExecutionLog[]
  errorConnections: Connection[] | null
  routines: number | null
  nextRoutine: { name: string; at: Date } | null
}

interface WorkspaceViewProps {
  /** In-flight chat run (botId/chatId) from the app-level WebSocket, if any */
  activeRun?: { botId: string | null; chatId: string | null } | null
}

export function WorkspaceView({ activeRun }: WorkspaceViewProps) {
  const navigate = useNavigate()
  const { bots, activeBotId } = useBotStore()
  const { chats, messages, getChatsByBot } = useChatStore()
  const { stats } = useUsageStore()
  const { pending: pendingApprovals } = useApprovalsStore()
  const { setCreateBotOpen, setSettingsSection } = useUIStore()
  const [botData, setBotData] = useState<Record<string, BotWorkspaceData | undefined>>({})
  const [dataLoaded, setDataLoaded] = useState(false)
  const [clearingRuns, setClearingRuns] = useState(false)

  // Order bots the same way the sidebar does (v1 rail order, unknown last)
  const { railOrder } = useRailStore()
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

  const botById = useMemo(() => new Map(bots.map((b) => [b.id, b])), [bots])

  // Per-bot data from existing backend APIs. A failed endpoint yields null
  // for its figures so uncomputable values are hidden rather than faked as 0.
  useEffect(() => {
    if (bots.length === 0) {
      setDataLoaded(true)
      return
    }
    let cancelled = false
    const weekAgo = new Date(Date.now() - WEEK_MS).toISOString()

    const loadBot = async (botId: string): Promise<[string, BotWorkspaceData | undefined]> => {
      try {
        // null marks "couldn't load" so empty states stay honest
        const [schedules, failed, running, connections] = await Promise.all([
          getSchedules(botId).catch(() => null as Schedule[] | null),
          getExecutions(botId, { status: 'error', fromDate: weekAgo, limit: 200 }).catch(
            () => null as ExecutionLog[] | null
          ),
          getRunningExecutions(botId).catch(() => null as ExecutionLog[] | null),
          getConnections(botId).catch(() => null as Connection[] | null),
        ])
        const now = Date.now()
        const upcoming = (schedules ?? [])
          .filter((s) => s.enabled && s.nextRunAt)
          .map((s) => ({ name: s.name, at: parseApiDate(s.nextRunAt as string) }))
          .filter((r) => r.at.getTime() > now)
          .sort((a, b) => a.at.getTime() - b.at.getTime())
        return [
          botId,
          {
            failedRuns: failed ? failed.length : null,
            running,
            stuck: (running ?? []).filter(
              (r) => now - parseApiDate(r.startedAt).getTime() > STUCK_MS
            ),
            errorConnections: connections ? connections.filter((c) => c.status === 'error') : null,
            routines: schedules ? schedules.filter((s) => s.enabled).length : null,
            nextRoutine: upcoming[0] ?? null,
          },
        ]
      } catch {
        return [botId, undefined]
      }
    }

    Promise.all(bots.map((b) => loadBot(b.id))).then((entries) => {
      if (cancelled) return
      setBotData(Object.fromEntries(entries))
      setDataLoaded(true)
    })
    return () => {
      cancelled = true
    }
  }, [bots])

  // Weekly message counts per bot from the chat store (the UI's real history)
  const weeklyMessages = useMemo(() => {
    const cutoff = Date.now() - WEEK_MS
    const counts: Record<string, number> = {}
    for (const chat of chats) {
      let count = 0
      for (const m of messages[chat.id] || []) {
        if (new Date(m.timestamp).getTime() >= cutoff) count++
      }
      if (count > 0) counts[chat.botId] = (counts[chat.botId] || 0) + count
    }
    return counts
  }, [chats, messages])

  // "This week" totals: messages from the chat store, tokens/cost from the
  // usage store's daily slice (fed by real `usage` WS payloads).
  const weekStats = useMemo(() => {
    const cutoffDate = new Date(Date.now() - 6 * 24 * 60 * 60 * 1000)
      .toISOString()
      .split('T')[0]
    const daily = stats.daily.filter((d) => d.date >= cutoffDate)
    const tokens = daily.reduce((acc, d) => acc + d.tokens, 0)
    const cost = daily.reduce((acc, d) => acc + d.cost, 0)
    const totalMessages = Object.values(weeklyMessages).reduce((a, b) => a + b, 0)
    return { messages: totalMessages, tokens, cost }
  }, [stats, weeklyMessages])

  const openBotChat = (bot: Bot) => {
    const chats = getChatsByBot(bot.id)
    const latest = chats[0]
    navigate(latest ? `/${bot.id}/chats/${latest.platform ?? latest.id}` : `/${bot.id}/chats`)
  }

  // Runs is operator+ (per the "where things moved" map): entry points and
  // run-related Needs-you items only appear when the user can operate at
  // least one bot (admins always can).
  const { user } = useAuthStore()
  const hasOperableBot = bots.some((b) => botAccessRank(b, user?.role === 'admin') >= 2)

  const openRuns = () => navigate('/runs')
  const openBotRuns = (botId: string) => navigate(`/runs?bot=${botId}`)

  const openConnections = (botId: string) => {
    setSettingsSection('connections')
    navigate(`/${botId}/settings`)
  }

  // Cancel every stuck run via the existing per-execution cancel endpoint
  const clearStuckRuns = async () => {
    const stuckEntries = orderedBots
      .map((b) => ({ bot: b, stuck: botData[b.id]?.stuck ?? [] }))
      .filter((e) => e.stuck.length > 0)
    if (stuckEntries.length === 0) return
    setClearingRuns(true)
    let cleared = 0
    let failures = 0
    for (const { stuck } of stuckEntries) {
      for (const run of stuck) {
        const botId = run.botId
        try {
          await cancelExecution(botId, run.id)
          cleared++
        } catch {
          failures++
        }
      }
    }
    setClearingRuns(false)
    if (failures === 0) {
      toast.success(cleared === 1 ? 'Run cancelled' : `${cleared} runs cancelled`)
    } else {
      toast.error(`Cancelled ${cleared}; ${failures} couldn't be cancelled`)
    }
    // Refresh per-bot data so the list reflects the cancellations
    setBotData((prev) => {
      const next = { ...prev }
      for (const { bot } of stuckEntries) {
        const d = next[bot.id]
        if (d) next[bot.id] = { ...d, running: [], stuck: [] }
      }
      return next
    })
  }

  // ── "Needs you" items (real only; section hidden when empty) ──
  const stuckTotal = orderedBots.reduce((acc, b) => acc + (botData[b.id]?.stuck.length ?? 0), 0)
  const earliestStuck = orderedBots
    .flatMap((b) => botData[b.id]?.stuck ?? [])
    .reduce<ExecutionLog | null>(
      (earliest, r) =>
        !earliest || parseApiDate(r.startedAt) < parseApiDate(earliest.startedAt) ? r : earliest,
      null
    )

  interface NeedsYouItem {
    key: string
    bot: Bot | null
    text: string
    actionLabel: string
    onAction: () => void | Promise<void>
    /** Optional: clicking the description text opens this destination (e.g. /runs) */
    onOpen?: () => void
    busy?: boolean
  }

  const needsYou: NeedsYouItem[] = []

  for (const approval of pendingApprovals) {
    // Without a bot we can't open anything meaningful for it
    if (!approval.botId) continue
    const bot = botById.get(approval.botId) ?? null
    needsYou.push({
      key: `approval-${approval.id}`,
      bot,
      text: approval.action || `${approval.tool} needs your approval`,
      actionLabel: 'Open chat',
      onAction: () =>
        navigate(approval.chatId ? `/${approval.botId}/chats/${approval.chatId}` : `/${approval.botId}/chats`),
    })
  }

  if (stuckTotal > 0 && hasOperableBot) {
    needsYou.push({
      key: 'stuck-runs',
      bot: null,
      text:
        `${stuckTotal} ${stuckTotal === 1 ? 'run has' : 'runs have'} been stuck since ` +
        formatStuckSince(earliestStuck?.startedAt),
      actionLabel: 'Clear them',
      onAction: clearStuckRuns,
      onOpen: openRuns,
      busy: clearingRuns,
    })
  }

  for (const bot of orderedBots) {
    const failed = botData[bot.id]?.failedRuns
    if (failed && hasOperableBot) {
      needsYou.push({
        key: `failed-${bot.id}`,
        bot,
        text: `${failed} ${failed === 1 ? 'run failed' : 'runs failed'} this week`,
        actionLabel: 'Open runs',
        onAction: () => openBotRuns(bot.id),
        onOpen: () => openBotRuns(bot.id),
      })
    }
  }

  for (const bot of orderedBots) {
    const errorConnections = botData[bot.id]?.errorConnections
    if (!errorConnections) continue
    for (const conn of errorConnections) {
      needsYou.push({
        key: `conn-${conn.id}`,
        bot,
        text:
          `${conn.platform} connection is in error` +
          (conn.error ? `: ${truncate(conn.error, 60)}` : ''),
        actionLabel: 'Open connections',
        onAction: () => openConnections(bot.id),
      })
    }
  }

  // Quick links target the active bot (falling back to the first bot);
  // bot-dependent pills are hidden when there is no bot at all.
  const targetBotId =
    activeBotId && bots.some((b) => b.id === activeBotId) ? activeBotId : bots[0]?.id

  return (
    <div className="workspace">
      <div className="workspace__column">
        {/* Header */}
        <header className="workspace__header">
          <h1 className="workspace__title">Your bots</h1>
          <button
            type="button"
            className="v2-btn v2-btn--primary"
            onClick={() => setCreateBotOpen(true)}
          >
            New bot
          </button>
        </header>

        {/* Needs you — hidden entirely when there's nothing real to show */}
        {needsYou.length > 0 && (
          <section className="workspace__section" aria-label="Needs you">
            <div className="workspace__section-head">
              <h2 className="workspace__section-title">Needs you</h2>
              <span className="workspace__section-count">{needsYou.length}</span>
            </div>
            <div className="workspace__needs">
              {needsYou.map((item) => (
                <div key={item.key} className="workspace__need">
                  {item.bot ? (
                    <BotAvatar color={item.bot.color} name={item.bot.name} size={32} />
                  ) : (
                    <span className="workspace__need-icon" aria-hidden="true">
                      <Clock size={16} strokeWidth={1.8} />
                    </span>
                  )}
                  <span className="workspace__need-main">
                    <span className="workspace__need-label">
                      {item.bot ? item.bot.name : 'Runs'}
                    </span>
                    {item.onOpen ? (
                      <button
                        type="button"
                        className="workspace__need-text workspace__need-text--link"
                        title="View runs"
                        onClick={() => item.onOpen?.()}
                      >
                        {item.text}
                      </button>
                    ) : (
                      <span className="workspace__need-text">{item.text}</span>
                    )}
                  </span>
                  <button
                    type="button"
                    className="v2-btn v2-btn--secondary"
                    disabled={item.busy}
                    onClick={() => void item.onAction()}
                  >
                    {item.busy ? 'Clearing…' : item.actionLabel}
                  </button>
                </div>
              ))}
            </div>
          </section>
        )}

        {/* Bots */}
        <section className="workspace__section" aria-label="Bots">
          <div className="workspace__section-head">
            <h2 className="workspace__section-title">Bots</h2>
          </div>
          {orderedBots.length === 0 ? (
            <p className="workspace__empty">No bots yet — create your first bot to get started.</p>
          ) : (
            <div className={cn('workspace__bots', !dataLoaded && 'workspace__bots--loading')}>
              {orderedBots.map((bot) => {
                const data = botData[bot.id]
                const waiting = pendingApprovals.some((a) => a.botId === bot.id)
                const hasRunning = (data?.running?.length ?? 0) > 0 || activeRun?.botId === bot.id
                // "Idle" is only claimed when the runs API answered
                const status = waiting
                  ? 'Waiting on you'
                  : hasRunning
                    ? 'Running'
                    : data?.running
                      ? 'Idle'
                      : null
                const weekly = weeklyMessages[bot.id] ?? 0
                const routineSuffix = data?.nextRoutine
                  ? ` · ${data.nextRoutine.name} at ${formatRoutineTime(data.nextRoutine.at)}`
                  : ''
                return (
                  <button
                    key={bot.id}
                    type="button"
                    className="workspace__bot-row"
                    onClick={() => openBotChat(bot)}
                  >
                    <BotAvatar color={bot.color} name={bot.name} size={44} />
                    <span className="workspace__bot-main">
                      <span className="workspace__bot-name">
                        {bot.name}
                        {bot.description && (
                          <span className="workspace__bot-desc"> · {bot.description}</span>
                        )}
                      </span>
                      <span className="workspace__bot-status">
                        {status ? status + routineSuffix : routineSuffix.replace(/^ · /, '')}
                      </span>
                    </span>
                    <span className="workspace__bot-figures">
                      <span>
                        {weekly > 0
                          ? `${weekly} ${weekly === 1 ? 'message' : 'messages'} this week`
                          : 'No messages this week'}
                      </span>
                      {data?.routines != null && (
                        <span>
                          {data.routines > 0
                            ? `${data.routines} ${data.routines === 1 ? 'routine' : 'routines'}`
                            : 'No routines'}
                        </span>
                      )}
                    </span>
                    <ChevronRight size={14} strokeWidth={1.8} className="workspace__bot-chevron" />
                  </button>
                )
              })}
            </div>
          )}
        </section>

        {/* This week */}
        <section className="workspace__section" aria-label="This week">
          <div className="workspace__section-head">
            <h2 className="workspace__section-title">This week</h2>
            <button type="button" className="workspace__link" onClick={() => navigate('/dashboard/usage')}>
              Usage details
            </button>
          </div>
          <div className="workspace__week">
            <div className="workspace__week-stat">
              <span className="workspace__week-label">Messages</span>
              <span className="workspace__week-value">{weekStats.messages}</span>
            </div>
            <div className="workspace__week-stat">
              <span className="workspace__week-label">Tokens</span>
              <span className="workspace__week-value">{formatNumber(weekStats.tokens)}</span>
            </div>
            <div className="workspace__week-stat">
              <span className="workspace__week-label">Cost</span>
              <span className="workspace__week-value">{formatCost(weekStats.cost)}</span>
            </div>
          </div>
        </section>

        {/* Quick links — routed to the existing pages */}
        <nav className="workspace__quick" aria-label="Workspace">
          {targetBotId && (
            <>
              <button
                type="button"
                className="v2-btn v2-btn--secondary"
                onClick={() => navigate(`/${targetBotId}/routines`)}
              >
                Routines
              </button>
              {hasOperableBot && (
                <button
                  type="button"
                  className="v2-btn v2-btn--secondary"
                  onClick={() => navigate('/runs')}
                >
                  Runs
                </button>
              )}
              <button
                type="button"
                className="v2-btn v2-btn--secondary"
                onClick={() => {
                  setSettingsSection('connections')
                  navigate(`/${targetBotId}/settings`)
                }}
              >
                Connections
              </button>
              <button
                type="button"
                className="v2-btn v2-btn--secondary"
                onClick={() => {
                  setSettingsSection('knowledge')
                  navigate(`/${targetBotId}/settings`)
                }}
              >
                Knowledge
              </button>
            </>
          )}
          <button
            type="button"
            className="v2-btn v2-btn--secondary"
            onClick={() => navigate('/settings')}
          >
            Settings
          </button>
        </nav>
      </div>
    </div>
  )
}

function formatStuckSince(iso: string | undefined): string {
  if (!iso) return 'earlier'
  return parseApiDate(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatRoutineTime(d: Date): string {
  return d.toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })
}

function formatCost(cost: number): string {
  return `$${cost < 1 ? cost.toFixed(4) : cost.toFixed(2)}`
}

function formatNumber(num: number): string {
  if (num >= 1_000_000) return `${(num / 1_000_000).toFixed(1)}M`
  if (num >= 1_000) return `${(num / 1_000).toFixed(1)}K`
  return num.toString()
}

function truncate(s: string, max: number): string {
  return s.length > max ? `${s.slice(0, max - 1)}…` : s
}

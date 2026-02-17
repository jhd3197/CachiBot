import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Plus,
  Search,
  Code,
  FolderKanban,
  CalendarClock,
  Loader2,
  LayoutGrid,
  Filter,
} from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { useAutomationsStore } from '../../stores/automations'
import { useUIStore, type AutomationSection } from '../../stores/ui'
import { AutomationCard } from '../automations/AutomationCard'
import {
  getScripts,
  runScript,
  activateScript,
  disableScript,
  type Script,
} from '../../api/automations'
import { getFunctions, getSchedules, runFunction, toggleSchedule } from '../../api/client'
import { cn } from '../../lib/utils'
import type { BotFunction, Schedule } from '../../types'

type UnifiedItem = {
  id: string
  name: string
  description: string
  type: 'function' | 'script' | 'schedule'
  status: string
  lastRunAt: string | null
  runCount: number
  raw: BotFunction | Script | Schedule
}

const sectionTabs: { id: AutomationSection; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { id: 'all', label: 'All', icon: LayoutGrid },
  { id: 'functions', label: 'Functions', icon: FolderKanban },
  { id: 'scripts', label: 'Scripts', icon: Code },
  { id: 'schedules', label: 'Schedules', icon: CalendarClock },
]

export function AutomationsView() {
  const navigate = useNavigate()
  const { getActiveBot, activeBotId } = useBotStore()
  const { scripts, setScripts } = useAutomationsStore()
  const { automationSection, setAutomationSection } = useUIStore()
  const activeBot = getActiveBot()

  const [functions, setFunctions] = useState<BotFunction[]>([])
  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!activeBotId) return
    let cancelled = false
    setLoading(true)

    Promise.all([
      getFunctions(activeBotId).catch(() => []),
      getScripts(activeBotId).catch(() => []),
      getSchedules(activeBotId).catch(() => []),
    ]).then(([fns, scr, sch]) => {
      if (cancelled) return
      setFunctions(fns)
      setScripts(scr)
      setSchedules(sch)
      setLoading(false)
    })

    return () => { cancelled = true }
  }, [activeBotId, setScripts])

  if (!activeBot || !activeBotId) return null

  // Unify items
  const items: UnifiedItem[] = []

  if (automationSection === 'all' || automationSection === 'functions') {
    for (const fn of functions) {
      items.push({
        id: fn.id,
        name: fn.name,
        description: fn.description || '',
        type: 'function',
        status: 'active',
        lastRunAt: fn.lastRunAt || null,
        runCount: fn.runCount || 0,
        raw: fn,
      })
    }
  }

  if (automationSection === 'all' || automationSection === 'scripts') {
    for (const sc of scripts) {
      items.push({
        id: sc.id,
        name: sc.name,
        description: sc.description,
        type: 'script',
        status: sc.status,
        lastRunAt: sc.lastRunAt,
        runCount: sc.runCount,
        raw: sc,
      })
    }
  }

  if (automationSection === 'all' || automationSection === 'schedules') {
    for (const sch of schedules) {
      items.push({
        id: sch.id,
        name: sch.name,
        description: sch.description || '',
        type: 'schedule',
        status: sch.enabled ? 'enabled' : 'disabled',
        lastRunAt: sch.lastRunAt || null,
        runCount: sch.totalRuns || 0,
        raw: sch,
      })
    }
  }

  // Filter
  const filtered = search
    ? items.filter(
        (it) =>
          it.name.toLowerCase().includes(search.toLowerCase()) ||
          it.description.toLowerCase().includes(search.toLowerCase())
      )
    : items

  const handleRun = async (item: UnifiedItem) => {
    try {
      if (item.type === 'function') {
        await runFunction(activeBotId, item.id)
        toast.success(`Function "${item.name}" started`)
      } else if (item.type === 'script') {
        await runScript(activeBotId, item.id)
        toast.success(`Script "${item.name}" started`)
      }
    } catch (err) {
      toast.error(`Failed to run: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleToggle = async (item: UnifiedItem) => {
    try {
      if (item.type === 'script') {
        if (item.status === 'disabled') {
          const updated = await activateScript(activeBotId, item.id)
          useAutomationsStore.getState().updateScript(item.id, updated)
        } else {
          const updated = await disableScript(activeBotId, item.id)
          useAutomationsStore.getState().updateScript(item.id, updated)
        }
      } else if (item.type === 'schedule') {
        const updated = await toggleSchedule(activeBotId, item.id)
        setSchedules((prev) => prev.map((s) => (s.id === item.id ? updated : s)))
      }
    } catch (err) {
      toast.error(`Failed to toggle: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleClick = (item: UnifiedItem) => {
    if (item.type === 'script') {
      navigate(`/${activeBotId}/automations/${item.id}/edit`)
    } else if (item.type === 'function') {
      navigate(`/${activeBotId}/work`)
    } else if (item.type === 'schedule') {
      navigate(`/${activeBotId}/schedules`)
    }
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-200 px-6 py-4 dark:border-zinc-800">
        <div>
          <h1 className="text-lg font-semibold text-zinc-900 dark:text-zinc-100">Automations</h1>
          <p className="text-xs text-zinc-500">
            Functions, scripts, and schedules for {activeBot.name}
          </p>
        </div>
        <button
          onClick={() => navigate(`/${activeBotId}/automations/new`)}
          className="flex items-center gap-2 rounded-lg bg-accent-600 px-3 py-2 text-sm font-medium text-white hover:bg-accent-700"
        >
          <Plus className="h-4 w-4" />
          New Script
        </button>
      </div>

      {/* Section tabs + search */}
      <div className="flex items-center gap-4 border-b border-zinc-200 px-6 py-2 dark:border-zinc-800">
        <div className="flex items-center gap-1">
          {sectionTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setAutomationSection(tab.id)}
              className={cn(
                'flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium transition-colors',
                automationSection === tab.id
                  ? 'bg-accent-600/10 text-accent-600 dark:text-accent-400'
                  : 'text-zinc-500 hover:bg-zinc-100 hover:text-zinc-700 dark:hover:bg-zinc-800 dark:hover:text-zinc-300'
              )}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-zinc-400" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-8 w-48 rounded-lg border border-zinc-200 bg-white pl-8 pr-3 text-xs text-zinc-900 placeholder-zinc-400 focus:border-accent-500 focus:outline-none focus:ring-1 focus:ring-accent-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-zinc-400" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-zinc-400">
            <Code className="mb-3 h-10 w-10" />
            <p className="text-sm font-medium">No automations found</p>
            <p className="mt-1 text-xs">Create a script or function to get started</p>
          </div>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {filtered.map((item) => (
              <AutomationCard
                key={`${item.type}-${item.id}`}
                id={item.id}
                name={item.name}
                description={item.description}
                type={item.type}
                status={item.status}
                lastRunAt={item.lastRunAt}
                runCount={item.runCount}
                onClick={() => handleClick(item)}
                onRun={item.type !== 'schedule' ? () => handleRun(item) : undefined}
                onToggle={item.type !== 'function' ? () => handleToggle(item) : undefined}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

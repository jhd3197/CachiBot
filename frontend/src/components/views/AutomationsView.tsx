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
        runCount: sch.runCount || 0,
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
    <div className="automations-view">
      {/* Header */}
      <div className="automations-view__header">
        <div>
          <h1 className="automations-view__title">Automations</h1>
          <p className="automations-view__subtitle">
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
      <div className="automations-view__toolbar">
        <div className="flex items-center gap-1">
          {sectionTabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setAutomationSection(tab.id)}
              className={cn(
                'automation-tab',
                automationSection === tab.id && 'automation-tab--active'
              )}
            >
              <tab.icon className="h-3.5 w-3.5" />
              {tab.label}
            </button>
          ))}
        </div>

        <div className="ml-auto flex items-center gap-2">
          <div className="relative">
            <Search className="absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-[var(--color-text-secondary)]" />
            <input
              type="text"
              placeholder="Search..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="automation-search__input"
            />
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="automations-view__content">
        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-5 w-5 animate-spin text-[var(--color-text-secondary)]" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="automations-view__empty">
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

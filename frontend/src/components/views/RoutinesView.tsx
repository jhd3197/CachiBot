import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Plus, Search } from 'lucide-react'
import { toast } from 'sonner'
import { useBotStore } from '../../stores/bots'
import { useAutomationsStore } from '../../stores/automations'
import { useUIStore } from '../../stores/ui'
import { useBotAccess } from '../../hooks/useBotAccess'
import { PageLoading } from '../common/PageLoading'
import { AutomationCard } from '../automations/AutomationCard'
import {
  getScripts,
  runScript,
  activateScript,
  disableScript,
  type Script,
} from '../../api/automations'
import {
  getFunctions,
  getSchedules,
  runFunction,
  toggleSchedule,
} from '../../api/client'
import { describeSchedule, formatLastRun } from '../../lib/schedules'
import { cn } from '../../lib/utils'
import type { BotFunction, Schedule } from '../../types'

export function RoutinesView() {
  const navigate = useNavigate()
  const { getActiveBot, activeBotId } = useBotStore()
  const { scripts, setScripts } = useAutomationsStore()
  const { automationSection, setAutomationSection } = useUIStore()
  const { canOperate, canEdit } = useBotAccess(activeBotId)
  const activeBot = getActiveBot()

  const [schedules, setSchedules] = useState<Schedule[]>([])
  const [functions, setFunctions] = useState<BotFunction[]>([])
  const [search, setSearch] = useState('')
  const [loading, setLoading] = useState(true)

  const showAdvanced = automationSection === 'advanced'

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

    return () => {
      cancelled = true
    }
  }, [activeBotId, setScripts])

  if (!activeBot || !activeBotId) return null

  const q = search.trim().toLowerCase()
  const filteredSchedules = q
    ? schedules.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          (s.description ?? '').toLowerCase().includes(q)
      )
    : schedules
  const filteredScripts = q
    ? scripts.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q)
      )
    : scripts
  const filteredFunctions = q
    ? functions.filter(
        (f) =>
          f.name.toLowerCase().includes(q) ||
          (f.description ?? '').toLowerCase().includes(q)
      )
    : functions

  const handleToggleSchedule = async (schedule: Schedule) => {
    try {
      const updated = await toggleSchedule(activeBotId, schedule.id)
      setSchedules((prev) => prev.map((s) => (s.id === updated.id ? updated : s)))
    } catch (err) {
      toast.error(`Failed to toggle: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleRunScript = async (script: Script) => {
    try {
      await runScript(activeBotId, script.id)
      toast.success(`Script "${script.name}" started`)
    } catch (err) {
      toast.error(`Failed to run: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleToggleScript = async (script: Script) => {
    try {
      if (script.status === 'disabled') {
        const updated = await activateScript(activeBotId, script.id)
        useAutomationsStore.getState().updateScript(script.id, updated)
      } else {
        const updated = await disableScript(activeBotId, script.id)
        useAutomationsStore.getState().updateScript(script.id, updated)
      }
    } catch (err) {
      toast.error(`Failed to toggle: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  const handleRunFunction = async (fn: BotFunction) => {
    try {
      await runFunction(activeBotId, fn.id)
      toast.success(`Function "${fn.name}" started`)
    } catch (err) {
      toast.error(`Failed to run: ${err instanceof Error ? err.message : 'Unknown error'}`)
    }
  }

  return (
    <div className="routines">
      <div className="routines__column">
        {/* Header */}
        <div className="routines__header">
          <div>
            <h1 className="routines__title">Routines</h1>
            <p className="routines__subtitle">
              Things {activeBot.name} does on its own
            </p>
          </div>
          {canEdit && (
            <button
              onClick={() => navigate(`/${activeBotId}/routines/new`)}
              className="routines__new-btn"
            >
              <Plus className="h-4 w-4" />
              New routine
            </button>
          )}
        </div>

        {/* Routines / Advanced tabs + See runs */}
        <div className="routines__tabs-row">
          <div className="routines__tabs">
            <button
              onClick={() => setAutomationSection('routines')}
              className={cn('routines__tab', !showAdvanced && 'routines__tab--active')}
            >
              Routines
            </button>
            <button
              onClick={() => setAutomationSection('advanced')}
              className={cn('routines__tab', showAdvanced && 'routines__tab--active')}
            >
              Advanced
            </button>
          </div>
          <button
            className="routines__runs-link"
            onClick={() => navigate(`/runs?bot=${activeBotId}`)}
          >
            See runs
          </button>
        </div>

        {/* Search */}
        <div className="routines__search">
          <Search className="routines__search-icon" />
          <input
            type="text"
            placeholder="Search..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="routines__search-input"
          />
        </div>

        {/* Content */}
        {loading ? (
          <PageLoading pending={loading} label="Loading routines..." />
        ) : !showAdvanced ? (
          filteredSchedules.length === 0 ? (
            <div className="routines__empty">
              <p className="routines__empty-title">
                {q ? 'No routines match your search' : 'No routines yet'}
              </p>
              {!q && (
                <p className="routines__empty-sub">
                  {canEdit
                    ? `Create one and ${activeBot.name} does it on its own, on schedule.`
                    : 'Routines will appear here once an editor creates one.'}
                </p>
              )}
            </div>
          ) : (
            <div className="routines__list">
              {filteredSchedules.map((schedule) => {
                const lastRun = formatLastRun(schedule.lastRunAt)
                return (
                  <div key={schedule.id} className="routines__row">
                    <button
                      type="button"
                      className="routines__row-main"
                      onClick={() => navigate(`/${activeBotId}/routines/${schedule.id}`)}
                    >
                      <span className="routines__row-name">{schedule.name}</span>
                      <span className="routines__row-summary">{describeSchedule(schedule)}</span>
                    </button>
                    {lastRun && <span className="routines__row-lastrun">Last run {lastRun}</span>}
                    {canOperate && (
                      <button
                        type="button"
                        role="switch"
                        aria-checked={schedule.enabled}
                        aria-label={schedule.enabled ? 'Disable routine' : 'Enable routine'}
                        className="routines__switch"
                        onClick={() => handleToggleSchedule(schedule)}
                      >
                        <span className="routines__switch-knob" />
                      </button>
                    )}
                  </div>
                )
              })}
            </div>
          )
        ) : (
          <div className="routines__advanced">
            {filteredScripts.length > 0 && (
              <section className="routines__advanced-section">
                <h2 className="routines__advanced-title">Scripts</h2>
                <div className="routines__grid">
                  {filteredScripts.map((script) => (
                    <AutomationCard
                      key={`script-${script.id}`}
                      id={script.id}
                      name={script.name}
                      description={script.description}
                      type="script"
                      status={script.status}
                      lastRunAt={script.lastRunAt}
                      runCount={script.runCount}
                      onClick={() => navigate(`/${activeBotId}/automations/${script.id}/edit`)}
                      onRun={canOperate ? () => handleRunScript(script) : undefined}
                      onToggle={canOperate ? () => handleToggleScript(script) : undefined}
                    />
                  ))}
                </div>
              </section>
            )}

            {filteredFunctions.length > 0 && (
              <section className="routines__advanced-section">
                <h2 className="routines__advanced-title">Functions</h2>
                <div className="routines__grid">
                  {filteredFunctions.map((fn) => (
                    <AutomationCard
                      key={`function-${fn.id}`}
                      id={fn.id}
                      name={fn.name}
                      description={fn.description || ''}
                      type="function"
                      status="active"
                      lastRunAt={fn.lastRunAt || null}
                      runCount={fn.runCount || 0}
                      onClick={() => navigate(`/${activeBotId}/work`)}
                      onRun={canOperate ? () => handleRunFunction(fn) : undefined}
                    />
                  ))}
                </div>
              </section>
            )}

            {filteredScripts.length === 0 && filteredFunctions.length === 0 && (
              <div className="routines__empty">
                <p className="routines__empty-title">
                  {q ? 'Nothing matches your search' : 'No scripts or functions'}
                </p>
                {!q && (
                  <p className="routines__empty-sub">
                    Scripts and functions are advanced building blocks managed from the API.
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

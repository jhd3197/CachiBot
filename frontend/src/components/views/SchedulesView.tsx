import { useState } from 'react'
import {
  Calendar,
  Timer,
  Clock,
  Zap,
  ToggleLeft,
  ToggleRight,
  Search,
  Plus,
  AlertCircle,
  Trash2,
} from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useBotStore, useScheduleStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { cn } from '../../lib/utils'
import type { Schedule, ScheduleType } from '../../types'

export function SchedulesView() {
  const { getActiveBot } = useBotStore()
  const { scheduleSection } = useUIStore()

  const activeBot = getActiveBot()
  if (!activeBot) return null

  return (
    <div className="flex h-full flex-col bg-zinc-950">
      {scheduleSection === 'all' && <ScheduleListSection botId={activeBot.id} filter="all" />}
      {scheduleSection === 'enabled' && <ScheduleListSection botId={activeBot.id} filter="enabled" />}
      {scheduleSection === 'disabled' && <ScheduleListSection botId={activeBot.id} filter="disabled" />}
      {scheduleSection === 'create' && <CreateScheduleSection botId={activeBot.id} />}
    </div>
  )
}

// =============================================================================
// SCHEDULE LIST SECTION
// =============================================================================

function ScheduleListSection({ botId, filter }: { botId: string; filter: 'all' | 'enabled' | 'disabled' }) {
  const navigate = useNavigate()
  const { getSchedulesByBot, activeScheduleId, setActiveSchedule, toggleEnabled } = useScheduleStore()
  const [search, setSearch] = useState('')

  const allSchedules = getSchedulesByBot(botId)
  const filteredSchedules = allSchedules.filter((schedule) => {
    // Apply filter
    if (filter === 'enabled' && !schedule.enabled) return false
    if (filter === 'disabled' && schedule.enabled) return false

    // Apply search
    if (search && !schedule.name.toLowerCase().includes(search.toLowerCase())) return false
    return true
  })

  const selectedSchedule = filteredSchedules.find((s) => s.id === activeScheduleId)

  const stats = {
    total: allSchedules.length,
    enabled: allSchedules.filter((s) => s.enabled).length,
    disabled: allSchedules.filter((s) => !s.enabled).length,
  }

  const titles: Record<string, string> = {
    all: 'All Schedules',
    enabled: 'Enabled Schedules',
    disabled: 'Disabled Schedules',
  }

  const descriptions: Record<string, string> = {
    all: 'Manage automated triggers and scheduled tasks',
    enabled: 'Schedules that are currently active',
    disabled: 'Schedules that are paused or inactive',
  }

  const handleScheduleClick = (schedule: Schedule) => {
    setActiveSchedule(schedule.id)
    navigate(`/${botId}/schedules/${schedule.id}`)
  }

  return (
    <div className="flex h-full flex-col">
      {/* Header */}
      <div className="border-b border-zinc-800 px-6 py-4">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold text-zinc-100">{titles[filter]}</h1>
            <p className="text-sm text-zinc-500">{descriptions[filter]}</p>
          </div>

          {/* Stats */}
          {filter === 'all' && (
            <div className="flex items-center gap-4">
              <Stat label="Total" value={stats.total} color="zinc" />
              <Stat label="Enabled" value={stats.enabled} color="green" />
              <Stat label="Disabled" value={stats.disabled} color="zinc" />
            </div>
          )}
        </div>
      </div>

      {/* Search */}
      <div className="border-b border-zinc-800 px-6 py-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
          <input
            type="text"
            placeholder="Search schedules..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800/50 pl-10 pr-4 text-sm text-zinc-100 placeholder-zinc-500 outline-none focus:border-purple-500"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Schedule list */}
        <div className="w-96 flex-shrink-0 overflow-y-auto border-r border-zinc-800 p-4">
          {filteredSchedules.length === 0 ? (
            <div className="py-12 text-center">
              <AlertCircle className="mx-auto mb-3 h-8 w-8 text-zinc-600" />
              <p className="text-sm text-zinc-500">
                {search ? 'No schedules match your search' : 'No schedules yet'}
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {filteredSchedules.map((schedule) => (
                <ScheduleCard
                  key={schedule.id}
                  schedule={schedule}
                  selected={activeScheduleId === schedule.id}
                  onClick={() => handleScheduleClick(schedule)}
                  onToggle={() => toggleEnabled(schedule.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Schedule details */}
        <div className="flex-1 overflow-y-auto">
          {selectedSchedule ? (
            <ScheduleDetails schedule={selectedSchedule} />
          ) : (
            <div className="flex h-full items-center justify-center">
              <p className="text-zinc-500">Select a schedule to view details</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// CREATE SCHEDULE SECTION
// =============================================================================

function CreateScheduleSection({ botId: _botId }: { botId: string }) {
  const { setScheduleSection } = useUIStore()
  const [formData, setFormData] = useState({
    name: '',
    description: '',
    scheduleType: 'interval' as ScheduleType,
    cronExpression: '',
    intervalSeconds: 3600,
    runAt: '',
    eventTrigger: '',
    enabled: true,
  })

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    // TODO: Implement create schedule API call
    console.log('Create schedule:', formData)
    setScheduleSection('all')
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-zinc-800 px-6 py-4">
        <h1 className="text-xl font-bold text-zinc-100">Create Schedule</h1>
        <p className="text-sm text-zinc-500">Set up a new automated trigger</p>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <form onSubmit={handleSubmit} className="mx-auto max-w-2xl space-y-6">
          {/* Name */}
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Daily Report"
              className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-purple-500"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="What does this schedule do?"
              rows={2}
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-zinc-100 outline-none focus:border-purple-500"
            />
          </div>

          {/* Schedule Type */}
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">Schedule Type</label>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {(['cron', 'interval', 'once', 'event'] as ScheduleType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setFormData({ ...formData, scheduleType: type })}
                  className={cn(
                    'flex flex-col items-center gap-2 rounded-lg border p-4 transition-all',
                    formData.scheduleType === type
                      ? 'border-purple-500 bg-purple-500/10'
                      : 'border-zinc-700 bg-zinc-800/50 hover:border-zinc-600'
                  )}
                >
                  {type === 'cron' && <Calendar className="h-5 w-5 text-purple-400" />}
                  {type === 'interval' && <Timer className="h-5 w-5 text-blue-400" />}
                  {type === 'once' && <Clock className="h-5 w-5 text-orange-400" />}
                  {type === 'event' && <Zap className="h-5 w-5 text-yellow-400" />}
                  <span className="text-sm capitalize text-zinc-300">{type}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Type-specific fields */}
          {formData.scheduleType === 'cron' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-300">Cron Expression</label>
              <input
                type="text"
                value={formData.cronExpression}
                onChange={(e) => setFormData({ ...formData, cronExpression: e.target.value })}
                placeholder="0 2 * * *"
                className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 font-mono text-zinc-100 outline-none focus:border-purple-500"
              />
              <p className="mt-1 text-xs text-zinc-500">
                Format: minute hour day month weekday (e.g., "0 2 * * *" = 2am daily)
              </p>
            </div>
          )}

          {formData.scheduleType === 'interval' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-300">Interval</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={formData.intervalSeconds / 60}
                  onChange={(e) => setFormData({ ...formData, intervalSeconds: parseInt(e.target.value) * 60 })}
                  min={1}
                  className="h-10 w-24 rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-purple-500"
                />
                <span className="text-zinc-400">minutes</span>
              </div>
            </div>
          )}

          {formData.scheduleType === 'once' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-300">Run At</label>
              <input
                type="datetime-local"
                value={formData.runAt}
                onChange={(e) => setFormData({ ...formData, runAt: e.target.value })}
                className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-purple-500"
              />
            </div>
          )}

          {formData.scheduleType === 'event' && (
            <div>
              <label className="mb-2 block text-sm font-medium text-zinc-300">Event Trigger</label>
              <input
                type="text"
                value={formData.eventTrigger}
                onChange={(e) => setFormData({ ...formData, eventTrigger: e.target.value })}
                placeholder="webhook_received"
                className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-purple-500"
              />
            </div>
          )}

          {/* Enabled toggle */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-700 bg-zinc-800/50 p-4">
            <div>
              <div className="font-medium text-zinc-200">Enable immediately</div>
              <div className="text-sm text-zinc-500">Start running this schedule right away</div>
            </div>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
              className={formData.enabled ? 'text-purple-400' : 'text-zinc-600'}
            >
              {formData.enabled ? <ToggleRight className="h-8 w-8" /> : <ToggleLeft className="h-8 w-8" />}
            </button>
          </div>

          {/* Submit */}
          <div className="flex justify-end gap-3 pt-4">
            <button
              type="button"
              onClick={() => setScheduleSection('all')}
              className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="flex items-center gap-2 rounded-lg bg-purple-600 px-4 py-2 text-sm font-medium text-white hover:bg-purple-500"
            >
              <Plus className="h-4 w-4" />
              Create Schedule
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// =============================================================================
// COMPONENTS
// =============================================================================

function Stat({
  label,
  value,
  color,
}: {
  label: string
  value: number
  color: 'green' | 'zinc'
}) {
  const colors = {
    green: 'bg-green-500/20 text-green-400',
    zinc: 'bg-zinc-700 text-zinc-400',
  }

  return (
    <div className="flex items-center gap-2">
      <div className={cn('flex h-8 min-w-[2rem] items-center justify-center rounded-lg px-2 text-sm font-bold', colors[color])}>
        {value}
      </div>
      <span className="text-xs text-zinc-500">{label}</span>
    </div>
  )
}

function ScheduleCard({
  schedule,
  selected,
  onClick,
  onToggle,
}: {
  schedule: Schedule
  selected?: boolean
  onClick?: () => void
  onToggle?: () => void
}) {
  const getScheduleTypeIcon = (type: ScheduleType) => {
    switch (type) {
      case 'cron': return <Calendar className="h-4 w-4 text-purple-400" />
      case 'interval': return <Timer className="h-4 w-4 text-blue-400" />
      case 'once': return <Clock className="h-4 w-4 text-orange-400" />
      case 'event': return <Zap className="h-4 w-4 text-yellow-400" />
    }
  }

  const formatSchedule = (s: Schedule) => {
    switch (s.scheduleType) {
      case 'cron':
        return s.cronExpression || 'No cron set'
      case 'interval':
        if (!s.intervalSeconds) return 'No interval set'
        if (s.intervalSeconds < 60) return `Every ${s.intervalSeconds}s`
        if (s.intervalSeconds < 3600) return `Every ${Math.floor(s.intervalSeconds / 60)}m`
        if (s.intervalSeconds < 86400) return `Every ${Math.floor(s.intervalSeconds / 3600)}h`
        return `Every ${Math.floor(s.intervalSeconds / 86400)}d`
      case 'once':
        if (!s.runAt) return 'Not scheduled'
        return new Date(s.runAt).toLocaleDateString()
      case 'event':
        return s.eventTrigger || 'No event set'
    }
  }

  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full rounded-xl border p-4 text-left transition-all',
        selected && 'ring-1 ring-purple-500',
        schedule.enabled
          ? 'border-purple-500/30 bg-purple-500/5'
          : 'border-zinc-700 bg-zinc-800/30 opacity-60'
      )}
    >
      <div className="flex items-start gap-3">
        {getScheduleTypeIcon(schedule.scheduleType)}
        <div className="min-w-0 flex-1">
          <span className="font-medium text-zinc-200">{schedule.name}</span>
          {schedule.description && (
            <p className="mt-0.5 truncate text-sm text-zinc-500">{schedule.description}</p>
          )}

          {/* Schedule info */}
          <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">
            <span className="rounded bg-zinc-700/50 px-1.5 py-0.5 font-mono">
              {formatSchedule(schedule)}
            </span>
          </div>

          {/* Run stats */}
          {schedule.runCount > 0 && (
            <div className="mt-2 flex items-center gap-2 text-xs text-zinc-500">
              <span>{schedule.runCount} runs</span>
            </div>
          )}
        </div>

        {/* Toggle button */}
        <button
          onClick={(e) => {
            e.stopPropagation()
            onToggle?.()
          }}
          className={cn(
            'flex-shrink-0 transition-colors',
            schedule.enabled ? 'text-purple-400' : 'text-zinc-600'
          )}
          title={schedule.enabled ? 'Disable' : 'Enable'}
        >
          {schedule.enabled ? <ToggleRight className="h-6 w-6" /> : <ToggleLeft className="h-6 w-6" />}
        </button>
      </div>
    </button>
  )
}

function ScheduleDetails({ schedule }: { schedule: Schedule }) {
  const formatTime = (isoString?: string) => {
    if (!isoString) return '-'
    return new Date(isoString).toLocaleString()
  }

  const getScheduleTypeLabel = (type: ScheduleType) => {
    switch (type) {
      case 'cron': return 'Cron Schedule'
      case 'interval': return 'Interval Timer'
      case 'once': return 'One-Time'
      case 'event': return 'Event Trigger'
    }
  }

  return (
    <div className="p-6">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-xl font-bold text-zinc-100">{schedule.name}</h2>
            <span
              className={cn(
                'rounded-full px-2 py-0.5 text-xs font-medium',
                schedule.enabled ? 'bg-green-500/20 text-green-400' : 'bg-zinc-700 text-zinc-400'
              )}
            >
              {schedule.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          {schedule.description && <p className="mt-1 text-zinc-400">{schedule.description}</p>}
        </div>
        <button className="flex items-center gap-2 rounded-lg bg-red-600/20 px-3 py-2 text-sm text-red-400 hover:bg-red-600/30">
          <Trash2 className="h-4 w-4" />
          Delete
        </button>
      </div>

      {/* Info grid */}
      <div className="mb-6 grid grid-cols-2 gap-4 lg:grid-cols-4">
        <InfoCard label="Type" value={getScheduleTypeLabel(schedule.scheduleType)} />
        <InfoCard label="Timezone" value={schedule.timezone} />
        <InfoCard label="Run Count" value={String(schedule.runCount)} />
        <InfoCard label="Max Concurrent" value={String(schedule.maxConcurrent)} />
      </div>

      {/* Schedule expression */}
      <div className="mb-6 rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
        <div className="text-xs font-medium uppercase text-zinc-500">Schedule</div>
        <div className="mt-2 font-mono text-lg text-zinc-200">
          {schedule.scheduleType === 'cron' && schedule.cronExpression}
          {schedule.scheduleType === 'interval' && `Every ${schedule.intervalSeconds} seconds`}
          {schedule.scheduleType === 'once' && formatTime(schedule.runAt)}
          {schedule.scheduleType === 'event' && schedule.eventTrigger}
        </div>
      </div>

      {/* Timing info */}
      <div className="grid grid-cols-2 gap-4">
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="text-xs font-medium uppercase text-zinc-500">Next Run</div>
          <div className="mt-2 text-zinc-200">
            {schedule.nextRunAt ? formatTime(schedule.nextRunAt) : 'Not scheduled'}
          </div>
        </div>
        <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-4">
          <div className="text-xs font-medium uppercase text-zinc-500">Last Run</div>
          <div className="mt-2 text-zinc-200">
            {schedule.lastRunAt ? formatTime(schedule.lastRunAt) : 'Never'}
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3">
      <div className="text-xs text-zinc-500">{label}</div>
      <div className="mt-1 font-medium text-zinc-200">{value}</div>
    </div>
  )
}

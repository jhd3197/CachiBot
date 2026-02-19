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
    <div className="schedules-view">
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
      <div className="schedule-header">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="schedule-header__title">{titles[filter]}</h1>
            <p className="schedule-header__subtitle">{descriptions[filter]}</p>
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
      <div className="schedule-search">
        <div className="relative">
          <Search className="schedule-search__icon" />
          <input
            type="text"
            placeholder="Search schedules..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="schedule-search__input"
          />
        </div>
      </div>

      {/* Content */}
      <div className="flex flex-1 overflow-hidden">
        {/* Schedule list */}
        <div className="schedule-list">
          {filteredSchedules.length === 0 ? (
            <div className="schedule-empty">
              <AlertCircle className="schedule-empty__icon" />
              <p className="schedule-empty__text">
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
            <div className="schedule-placeholder">
              <p>Select a schedule to view details</p>
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

// eslint-disable-next-line @typescript-eslint/no-unused-vars
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
      <div className="schedule-header">
        <div>
          <h1 className="schedule-header__title">Create Schedule</h1>
          <p className="schedule-header__subtitle">Set up a new automated trigger</p>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-6">
        <form onSubmit={handleSubmit} className="schedule-form space-y-6">
          {/* Name */}
          <div>
            <label className="schedule-form__label">Name</label>
            <input
              type="text"
              value={formData.name}
              onChange={(e) => setFormData({ ...formData, name: e.target.value })}
              placeholder="Daily Report"
              className="schedule-form__input"
              required
            />
          </div>

          {/* Description */}
          <div>
            <label className="schedule-form__label">Description</label>
            <textarea
              value={formData.description}
              onChange={(e) => setFormData({ ...formData, description: e.target.value })}
              placeholder="What does this schedule do?"
              rows={2}
              className="schedule-form__textarea"
            />
          </div>

          {/* Schedule Type */}
          <div>
            <label className="schedule-form__label">Schedule Type</label>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
              {(['cron', 'interval', 'once', 'event'] as ScheduleType[]).map((type) => (
                <button
                  key={type}
                  type="button"
                  onClick={() => setFormData({ ...formData, scheduleType: type })}
                  className={cn(
                    'schedule-type-btn',
                    formData.scheduleType === type
                      ? 'schedule-type-btn--active'
                      : 'schedule-type-btn--inactive'
                  )}
                >
                  {type === 'cron' && <Calendar className="h-5 w-5 text-purple-400" />}
                  {type === 'interval' && <Timer className="h-5 w-5 text-blue-400" />}
                  {type === 'once' && <Clock className="h-5 w-5 text-orange-400" />}
                  {type === 'event' && <Zap className="h-5 w-5 text-yellow-400" />}
                  <span className="schedule-type-btn__label">{type}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Type-specific fields */}
          {formData.scheduleType === 'cron' && (
            <div>
              <label className="schedule-form__label">Cron Expression</label>
              <input
                type="text"
                value={formData.cronExpression}
                onChange={(e) => setFormData({ ...formData, cronExpression: e.target.value })}
                placeholder="0 2 * * *"
                className="schedule-form__input font-mono"
              />
              <p className="schedule-form__hint">
                Format: minute hour day month weekday (e.g., "0 2 * * *" = 2am daily)
              </p>
            </div>
          )}

          {formData.scheduleType === 'interval' && (
            <div>
              <label className="schedule-form__label">Interval</label>
              <div className="flex items-center gap-3">
                <input
                  type="number"
                  value={formData.intervalSeconds / 60}
                  onChange={(e) => setFormData({ ...formData, intervalSeconds: parseInt(e.target.value) * 60 })}
                  min={1}
                  className="schedule-form__input w-24"
                />
                <span className="schedule-form__unit">minutes</span>
              </div>
            </div>
          )}

          {formData.scheduleType === 'once' && (
            <div>
              <label className="schedule-form__label">Run At</label>
              <input
                type="datetime-local"
                value={formData.runAt}
                onChange={(e) => setFormData({ ...formData, runAt: e.target.value })}
                className="schedule-form__input"
              />
            </div>
          )}

          {formData.scheduleType === 'event' && (
            <div>
              <label className="schedule-form__label">Event Trigger</label>
              <input
                type="text"
                value={formData.eventTrigger}
                onChange={(e) => setFormData({ ...formData, eventTrigger: e.target.value })}
                placeholder="webhook_received"
                className="schedule-form__input"
              />
            </div>
          )}

          {/* Enabled toggle */}
          <div className="schedule-toggle-row">
            <div>
              <div className="schedule-toggle-row__title">Enable immediately</div>
              <div className="schedule-toggle-row__subtitle">Start running this schedule right away</div>
            </div>
            <button
              type="button"
              onClick={() => setFormData({ ...formData, enabled: !formData.enabled })}
              className={cn(
                'schedule-card__toggle',
                formData.enabled ? 'schedule-card__toggle--on' : 'schedule-card__toggle--off'
              )}
            >
              {formData.enabled ? <ToggleRight className="h-8 w-8" /> : <ToggleLeft className="h-8 w-8" />}
            </button>
          </div>

          {/* Submit */}
          <div className="schedule-form-actions">
            <button
              type="button"
              onClick={() => setScheduleSection('all')}
              className="schedule-btn-cancel"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="schedule-btn-create"
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
  return (
    <div className="flex items-center gap-2">
      <div className={cn(
        'schedule-stat__value',
        color === 'green' ? 'schedule-stat__value--green' : 'schedule-stat__value--zinc'
      )}>
        {value}
      </div>
      <span className="schedule-stat__label">{label}</span>
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
        'schedule-card',
        schedule.enabled ? 'schedule-card--enabled' : 'schedule-card--disabled',
        selected && 'schedule-card--selected'
      )}
    >
      <div className="flex items-start gap-3">
        {getScheduleTypeIcon(schedule.scheduleType)}
        <div className="min-w-0 flex-1">
          <span className="schedule-card__name">{schedule.name}</span>
          {schedule.description && (
            <p className="schedule-card__description">{schedule.description}</p>
          )}

          {/* Schedule info */}
          <div className="mt-2 flex items-center gap-2 text-xs">
            <span className="schedule-card__expression">
              {formatSchedule(schedule)}
            </span>
          </div>

          {/* Run stats */}
          {schedule.runCount > 0 && (
            <div className="mt-2">
              <span className="schedule-card__runs">{schedule.runCount} runs</span>
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
            'schedule-card__toggle',
            schedule.enabled ? 'schedule-card__toggle--on' : 'schedule-card__toggle--off'
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
    <div className="schedule-details">
      {/* Header */}
      <div className="mb-6 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="schedule-details__title">{schedule.name}</h2>
            <span className={cn(
              'schedule-badge',
              schedule.enabled ? 'schedule-badge--enabled' : 'schedule-badge--disabled'
            )}>
              {schedule.enabled ? 'Enabled' : 'Disabled'}
            </span>
          </div>
          {schedule.description && <p className="schedule-details__description">{schedule.description}</p>}
        </div>
        <button className="schedule-details__delete-btn">
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
      <div className="schedule-info-card mb-6" style={{ padding: '1rem' }}>
        <div className="schedule-info-card__label schedule-info-card__label--uppercase">Schedule</div>
        <div className="schedule-info-card__value schedule-info-card__value--mono">
          {schedule.scheduleType === 'cron' && schedule.cronExpression}
          {schedule.scheduleType === 'interval' && `Every ${schedule.intervalSeconds} seconds`}
          {schedule.scheduleType === 'once' && formatTime(schedule.runAt)}
          {schedule.scheduleType === 'event' && schedule.eventTrigger}
        </div>
      </div>

      {/* Timing info */}
      <div className="grid grid-cols-2 gap-4">
        <div className="schedule-info-card" style={{ padding: '1rem' }}>
          <div className="schedule-info-card__label schedule-info-card__label--uppercase">Next Run</div>
          <div className="schedule-info-card__value">
            {schedule.nextRunAt ? formatTime(schedule.nextRunAt) : 'Not scheduled'}
          </div>
        </div>
        <div className="schedule-info-card" style={{ padding: '1rem' }}>
          <div className="schedule-info-card__label schedule-info-card__label--uppercase">Last Run</div>
          <div className="schedule-info-card__value">
            {schedule.lastRunAt ? formatTime(schedule.lastRunAt) : 'Never'}
          </div>
        </div>
      </div>
    </div>
  )
}

function InfoCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="schedule-info-card">
      <div className="schedule-info-card__label">{label}</div>
      <div className="schedule-info-card__value">{value}</div>
    </div>
  )
}

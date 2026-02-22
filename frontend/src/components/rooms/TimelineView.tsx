import { useMemo } from 'react'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import type { RoomBot } from '../../types'

interface TimelineViewProps {
  roomId: string
  roomBots: RoomBot[]
}

export function TimelineView({ roomId, roomBots }: TimelineViewProps) {
  const bots = useBotStore((s) => s.bots)
  const timeline = useRoomStore((s) => s.botTimeline[roomId] || [])

  // Calculate time bounds
  const { minTime, maxTime, duration } = useMemo(() => {
    if (timeline.length === 0) return { minTime: 0, maxTime: 0, duration: 0 }
    const starts = timeline.map((e) => e.startTime)
    const ends = timeline.map((e) => e.endTime).filter((e) => e > 0)
    const min = Math.min(...starts)
    const max = ends.length > 0 ? Math.max(...ends) : Date.now()
    return { minTime: min, maxTime: max, duration: max - min || 1 }
  }, [timeline])

  // Group entries by bot
  const botEntries = useMemo(() => {
    const grouped: Record<string, typeof timeline> = {}
    for (const rb of roomBots) {
      grouped[rb.botId] = []
    }
    for (const entry of timeline) {
      if (grouped[entry.botId]) {
        grouped[entry.botId].push(entry)
      }
    }
    return grouped
  }, [timeline, roomBots])

  if (timeline.length === 0) {
    return (
      <div className="room-panel__empty" style={{ flex: 1 }}>
        No timeline data yet. Send a message to see bot response timings.
      </div>
    )
  }

  // Format time axis labels
  const formatTime = (ms: number) => {
    const s = ms / 1000
    if (s < 60) return `${s.toFixed(1)}s`
    return `${Math.floor(s / 60)}m${Math.floor(s % 60)}s`
  }

  return (
    <div className="room-timeline">
      {/* Time axis */}
      <div className="room-timeline__axis">
        <span>0s</span>
        <span>{formatTime(duration / 2)}</span>
        <span>{formatTime(duration)}</span>
      </div>

      {/* Bot rows */}
      {roomBots.map((rb) => {
        const bot = bots.find((b) => b.id === rb.botId)
        const entries = botEntries[rb.botId] || []

        return (
          <div key={rb.botId} className="room-timeline__row">
            <div className="room-timeline__label">
              {bot?.name || rb.botName}
            </div>
            <div className="room-timeline__track">
              {entries.map((entry, i) => {
                const left = ((entry.startTime - minTime) / duration) * 100
                const end = entry.endTime > 0 ? entry.endTime : maxTime
                const width = ((end - entry.startTime) / duration) * 100
                const durationMs = end - entry.startTime

                return (
                  <div
                    key={i}
                    className="room-timeline__bar"
                    style={{
                      left: `${left}%`,
                      width: `${Math.max(width, 1)}%`,
                      backgroundColor: bot?.color || 'var(--accent-500)',
                    }}
                    title={`${entry.botName}: ${formatTime(durationMs)}${entry.tokens ? ` (${entry.tokens} tokens)` : ''}`}
                  />
                )
              })}
            </div>
          </div>
        )
      })}
    </div>
  )
}

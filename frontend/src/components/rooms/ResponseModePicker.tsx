import type { Bot, RoomSettings } from '../../types'
import { DebateSettings } from './ModeSubSettings'
import { RouterSettings } from './ModeSubSettings'
import { WaterfallSettings } from './ModeSubSettings'

type ResponseMode = RoomSettings['response_mode']

const MODE_INFO: Record<ResponseMode, { label: string; description: string }> = {
  parallel: { label: 'Parallel', description: 'All bots respond at the same time' },
  sequential: { label: 'One by one', description: 'Bots take turns responding one after another' },
  chain: { label: 'Chain', description: 'Bots respond in order, each building on previous outputs' },
  router: { label: 'Router', description: 'An AI picks the best bot for each message' },
  debate: { label: 'Debate', description: 'Bots argue different positions with structured rounds' },
  waterfall: { label: 'Waterfall', description: 'Bots respond in sequence, stopping when resolved' },
}

interface ResponseModePickerProps {
  responseMode: ResponseMode
  onResponseModeChange: (mode: ResponseMode) => void
  selectedBots: Pick<Bot, 'id' | 'name' | 'icon' | 'color'>[]

  // Debate settings
  debateRounds: number
  onDebateRoundsChange: (rounds: number) => void
  debatePositions: Record<string, string>
  onDebatePositionsChange: (positions: Record<string, string>) => void
  debateJudgeBotId: string | null
  onDebateJudgeBotIdChange: (botId: string | null) => void

  // Router settings
  routingStrategy: 'llm' | 'keyword' | 'round_robin'
  onRoutingStrategyChange: (strategy: 'llm' | 'keyword' | 'round_robin') => void
  botKeywords: Record<string, string[]>
  onBotKeywordsChange: (keywords: Record<string, string[]>) => void

  // Waterfall settings
  waterfallConditions: Record<string, string>
  onWaterfallConditionsChange: (conditions: Record<string, string>) => void
}

export function ResponseModePicker({
  responseMode,
  onResponseModeChange,
  selectedBots,
  debateRounds,
  onDebateRoundsChange,
  debatePositions,
  onDebatePositionsChange,
  debateJudgeBotId,
  onDebateJudgeBotIdChange,
  routingStrategy,
  onRoutingStrategyChange,
  botKeywords,
  onBotKeywordsChange,
  waterfallConditions,
  onWaterfallConditionsChange,
}: ResponseModePickerProps) {
  return (
    <div className="form-field">
      <label className="form-field__label">Response Mode</label>
      <div className="room-settings__mode-toggle">
        {(Object.keys(MODE_INFO) as ResponseMode[]).map((mode) => (
          <button
            key={mode}
            type="button"
            onClick={() => onResponseModeChange(mode)}
            className={`room-settings__mode-btn ${responseMode === mode ? 'room-settings__mode-btn--active' : ''}`}
          >
            {MODE_INFO[mode].label}
          </button>
        ))}
      </div>
      <p className="form-field__help">{MODE_INFO[responseMode].description}</p>

      {/* Mode-specific settings */}
      {responseMode === 'debate' && (
        <DebateSettings
          bots={selectedBots}
          rounds={debateRounds}
          onRoundsChange={onDebateRoundsChange}
          positions={debatePositions}
          onPositionsChange={onDebatePositionsChange}
          judgeBotId={debateJudgeBotId}
          onJudgeBotIdChange={onDebateJudgeBotIdChange}
        />
      )}

      {responseMode === 'router' && (
        <RouterSettings
          bots={selectedBots}
          strategy={routingStrategy}
          onStrategyChange={onRoutingStrategyChange}
          keywords={botKeywords}
          onKeywordsChange={onBotKeywordsChange}
        />
      )}

      {responseMode === 'waterfall' && (
        <WaterfallSettings
          bots={selectedBots}
          conditions={waterfallConditions}
          onConditionsChange={onWaterfallConditionsChange}
        />
      )}
    </div>
  )
}

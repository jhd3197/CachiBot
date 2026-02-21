import { useState } from 'react'
import { X } from 'lucide-react'
import type { Bot, RoomSettings } from '../../types'

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

// ---------- Debate Settings ----------

function DebateSettings({
  bots,
  rounds,
  onRoundsChange,
  positions,
  onPositionsChange,
  judgeBotId,
  onJudgeBotIdChange,
}: {
  bots: Pick<Bot, 'id' | 'name'>[]
  rounds: number
  onRoundsChange: (n: number) => void
  positions: Record<string, string>
  onPositionsChange: (p: Record<string, string>) => void
  judgeBotId: string | null
  onJudgeBotIdChange: (id: string | null) => void
}) {
  return (
    <div className="room-mode-settings">
      {/* Rounds */}
      <div className="room-mode-settings__row">
        <label className="form-field__label">Debate Rounds</label>
        <input
          type="number"
          value={rounds}
          onChange={(e) => onRoundsChange(Math.max(1, Math.min(5, Number(e.target.value))))}
          min={1}
          max={5}
          className="input"
          style={{ width: '5rem' }}
        />
      </div>

      {/* Per-bot positions */}
      {bots.length > 0 && (
        <div className="room-mode-settings__row">
          <label className="form-field__label">Positions</label>
          <div className="room-mode-settings__bot-configs">
            {bots.map((bot) => (
              <div key={bot.id} className="room-mode-settings__bot-row">
                <span className="room-mode-settings__bot-name">{bot.name}</span>
                <select
                  value={positions[bot.id] || 'NEUTRAL'}
                  onChange={(e) =>
                    onPositionsChange({ ...positions, [bot.id]: e.target.value })
                  }
                  className="room-settings__role-select"
                >
                  <option value="FOR">For</option>
                  <option value="AGAINST">Against</option>
                  <option value="NEUTRAL">Neutral</option>
                </select>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Judge bot */}
      {bots.length > 0 && (
        <div className="room-mode-settings__row">
          <label className="form-field__label">Judge Bot (optional)</label>
          <select
            value={judgeBotId || ''}
            onChange={(e) => onJudgeBotIdChange(e.target.value || null)}
            className="room-settings__role-select"
            style={{ width: '100%' }}
          >
            <option value="">No judge</option>
            {bots.map((bot) => (
              <option key={bot.id} value={bot.id}>
                {bot.name}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  )
}

// ---------- Router Settings ----------

function RouterSettings({
  bots,
  strategy,
  onStrategyChange,
  keywords,
  onKeywordsChange,
}: {
  bots: Pick<Bot, 'id' | 'name'>[]
  strategy: 'llm' | 'keyword' | 'round_robin'
  onStrategyChange: (s: 'llm' | 'keyword' | 'round_robin') => void
  keywords: Record<string, string[]>
  onKeywordsChange: (k: Record<string, string[]>) => void
}) {
  const [keywordInput, setKeywordInput] = useState<Record<string, string>>({})

  const addKeyword = (botId: string) => {
    const word = (keywordInput[botId] || '').trim()
    if (!word) return
    const current = keywords[botId] || []
    if (!current.includes(word)) {
      onKeywordsChange({ ...keywords, [botId]: [...current, word] })
    }
    setKeywordInput((prev) => ({ ...prev, [botId]: '' }))
  }

  const removeKeyword = (botId: string, word: string) => {
    const current = keywords[botId] || []
    onKeywordsChange({ ...keywords, [botId]: current.filter((k) => k !== word) })
  }

  return (
    <div className="room-mode-settings">
      {/* Strategy */}
      <div className="room-mode-settings__row">
        <label className="form-field__label">Routing Strategy</label>
        <div className="room-settings__mode-toggle">
          <button
            type="button"
            onClick={() => onStrategyChange('llm')}
            className={`room-settings__mode-btn ${strategy === 'llm' ? 'room-settings__mode-btn--active' : ''}`}
          >
            AI Picks
          </button>
          <button
            type="button"
            onClick={() => onStrategyChange('keyword')}
            className={`room-settings__mode-btn ${strategy === 'keyword' ? 'room-settings__mode-btn--active' : ''}`}
          >
            Keyword
          </button>
          <button
            type="button"
            onClick={() => onStrategyChange('round_robin')}
            className={`room-settings__mode-btn ${strategy === 'round_robin' ? 'room-settings__mode-btn--active' : ''}`}
          >
            Round Robin
          </button>
        </div>
      </div>

      {/* Per-bot keywords (only for keyword strategy) */}
      {strategy === 'keyword' && bots.length > 0 && (
        <div className="room-mode-settings__row">
          <label className="form-field__label">Bot Keywords</label>
          <div className="room-mode-settings__bot-configs">
            {bots.map((bot) => (
              <div key={bot.id} className="room-mode-settings__keyword-group">
                <span className="room-mode-settings__bot-name">{bot.name}</span>
                <div className="room-mode-settings__keyword-tags">
                  {(keywords[bot.id] || []).map((word) => (
                    <span key={word} className="room-mode-settings__keyword-tag">
                      {word}
                      <button
                        type="button"
                        onClick={() => removeKeyword(bot.id, word)}
                        className="room-mode-settings__keyword-remove"
                      >
                        <X size={10} />
                      </button>
                    </span>
                  ))}
                  <input
                    type="text"
                    value={keywordInput[bot.id] || ''}
                    onChange={(e) =>
                      setKeywordInput((prev) => ({ ...prev, [bot.id]: e.target.value }))
                    }
                    onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addKeyword(bot.id))}
                    placeholder="Add keyword..."
                    className="room-mode-settings__keyword-input"
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}

// ---------- Waterfall Settings ----------

function WaterfallSettings({
  bots,
  conditions,
  onConditionsChange,
}: {
  bots: Pick<Bot, 'id' | 'name'>[]
  conditions: Record<string, string>
  onConditionsChange: (c: Record<string, string>) => void
}) {
  if (bots.length === 0) return null

  return (
    <div className="room-mode-settings">
      <div className="room-mode-settings__row">
        <label className="form-field__label">Continuation Conditions</label>
        <div className="room-mode-settings__bot-configs">
          {bots.map((bot) => (
            <div key={bot.id} className="room-mode-settings__bot-row">
              <span className="room-mode-settings__bot-name">{bot.name}</span>
              <select
                value={conditions[bot.id] || 'always_continue'}
                onChange={(e) =>
                  onConditionsChange({ ...conditions, [bot.id]: e.target.value })
                }
                className="room-settings__role-select"
              >
                <option value="always_continue">Always continue</option>
                <option value="resolved">Stop if resolved</option>
                <option value="escalate">Escalate to next</option>
              </select>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

import type { Bot, RoomSettings } from '../../types'
import { DebateSettings, RouterSettings, WaterfallSettings, ConsensusSettings, InterviewSettings } from './ModeSubSettings'

type ResponseMode = RoomSettings['response_mode']

const MODE_INFO: Record<ResponseMode, { label: string; description: string }> = {
  parallel: { label: 'Parallel', description: 'All bots respond at the same time' },
  sequential: { label: 'One by one', description: 'Bots take turns responding one after another' },
  chain: { label: 'Chain', description: 'Bots respond in order, each building on previous outputs' },
  router: { label: 'Router', description: 'An AI picks the best bot for each message' },
  debate: { label: 'Debate', description: 'Bots argue different positions with structured rounds' },
  waterfall: { label: 'Waterfall', description: 'Bots respond in sequence, stopping when resolved' },
  relay: { label: 'Relay', description: 'Each message goes to the next bot in rotation' },
  consensus: { label: 'Consensus', description: 'All bots respond hidden, then a synthesizer merges into one answer' },
  interview: { label: 'Interview', description: 'One bot interviews for context, then hands off to specialists' },
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

  // Consensus settings
  consensusSynthesizerBotId: string | null
  onConsensusSynthesizerBotIdChange: (botId: string | null) => void
  consensusShowIndividual: boolean
  onConsensusShowIndividualChange: (show: boolean) => void

  // Interview settings
  interviewBotId: string | null
  onInterviewBotIdChange: (botId: string | null) => void
  interviewMaxQuestions: number
  onInterviewMaxQuestionsChange: (n: number) => void
  interviewHandoffTrigger: 'auto' | 'manual' | 'keyword'
  onInterviewHandoffTriggerChange: (trigger: 'auto' | 'manual' | 'keyword') => void
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
  consensusSynthesizerBotId,
  onConsensusSynthesizerBotIdChange,
  consensusShowIndividual,
  onConsensusShowIndividualChange,
  interviewBotId,
  onInterviewBotIdChange,
  interviewMaxQuestions,
  onInterviewMaxQuestionsChange,
  interviewHandoffTrigger,
  onInterviewHandoffTriggerChange,
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

      {responseMode === 'consensus' && (
        <ConsensusSettings
          bots={selectedBots}
          synthesizerBotId={consensusSynthesizerBotId}
          onSynthesizerBotIdChange={onConsensusSynthesizerBotIdChange}
          showIndividual={consensusShowIndividual}
          onShowIndividualChange={onConsensusShowIndividualChange}
        />
      )}

      {responseMode === 'interview' && (
        <InterviewSettings
          bots={selectedBots}
          interviewBotId={interviewBotId}
          onInterviewBotIdChange={onInterviewBotIdChange}
          maxQuestions={interviewMaxQuestions}
          onMaxQuestionsChange={onInterviewMaxQuestionsChange}
          handoffTrigger={interviewHandoffTrigger}
          onHandoffTriggerChange={onInterviewHandoffTriggerChange}
        />
      )}
    </div>
  )
}

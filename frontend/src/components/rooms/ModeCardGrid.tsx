import type { Bot, RoomSettings } from '../../types'
import {
  ParallelIllustration,
  SequentialIllustration,
  ChainIllustration,
  RouterIllustration,
  DebateIllustration,
  WaterfallIllustration,
  RelayIllustration,
  ConsensusIllustration,
  InterviewIllustration,
} from './ModeIllustrations'
import {
  DebateSettings,
  RouterSettings,
  WaterfallSettings,
  ConsensusSettings,
  InterviewSettings,
} from './ModeSubSettings'

type ResponseMode = RoomSettings['response_mode']

const MODE_CARDS: {
  mode: ResponseMode
  title: string
  description: string
  Illustration: React.FC
}[] = [
  {
    mode: 'parallel',
    title: 'Parallel',
    description: 'All bots respond to prompts simultaneously without waiting.',
    Illustration: ParallelIllustration,
  },
  {
    mode: 'sequential',
    title: 'One by one',
    description: 'Bots take turns answering sequentially, reading previous replies.',
    Illustration: SequentialIllustration,
  },
  {
    mode: 'debate',
    title: 'Debate',
    description: 'Bots actively argue and critique each other\u2019s viewpoints.',
    Illustration: DebateIllustration,
  },
  {
    mode: 'chain',
    title: 'Chain',
    description: 'Output of one bot automatically becomes the prompt for the next.',
    Illustration: ChainIllustration,
  },
  {
    mode: 'router',
    title: 'Router',
    description: 'An AI picks the best bot for each message.',
    Illustration: RouterIllustration,
  },
  {
    mode: 'waterfall',
    title: 'Waterfall',
    description: 'Bots process in sequence, stopping when the issue is resolved.',
    Illustration: WaterfallIllustration,
  },
  {
    mode: 'relay',
    title: 'Relay',
    description: 'Each message goes to the next bot in rotation.',
    Illustration: RelayIllustration,
  },
  {
    mode: 'consensus',
    title: 'Consensus',
    description: 'All bots respond hidden, then a synthesizer merges into one answer.',
    Illustration: ConsensusIllustration,
  },
  {
    mode: 'interview',
    title: 'Interview',
    description: 'One bot interviews for context, then hands off to specialists.',
    Illustration: InterviewIllustration,
  },
]

export { MODE_CARDS }

type BotInfo = Pick<Bot, 'id' | 'name' | 'icon' | 'color'>

export interface ModeCardGridProps {
  selectedMode: ResponseMode
  onSelectMode: (mode: ResponseMode) => void
  bots: BotInfo[]

  // Debate
  debateRounds: number
  onDebateRoundsChange: (n: number) => void
  debatePositions: Record<string, string>
  onDebatePositionsChange: (p: Record<string, string>) => void
  debateJudgeBotId: string | null
  onDebateJudgeBotIdChange: (id: string | null) => void

  // Router
  routingStrategy: 'llm' | 'keyword' | 'round_robin'
  onRoutingStrategyChange: (s: 'llm' | 'keyword' | 'round_robin') => void
  botKeywords: Record<string, string[]>
  onBotKeywordsChange: (k: Record<string, string[]>) => void

  // Waterfall
  waterfallConditions: Record<string, string>
  onWaterfallConditionsChange: (c: Record<string, string>) => void

  // Consensus
  consensusSynthesizerBotId: string | null
  onConsensusSynthesizerBotIdChange: (id: string | null) => void
  consensusShowIndividual: boolean
  onConsensusShowIndividualChange: (show: boolean) => void

  // Interview
  interviewBotId: string | null
  onInterviewBotIdChange: (id: string | null) => void
  interviewMaxQuestions: number
  onInterviewMaxQuestionsChange: (n: number) => void
  interviewHandoffTrigger: 'auto' | 'manual' | 'keyword'
  onInterviewHandoffTriggerChange: (t: 'auto' | 'manual' | 'keyword') => void
}

export function ModeCardGrid({
  selectedMode,
  onSelectMode,
  bots,
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
}: ModeCardGridProps) {
  return (
    <>
      <div className="room-wizard__mode-grid">
        {MODE_CARDS.map(({ mode, title, description, Illustration }) => (
          <button
            key={mode}
            type="button"
            onClick={() => onSelectMode(mode)}
            className={`room-wizard__mode-card${selectedMode === mode ? ' room-wizard__mode-card--selected' : ''}`}
          >
            <div className="room-wizard__mode-header">
              <span className="room-wizard__mode-title">{title}</span>
              <span className="room-wizard__mode-radio" />
            </div>
            <span className="room-wizard__mode-desc">{description}</span>
            <Illustration />
          </button>
        ))}
      </div>

      {selectedMode === 'debate' && (
        <DebateSettings
          bots={bots}
          rounds={debateRounds}
          onRoundsChange={onDebateRoundsChange}
          positions={debatePositions}
          onPositionsChange={onDebatePositionsChange}
          judgeBotId={debateJudgeBotId}
          onJudgeBotIdChange={onDebateJudgeBotIdChange}
        />
      )}

      {selectedMode === 'router' && (
        <RouterSettings
          bots={bots}
          strategy={routingStrategy}
          onStrategyChange={onRoutingStrategyChange}
          keywords={botKeywords}
          onKeywordsChange={onBotKeywordsChange}
        />
      )}

      {selectedMode === 'waterfall' && (
        <WaterfallSettings
          bots={bots}
          conditions={waterfallConditions}
          onConditionsChange={onWaterfallConditionsChange}
        />
      )}

      {selectedMode === 'consensus' && (
        <ConsensusSettings
          bots={bots}
          synthesizerBotId={consensusSynthesizerBotId}
          onSynthesizerBotIdChange={onConsensusSynthesizerBotIdChange}
          showIndividual={consensusShowIndividual}
          onShowIndividualChange={onConsensusShowIndividualChange}
        />
      )}

      {selectedMode === 'interview' && (
        <InterviewSettings
          bots={bots}
          interviewBotId={interviewBotId}
          onInterviewBotIdChange={onInterviewBotIdChange}
          maxQuestions={interviewMaxQuestions}
          onMaxQuestionsChange={onInterviewMaxQuestionsChange}
          handoffTrigger={interviewHandoffTrigger}
          onHandoffTriggerChange={onInterviewHandoffTriggerChange}
        />
      )}
    </>
  )
}

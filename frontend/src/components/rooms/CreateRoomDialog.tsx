import { useState } from 'react'
import { Store, Users } from 'lucide-react'
import { toast } from 'sonner'
import { createRoom } from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
  DialogStepper,
} from '../common/Dialog'
import { DebateSettings, RouterSettings, WaterfallSettings } from './ModeSubSettings'
import {
  ParallelIllustration,
  SequentialIllustration,
  ChainIllustration,
  RouterIllustration,
  DebateIllustration,
  WaterfallIllustration,
} from './ModeIllustrations'
import type { RoomSettings } from '../../types'

type ResponseMode = RoomSettings['response_mode']

const STEPS = [
  { id: 'details', label: 'Room Details' },
  { id: 'bots', label: 'Invite Bots' },
  { id: 'behavior', label: 'Response Behavior' },
] as const

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
]

interface CreateRoomDialogProps {
  onClose: () => void
  onOpenMarketplace?: () => void
}

export function CreateRoomDialog({ onClose, onOpenMarketplace }: CreateRoomDialogProps) {
  const { bots } = useBotStore()
  const { addRoom, setActiveRoom } = useRoomStore()

  // Wizard step
  const [step, setStep] = useState(0)

  // Step 0 — Room Details
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')

  // Step 1 — Invite Bots
  const [selectedBotIds, setSelectedBotIds] = useState<string[]>([])

  // Step 2 — Response Behavior
  const [responseMode, setResponseMode] = useState<ResponseMode>('parallel')
  const [cooldown, setCooldown] = useState(5)
  const [autoRelevance, setAutoRelevance] = useState(true)

  // Debate settings
  const [debateRounds, setDebateRounds] = useState(2)
  const [debatePositions, setDebatePositions] = useState<Record<string, string>>({})
  const [debateJudgeBotId, setDebateJudgeBotId] = useState<string | null>(null)

  // Router settings
  const [routingStrategy, setRoutingStrategy] = useState<'llm' | 'keyword' | 'round_robin'>('llm')
  const [botKeywords, setBotKeywords] = useState<Record<string, string[]>>({})

  // Waterfall settings
  const [waterfallConditions, setWaterfallConditions] = useState<Record<string, string>>({})

  const [creating, setCreating] = useState(false)

  // ---- Helpers ----

  const currentStepId = STEPS[step].id
  const completedSteps = STEPS.slice(0, step).map((s) => s.id)
  const selectedBots = bots.filter((b) => selectedBotIds.includes(b.id))

  const toggleBot = (botId: string) => {
    setSelectedBotIds((prev) =>
      prev.includes(botId)
        ? prev.filter((id) => id !== botId)
        : prev.length < 4
          ? [...prev, botId]
          : prev
    )
  }

  const canAdvance = (): boolean => {
    if (step === 0) return title.trim() !== ''
    if (step === 1) return selectedBotIds.length >= 2
    return true
  }

  const handleNext = () => {
    if (step === 0 && !title.trim()) {
      toast.error('Title is required')
      return
    }
    if (step === 1 && selectedBotIds.length < 2) {
      toast.error('Select at least 2 bots')
      return
    }
    if (step < STEPS.length - 1) {
      setStep(step + 1)
    } else {
      handleCreate()
    }
  }

  const handleBack = () => {
    if (step > 0) setStep(step - 1)
  }

  const buildSettings = (): RoomSettings => {
    const settings: RoomSettings = {
      cooldown_seconds: cooldown,
      auto_relevance: autoRelevance,
      response_mode: responseMode,
    }

    if (responseMode === 'debate') {
      settings.debate_rounds = debateRounds
      const positions: Record<string, string> = {}
      for (const botId of selectedBotIds) {
        positions[botId] = debatePositions[botId] || 'NEUTRAL'
      }
      settings.debate_positions = positions
      if (debateJudgeBotId) {
        settings.debate_judge_bot_id = debateJudgeBotId
      }
    }

    if (responseMode === 'router') {
      settings.routing_strategy = routingStrategy
      if (routingStrategy === 'keyword') {
        const keywords: Record<string, string[]> = {}
        for (const botId of selectedBotIds) {
          if (botKeywords[botId]?.length) {
            keywords[botId] = botKeywords[botId]
          }
        }
        settings.bot_keywords = keywords
      }
    }

    if (responseMode === 'waterfall') {
      const conditions: Record<string, string> = {}
      for (const botId of selectedBotIds) {
        conditions[botId] = waterfallConditions[botId] || 'always_continue'
      }
      settings.waterfall_conditions = conditions
    }

    return settings
  }

  const handleCreate = async () => {
    setCreating(true)
    try {
      const room = await createRoom({
        title: title.trim(),
        description: description.trim() || undefined,
        bot_ids: selectedBotIds,
        settings: buildSettings(),
      })
      addRoom(room)
      setActiveRoom(room.id)
      toast.success('Room created')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create room')
    } finally {
      setCreating(false)
    }
  }

  // ---- Render ----

  return (
    <Dialog open onClose={onClose} size="lg" ariaLabel="Create Room">
      <DialogHeader
        title="Create Room"
        icon={<Users className="h-5 w-5" style={{ color: 'var(--accent-500)' }} />}
        onClose={onClose}
      >
        <DialogStepper
          steps={[...STEPS]}
          currentStep={currentStepId}
          completedSteps={completedSteps}
          variant="progress"
        />
      </DialogHeader>

      <DialogContent scrollable>
        <div className="room-wizard">
          {/* ---- Step 0: Room Details ---- */}
          {step === 0 && (
            <>
              <h3 className="room-wizard__step-title">Room Details</h3>
              <p className="room-wizard__step-desc">
                Give your room a name and purpose to get started.
              </p>

              <div className="room-wizard__fields">
                {onOpenMarketplace && (
                  <button
                    onClick={() => { onClose(); onOpenMarketplace() }}
                    className="room-wizard__template-btn"
                  >
                    <Store size={15} />
                    Browse Room Templates
                  </button>
                )}

                <div className="form-field">
                  <label className="form-field__label">Room Title</label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Security Review Team"
                    className="input"
                    autoFocus
                  />
                </div>

                <div className="form-field">
                  <label className="form-field__label">
                    Description <span className="room-create__optional">optional</span>
                  </label>
                  <textarea
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                    placeholder="What is the main goal of this discussion?"
                    className="input"
                    rows={3}
                    style={{ resize: 'vertical' }}
                  />
                </div>
              </div>
            </>
          )}

          {/* ---- Step 1: Invite Bots ---- */}
          {step === 1 && (
            <>
              <h3 className="room-wizard__step-title">Invite Bots</h3>
              <p className="room-wizard__step-desc">
                Select between 2 and 4 AI agents to join the room.
              </p>

              <div className="room-wizard__bot-header">
                <span />
                <span className="room-wizard__bot-badge">{selectedBotIds.length}/4</span>
              </div>

              {bots.length === 0 ? (
                <div className="room-wizard__empty-bots">
                  No bots available. Create some bots first.
                </div>
              ) : (
                <div className="room-wizard__bot-list">
                  {bots.map((bot) => {
                    const selected = selectedBotIds.includes(bot.id)
                    const atLimit = selectedBotIds.length >= 4 && !selected
                    return (
                      <label
                        key={bot.id}
                        className={`room-wizard__bot-item${atLimit ? ' room-wizard__bot-item--disabled' : ''}`}
                      >
                        <div
                          className="room-wizard__bot-avatar"
                          style={{
                            backgroundColor: (bot.color || '#666') + '18',
                            color: bot.color || '#666',
                          }}
                        >
                          <BotIconRenderer icon={bot.icon} size={16} />
                        </div>
                        <span className="room-wizard__bot-name">{bot.name}</span>
                        <input
                          type="checkbox"
                          checked={selected}
                          onChange={() => toggleBot(bot.id)}
                          disabled={atLimit}
                          className="room-wizard__bot-checkbox"
                        />
                      </label>
                    )
                  })}
                </div>
              )}

              {selectedBotIds.length > 0 && selectedBotIds.length < 2 && (
                <p className="room-wizard__bot-hint">Select at least one more bot</p>
              )}
            </>
          )}

          {/* ---- Step 2: Response Behavior ---- */}
          {step === 2 && (
            <>
              <h3 className="room-wizard__step-title">Response Behavior</h3>
              <p className="room-wizard__step-desc">
                How should the bots interact with each other and you?
              </p>

              <div className="room-wizard__mode-grid">
                {MODE_CARDS.map(({ mode, title: modeTitle, description: modeDesc, Illustration }) => (
                  <button
                    key={mode}
                    type="button"
                    onClick={() => setResponseMode(mode)}
                    className={`room-wizard__mode-card${responseMode === mode ? ' room-wizard__mode-card--selected' : ''}`}
                  >
                    <div className="room-wizard__mode-header">
                      <span className="room-wizard__mode-title">{modeTitle}</span>
                      <span className="room-wizard__mode-radio" />
                    </div>
                    <span className="room-wizard__mode-desc">{modeDesc}</span>
                    <Illustration />
                  </button>
                ))}
              </div>

              {/* Mode-specific sub-settings */}
              {responseMode === 'debate' && (
                <DebateSettings
                  bots={selectedBots}
                  rounds={debateRounds}
                  onRoundsChange={setDebateRounds}
                  positions={debatePositions}
                  onPositionsChange={setDebatePositions}
                  judgeBotId={debateJudgeBotId}
                  onJudgeBotIdChange={setDebateJudgeBotId}
                />
              )}

              {responseMode === 'router' && (
                <RouterSettings
                  bots={selectedBots}
                  strategy={routingStrategy}
                  onStrategyChange={setRoutingStrategy}
                  keywords={botKeywords}
                  onKeywordsChange={setBotKeywords}
                />
              )}

              {responseMode === 'waterfall' && (
                <WaterfallSettings
                  bots={selectedBots}
                  conditions={waterfallConditions}
                  onConditionsChange={setWaterfallConditions}
                />
              )}

              {/* Cooldown + Auto-respond */}
              <div className="room-wizard__bottom-settings">
                <div className="room-wizard__setting">
                  <label className="form-field__label">Cooldown (seconds)</label>
                  <input
                    type="number"
                    value={cooldown}
                    onChange={(e) => setCooldown(Math.max(1, Math.min(30, Number(e.target.value))))}
                    min={1}
                    max={30}
                    className="input"
                  />
                </div>
                <label className="room-wizard__toggle">
                  <input
                    type="checkbox"
                    checked={autoRelevance}
                    onChange={(e) => setAutoRelevance(e.target.checked)}
                    className="consent__checkbox"
                  />
                  <div>
                    <span className="room-wizard__toggle-label">Auto-respond</span>
                    <span className="room-wizard__toggle-desc">
                      Bots respond to relevant messages automatically
                    </span>
                  </div>
                </label>
              </div>
            </>
          )}
        </div>
      </DialogContent>

      <DialogFooter
        leftContent={
          <DialogButton variant="ghost" onClick={onClose}>
            Cancel
          </DialogButton>
        }
      >
        {step > 0 && (
          <DialogButton variant="secondary" onClick={handleBack}>
            Back
          </DialogButton>
        )}
        <DialogButton
          variant="primary"
          onClick={handleNext}
          disabled={!canAdvance() || creating}
        >
          {step < STEPS.length - 1
            ? 'Next Step'
            : creating
              ? 'Creating...'
              : 'Create Room'}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}

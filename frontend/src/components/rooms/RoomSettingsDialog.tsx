import { useState, useEffect } from 'react'
import { X, UserPlus, UserMinus, Plus, Minus, RotateCcw, Trash2, Pencil, Zap, Settings } from 'lucide-react'
import { toast } from 'sonner'
import {
  updateRoom as updateRoomApi,
  deleteRoom as deleteRoomApi,
  inviteMember,
  removeMember,
  addRoomBot,
  removeRoomBot,
  clearRoomMessages,
  updateBotRole,
  getAutomations,
  createAutomation,
  updateAutomation,
  deleteAutomation,
  getRoom,
} from '../../api/rooms'
import { useBotStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { BotIconRenderer } from '../common/BotIconRenderer'
import {
  Dialog,
  DialogHeader,
  DialogContent,
  DialogFooter,
  DialogButton,
} from '../common/Dialog'
import { ModeCardGrid } from './ModeCardGrid'
import type { Room, RoomBotRole, RoomSettings, RoomAutomation, AutomationTriggerType, AutomationActionType } from '../../types'

interface RoomSettingsDialogProps {
  room: Room
  onClose: () => void
  onUpdate: (room: Room) => void
  onDelete?: () => void
}

export function RoomSettingsDialog({ room, onClose, onUpdate, onDelete }: RoomSettingsDialogProps) {
  const { bots: allBots } = useBotStore()
  const { clearMessages } = useRoomStore()
  const [title, setTitle] = useState(room.title)
  const [description, setDescription] = useState(room.description || '')
  const [cooldown, setCooldown] = useState(room.settings.cooldown_seconds)
  const [autoRelevance, setAutoRelevance] = useState(room.settings.auto_relevance)
  const [responseMode, setResponseMode] = useState<RoomSettings['response_mode']>(room.settings.response_mode || 'parallel')
  const [botRoles, setBotRoles] = useState<Record<string, RoomBotRole>>(
    Object.fromEntries(room.bots.map((b) => [b.botId, b.role || 'default']))
  )
  const [inviteUsername, setInviteUsername] = useState('')
  const [saving, setSaving] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)

  // Debate settings
  const [debateRounds, setDebateRounds] = useState(room.settings.debate_rounds ?? 2)
  const [debatePositions, setDebatePositions] = useState<Record<string, string>>(
    room.settings.debate_positions ?? {}
  )
  const [debateJudgeBotId, setDebateJudgeBotId] = useState<string | null>(
    room.settings.debate_judge_bot_id ?? null
  )

  // Router settings
  const [routingStrategy, setRoutingStrategy] = useState<'llm' | 'keyword' | 'round_robin'>(
    room.settings.routing_strategy ?? 'llm'
  )
  const [botKeywords, setBotKeywords] = useState<Record<string, string[]>>(
    room.settings.bot_keywords ?? {}
  )

  // Waterfall settings
  const [waterfallConditions, setWaterfallConditions] = useState<Record<string, string>>(
    room.settings.waterfall_conditions ?? {}
  )

  // Room personality
  const [systemPrompt, setSystemPrompt] = useState(room.settings.system_prompt ?? '')

  // Room variables
  const [variables, setVariables] = useState<Array<{ key: string; value: string }>>(
    Object.entries(room.settings.variables ?? {}).map(([key, value]) => ({ key, value }))
  )

  // Auto-summary
  const [autoSummaryInterval, setAutoSummaryInterval] = useState(room.settings.auto_summary_interval ?? 0)
  const [autoSummaryBotId, setAutoSummaryBotId] = useState<string | null>(
    room.settings.auto_summary_bot_id ?? null
  )
  const [autoSummaryAutoPin, setAutoSummaryAutoPin] = useState(room.settings.auto_summary_auto_pin ?? true)

  // Automations
  const [automations, setAutomations] = useState<RoomAutomation[]>([])
  const [showAddAutomation, setShowAddAutomation] = useState(false)
  const [newAutoName, setNewAutoName] = useState('')
  const [newAutoTrigger, setNewAutoTrigger] = useState<AutomationTriggerType>('on_keyword')
  const [newAutoKeywords, setNewAutoKeywords] = useState('')
  const [newAutoAction, setNewAutoAction] = useState<AutomationActionType>('send_message')
  const [newAutoActionBotId, setNewAutoActionBotId] = useState('')
  const [newAutoActionMessage, setNewAutoActionMessage] = useState('')

  useEffect(() => {
    getAutomations(room.id).then(setAutomations).catch(() => {})
  }, [room.id])

  const handleCreateAutomation = async () => {
    if (!newAutoName.trim()) return
    const triggerConfig: Record<string, unknown> = {}
    if (newAutoTrigger === 'on_keyword' && newAutoKeywords.trim()) {
      triggerConfig.keywords = newAutoKeywords.split(',').map(k => k.trim()).filter(Boolean)
    }
    const actionConfig: Record<string, unknown> = {}
    if (newAutoAction === 'send_message') {
      if (newAutoActionBotId) actionConfig.bot_id = newAutoActionBotId
      actionConfig.message = newAutoActionMessage
    } else if (newAutoAction === 'summarize') {
      if (newAutoActionBotId) actionConfig.bot_id = newAutoActionBotId
      actionConfig.message_count = 50
    }
    try {
      const auto = await createAutomation(room.id, {
        name: newAutoName.trim(),
        trigger_type: newAutoTrigger,
        trigger_config: triggerConfig,
        action_type: newAutoAction,
        action_config: actionConfig,
      })
      setAutomations(prev => [...prev, auto])
      setShowAddAutomation(false)
      setNewAutoName('')
      setNewAutoKeywords('')
      setNewAutoActionMessage('')
      toast.success('Automation created')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to create automation')
    }
  }

  const handleToggleAutomation = async (auto: RoomAutomation) => {
    try {
      const updated = await updateAutomation(room.id, auto.id, { enabled: !auto.enabled })
      setAutomations(prev => prev.map(a => a.id === auto.id ? updated : a))
    } catch { /* ignore */ }
  }

  const handleDeleteAutomation = async (autoId: string) => {
    try {
      await deleteAutomation(room.id, autoId)
      setAutomations(prev => prev.filter(a => a.id !== autoId))
      toast.success('Automation deleted')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to delete')
    }
  }

  // Consensus settings
  const [consensusSynthesizerBotId, setConsensusSynthesizerBotId] = useState<string | null>(
    room.settings.consensus_synthesizer_bot_id ?? null
  )
  const [consensusShowIndividual, setConsensusShowIndividual] = useState(
    room.settings.consensus_show_individual ?? false
  )

  // Interview settings
  const [interviewBotId, setInterviewBotId] = useState<string | null>(
    room.settings.interview_bot_id ?? null
  )
  const [interviewMaxQuestions, setInterviewMaxQuestions] = useState(
    room.settings.interview_max_questions ?? 5
  )
  const [interviewHandoffTrigger, setInterviewHandoffTrigger] = useState<'auto' | 'manual' | 'keyword'>(
    room.settings.interview_handoff_trigger ?? 'auto'
  )

  const buildSettings = (): RoomSettings => {
    const settings: RoomSettings = {
      cooldown_seconds: cooldown,
      auto_relevance: autoRelevance,
      response_mode: responseMode,
    }

    if (responseMode === 'debate') {
      settings.debate_rounds = debateRounds
      const positions: Record<string, string> = {}
      for (const bot of room.bots) {
        positions[bot.botId] = debatePositions[bot.botId] || 'NEUTRAL'
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
        for (const bot of room.bots) {
          if (botKeywords[bot.botId]?.length) {
            keywords[bot.botId] = botKeywords[bot.botId]
          }
        }
        settings.bot_keywords = keywords
      }
    }

    if (responseMode === 'waterfall') {
      const conditions: Record<string, string> = {}
      for (const bot of room.bots) {
        conditions[bot.botId] = waterfallConditions[bot.botId] || 'always_continue'
      }
      settings.waterfall_conditions = conditions
    }

    if (responseMode === 'consensus') {
      if (consensusSynthesizerBotId) {
        settings.consensus_synthesizer_bot_id = consensusSynthesizerBotId
      }
      settings.consensus_show_individual = consensusShowIndividual
    }

    if (responseMode === 'interview') {
      if (interviewBotId) {
        settings.interview_bot_id = interviewBotId
      }
      settings.interview_max_questions = interviewMaxQuestions
      settings.interview_handoff_trigger = interviewHandoffTrigger
    }

    // Room personality
    if (systemPrompt.trim()) {
      settings.system_prompt = systemPrompt.trim()
    }

    // Room variables
    const vars: Record<string, string> = {}
    for (const v of variables) {
      if (v.key.trim()) {
        vars[v.key.trim()] = v.value
      }
    }
    if (Object.keys(vars).length > 0) {
      settings.variables = vars
    }

    // Auto-summary
    settings.auto_summary_interval = autoSummaryInterval
    if (autoSummaryBotId) {
      settings.auto_summary_bot_id = autoSummaryBotId
    }
    settings.auto_summary_auto_pin = autoSummaryAutoPin

    return settings
  }

  const handleSave = async () => {
    setSaving(true)
    try {
      await updateRoomApi(room.id, {
        title: title.trim() || undefined,
        description: description.trim() || undefined,
        settings: buildSettings(),
      })

      // Save changed bot roles
      for (const bot of room.bots) {
        const newRole = botRoles[bot.botId]
        if (newRole && newRole !== (bot.role || 'default')) {
          await updateBotRole(room.id, bot.botId, newRole)
        }
      }

      // Refresh room data to get updated roles
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
      toast.success('Room updated')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to update')
    } finally {
      setSaving(false)
    }
  }

  const handleInvite = async () => {
    if (!inviteUsername.trim()) return
    try {
      await inviteMember(room.id, inviteUsername.trim())
      toast.success(`Invited ${inviteUsername}`)
      setInviteUsername('')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to invite')
    }
  }

  const handleRemoveMember = async (userId: string, username: string) => {
    try {
      await removeMember(room.id, userId)
      toast.success(`Removed ${username}`)
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove')
    }
  }

  const handleAddBot = async (botId: string) => {
    try {
      await addRoomBot(room.id, botId)
      toast.success('Bot added')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add bot')
    }
  }

  const handleRemoveBot = async (botId: string) => {
    try {
      await removeRoomBot(room.id, botId)
      toast.success('Bot removed')
      const refreshed = await getRoom(room.id)
      onUpdate(refreshed)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove bot')
    }
  }

  const roomBotIds = new Set(room.bots.map((b) => b.botId))
  const availableBots = allBots.filter((b) => !roomBotIds.has(b.id))

  // Build bot info for the ModeCardGrid
  const selectedBots = room.bots.map((rb) => {
    const bot = allBots.find((b) => b.id === rb.botId)
    return {
      id: rb.botId,
      name: rb.botName,
      icon: bot?.icon ?? 'bot' as const,
      color: bot?.color ?? '#666',
    }
  })

  return (
    <Dialog open onClose={onClose} size="xl" ariaLabel="Room Settings">
      <DialogHeader
        title="Room Settings"
        icon={<Settings className="h-5 w-5" style={{ color: 'var(--accent-500)' }} />}
        onClose={onClose}
      />

      <DialogContent scrollable>
        {/* ---- Section 1: General ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">General</span>
          <div className="form-field">
            <label className="form-field__label">Title</label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              className="input"
            />
          </div>
          <div className="form-field">
            <label className="form-field__label">Description</label>
            <input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="input"
            />
          </div>
        </div>

        {/* ---- Section 2: Bots & Members ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">Bots & Members</span>

          {/* Members */}
          <div className="form-field">
            <label className="form-field__label">
              Members ({room.members.length})
            </label>
            <div className="room-settings__member-list">
              {room.members.map((m) => (
                <div key={m.userId} className="room-settings__member-item">
                  <span className="room-settings__member-name">
                    {m.username}
                    {m.role === 'creator' && (
                      <span className="room-settings__member-role">(creator)</span>
                    )}
                  </span>
                  {m.role !== 'creator' && (
                    <button
                      onClick={() => handleRemoveMember(m.userId, m.username)}
                      className="room-settings__bot-remove"
                    >
                      <UserMinus size={14} />
                    </button>
                  )}
                </div>
              ))}
              <div className="room-settings__invite-row">
                <input
                  type="text"
                  value={inviteUsername}
                  onChange={(e) => setInviteUsername(e.target.value)}
                  placeholder="Invite by username"
                  className="room-settings__invite-input"
                  onKeyDown={(e) => e.key === 'Enter' && handleInvite()}
                />
                <button
                  onClick={handleInvite}
                  disabled={!inviteUsername.trim()}
                  className="room-settings__invite-btn"
                >
                  <UserPlus size={14} />
                </button>
              </div>
            </div>
          </div>

          {/* Bots */}
          <div className="form-field">
            <label className="form-field__label">
              Bots ({room.bots.length}/4)
            </label>
            <div className="room-settings__member-list">
              {room.bots.map((rb) => (
                <div key={rb.botId} className="room-settings__member-item">
                  <span className="room-settings__member-name">{rb.botName}</span>
                  <div className="room-settings__bot-actions">
                    <button
                      onClick={() => {
                        onClose()
                        window.location.hash = `#/${rb.botId}/settings`
                      }}
                      className="room-panel__icon-btn"
                      title="Edit bot settings"
                    >
                      <Pencil size={12} />
                    </button>
                    <select
                      value={botRoles[rb.botId] || 'default'}
                      onChange={(e) =>
                        setBotRoles((prev) => ({ ...prev, [rb.botId]: e.target.value as RoomBotRole }))
                      }
                      className="room-settings__role-select"
                    >
                      <option value="default">Default</option>
                      <option value="lead">Lead</option>
                      <option value="reviewer">Reviewer</option>
                      <option value="observer">Observer</option>
                      <option value="specialist">Specialist</option>
                    </select>
                    {room.bots.length > 2 && (
                      <button
                        onClick={() => handleRemoveBot(rb.botId)}
                        className="room-settings__bot-remove"
                      >
                        <Minus size={14} />
                      </button>
                    )}
                  </div>
                </div>
              ))}
              {room.bots.length < 4 && availableBots.length > 0 && (
                <div className="room-settings__add-bot-area">
                  <p className="form-field__help">Add a bot:</p>
                  {availableBots.slice(0, 5).map((bot) => (
                    <button
                      key={bot.id}
                      onClick={() => handleAddBot(bot.id)}
                      className="room-settings__bot-item"
                    >
                      <BotIconRenderer icon={bot.icon} size={14} />
                      <span>{bot.name}</span>
                      <Plus size={14} className="room-settings__add-bot-icon" />
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>

        {/* ---- Section 3: Response Mode ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">Response Mode</span>

          <ModeCardGrid
            selectedMode={responseMode}
            onSelectMode={setResponseMode}
            bots={selectedBots}
            debateRounds={debateRounds}
            onDebateRoundsChange={setDebateRounds}
            debatePositions={debatePositions}
            onDebatePositionsChange={setDebatePositions}
            debateJudgeBotId={debateJudgeBotId}
            onDebateJudgeBotIdChange={setDebateJudgeBotId}
            routingStrategy={routingStrategy}
            onRoutingStrategyChange={setRoutingStrategy}
            botKeywords={botKeywords}
            onBotKeywordsChange={setBotKeywords}
            waterfallConditions={waterfallConditions}
            onWaterfallConditionsChange={setWaterfallConditions}
            consensusSynthesizerBotId={consensusSynthesizerBotId}
            onConsensusSynthesizerBotIdChange={setConsensusSynthesizerBotId}
            consensusShowIndividual={consensusShowIndividual}
            onConsensusShowIndividualChange={setConsensusShowIndividual}
            interviewBotId={interviewBotId}
            onInterviewBotIdChange={setInterviewBotId}
            interviewMaxQuestions={interviewMaxQuestions}
            onInterviewMaxQuestionsChange={setInterviewMaxQuestions}
            interviewHandoffTrigger={interviewHandoffTrigger}
            onInterviewHandoffTriggerChange={setInterviewHandoffTrigger}
          />

          {/* Cooldown & auto-relevance */}
          <div className="room-settings__setting-row">
            <div className="room-settings__setting-field">
              <label className="form-field__label">Cooldown (seconds)</label>
              <input
                type="number"
                value={cooldown}
                onChange={(e) => setCooldown(Number(e.target.value))}
                min={1}
                max={30}
                className="input"
              />
            </div>
            <div className="room-settings__auto-respond">
              <input
                id="settings-auto-relevance"
                type="checkbox"
                checked={autoRelevance}
                onChange={(e) => setAutoRelevance(e.target.checked)}
                className="consent__checkbox"
              />
              <label htmlFor="settings-auto-relevance" className="form-field__help">
                Auto-respond
              </label>
            </div>
          </div>
        </div>

        {/* ---- Section 4: Personality & Context ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">Personality & Context</span>

          <div className="form-field">
            <label className="form-field__label">Room Personality</label>
            <p className="form-field__help">System prompt injected into all bots in this room.</p>
            <textarea
              value={systemPrompt}
              onChange={(e) => setSystemPrompt(e.target.value)}
              className="input"
              rows={3}
              placeholder="e.g., Always respond in Spanish. Focus on security topics."
              style={{ resize: 'vertical', minHeight: '3rem' }}
            />
          </div>

          {/* Auto-Summary */}
          <div className="form-field">
            <label className="form-field__label">Auto-Summary</label>
            <p className="form-field__help">Automatically summarize every N messages.</p>
            <div className="room-settings__auto-summary-row">
              <span className="form-field__help">Every</span>
              <input
                type="number"
                value={autoSummaryInterval}
                onChange={(e) => setAutoSummaryInterval(Math.max(0, Number(e.target.value)))}
                min={0}
                className="input"
                style={{ width: '5rem' }}
              />
              <span className="form-field__help">messages (0 = off)</span>
            </div>
            {autoSummaryInterval > 0 && (
              <div className="room-settings__auto-summary-opts">
                <select
                  value={autoSummaryBotId || ''}
                  onChange={(e) => setAutoSummaryBotId(e.target.value || null)}
                  className="room-settings__role-select"
                >
                  <option value="">First bot (default)</option>
                  {room.bots.map((rb) => (
                    <option key={rb.botId} value={rb.botId}>{rb.botName}</option>
                  ))}
                </select>
                <div className="room-settings__auto-summary-pin">
                  <input
                    id="auto-summary-pin"
                    type="checkbox"
                    checked={autoSummaryAutoPin}
                    onChange={(e) => setAutoSummaryAutoPin(e.target.checked)}
                    className="consent__checkbox"
                  />
                  <label htmlFor="auto-summary-pin" className="form-field__help">
                    Auto-pin summary messages
                  </label>
                </div>
              </div>
            )}
          </div>

          {/* Room Variables */}
          <div className="form-field">
            <label className="form-field__label">Room Variables</label>
            <p className="form-field__help">Key-value pairs accessible to all bots.</p>
            <div className="room-settings__variables">
              {variables.map((v, i) => (
                <div key={i} className="room-settings__variables-row">
                  <input
                    type="text"
                    value={v.key}
                    onChange={(e) => {
                      const updated = [...variables]
                      updated[i] = { ...v, key: e.target.value }
                      setVariables(updated)
                    }}
                    className="room-settings__variables-key"
                    placeholder="Key"
                  />
                  <span className="room-settings__variables-eq">=</span>
                  <input
                    type="text"
                    value={v.value}
                    onChange={(e) => {
                      const updated = [...variables]
                      updated[i] = { ...v, value: e.target.value }
                      setVariables(updated)
                    }}
                    className="room-settings__variables-value"
                    placeholder="Value"
                  />
                  <button
                    onClick={() => setVariables(variables.filter((_, j) => j !== i))}
                    className="room-settings__variables-remove"
                  >
                    <X size={12} />
                  </button>
                </div>
              ))}
              <button
                onClick={() => setVariables([...variables, { key: '', value: '' }])}
                className="room-settings__variables-add"
              >
                <Plus size={12} /> Add Variable
              </button>
            </div>
          </div>
        </div>

        {/* ---- Section 5: Automations ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">
            <Zap size={12} /> Automations ({automations.length})
          </span>

          <div className="form-field">
            <p className="form-field__help">Trigger actions automatically based on events.</p>

            {automations.map((auto) => (
              <div key={auto.id} className="room-settings__member-item">
                <div className="room-settings__auto-item-left">
                  <input
                    type="checkbox"
                    checked={auto.enabled}
                    onChange={() => handleToggleAutomation(auto)}
                    className="consent__checkbox"
                  />
                  <span className="room-settings__member-name room-settings__auto-name">
                    {auto.name}
                  </span>
                  <span className="form-field__help room-settings__auto-type">
                    {auto.triggerType} → {auto.actionType}
                  </span>
                </div>
                <button
                  onClick={() => handleDeleteAutomation(auto.id)}
                  className="room-settings__bot-remove"
                >
                  <X size={12} />
                </button>
              </div>
            ))}

            {showAddAutomation ? (
              <div className="room-settings__add-auto-form">
                <input
                  type="text"
                  value={newAutoName}
                  onChange={(e) => setNewAutoName(e.target.value)}
                  placeholder="Automation name"
                  className="input"
                />
                <div className="room-settings__add-auto-selects">
                  <select
                    value={newAutoTrigger}
                    onChange={(e) => setNewAutoTrigger(e.target.value as AutomationTriggerType)}
                    className="room-settings__role-select"
                  >
                    <option value="on_message">On every message</option>
                    <option value="on_keyword">On keyword</option>
                    <option value="on_idle">On idle</option>
                    <option value="on_schedule">On schedule</option>
                  </select>
                  <select
                    value={newAutoAction}
                    onChange={(e) => setNewAutoAction(e.target.value as AutomationActionType)}
                    className="room-settings__role-select"
                  >
                    <option value="send_message">Send message</option>
                    <option value="summarize">Summarize</option>
                    <option value="pin_message">Pin message</option>
                  </select>
                </div>
                {newAutoTrigger === 'on_keyword' && (
                  <input
                    type="text"
                    value={newAutoKeywords}
                    onChange={(e) => setNewAutoKeywords(e.target.value)}
                    placeholder="Keywords (comma-separated)"
                    className="input"
                  />
                )}
                {(newAutoAction === 'send_message' || newAutoAction === 'summarize') && (
                  <select
                    value={newAutoActionBotId}
                    onChange={(e) => setNewAutoActionBotId(e.target.value)}
                    className="room-settings__role-select"
                  >
                    <option value="">Select bot...</option>
                    {room.bots.map((rb) => (
                      <option key={rb.botId} value={rb.botId}>{rb.botName}</option>
                    ))}
                  </select>
                )}
                {newAutoAction === 'send_message' && (
                  <input
                    type="text"
                    value={newAutoActionMessage}
                    onChange={(e) => setNewAutoActionMessage(e.target.value)}
                    placeholder="Message to send"
                    className="input"
                  />
                )}
                <div className="room-settings__add-auto-actions">
                  <button onClick={() => setShowAddAutomation(false)} className="btn btn--ghost btn--sm">
                    Cancel
                  </button>
                  <button onClick={handleCreateAutomation} disabled={!newAutoName.trim()} className="btn btn--primary btn--sm">
                    Create
                  </button>
                </div>
              </div>
            ) : (
              <button
                onClick={() => setShowAddAutomation(true)}
                className="room-settings__variables-add"
              >
                <Plus size={12} /> Add Automation
              </button>
            )}
          </div>
        </div>

        {/* ---- Section 6: Danger Zone ---- */}
        <div className="room-settings__group">
          <span className="room-settings__group-title">Danger Zone</span>

          {showResetConfirm ? (
            <div className="room-settings__reset-confirm">
              <p className="form-field__help" style={{ margin: 0 }}>
                Clear all messages in this room? This can't be undone.
              </p>
              <div className="room-settings__confirm-actions">
                <button
                  onClick={() => setShowResetConfirm(false)}
                  className="btn btn--ghost btn--sm"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      await clearRoomMessages(room.id)
                      clearMessages(room.id)
                      setShowResetConfirm(false)
                      toast.success('Chat cleared')
                    } catch {
                      toast.error('Failed to clear messages')
                    }
                  }}
                  className="btn btn--danger btn--sm"
                >
                  Clear Messages
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowResetConfirm(true)}
              className="btn btn--ghost btn--sm room-settings__danger-btn"
            >
              <RotateCcw size={14} />
              Start Over
            </button>
          )}

          {showDeleteConfirm ? (
            <div className="room-settings__reset-confirm">
              <p className="form-field__help" style={{ margin: 0 }}>
                Permanently delete this room and all its messages? This can't be undone.
              </p>
              <div className="room-settings__confirm-actions">
                <button
                  onClick={() => setShowDeleteConfirm(false)}
                  className="btn btn--ghost btn--sm"
                >
                  Cancel
                </button>
                <button
                  onClick={async () => {
                    try {
                      await deleteRoomApi(room.id)
                      toast.success('Room deleted')
                      onDelete?.()
                    } catch {
                      toast.error('Failed to delete room')
                    }
                  }}
                  className="btn btn--danger btn--sm"
                >
                  Delete Room
                </button>
              </div>
            </div>
          ) : (
            <button
              onClick={() => setShowDeleteConfirm(true)}
              className="btn btn--ghost btn--sm room-settings__danger-btn room-settings__danger-btn--delete"
            >
              <Trash2 size={14} />
              Delete Room
            </button>
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
        <DialogButton
          variant="primary"
          onClick={handleSave}
          disabled={saving}
        >
          {saving ? 'Saving...' : 'Save'}
        </DialogButton>
      </DialogFooter>
    </Dialog>
  )
}

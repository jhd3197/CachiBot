import { useEffect, useRef, useState } from 'react'
import {
  Loader2,
  Sparkles,
  AlertTriangle,
  Settings,
  Plus,
  Trash2,
  ChevronDown,
  ChevronUp,
  RefreshCw,
  Bot as BotIcon,
  Layers,
  Pencil,
} from 'lucide-react'
import {
  useCreationStore,
  PURPOSE_CATEGORIES,
  TONE_OPTIONS,
  EXPERTISE_LEVEL_OPTIONS,
  RESPONSE_LENGTH_OPTIONS,
  PERSONALITY_TRAIT_OPTIONS,
} from '../../../../stores/creation'
import type {
  ProposalBot,
  ProposalRoom,
  BotTone,
  BotExpertiseLevel,
  BotResponseLength,
  BotPersonalityTrait,
} from '../../../../stores/creation'
import { useModelsStore } from '../../../../stores/models'
import { useUIStore } from '../../../../stores/ui'
import { generateProjectProposal } from '../../../../api/client'
import { BotIconRenderer, BOT_ICON_OPTIONS } from '../../../common/BotIconRenderer'
import { ModelSelect } from '../../../common/ModelSelect'
import { cn } from '../../../../lib/utils'
import type { BotIcon as BotIconType, RoomBotRole, RoomSettings } from '../../../../types'

const BOT_COLORS = [
  '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899',
  '#f59e0b', '#ef4444', '#06b6d4', '#84cc16',
]

const ROLE_OPTIONS: { value: RoomBotRole; label: string }[] = [
  { value: 'default', label: 'Default' },
  { value: 'lead', label: 'Lead' },
  { value: 'specialist', label: 'Specialist' },
  { value: 'reviewer', label: 'Reviewer' },
  { value: 'observer', label: 'Observer' },
]

const MODE_OPTIONS: { value: RoomSettings['response_mode']; label: string; description: string }[] = [
  { value: 'parallel', label: 'Parallel', description: 'All bots respond simultaneously' },
  { value: 'sequential', label: 'Sequential', description: 'Bots take turns in order' },
  { value: 'chain', label: 'Chain', description: 'Output feeds into next bot' },
  { value: 'router', label: 'Router', description: 'AI picks best bot per message' },
  { value: 'debate', label: 'Debate', description: 'Bots argue viewpoints' },
  { value: 'waterfall', label: 'Waterfall', description: 'Process until resolved' },
  { value: 'relay', label: 'Relay', description: 'Messages rotate through bots' },
  { value: 'consensus', label: 'Consensus', description: 'Responses merged by synthesizer' },
]

const LOADING_MESSAGES = [
  { title: 'Designing your team...', sub: 'Creating specialized bots for your project' },
  { title: 'Crafting system prompts...', sub: 'Giving each bot a unique personality' },
  { title: 'Organizing rooms...', sub: 'Deciding how your bots should collaborate' },
  { title: 'Almost done...', sub: 'Putting the finishing touches on your proposal' },
]

export function ProjectProposalStep() {
  const {
    form,
    isGenerating,
    generationError,
    setGenerating,
    setGenerationError,
    setProjectProposal,
    updateProposalBot,
    removeProposalBot,
    addProposalBot,
    updateProposalRoom,
    removeProposalRoom,
    addProposalRoom,
  } = useCreationStore()

  const loadInitiatedRef = useRef(false)
  const [editingBotId, setEditingBotId] = useState<string | null>(null)
  const [editingRoomId, setEditingRoomId] = useState<string | null>(null)
  const [msgIndex, setMsgIndex] = useState(0)

  useEffect(() => {
    if (!form.projectProposal && !isGenerating && !loadInitiatedRef.current) {
      loadInitiatedRef.current = true
      generateProposal()
    }
  }, [])

  useEffect(() => {
    if (!isGenerating) return
    const interval = setInterval(() => {
      setMsgIndex((i) => (i + 1) % LOADING_MESSAGES.length)
    }, 3500)
    return () => clearInterval(interval)
  }, [isGenerating])

  const generateProposal = async () => {
    setGenerating(true)
    setGenerationError(null)

    try {
      const freshForm = useCreationStore.getState().form
      const categoryLabel =
        PURPOSE_CATEGORIES.find((c) => c.id === freshForm.purposeCategory)?.label || 'General'

      const followUpAnswers = freshForm.projectFollowUpQuestions
        .filter((q) => q.answer.trim())
        .map((q) => ({ question: q.question, answer: q.answer }))

      const result = await generateProjectProposal({
        category: categoryLabel,
        description: freshForm.purposeDescription,
        follow_up_answers: followUpAnswers,
      })

      // Transform API response into store types
      const { defaultModel } = useModelsStore.getState()
      const bots: ProposalBot[] = result.bots.map((b, i) => ({
        tempId: crypto.randomUUID(),
        name: b.name,
        description: b.description,
        role: (b.role as RoomBotRole) || 'default',
        icon: (['bot', 'brain', 'zap', 'sparkles', 'target', 'cpu'] as BotIconType[])[i % 6],
        color: BOT_COLORS[i % BOT_COLORS.length],
        systemPrompt: b.system_prompt,
        model: defaultModel || '',
        tone: (b.tone as BotTone) || 'friendly',
        expertiseLevel: (b.expertise_level as BotExpertiseLevel) || 'expert',
        responseLength: (b.response_length as BotResponseLength) || 'moderate',
        personalityTraits: (b.personality_traits as BotPersonalityTrait[]) || [],
      }))

      const rooms: ProposalRoom[] = result.rooms.map((r) => ({
        tempId: crypto.randomUUID(),
        name: r.name,
        description: r.description,
        responseMode: (r.response_mode as RoomSettings['response_mode']) || 'parallel',
        botTempIds: r.bot_names
          .map((name) => bots.find((b) => b.name === name)?.tempId)
          .filter((id): id is string => !!id),
        settings: {},
      }))

      setProjectProposal({
        projectName: result.project_name,
        projectDescription: result.project_description,
        bots,
        rooms,
      })
    } catch (error) {
      const msg = error instanceof Error ? error.message : 'Failed to generate proposal'
      setGenerationError(msg)
    } finally {
      setGenerating(false)
    }
  }

  const handleRegenerate = () => {
    loadInitiatedRef.current = false
    setEditingBotId(null)
    setEditingRoomId(null)
    useCreationStore.setState((state) => ({
      form: { ...state.form, projectProposal: null },
    }))
    generateProposal()
  }

  const handleAddBot = () => {
    const newBot: ProposalBot = {
      tempId: crypto.randomUUID(),
      name: 'New Bot',
      description: 'A new team member',
      role: 'default',
      icon: 'bot',
      color: BOT_COLORS[Math.floor(Math.random() * BOT_COLORS.length)],
      systemPrompt: '',
      model: useModelsStore.getState().defaultModel || '',
      tone: 'friendly',
      expertiseLevel: 'expert',
      responseLength: 'moderate',
      personalityTraits: [],
    }
    addProposalBot(newBot)
    setEditingBotId(newBot.tempId)
  }

  const handleAddRoom = () => {
    const newRoom: ProposalRoom = {
      tempId: crypto.randomUUID(),
      name: 'New Room',
      description: 'A new collaboration space',
      responseMode: 'parallel',
      botTempIds: [],
      settings: {},
    }
    addProposalRoom(newRoom)
    setEditingRoomId(newRoom.tempId)
  }

  const isNoModel = generationError?.toLowerCase().includes('no ai model configured')

  if (isGenerating) {
    const msg = LOADING_MESSAGES[msgIndex]
    return (
      <div className="flex h-72 flex-col items-center justify-center gap-4">
        <div className="relative">
          <div className="absolute inset-0 animate-ping rounded-full bg-cachi-500/20" />
          <div className="relative flex h-16 w-16 items-center justify-center rounded-full bg-cachi-500/10">
            <Sparkles className="h-8 w-8 text-cachi-400" />
          </div>
        </div>
        <div className="text-center transition-opacity duration-500">
          <p className="text-lg font-medium text-[var(--color-text-primary)]">{msg.title}</p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">{msg.sub}</p>
        </div>
        <Loader2 className="h-5 w-5 animate-spin text-cachi-400" />
      </div>
    )
  }

  if (generationError && !form.projectProposal) {
    return (
      <div className="flex h-64 flex-col items-center justify-center gap-4">
        <div className="flex h-16 w-16 items-center justify-center rounded-full bg-red-500/10">
          <AlertTriangle className="h-8 w-8 text-red-400" />
        </div>
        <div className="text-center">
          <p className="text-lg font-medium text-[var(--color-text-primary)]">
            {isNoModel ? 'No AI Model Configured' : 'Failed to generate proposal'}
          </p>
          <p className="mt-1 text-sm text-[var(--color-text-secondary)]">
            {isNoModel
              ? 'You need to set a default model first.'
              : generationError}
          </p>
        </div>
        {isNoModel ? (
          <button
            onClick={() => useUIStore.getState().setSettingsOpen(true)}
            className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-cachi-500"
          >
            <Settings className="h-4 w-4" />
            Open Settings
          </button>
        ) : (
          <button
            onClick={handleRegenerate}
            className="text-sm text-cachi-400 hover:text-cachi-300"
          >
            Try again
          </button>
        )}
      </div>
    )
  }

  if (!form.projectProposal) return null

  const proposal = form.projectProposal

  return (
    <div className="space-y-6">
      {/* Project header */}
      <div className="flex items-start justify-between">
        <div className="flex-1">
          <input
            value={proposal.projectName}
            onChange={(e) =>
              setProjectProposal({ ...proposal, projectName: e.target.value })
            }
            className="w-full bg-transparent text-lg font-bold text-[var(--color-text-primary)] outline-none placeholder-[var(--input-placeholder)] focus:underline"
            placeholder="Project name"
          />
          <input
            value={proposal.projectDescription}
            onChange={(e) =>
              setProjectProposal({ ...proposal, projectDescription: e.target.value })
            }
            className="mt-1 w-full bg-transparent text-sm text-[var(--color-text-secondary)] outline-none placeholder-[var(--input-placeholder)] focus:underline"
            placeholder="Project description"
          />
        </div>
        <button
          onClick={handleRegenerate}
          className="ml-3 flex items-center gap-1.5 rounded-lg border border-[var(--color-border-primary)] px-3 py-1.5 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-cachi-500 hover:text-cachi-400"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Regenerate
        </button>
      </div>

      {/* Bots section */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
            <BotIcon className="h-4 w-4 text-cachi-400" />
            Bots ({proposal.bots.length})
          </h3>
          <button
            onClick={handleAddBot}
            className="flex items-center gap-1 rounded-lg border border-dashed border-[var(--color-border-primary)] px-2.5 py-1 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-cachi-500 hover:text-cachi-400"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Bot
          </button>
        </div>

        <div className="grid grid-cols-2 gap-3">
          {proposal.bots.map((bot) => (
            <BotCard
              key={bot.tempId}
              bot={bot}
              isEditing={editingBotId === bot.tempId}
              onToggleEdit={() =>
                setEditingBotId(editingBotId === bot.tempId ? null : bot.tempId)
              }
              onUpdate={(updates) => updateProposalBot(bot.tempId, updates)}
              onRemove={
                proposal.bots.length > 2
                  ? () => removeProposalBot(bot.tempId)
                  : undefined
              }
            />
          ))}
        </div>
      </div>

      {/* Rooms section */}
      <div>
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 text-sm font-semibold text-[var(--color-text-primary)]">
            <Layers className="h-4 w-4 text-cachi-400" />
            Rooms ({proposal.rooms.length})
          </h3>
          <button
            onClick={handleAddRoom}
            className="flex items-center gap-1 rounded-lg border border-dashed border-[var(--color-border-primary)] px-2.5 py-1 text-xs text-[var(--color-text-secondary)] transition-colors hover:border-cachi-500 hover:text-cachi-400"
          >
            <Plus className="h-3.5 w-3.5" />
            Add Room
          </button>
        </div>

        <div className="space-y-3">
          {proposal.rooms.map((room) => (
            <RoomCard
              key={room.tempId}
              room={room}
              bots={proposal.bots}
              isEditing={editingRoomId === room.tempId}
              onToggleEdit={() =>
                setEditingRoomId(editingRoomId === room.tempId ? null : room.tempId)
              }
              onUpdate={(updates) => updateProposalRoom(room.tempId, updates)}
              onRemove={
                proposal.rooms.length > 1
                  ? () => removeProposalRoom(room.tempId)
                  : undefined
              }
            />
          ))}
        </div>
      </div>
    </div>
  )
}

// ─── Bot Card ─────────────────────────────────────────────────────────────────

function BotCard({
  bot,
  isEditing,
  onToggleEdit,
  onUpdate,
  onRemove,
}: {
  bot: ProposalBot
  isEditing: boolean
  onToggleEdit: () => void
  onUpdate: (updates: Partial<ProposalBot>) => void
  onRemove?: () => void
}) {
  const [showPrompt, setShowPrompt] = useState(false)

  return (
    <div
      className={cn(
        'rounded-xl border transition-all',
        isEditing
          ? 'col-span-2 border-cachi-500/50 bg-[var(--color-bg-primary)]'
          : 'border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)]',
      )}
    >
      {/* Header */}
      <div className="flex items-center gap-3 p-3">
        <div
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg"
          style={{ backgroundColor: bot.color + '20' }}
        >
          <BotIconRenderer icon={bot.icon} size={20} color={bot.color} />
        </div>
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <input
              value={bot.name}
              onChange={(e) => onUpdate({ name: e.target.value })}
              className="w-full bg-transparent text-sm font-semibold text-[var(--color-text-primary)] outline-none focus:underline"
            />
          ) : (
            <p className="truncate text-sm font-semibold text-[var(--color-text-primary)]">
              {bot.name}
            </p>
          )}
          <p className="truncate text-xs text-[var(--color-text-secondary)]">
            Role: {ROLE_OPTIONS.find((r) => r.value === bot.role)?.label || bot.role}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleEdit}
            className="rounded-md p-1.5 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
          >
            {isEditing ? <ChevronUp className="h-4 w-4" /> : <Pencil className="h-3.5 w-3.5" />}
          </button>
          {onRemove && (
            <button
              onClick={onRemove}
              className="rounded-md p-1.5 text-[var(--color-text-tertiary)] transition-colors hover:bg-red-500/10 hover:text-red-400"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {!isEditing && (
        <div className="border-t border-[var(--color-border-primary)] px-3 py-2">
          <p className="line-clamp-2 text-xs text-[var(--color-text-secondary)]">
            {bot.description}
          </p>
        </div>
      )}

      {/* Expanded edit form */}
      {isEditing && (
        <div className="space-y-4 border-t border-[var(--color-border-primary)] p-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
              Description
            </label>
            <input
              value={bot.description}
              onChange={(e) => onUpdate({ description: e.target.value })}
              className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Role
              </label>
              <select
                value={bot.role}
                onChange={(e) => onUpdate({ role: e.target.value as RoomBotRole })}
                className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
              >
                {ROLE_OPTIONS.map((r) => (
                  <option key={r.value} value={r.value}>{r.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Model
              </label>
              <ModelSelect
                value={bot.model}
                onChange={(model) => onUpdate({ model })}
              />
            </div>
          </div>

          {/* Personality: Tone + Expertise Level */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Tone
              </label>
              <select
                value={bot.tone}
                onChange={(e) => onUpdate({ tone: e.target.value as BotTone })}
                className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
              >
                {TONE_OPTIONS.map((t) => (
                  <option key={t.value} value={t.value}>{t.label}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Expertise Level
              </label>
              <select
                value={bot.expertiseLevel}
                onChange={(e) => onUpdate({ expertiseLevel: e.target.value as BotExpertiseLevel })}
                className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
              >
                {EXPERTISE_LEVEL_OPTIONS.map((l) => (
                  <option key={l.value} value={l.value}>{l.label}</option>
                ))}
              </select>
            </div>
          </div>

          {/* Response Length */}
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
              Response Length
            </label>
            <select
              value={bot.responseLength}
              onChange={(e) => onUpdate({ responseLength: e.target.value as BotResponseLength })}
              className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
            >
              {RESPONSE_LENGTH_OPTIONS.map((l) => (
                <option key={l.value} value={l.value}>{l.label}</option>
              ))}
            </select>
          </div>

          {/* Personality Traits */}
          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--color-text-secondary)]">
              Personality Traits
            </label>
            <div className="flex flex-wrap gap-2">
              {PERSONALITY_TRAIT_OPTIONS.map((trait) => {
                const isSelected = bot.personalityTraits.includes(trait.value)
                return (
                  <button
                    key={trait.value}
                    onClick={() => {
                      const current = bot.personalityTraits
                      if (isSelected) {
                        onUpdate({ personalityTraits: current.filter((t) => t !== trait.value) })
                      } else if (current.length < 4) {
                        onUpdate({ personalityTraits: [...current, trait.value] })
                      }
                    }}
                    className={cn(
                      'rounded-lg border px-3 py-1.5 text-xs font-medium transition-all',
                      isSelected
                        ? 'border-cachi-500 bg-cachi-500/10 text-cachi-400'
                        : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] text-[var(--color-text-secondary)] hover:border-[var(--color-border-secondary)]',
                    )}
                  >
                    {trait.label}
                  </button>
                )
              })}
            </div>
            {bot.personalityTraits.length === 0 && (
              <p className="mt-1.5 text-[10px] text-[var(--color-text-tertiary)]">
                Select up to 4 traits
              </p>
            )}
          </div>

          {/* Icon + Color */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Icon
              </label>
              <div className="flex flex-wrap gap-1">
                {BOT_ICON_OPTIONS.slice(0, 12).map((option) => (
                  <button
                    key={option.id}
                    onClick={() => onUpdate({ icon: option.id as BotIconType })}
                    title={option.label}
                    className={cn(
                      'flex h-8 w-8 items-center justify-center rounded-md border transition-all',
                      bot.icon === option.id
                        ? 'border-cachi-500 bg-cachi-500/20'
                        : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]',
                    )}
                  >
                    <BotIconRenderer icon={option.id as BotIconType} size={14} color={bot.icon === option.id ? bot.color : undefined} />
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
                Color
              </label>
              <div className="flex flex-wrap gap-1.5">
                {BOT_COLORS.map((color) => (
                  <button
                    key={color}
                    onClick={() => onUpdate({ color })}
                    className={cn(
                      'h-7 w-7 rounded-full border-2 transition-all',
                      bot.color === color ? 'border-white scale-110' : 'border-transparent',
                    )}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>
          </div>

          {/* Collapsible system prompt */}
          <div>
            <button
              onClick={() => setShowPrompt(!showPrompt)}
              className="flex items-center gap-1.5 text-xs font-medium text-[var(--color-text-secondary)] transition-colors hover:text-[var(--color-text-primary)]"
            >
              {showPrompt ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
              System Prompt
            </button>
            {showPrompt && (
              <textarea
                value={bot.systemPrompt}
                onChange={(e) => onUpdate({ systemPrompt: e.target.value })}
                rows={6}
                className="mt-2 w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-xs text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
              />
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// ─── Room Card ────────────────────────────────────────────────────────────────

function RoomCard({
  room,
  bots,
  isEditing,
  onToggleEdit,
  onUpdate,
  onRemove,
}: {
  room: ProposalRoom
  bots: ProposalBot[]
  isEditing: boolean
  onToggleEdit: () => void
  onUpdate: (updates: Partial<ProposalRoom>) => void
  onRemove?: () => void
}) {
  const modeLabel = MODE_OPTIONS.find((m) => m.value === room.responseMode)?.label || room.responseMode

  const assignedBots = bots.filter((b) => room.botTempIds.includes(b.tempId))
  const botDisplay =
    room.responseMode === 'chain'
      ? assignedBots.map((b) => b.name).join(' → ')
      : assignedBots.map((b) => b.name).join(', ')

  const toggleBot = (tempId: string) => {
    const current = room.botTempIds
    if (current.includes(tempId)) {
      onUpdate({ botTempIds: current.filter((id) => id !== tempId) })
    } else {
      onUpdate({ botTempIds: [...current, tempId] })
    }
  }

  return (
    <div
      className={cn(
        'rounded-xl border transition-all',
        isEditing
          ? 'border-cachi-500/50 bg-[var(--color-bg-primary)]'
          : 'border-[var(--color-border-primary)] bg-[var(--color-bg-secondary)]',
      )}
    >
      {/* Header */}
      <div className="flex items-center justify-between p-3">
        <div className="min-w-0 flex-1">
          {isEditing ? (
            <input
              value={room.name}
              onChange={(e) => onUpdate({ name: e.target.value })}
              className="w-full bg-transparent text-sm font-semibold text-[var(--color-text-primary)] outline-none focus:underline"
            />
          ) : (
            <p className="text-sm font-semibold text-[var(--color-text-primary)]">{room.name}</p>
          )}
          <p className="mt-0.5 text-xs text-[var(--color-text-secondary)]">
            Mode: {modeLabel}
            {assignedBots.length > 0 && <> &middot; Bots: {botDisplay}</>}
          </p>
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={onToggleEdit}
            className="rounded-md p-1.5 text-[var(--color-text-tertiary)] transition-colors hover:bg-[var(--color-hover-bg)] hover:text-[var(--color-text-primary)]"
          >
            {isEditing ? <ChevronUp className="h-4 w-4" /> : <Pencil className="h-3.5 w-3.5" />}
          </button>
          {onRemove && (
            <button
              onClick={onRemove}
              className="rounded-md p-1.5 text-[var(--color-text-tertiary)] transition-colors hover:bg-red-500/10 hover:text-red-400"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </button>
          )}
        </div>
      </div>

      {/* Expanded edit form */}
      {isEditing && (
        <div className="space-y-4 border-t border-[var(--color-border-primary)] p-4">
          <div>
            <label className="mb-1 block text-xs font-medium text-[var(--color-text-secondary)]">
              Description
            </label>
            <input
              value={room.description}
              onChange={(e) => onUpdate({ description: e.target.value })}
              className="w-full rounded-lg border border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] px-3 py-2 text-sm text-[var(--color-text-primary)] outline-none focus:border-[var(--color-border-focus)]"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--color-text-secondary)]">
              Response Mode
            </label>
            <div className="grid grid-cols-4 gap-2">
              {MODE_OPTIONS.map((m) => (
                <button
                  key={m.value}
                  onClick={() => onUpdate({ responseMode: m.value })}
                  className={cn(
                    'rounded-lg border px-2 py-1.5 text-left transition-all',
                    room.responseMode === m.value
                      ? 'border-cachi-500 bg-cachi-500/10'
                      : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]',
                  )}
                >
                  <p className={cn(
                    'text-xs font-medium',
                    room.responseMode === m.value
                      ? 'text-cachi-400'
                      : 'text-[var(--color-text-primary)]',
                  )}>
                    {m.label}
                  </p>
                  <p className="mt-0.5 text-[10px] text-[var(--color-text-tertiary)]">
                    {m.description}
                  </p>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-xs font-medium text-[var(--color-text-secondary)]">
              Bots in this room
            </label>
            <div className="flex flex-wrap gap-2">
              {bots.map((bot) => {
                const isAssigned = room.botTempIds.includes(bot.tempId)
                return (
                  <button
                    key={bot.tempId}
                    onClick={() => toggleBot(bot.tempId)}
                    className={cn(
                      'flex items-center gap-2 rounded-lg border px-3 py-2 text-left transition-all',
                      isAssigned
                        ? 'border-cachi-500 bg-cachi-500/10'
                        : 'border-[var(--color-border-secondary)] bg-[var(--color-bg-secondary)] hover:border-[var(--color-border-secondary)]',
                    )}
                  >
                    <BotIconRenderer icon={bot.icon} size={14} color={isAssigned ? bot.color : undefined} />
                    <span
                      className={cn(
                        'text-xs font-medium',
                        isAssigned ? 'text-cachi-400' : 'text-[var(--color-text-secondary)]',
                      )}
                    >
                      {bot.name}
                    </span>
                  </button>
                )
              })}
            </div>
            {room.botTempIds.length < 2 && (
              <p className="mt-1.5 text-[10px] text-amber-400">
                Each room needs at least 2 bots
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

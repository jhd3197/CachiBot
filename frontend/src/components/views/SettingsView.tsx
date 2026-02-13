import { useState, useEffect, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Save,
  Trash2,
  AlertTriangle,
  Palette,
  Brain,
  RotateCcw,
  RefreshCw,
  Download,
  ExternalLink,
  Search,
  Sparkles,
  ToggleLeft,
  ToggleRight,
  X,
  Image,
  Cpu,
  AudioLines,
  Layers,
  Mic,
} from 'lucide-react'
import { useBotStore, DEFAULT_BOT_SETTINGS, getEffectiveModels } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { BotIconRenderer, BOT_ICON_OPTIONS } from '../common/BotIconRenderer'
import { ModelSelect } from '../common/ModelSelect'
import { useModelsStore } from '../../stores/models'
import {
  DocumentUploader,
  DocumentList,
  InstructionsEditor,
  NotesManager,
  NoteEditorDialog,
  KnowledgeStats as KnowledgeStatsComponent,
  KnowledgeSearch,
  DocumentChunksDialog,
} from '../knowledge'
import { BotConnectionsPanel } from '../settings/BotConnectionsPanel'
import { useVoiceStore } from '../../stores/voice'
import { cn } from '../../lib/utils'
import * as skillsApi from '../../api/skills'
import type { Bot as BotType, BotModels, SkillDefinition } from '../../types'

const COLOR_OPTIONS = [
  '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899',
  '#f59e0b', '#ef4444', '#06b6d4', '#84cc16',
]

export function SettingsView() {
  const navigate = useNavigate()
  const { getActiveBot, updateBot, deleteBot } = useBotStore()
  const { settingsSection } = useUIStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [saved, setSaved] = useState(false)

  const activeBot = getActiveBot()

  const [form, setForm] = useState<Partial<BotType>>({
    name: activeBot?.name || '',
    description: activeBot?.description || '',
    icon: activeBot?.icon,
    color: activeBot?.color,
    model: activeBot?.model || '',
    models: activeBot ? getEffectiveModels(activeBot) : undefined,
    systemPrompt: activeBot?.systemPrompt || '',
    capabilities: activeBot?.capabilities,
  })

  useEffect(() => {
    if (activeBot) {
      setForm({
        name: activeBot.name,
        description: activeBot.description,
        icon: activeBot.icon,
        color: activeBot.color,
        model: activeBot.model,
        models: getEffectiveModels(activeBot),
        systemPrompt: activeBot.systemPrompt,
        capabilities: activeBot.capabilities,
      })
    }
  }, [activeBot?.id])

  if (!activeBot) return null

  const handleSave = () => {
    // Exclude capabilities from form save — those are toggled live in Skills section
    const { capabilities: _caps, ...formWithoutCaps } = form
    void _caps
    updateBot(activeBot.id, formWithoutCaps)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleDelete = () => {
    const botId = activeBot.id
    setShowDeleteConfirm(false)
    navigate('/dashboard')
    deleteBot(botId)
  }

  const sectionTitles = {
    general: 'General',
    knowledge: 'Knowledge',
    skills: 'Skills',
    connections: 'Connections',
    voice: 'Voice',
    advanced: 'Advanced',
    danger: 'Danger Zone',
  }

  return (
    <div className="flex h-full flex-col bg-zinc-100 dark:bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-800 px-6 py-3">
        <h1 className="text-lg font-semibold text-zinc-100">
          {sectionTitles[settingsSection]}
        </h1>
        {settingsSection !== 'danger' && (
          <button
            onClick={handleSave}
            className={cn(
              'flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors',
              saved
                ? 'bg-green-600 text-white'
                : 'bg-cachi-600 text-white hover:bg-cachi-500'
            )}
          >
            <Save className="h-4 w-4" />
            {saved ? 'Saved!' : 'Save'}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="mx-auto max-w-2xl">
          {settingsSection === 'general' && (
            <GeneralSection
              form={form}
              setForm={setForm}
              onReset={() => {
                const appDefault = useModelsStore.getState().defaultModel
                setForm({
                  name: DEFAULT_BOT_SETTINGS.name,
                  description: DEFAULT_BOT_SETTINGS.description,
                  icon: DEFAULT_BOT_SETTINGS.icon,
                  color: DEFAULT_BOT_SETTINGS.color,
                  model: appDefault,
                  models: { default: appDefault, image: '', audio: '', structured: '' },
                  systemPrompt: DEFAULT_BOT_SETTINGS.systemPrompt,
                })
              }}
            />
          )}
          {settingsSection === 'knowledge' && (
            <KnowledgeSection botId={activeBot.id} />
          )}
          {settingsSection === 'skills' && (
            <SkillsSection botId={activeBot.id} />
          )}
          {settingsSection === 'connections' && (
            <ConnectionsSection botId={activeBot.id} />
          )}
          {settingsSection === 'voice' && (
            <VoiceSettingsSection botId={activeBot.id} />
          )}
          {settingsSection === 'advanced' && (
            <AdvancedSection />
          )}
          {settingsSection === 'danger' && (
            <DangerSection
              botId={activeBot.id}
              botName={activeBot.name}
              isDefault={activeBot.id === 'default'}
              onDelete={() => setShowDeleteConfirm(true)}
            />
          )}
        </div>
      </div>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="text-lg font-bold">Delete Bot</h2>
            </div>
            <p className="mb-6 text-zinc-400">
              Are you sure you want to delete <strong className="text-zinc-200">{activeBot.name}</strong>?
              This action cannot be undone.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
              >
                Delete Bot
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

// =============================================================================
// SECTION COMPONENTS
// =============================================================================

interface GeneralSectionProps {
  form: Partial<BotType>
  setForm: (form: Partial<BotType>) => void
  onReset: () => void
}

function GeneralSection({ form, setForm, onReset }: GeneralSectionProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const { imageGroups, audioGroups } = useModelsStore()
  const { getActiveBot, updateBot } = useBotStore()
  const activeBot = getActiveBot()

  const toggleCapability = (key: string, value: boolean) => {
    if (!activeBot) return
    const caps = { ...(activeBot.capabilities || {}), [key]: value }
    updateBot(activeBot.id, { capabilities: caps as unknown as BotType['capabilities'] })
  }

  return (
    <div className="space-y-6">
      {/* Reset to Default button */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowResetConfirm(true)}
          className="flex items-center gap-2 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 transition-colors hover:border-zinc-600 hover:text-zinc-300"
        >
          <RotateCcw className="h-3 w-3" />
          Reset to Default
        </button>
      </div>

      {/* Reset confirmation modal */}
      {showResetConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-amber-400">
              <RotateCcw className="h-6 w-6" />
              <h2 className="text-lg font-bold">Reset General Settings</h2>
            </div>
            <p className="mb-6 text-zinc-400">
              This will reset the bot's name, description, icon, color, model, and system prompt to their default values.
              <br /><br />
              <strong className="text-zinc-200">Connections will not be affected.</strong>
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowResetConfirm(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onReset()
                  setShowResetConfirm(false)
                }}
                className="rounded-lg bg-amber-600 px-4 py-2 text-sm font-medium text-white hover:bg-amber-500"
              >
                Reset Settings
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-300">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-cachi-500"
          />
        </div>

        <div>
          <label className="mb-2 block text-sm font-medium text-zinc-300">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-2 text-zinc-100 outline-none focus:border-cachi-500"
          />
        </div>
      </div>

      {/* Models */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Cpu className="h-4 w-4 text-zinc-400" />
          Models
        </h3>
        <div className="space-y-4">
          <div>
            <label className="mb-2 flex items-center gap-2 text-sm font-medium text-zinc-300">
              <Layers className="h-3.5 w-3.5 text-zinc-500" />
              Default Model
            </label>
            <ModelSelect
              value={form.models?.default || form.model || ''}
              onChange={(model) => {
                const models: BotModels = { ...(form.models || { default: '' }), default: model }
                setForm({ ...form, model, models })
              }}
              placeholder="Use system default"
              className="w-full"
              filter={(m) => !m.supports_image_generation && !m.supports_audio}
            />
            <p className="mt-1 text-xs text-zinc-500">
              Main conversational model. Leave empty to use the system default.
            </p>
          </div>

          {/* Image Generation toggle + model */}
          <div>
            <CapabilityToggle
              icon={<Image className="h-4 w-4" />}
              label="Image Generation"
              description="Generate images via DALL-E, Imagen, Stability AI"
              enabled={!!activeBot?.capabilities?.imageGeneration}
              onToggle={(v) => toggleCapability('imageGeneration', v)}
            />
            {!!activeBot?.capabilities?.imageGeneration && (
              <div className="mt-2 ml-7 pl-3 border-l-2 border-cachi-500/30">
                <label className="mb-1.5 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <Image className="h-3 w-3 text-zinc-500" />
                  Image Model
                </label>
                <ModelSelect
                  value={form.models?.image || ''}
                  onChange={(model) => {
                    const models: BotModels = { ...(form.models || { default: '' }), image: model }
                    setForm({ ...form, models })
                  }}
                  placeholder="Use plugin default"
                  className="w-full"
                  groups={imageGroups}
                />
                <p className="mt-1 text-xs text-zinc-500">
                  e.g. openai/dall-e-3, google/imagen-3, stability/sd3-large
                </p>
              </div>
            )}
          </div>

          {/* Audio Generation toggle + model */}
          <div>
            <CapabilityToggle
              icon={<AudioLines className="h-4 w-4" />}
              label="Audio Generation"
              description="Text-to-speech and speech-to-text via OpenAI, ElevenLabs"
              enabled={!!activeBot?.capabilities?.audioGeneration}
              onToggle={(v) => toggleCapability('audioGeneration', v)}
            />
            {!!activeBot?.capabilities?.audioGeneration && (
              <div className="mt-2 ml-7 pl-3 border-l-2 border-cachi-500/30">
                <label className="mb-1.5 flex items-center gap-2 text-xs font-medium text-zinc-400">
                  <AudioLines className="h-3 w-3 text-zinc-500" />
                  Audio Model
                </label>
                <ModelSelect
                  value={form.models?.audio || ''}
                  onChange={(model) => {
                    const models: BotModels = { ...(form.models || { default: '' }), audio: model }
                    setForm({ ...form, models })
                  }}
                  placeholder="Use plugin default"
                  className="w-full"
                  groups={audioGroups}
                />
                <p className="mt-1 text-xs text-zinc-500">
                  e.g. openai/tts-1, openai/whisper-1, elevenlabs/eleven_multilingual_v2
                </p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Appearance */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Palette className="h-4 w-4 text-zinc-400" />
          Appearance
        </h3>
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-xs text-zinc-500">Icon</label>
            <div className="flex flex-wrap gap-2">
              {BOT_ICON_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setForm({ ...form, icon: option.id })}
                  title={option.label}
                  className={cn(
                    'flex h-10 w-10 items-center justify-center rounded-lg border transition-all',
                    form.icon === option.id
                      ? 'border-cachi-500 bg-cachi-500/20'
                      : 'border-zinc-700 bg-zinc-800 hover:border-zinc-600'
                  )}
                >
                  <BotIconRenderer icon={option.id} size={20} />
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="mb-2 block text-xs text-zinc-500">Color</label>
            <div className="flex flex-wrap gap-2">
              {COLOR_OPTIONS.map((color) => (
                <button
                  key={color}
                  onClick={() => setForm({ ...form, color })}
                  className={cn(
                    'h-8 w-8 rounded-lg border-2 transition-all',
                    form.color === color
                      ? 'border-white scale-110'
                      : 'border-transparent hover:scale-105'
                  )}
                  style={{ backgroundColor: color }}
                />
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* System Prompt */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-4 flex items-center gap-2 text-sm font-medium text-zinc-200">
          <Brain className="h-4 w-4 text-zinc-400" />
          System Prompt
        </h3>
        <textarea
          value={form.systemPrompt}
          onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
          rows={6}
          placeholder="Define the bot's personality and behavior..."
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-4 py-3 font-mono text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
        />
      </div>
    </div>
  )
}

function KnowledgeSection({ botId }: { botId: string }) {
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [showNoteEditor, setShowNoteEditor] = useState(false)
  const [chunksDoc, setChunksDoc] = useState<{ id: string; filename: string } | null>(null)

  const handleEditNote = (noteId: string) => {
    setEditingNoteId(noteId)
    setShowNoteEditor(true)
  }

  const handleNewNote = () => {
    setEditingNoteId(null)
    setShowNoteEditor(true)
  }

  const handleCloseNoteEditor = () => {
    setShowNoteEditor(false)
    setEditingNoteId(null)
  }

  return (
    <div className="space-y-6">
      {/* Stats overview */}
      <KnowledgeStatsComponent botId={botId} />

      {/* Notes section (main feature) */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-2 text-sm font-medium text-zinc-200">Notes & Memory</h3>
        <p className="mb-4 text-xs text-zinc-500">
          Save notes for your bot to remember. The bot can also create notes during conversations.
        </p>
        <NotesManager
          botId={botId}
          onEditNote={handleEditNote}
          onNewNote={handleNewNote}
        />
      </div>

      {/* Search tester */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-2 text-sm font-medium text-zinc-200">Search Knowledge</h3>
        <p className="mb-4 text-xs text-zinc-500">
          Test search across documents and notes.
        </p>
        <KnowledgeSearch botId={botId} />
      </div>

      {/* Documents section */}
      <div className="border-t border-zinc-800 pt-6">
        <h3 className="mb-2 text-sm font-medium text-zinc-200">Documents</h3>
        <p className="mb-4 text-xs text-zinc-500">
          Upload documents to give your bot specialized knowledge.
        </p>
        <DocumentUploader botId={botId} />
        <div className="mt-4">
          <DocumentList
            botId={botId}
            onViewChunks={(docId, filename) => setChunksDoc({ id: docId, filename })}
          />
        </div>
      </div>

      {/* Instructions editor */}
      <div className="border-t border-zinc-800 pt-6">
        <InstructionsEditor botId={botId} />
      </div>

      {/* Note editor dialog */}
      <NoteEditorDialog
        botId={botId}
        noteId={editingNoteId}
        open={showNoteEditor}
        onClose={handleCloseNoteEditor}
      />

      {/* Document chunks dialog */}
      {chunksDoc && (
        <DocumentChunksDialog
          botId={botId}
          documentId={chunksDoc.id}
          filename={chunksDoc.filename}
          open={!!chunksDoc}
          onClose={() => setChunksDoc(null)}
        />
      )}
    </div>
  )
}

function SkillsSection({ botId }: { botId: string }) {
  const [allSkills, setAllSkills] = useState<SkillDefinition[]>([])
  const [activeSkillIds, setActiveSkillIds] = useState<Set<string>>(new Set())
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [showInstallDialog, setShowInstallDialog] = useState(false)

  // Load skills and bot's active skills
  const loadData = useCallback(async () => {
    try {
      setError(null)
      const [skills, botSkillIds] = await Promise.all([
        skillsApi.getSkills(),
        skillsApi.getBotSkillIds(botId),
      ])
      setAllSkills(skills)
      setActiveSkillIds(new Set(botSkillIds))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load skills')
    } finally {
      setLoading(false)
    }
  }, [botId])

  useEffect(() => {
    loadData()
  }, [loadData])

  // Refresh skills from filesystem
  const handleRefresh = async () => {
    setRefreshing(true)
    try {
      const skills = await skillsApi.refreshSkills()
      setAllSkills(skills)
      setError(null)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to refresh skills')
    } finally {
      setRefreshing(false)
    }
  }

  // Toggle skill activation
  const handleToggle = async (skillId: string, activate: boolean) => {
    try {
      if (activate) {
        await skillsApi.activateSkill(botId, skillId)
        setActiveSkillIds((prev) => new Set([...prev, skillId]))
      } else {
        await skillsApi.deactivateSkill(botId, skillId)
        setActiveSkillIds((prev) => {
          const next = new Set(prev)
          next.delete(skillId)
          return next
        })
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to toggle skill')
    }
  }

  // Delete skill
  const handleDelete = async (skillId: string) => {
    if (!confirm('Are you sure you want to delete this skill?')) return
    try {
      await skillsApi.deleteSkill(skillId)
      setAllSkills((prev) => prev.filter((s) => s.id !== skillId))
      setActiveSkillIds((prev) => {
        const next = new Set(prev)
        next.delete(skillId)
        return next
      })
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to delete skill')
    }
  }

  // Handle skill installation
  const handleInstalled = (skill: SkillDefinition) => {
    setAllSkills((prev) => [...prev, skill])
    setShowInstallDialog(false)
  }

  // Filter skills by search query
  const filteredSkills = allSkills.filter((skill) => {
    if (!searchQuery) return true
    const query = searchQuery.toLowerCase()
    return (
      skill.name.toLowerCase().includes(query) ||
      skill.description.toLowerCase().includes(query) ||
      skill.tags.some((tag) => tag.toLowerCase().includes(query))
    )
  })

  // Sort: active skills first, then by name
  const sortedSkills = [...filteredSkills].sort((a, b) => {
    const aActive = activeSkillIds.has(a.id)
    const bActive = activeSkillIds.has(b.id)
    if (aActive && !bActive) return -1
    if (!aActive && bActive) return 1
    return a.name.localeCompare(b.name)
  })

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="text-sm text-zinc-500">Loading skills...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">

      {/* Error display */}
      {error && (
        <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
          {error}
        </div>
      )}

      {/* Header with actions */}
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-zinc-400">
          Activate skills to give your bot specialized behaviors and capabilities.
        </p>
        <div className="flex gap-2">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="flex items-center gap-1.5 rounded-lg border border-zinc-700 px-3 py-1.5 text-xs text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200 disabled:opacity-50"
            title="Rescan skill directories"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={() => setShowInstallDialog(true)}
            className="flex items-center gap-1.5 rounded-lg bg-cachi-600 px-3 py-1.5 text-xs text-white hover:bg-cachi-500"
          >
            <Download className="h-3.5 w-3.5" />
            Install
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search skills..."
          className="w-full rounded-lg border border-zinc-700 bg-zinc-800 py-2 pl-9 pr-3 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-cachi-500 focus:outline-none"
        />
      </div>

      {/* Skills list */}
      {sortedSkills.length > 0 ? (
        <div className="space-y-3">
          {sortedSkills.map((skill) => (
            <SkillCard
              key={skill.id}
              skill={skill}
              isActive={activeSkillIds.has(skill.id)}
              onToggle={handleToggle}
              onDelete={handleDelete}
              showDelete={skill.source === 'local' || skill.source === 'installed'}
            />
          ))}
        </div>
      ) : searchQuery ? (
        <div className="rounded-lg border border-dashed border-zinc-700 p-8 text-center">
          <p className="text-sm text-zinc-500">No skills match your search.</p>
        </div>
      ) : (
        <div className="rounded-lg border border-dashed border-zinc-700 p-8 text-center">
          <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-zinc-800">
            <Sparkles className="h-6 w-6 text-zinc-500" />
          </div>
          <h3 className="mb-2 font-medium text-zinc-300">No skills available</h3>
          <p className="mb-4 text-sm text-zinc-500">
            Create SKILL.md files in <code className="text-zinc-400">~/.claude/skills/</code>
            {' '}or install from a URL.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => setShowInstallDialog(true)}
              className="flex items-center gap-1.5 rounded-lg bg-cachi-600 px-4 py-2 text-sm text-white hover:bg-cachi-500"
            >
              <Download className="h-4 w-4" />
              Install Skill
            </button>
            <a
              href="https://skills.sh"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
            >
              <ExternalLink className="h-4 w-4" />
              Browse skills.sh
            </a>
          </div>
        </div>
      )}

      {/* Active skills count */}
      {activeSkillIds.size > 0 && (
        <div className="text-center text-xs text-zinc-500">
          {activeSkillIds.size} skill{activeSkillIds.size !== 1 ? 's' : ''} active
        </div>
      )}

      {/* Install dialog */}
      {showInstallDialog && (
        <SkillInstallDialog
          onClose={() => setShowInstallDialog(false)}
          onInstalled={handleInstalled}
        />
      )}
    </div>
  )
}

// Capability toggle component
interface CapabilityToggleProps {
  icon: React.ReactNode
  label: string
  description: string
  enabled: boolean
  onToggle: (enabled: boolean) => void
}

function CapabilityToggle({ icon, label, description, enabled, onToggle }: CapabilityToggleProps) {
  return (
    <div
      className={cn(
        'flex items-center justify-between rounded-lg border p-3 transition-colors',
        enabled
          ? 'border-cachi-500/50 bg-cachi-500/5'
          : 'border-zinc-700 bg-zinc-800/30'
      )}
    >
      <div className="flex items-center gap-3">
        <div className={cn('text-zinc-400', enabled && 'text-cachi-500')}>
          {icon}
        </div>
        <div>
          <div className="text-sm font-medium text-zinc-200">{label}</div>
          <div className="text-xs text-zinc-500">{description}</div>
        </div>
      </div>
      <button
        onClick={() => onToggle(!enabled)}
        className={enabled ? 'text-cachi-500' : 'text-zinc-600'}
      >
        {enabled ? <ToggleRight className="h-7 w-7" /> : <ToggleLeft className="h-7 w-7" />}
      </button>
    </div>
  )
}

// Skill card component
interface SkillCardProps {
  skill: SkillDefinition
  isActive: boolean
  onToggle: (skillId: string, activate: boolean) => void
  onDelete: (skillId: string) => void
  showDelete: boolean
}

function SkillCard({ skill, isActive, onToggle, onDelete, showDelete }: SkillCardProps) {
  return (
    <div
      className={cn(
        'rounded-lg border p-4 transition-colors',
        isActive
          ? 'border-cachi-500/50 bg-cachi-500/5'
          : 'border-zinc-700 bg-zinc-800/30'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="font-medium text-zinc-200">{skill.name}</h3>
            {skill.version && (
              <span className="rounded bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-400">
                v{skill.version}
              </span>
            )}
            <span className="rounded bg-zinc-700 px-1.5 py-0.5 text-xs text-zinc-500">
              {skill.source}
            </span>
          </div>
          <p className="mt-1 text-sm text-zinc-400">{skill.description}</p>
          {skill.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {skill.tags.map((tag) => (
                <span
                  key={tag}
                  className="rounded bg-zinc-800 px-1.5 py-0.5 text-xs text-zinc-500"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {skill.requiresTools.length > 0 && (
            <div className="mt-2 text-xs text-zinc-500">
              Requires: {skill.requiresTools.join(', ')}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {showDelete && (
            <button
              onClick={() => onDelete(skill.id)}
              className="rounded p-1 text-zinc-500 hover:bg-zinc-700 hover:text-red-400"
              title="Delete skill"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => onToggle(skill.id, !isActive)}
            className={isActive ? 'text-cachi-500' : 'text-zinc-600'}
          >
            {isActive ? <ToggleRight className="h-8 w-8" /> : <ToggleLeft className="h-8 w-8" />}
          </button>
        </div>
      </div>
    </div>
  )
}

// Skill install dialog component
interface SkillInstallDialogProps {
  onClose: () => void
  onInstalled: (skill: SkillDefinition) => void
}

function SkillInstallDialog({ onClose, onInstalled }: SkillInstallDialogProps) {
  const [url, setUrl] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleInstall = async () => {
    if (!url.trim()) return
    setLoading(true)
    setError(null)
    try {
      const skill = await skillsApi.installSkill(url.trim())
      onInstalled(skill)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to install skill')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-xl bg-zinc-900 shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800 p-4">
          <h2 className="text-lg font-semibold text-zinc-100">Install Skill</h2>
          <button
            onClick={onClose}
            className="rounded-lg p-2 text-zinc-400 hover:bg-zinc-800 hover:text-zinc-200"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="p-4 space-y-4">
          {error && (
            <div className="rounded-lg border border-red-500/50 bg-red-500/10 p-3 text-sm text-red-400">
              {error}
            </div>
          )}
          <div>
            <label className="mb-2 block text-sm font-medium text-zinc-300">
              Skill URL or skills.sh identifier
            </label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://... or skills.sh/skill-name"
              className="w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 py-2 text-sm text-zinc-100 placeholder:text-zinc-500 focus:border-cachi-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-zinc-500">
              Enter a URL to a skill markdown file or a skills.sh identifier.
            </p>
          </div>
        </div>
        <div className="flex justify-end gap-3 border-t border-zinc-800 p-4">
          <button
            onClick={onClose}
            className="rounded-lg border border-zinc-700 px-4 py-2 text-sm text-zinc-300 hover:bg-zinc-800"
          >
            Cancel
          </button>
          <button
            onClick={handleInstall}
            disabled={!url.trim() || loading}
            className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500 disabled:opacity-50"
          >
            {loading ? (
              <>
                <RefreshCw className="h-4 w-4 animate-spin" />
                Installing...
              </>
            ) : (
              <>
                <Download className="h-4 w-4" />
                Install
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  )
}

function ConnectionsSection({ botId }: { botId: string }) {
  return (
    <div className="space-y-6">
      <div>
        <p className="mb-4 text-sm text-zinc-400">
          Connect your bot to messaging platforms like Telegram and Discord to send and receive messages.
        </p>
        <BotConnectionsPanel botId={botId} />
      </div>
    </div>
  )
}

// =============================================================================
// VOICE SETTINGS SECTION
// =============================================================================

const TTS_VOICES = ['alloy', 'echo', 'fable', 'onyx', 'nova', 'shimmer']

const STT_LANGUAGES = [
  { value: '', label: 'Auto-detect' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Spanish' },
  { value: 'fr', label: 'French' },
  { value: 'de', label: 'German' },
  { value: 'pt', label: 'Portuguese' },
  { value: 'ja', label: 'Japanese' },
  { value: 'zh', label: 'Chinese' },
  { value: 'ko', label: 'Korean' },
  { value: 'it', label: 'Italian' },
  { value: 'ru', label: 'Russian' },
  { value: 'ar', label: 'Arabic' },
]

function VoiceSettingsSection({ botId: _botId }: { botId: string }) {
  const { getActiveBot } = useBotStore()
  const { voiceSettings, updateVoiceSettings } = useVoiceStore()
  const activeBot = getActiveBot()
  void _botId

  const audioEnabled = !!activeBot?.capabilities?.audioGeneration

  if (!audioEnabled) {
    return (
      <div className="space-y-4">
        <div className="flex items-center gap-3 rounded-xl border border-amber-500/30 bg-amber-500/5 p-4">
          <AudioLines className="h-5 w-5 text-amber-400" />
          <div>
            <p className="text-sm font-medium text-amber-300">Audio Generation Required</p>
            <p className="mt-1 text-xs text-zinc-500">
              Enable the "Audio Generation" capability in the General settings to use voice features.
            </p>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* TTS Voice */}
      <div>
        <label className="mb-2 flex items-center gap-2 text-sm font-medium text-zinc-300">
          <Mic className="h-4 w-4 text-zinc-400" />
          TTS Voice
        </label>
        <div className="flex flex-wrap gap-2">
          {TTS_VOICES.map((voice) => (
            <button
              key={voice}
              onClick={() => updateVoiceSettings({ ttsVoice: voice })}
              className={cn(
                'rounded-lg border px-3 py-1.5 text-sm capitalize transition-all',
                voiceSettings.ttsVoice === voice
                  ? 'border-cachi-500 bg-cachi-500/20 text-cachi-300'
                  : 'border-zinc-700 bg-zinc-800 text-zinc-400 hover:border-zinc-600',
              )}
            >
              {voice}
            </button>
          ))}
        </div>
        <p className="mt-1 text-xs text-zinc-500">
          For ElevenLabs, set a voice ID in the input below instead.
        </p>
        <input
          type="text"
          placeholder="Custom voice ID (ElevenLabs)"
          value={voiceSettings.ttsVoice}
          onChange={(e) => updateVoiceSettings({ ttsVoice: e.target.value })}
          className="mt-2 h-9 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-100 placeholder-zinc-600 outline-none focus:border-cachi-500"
        />
      </div>

      {/* Speech Speed */}
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">
          Speech Speed
        </label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0.5"
            max="2"
            step="0.1"
            value={voiceSettings.ttsSpeed}
            onChange={(e) => updateVoiceSettings({ ttsSpeed: parseFloat(e.target.value) })}
            className="flex-1"
          />
          <span className="w-12 text-center text-sm text-zinc-400">{voiceSettings.ttsSpeed}x</span>
        </div>
      </div>

      {/* STT Language */}
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">
          Speech Recognition Language
        </label>
        <select
          value={voiceSettings.sttLanguage || ''}
          onChange={(e) => updateVoiceSettings({ sttLanguage: e.target.value || null })}
          className="h-10 w-full rounded-lg border border-zinc-700 bg-zinc-800 px-3 text-sm text-zinc-100 outline-none focus:border-cachi-500"
        >
          {STT_LANGUAGES.map((lang) => (
            <option key={lang.value} value={lang.value}>{lang.label}</option>
          ))}
        </select>
      </div>

      {/* Toggles */}
      <div className="space-y-4 border-t border-zinc-800 pt-6">
        <label className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-300">Enable Interruption</p>
            <p className="text-xs text-zinc-500">Allow interrupting the bot while it speaks</p>
          </div>
          <button
            onClick={() => updateVoiceSettings({ enableInterruption: !voiceSettings.enableInterruption })}
            className="text-zinc-400"
          >
            {voiceSettings.enableInterruption
              ? <ToggleRight className="h-6 w-6 text-cachi-500" />
              : <ToggleLeft className="h-6 w-6" />}
          </button>
        </label>

        <label className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-zinc-300">Save Transcripts</p>
            <p className="text-xs text-zinc-500">Save voice conversations to chat history</p>
          </div>
          <button
            onClick={() => updateVoiceSettings({ saveTranscripts: !voiceSettings.saveTranscripts })}
            className="text-zinc-400"
          >
            {voiceSettings.saveTranscripts
              ? <ToggleRight className="h-6 w-6 text-cachi-500" />
              : <ToggleLeft className="h-6 w-6" />}
          </button>
        </label>
      </div>
    </div>
  )
}

// =============================================================================
// ADVANCED SECTION
// =============================================================================

function AdvancedSection() {
  return (
    <div className="space-y-6">
      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">Temperature</label>
        <div className="flex items-center gap-4">
          <input
            type="range"
            min="0"
            max="1"
            step="0.1"
            defaultValue="0.7"
            className="flex-1"
          />
          <span className="w-12 text-center text-sm text-zinc-400">0.7</span>
        </div>
        <p className="mt-1 text-xs text-zinc-500">Lower = focused, higher = creative</p>
      </div>

      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">Max Iterations</label>
        <input
          type="number"
          defaultValue={20}
          min={1}
          max={50}
          className="h-10 w-32 rounded-lg border border-zinc-700 bg-zinc-800 px-4 text-zinc-100 outline-none focus:border-cachi-500"
        />
      </div>

      <div>
        <label className="mb-2 block text-sm font-medium text-zinc-300">Approval Mode</label>
        <div className="space-y-2">
          <label className="flex items-center gap-2">
            <input type="radio" name="approval" defaultChecked className="text-cachi-500" />
            <span className="text-sm text-zinc-300">Auto-approve safe actions</span>
          </label>
          <label className="flex items-center gap-2">
            <input type="radio" name="approval" className="text-cachi-500" />
            <span className="text-sm text-zinc-300">Approve all actions</span>
          </label>
        </div>
      </div>
    </div>
  )
}

function DangerSection({
  botId,
  botName,
  isDefault,
  onDelete,
}: {
  botId: string
  botName: string
  isDefault: boolean
  onDelete: () => void
}) {
  const [isExporting, setIsExporting] = useState(false)
  const [exportError, setExportError] = useState<string | null>(null)

  const handleExport = async () => {
    setIsExporting(true)
    setExportError(null)

    try {
      const { exportBot } = await import('../../api/client')
      const data = await exportBot(botId)

      // Create and download the file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${botName.toLowerCase().replace(/\s+/g, '-')}-export.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      setExportError(err instanceof Error ? err.message : 'Failed to export bot')
    } finally {
      setIsExporting(false)
    }
  }

  return (
    <div className="space-y-6">
      {/* Export section */}
      <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-6">
        <h3 className="text-lg font-semibold text-zinc-200">Export Bot</h3>
        <p className="mt-2 text-sm text-zinc-400">
          Download this bot's configuration as a JSON file. You can import it later to recreate the bot.
        </p>
        {exportError && (
          <p className="mt-2 text-sm text-red-400">{exportError}</p>
        )}
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="mt-4 flex items-center gap-2 rounded-lg border border-zinc-600 bg-zinc-800 px-4 py-2 text-sm font-medium text-zinc-200 hover:bg-zinc-700 disabled:opacity-50"
        >
          <Download className="h-4 w-4" />
          {isExporting ? 'Exporting...' : 'Export Configuration'}
        </button>
      </div>

      {/* Delete section */}
      {isDefault ? (
        <div className="rounded-lg border border-zinc-700 bg-zinc-900/50 p-6">
          <h3 className="text-lg font-semibold text-zinc-400">Delete this bot</h3>
          <p className="mt-2 text-sm text-zinc-500">
            The default bot cannot be deleted.
          </p>
        </div>
      ) : (
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-6">
          <h3 className="text-lg font-semibold text-red-400">Delete this bot</h3>
          <p className="mt-2 text-sm text-zinc-400">
            Once you delete <strong className="text-zinc-200">{botName}</strong>, there is no going back.
            All chats, jobs, and tasks will be permanently deleted.
          </p>
          <button
            onClick={onDelete}
            className="mt-4 flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
          >
            <Trash2 className="h-4 w-4" />
            Delete Bot
          </button>
        </div>
      )}
    </div>
  )
}


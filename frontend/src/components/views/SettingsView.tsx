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
  Plus,
  CheckCircle,
  XCircle,
  Terminal,
} from 'lucide-react'
import { getCodingAgents } from '../../api/client'
import { useBotStore, DEFAULT_BOT_SETTINGS, getEffectiveModels } from '../../stores/bots'
import { usePlatformToolsStore } from '../../stores/platform-tools'
import { useUIStore } from '../../stores/ui'
import { useVoiceStore } from '../../stores/voice'
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
import { BotEnvironmentPanel } from '../settings/BotEnvironmentPanel'
import { DeveloperPanel } from '../settings/DeveloperPanel'
import { cn } from '../../lib/utils'
import * as skillsApi from '../../api/skills'
import type { Bot as BotType, BotModels, SkillDefinition, CodingAgentInfo } from '../../types'

const COLOR_OPTIONS = [
  '#22c55e', '#3b82f6', '#8b5cf6', '#ec4899',
  '#f59e0b', '#ef4444', '#06b6d4', '#84cc16',
  '#14b8a6', '#6366f1', '#f43f5e', '#eab308',
  '#a855f7',
]

export function SettingsView() {
  const navigate = useNavigate()
  const { getActiveBot, updateBot, deleteBot } = useBotStore()
  const { settingsSection } = useUIStore()
  const { fetchConfig: fetchPlatformConfig } = usePlatformToolsStore()
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [saved, setSaved] = useState(false)

  // Preload platform tool config for capability/skill filtering
  useEffect(() => {
    fetchPlatformConfig()
  }, [fetchPlatformConfig])

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

  const sectionTitles: Record<string, string> = {
    general: 'General',
    knowledge: 'Knowledge',
    skills: 'Skills',
    connections: 'Connections',
    environment: 'Environment',
    developer: 'Developer',
    danger: 'Danger Zone',
  }

  return (
    <div className="settings-view">
      {/* Header */}
      <div className="settings-view__header">
        <h1 className="settings-view__title">
          {sectionTitles[settingsSection]}
        </h1>
        {settingsSection !== 'danger' && settingsSection !== 'environment' && settingsSection !== 'developer' && (
          <button
            onClick={handleSave}
            className={cn(
              'settings-save-btn flex items-center gap-2',
              saved ? 'settings-save-btn--saved' : 'settings-save-btn--default'
            )}
          >
            <Save className="h-4 w-4" />
            {saved ? 'Saved!' : 'Save'}
          </button>
        )}
      </div>

      {/* Content */}
      <div className="settings-view__content">
        <div className="settings-view__inner">
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
          {settingsSection === 'environment' && (
            <BotEnvironmentPanel botId={activeBot.id} />
          )}
          {settingsSection === 'developer' && (
            <DeveloperPanel botId={activeBot.id} />
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
        <div className="settings-modal">
          <div className="settings-modal__panel">
            <div className="settings-modal__header settings-modal__header--danger">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="settings-modal__header-title">Delete Bot</h2>
            </div>
            <p className="settings-modal__body">
              Are you sure you want to delete <strong className="settings-modal__strong">{activeBot.name}</strong>?
              This action cannot be undone.
            </p>
            <div className="settings-modal__footer">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="settings-modal__cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleDelete}
                className="settings-modal__confirm-btn--danger"
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

function GeneralSection({ form, setForm, onReset }: GeneralSectionProps) {
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const { imageGroups, audioGroups } = useModelsStore()
  const { getActiveBot, updateBot } = useBotStore()
  const { isCapabilityDisabled } = usePlatformToolsStore()
  const { voiceSettings, updateVoiceSettings } = useVoiceStore()
  const activeBot = getActiveBot()

  // Coding agents discovery state
  const [codingAgents, setCodingAgents] = useState<CodingAgentInfo[]>([])
  const [codingAgentsDefault, setCodingAgentsDefault] = useState('')
  const codingAgentEnabled = !!activeBot?.capabilities?.codingAgent

  useEffect(() => {
    if (!codingAgentEnabled) {
      setCodingAgents([])
      return
    }
    let cancelled = false
    getCodingAgents()
      .then((res) => {
        if (!cancelled) {
          setCodingAgents(res.agents)
          setCodingAgentsDefault(res.default_agent)
        }
      })
      .catch(() => {
        if (!cancelled) setCodingAgents([])
      })
    return () => { cancelled = true }
  }, [codingAgentEnabled])

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
          className="settings-reset-btn flex items-center gap-2"
        >
          <RotateCcw className="h-3 w-3" />
          Reset to Default
        </button>
      </div>

      {/* Reset confirmation modal */}
      {showResetConfirm && (
        <div className="settings-modal">
          <div className="settings-modal__panel">
            <div className="settings-modal__header settings-modal__header--warning">
              <RotateCcw className="h-6 w-6" />
              <h2 className="settings-modal__header-title">Reset General Settings</h2>
            </div>
            <p className="settings-modal__body">
              This will reset the bot's name, description, icon, color, model, and system prompt to their default values.
              <br /><br />
              <strong className="settings-modal__strong">Connections will not be affected.</strong>
            </p>
            <div className="settings-modal__footer">
              <button
                onClick={() => setShowResetConfirm(false)}
                className="settings-modal__cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  onReset()
                  setShowResetConfirm(false)
                }}
                className="settings-modal__confirm-btn--warning"
              >
                Reset Settings
              </button>
            </div>
          </div>
        </div>
      )}

      <div className="space-y-4">
        <div>
          <label className="settings-form__label">Name</label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => setForm({ ...form, name: e.target.value })}
            className="settings-form__input"
          />
        </div>

        <div>
          <label className="settings-form__label">Description</label>
          <textarea
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            rows={2}
            className="settings-form__textarea"
          />
        </div>
      </div>

      {/* Models */}
      <div className="settings-section">
        <h3 className="settings-section__heading">
          <Cpu className="h-4 w-4 settings-section__heading-icon" />
          Models
        </h3>
        <div className="space-y-4">
          <div>
            <label className="settings-form__label--small">
              <Layers className="h-3.5 w-3.5" />
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
            <p className="settings-form__hint">
              Main conversational model. Leave empty to use the system default.
            </p>
          </div>

          {/* Image Generation toggle + model (hidden if globally disabled) */}
          {!isCapabilityDisabled('imageGeneration') && (
            <div>
              <CapabilityToggle
                icon={<Image className="h-4 w-4" />}
                label="Image Generation"
                description="Generate images via DALL-E, Imagen, Stability AI"
                enabled={!!activeBot?.capabilities?.imageGeneration}
                onToggle={(v) => toggleCapability('imageGeneration', v)}
              />
              {!!activeBot?.capabilities?.imageGeneration && (
                <div className="settings-capability-nest">
                  <label className="settings-form__label--small">
                    <Image className="h-3 w-3" />
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
                  <p className="settings-form__hint">
                    e.g. openai/dall-e-3, google/imagen-3, stability/sd3-large
                  </p>
                </div>
              )}
            </div>
          )}

          {/* Audio Generation toggle + model + voice settings (hidden if globally disabled) */}
          {!isCapabilityDisabled('audioGeneration') && (
            <div>
              <CapabilityToggle
                icon={<AudioLines className="h-4 w-4" />}
                label="Audio Generation"
                description="Text-to-speech and speech-to-text via OpenAI, ElevenLabs"
                enabled={!!activeBot?.capabilities?.audioGeneration}
                onToggle={(v) => toggleCapability('audioGeneration', v)}
              />
              {!!activeBot?.capabilities?.audioGeneration && (
                <div className="settings-capability-nest space-y-4">
                  {/* Audio Model */}
                  <div>
                    <label className="settings-form__label--small">
                      <AudioLines className="h-3 w-3" />
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
                    <p className="settings-form__hint">
                      e.g. openai/tts-1, openai/whisper-1, elevenlabs/eleven_multilingual_v2
                    </p>
                  </div>

                  {/* TTS Voice */}
                  <div>
                    <label className="settings-form__label--small">
                      <Mic className="h-3 w-3" />
                      TTS Voice
                    </label>
                    <div className="flex flex-wrap gap-1.5">
                      {TTS_VOICES.map((voice) => (
                        <button
                          key={voice}
                          onClick={() => updateVoiceSettings({ ttsVoice: voice })}
                          className={cn(
                            'settings-voice-chip',
                            voiceSettings.ttsVoice === voice
                              ? 'settings-voice-chip--active'
                              : 'settings-voice-chip--inactive',
                          )}
                        >
                          {voice}
                        </button>
                      ))}
                    </div>
                    <input
                      type="text"
                      placeholder="Custom voice ID (ElevenLabs)"
                      value={voiceSettings.ttsVoice}
                      onChange={(e) => updateVoiceSettings({ ttsVoice: e.target.value })}
                      className="settings-form__input--small mt-1.5"
                    />
                  </div>

                  {/* Speech Speed */}
                  <div>
                    <label className="settings-form__label--small">
                      Speech Speed
                    </label>
                    <div className="flex items-center gap-3">
                      <input
                        type="range"
                        min="0.5"
                        max="2"
                        step="0.1"
                        value={voiceSettings.ttsSpeed}
                        onChange={(e) => updateVoiceSettings({ ttsSpeed: parseFloat(e.target.value) })}
                        className="flex-1"
                      />
                      <span className="settings-speed-value">{voiceSettings.ttsSpeed}x</span>
                    </div>
                  </div>

                  {/* STT Language */}
                  <div>
                    <label className="settings-form__label--small">
                      Speech Recognition Language
                    </label>
                    <select
                      value={voiceSettings.sttLanguage || ''}
                      onChange={(e) => updateVoiceSettings({ sttLanguage: e.target.value || null })}
                      className="settings-form__select"
                    >
                      {STT_LANGUAGES.map((lang) => (
                        <option key={lang.value} value={lang.value}>{lang.label}</option>
                      ))}
                    </select>
                  </div>

                  {/* Voice toggles */}
                  <div className="space-y-2">
                    <label className="settings-voice-toggle">
                      <div>
                        <p className="settings-voice-toggle__label">Enable Interruption</p>
                        <p className="settings-voice-toggle__sublabel">Allow interrupting the bot while it speaks</p>
                      </div>
                      <button
                        onClick={() => updateVoiceSettings({ enableInterruption: !voiceSettings.enableInterruption })}
                        className="settings-voice-toggle__btn"
                      >
                        {voiceSettings.enableInterruption
                          ? <ToggleRight className="h-5 w-5 text-cachi-500" />
                          : <ToggleLeft className="h-5 w-5" />}
                      </button>
                    </label>

                    <label className="settings-voice-toggle">
                      <div>
                        <p className="settings-voice-toggle__label">Save Transcripts</p>
                        <p className="settings-voice-toggle__sublabel">Save voice conversations to chat history</p>
                      </div>
                      <button
                        onClick={() => updateVoiceSettings({ saveTranscripts: !voiceSettings.saveTranscripts })}
                        className="settings-voice-toggle__btn"
                      >
                        {voiceSettings.saveTranscripts
                          ? <ToggleRight className="h-5 w-5 text-cachi-500" />
                          : <ToggleLeft className="h-5 w-5" />}
                      </button>
                    </label>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Coding Agent toggle (hidden if globally disabled) */}
          {!isCapabilityDisabled('codingAgent') && (
            <CapabilityToggle
              icon={<Cpu className="h-4 w-4" />}
              label="Coding Agents"
              description="Spawn Claude Code, Codex, or Gemini CLI to autonomously write code"
              enabled={!!activeBot?.capabilities?.codingAgent}
              onToggle={(v) => toggleCapability('codingAgent', v)}
            />
          )}

          {/* Coding Agents status panel (shown when enabled) */}
          {codingAgentEnabled && codingAgents.length > 0 && (
            <div className="settings-coding-agents">
              <div className="settings-coding-agents__header">
                <Terminal className="h-4 w-4" />
                <span>Available Coding Agents</span>
              </div>
              <div className="settings-coding-agents__list">
                {codingAgents.map((agent) => (
                  <div key={agent.id} className="settings-coding-agents__item">
                    <div className="settings-coding-agents__status">
                      {agent.available
                        ? <CheckCircle className="h-4 w-4 text-green-500" />
                        : <XCircle className="h-4 w-4 text-red-400" />}
                    </div>
                    <div className="settings-coding-agents__info">
                      <span className="settings-coding-agents__name">{agent.name}</span>
                      <span className="settings-coding-agents__binary">
                        {agent.custom_path ? agent.binary : agent.id}
                      </span>
                    </div>
                    {agent.id === codingAgentsDefault && (
                      <span className="settings-coding-agents__badge">default</span>
                    )}
                  </div>
                ))}
              </div>
              <div className="settings-coding-agents__default">
                <label className="text-xs text-[var(--color-text-secondary)]">Default agent for @mentions</label>
                <select
                  value={
                    (activeBot?.toolConfigs?.coding_agent?.defaultAgent as string)
                    || codingAgentsDefault
                  }
                  onChange={(e) => {
                    if (!activeBot) return
                    const current = activeBot.toolConfigs || {}
                    const toolCfg = { ...current, coding_agent: { ...(current.coding_agent || {}), defaultAgent: e.target.value } }
                    updateBot(activeBot.id, { toolConfigs: toolCfg })
                  }}
                  className="settings-coding-agents__select"
                >
                  {codingAgents.map((a) => (
                    <option key={a.id} value={a.id} disabled={!a.available}>
                      {a.name}{!a.available ? ' (not installed)' : ''}
                    </option>
                  ))}
                </select>
              </div>
              <div className="settings-coding-agents__default">
                <label className="text-xs text-[var(--color-text-secondary)]">Timeout per task</label>
                <select
                  value={
                    (activeBot?.toolConfigs?.coding_agent?.timeoutSeconds as number)
                    || 600
                  }
                  onChange={(e) => {
                    if (!activeBot) return
                    const current = activeBot.toolConfigs || {}
                    const toolCfg = { ...current, coding_agent: { ...(current.coding_agent || {}), timeoutSeconds: Number(e.target.value) } }
                    updateBot(activeBot.id, { toolConfigs: toolCfg })
                  }}
                  className="settings-coding-agents__select"
                >
                  {/* Seconds: 10s steps up to 60s */}
                  {[10, 20, 30, 40, 50, 60].map((s) => (
                    <option key={s} value={s}>{s}s</option>
                  ))}
                  {/* Minutes: 2–60 min */}
                  {[2, 3, 5, 10, 15, 20, 30, 45, 60].map((m) => (
                    <option key={`m${m}`} value={m * 60}>{m} min</option>
                  ))}
                  {/* Hours: 2–24h */}
                  {[2, 3, 4, 6, 8, 12, 18, 24].map((h) => (
                    <option key={`h${h}`} value={h * 3600}>{h}h</option>
                  ))}
                </select>
              </div>
              <p className="settings-coding-agents__hint">
                Type <code>@claude</code>, <code>@codex</code>, or <code>@gemini</code> in chat to invoke a coding agent.
              </p>
            </div>
          )}
        </div>
      </div>

      {/* Appearance */}
      <div className="settings-section">
        <h3 className="settings-section__heading">
          <Palette className="h-4 w-4 settings-section__heading-icon" />
          Appearance
        </h3>
        <div className="space-y-4">
          <div>
            <label className="settings-form__label--icon">Icon</label>
            <div className="flex flex-wrap gap-2">
              {BOT_ICON_OPTIONS.map((option) => (
                <button
                  key={option.id}
                  onClick={() => setForm({ ...form, icon: option.id })}
                  title={option.label}
                  className={cn(
                    'settings-icon-btn',
                    form.icon === option.id
                      ? 'settings-icon-btn--active'
                      : 'settings-icon-btn--inactive'
                  )}
                >
                  <BotIconRenderer icon={option.id} size={20} />
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="settings-form__label--icon">Color</label>
            <div className="settings-color-grid">
              {COLOR_OPTIONS.map((color) => (
                <button
                  key={color}
                  onClick={() => setForm({ ...form, color })}
                  className={cn(
                    'settings-color-circle',
                    form.color === color && 'settings-color-circle--active'
                  )}
                  style={{
                    backgroundColor: color,
                    boxShadow: form.color === color ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${color}` : undefined,
                  }}
                />
              ))}
              <label
                className={cn(
                  'settings-color-circle settings-color-circle--custom',
                  form.color && !COLOR_OPTIONS.includes(form.color) && 'settings-color-circle--active'
                )}
                style={{
                  backgroundColor: form.color && !COLOR_OPTIONS.includes(form.color) ? form.color : 'var(--color-active-bg)',
                  boxShadow: form.color && !COLOR_OPTIONS.includes(form.color) ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${form.color}` : undefined,
                }}
                title="Custom color"
              >
                <Plus className="settings-color-circle__icon" />
                <input
                  type="color"
                  value={form.color}
                  onChange={(e) => setForm({ ...form, color: e.target.value })}
                  className="settings-color-circle__input"
                />
              </label>
            </div>
          </div>
        </div>
      </div>

      {/* System Prompt */}
      <div className="settings-section">
        <h3 className="settings-section__heading">
          <Brain className="h-4 w-4 settings-section__heading-icon" />
          System Prompt
        </h3>
        <textarea
          value={form.systemPrompt}
          onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
          rows={6}
          placeholder="Define the bot's personality and behavior..."
          className="settings-form__textarea--mono"
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
      <div className="settings-section">
        <h3 className="settings-section__subtitle">Notes & Memory</h3>
        <p className="settings-section__description">
          Save notes for your bot to remember. The bot can also create notes during conversations.
        </p>
        <NotesManager
          botId={botId}
          onEditNote={handleEditNote}
          onNewNote={handleNewNote}
        />
      </div>

      {/* Search tester */}
      <div className="settings-section">
        <h3 className="settings-section__subtitle">Search Knowledge</h3>
        <p className="settings-section__description">
          Test search across documents and notes.
        </p>
        <KnowledgeSearch botId={botId} />
      </div>

      {/* Documents section */}
      <div className="settings-section">
        <h3 className="settings-section__subtitle">Documents</h3>
        <p className="settings-section__description">
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
      <div className="settings-section">
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
  const { isSkillDisabled } = usePlatformToolsStore()

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

  // Filter skills by search query and global visibility
  const filteredSkills = allSkills.filter((skill) => {
    // Skip globally disabled skills
    if (isSkillDisabled(skill.id)) return false
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
        <div className="settings-section__description">Loading skills...</div>
      </div>
    )
  }

  return (
    <div className="space-y-6">

      {/* Error display */}
      {error && (
        <div className="settings-error">
          {error}
        </div>
      )}

      {/* Header with actions */}
      <div className="flex items-center justify-between gap-4">
        <p className="settings-section__description" style={{ marginBottom: 0 }}>
          Activate skills to give your bot specialized behaviors and capabilities.
        </p>
        <div className="settings-skills__actions">
          <button
            onClick={handleRefresh}
            disabled={refreshing}
            className="settings-skills__refresh-btn flex items-center gap-1.5"
            title="Rescan skill directories"
          >
            <RefreshCw className={cn('h-3.5 w-3.5', refreshing && 'animate-spin')} />
            Refresh
          </button>
          <button
            onClick={() => setShowInstallDialog(true)}
            className="settings-skills__install-btn flex items-center gap-1.5"
          >
            <Download className="h-3.5 w-3.5" />
            Install
          </button>
        </div>
      </div>

      {/* Search */}
      <div className="settings-skills__search">
        <Search className="settings-skills__search-icon h-4 w-4" />
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search skills..."
          className="settings-skills__search-input"
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
        <div className="settings-skills-empty">
          <p className="settings-section__description" style={{ marginBottom: 0 }}>No skills match your search.</p>
        </div>
      ) : (
        <div className="settings-skills-empty">
          <div className="settings-skills-empty__icon">
            <Sparkles className="h-6 w-6" />
          </div>
          <h3 className="settings-skills-empty__title">No skills available</h3>
          <p className="settings-section__description">
            Create SKILL.md files in <code>~/.claude/skills/</code>
            {' '}or install from a URL.
          </p>
          <div className="flex justify-center gap-3">
            <button
              onClick={() => setShowInstallDialog(true)}
              className="settings-skills__install-btn flex items-center gap-1.5 px-4 py-2 text-sm"
            >
              <Download className="h-4 w-4" />
              Install Skill
            </button>
            <a
              href="https://skills.sh"
              target="_blank"
              rel="noopener noreferrer"
              className="settings-skills-empty__browse-btn flex items-center gap-1.5"
            >
              <ExternalLink className="h-4 w-4" />
              Browse skills.sh
            </a>
          </div>
        </div>
      )}

      {/* Active skills count */}
      {activeSkillIds.size > 0 && (
        <div className="settings-section__description" style={{ textAlign: 'center', marginBottom: 0 }}>
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
        'capability-toggle',
        enabled ? 'capability-toggle--active' : 'capability-toggle--inactive'
      )}
    >
      <div className="capability-toggle__info">
        <div className={cn('capability-toggle__icon', enabled && 'capability-toggle__icon--active')}>
          {icon}
        </div>
        <div>
          <div className="capability-toggle__label">{label}</div>
          <div className="capability-toggle__description">{description}</div>
        </div>
      </div>
      <button
        onClick={() => onToggle(!enabled)}
        className={cn(
          'capability-toggle__toggle',
          enabled ? 'capability-toggle__toggle--active' : 'capability-toggle__toggle--inactive'
        )}
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
        'skill-card',
        isActive ? 'skill-card--active' : 'skill-card--inactive'
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <h3 className="skill-card__name">{skill.name}</h3>
            {skill.version && (
              <span className="skill-card__badge">
                v{skill.version}
              </span>
            )}
            <span className="skill-card__badge">
              {skill.source}
            </span>
          </div>
          <p className="skill-card__description">{skill.description}</p>
          {skill.tags.length > 0 && (
            <div className="mt-2 flex flex-wrap gap-1">
              {skill.tags.map((tag) => (
                <span
                  key={tag}
                  className="skill-card__tag"
                >
                  {tag}
                </span>
              ))}
            </div>
          )}
          {skill.requiresTools.length > 0 && (
            <div className="skill-card__requires">
              Requires: {skill.requiresTools.join(', ')}
            </div>
          )}
        </div>
        <div className="flex items-center gap-2">
          {showDelete && (
            <button
              onClick={() => onDelete(skill.id)}
              className="skill-card__delete-btn"
              title="Delete skill"
            >
              <X className="h-4 w-4" />
            </button>
          )}
          <button
            onClick={() => onToggle(skill.id, !isActive)}
            className={cn(
              'skill-card__toggle',
              isActive ? 'skill-card__toggle--active' : 'skill-card__toggle--inactive'
            )}
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
    <div className="skill-install-dialog">
      <div className="skill-install-dialog__panel">
        <div className="skill-install-dialog__header">
          <h2 className="skill-install-dialog__title">Install Skill</h2>
          <button
            onClick={onClose}
            className="skill-install-dialog__close-btn"
          >
            <X className="h-5 w-5" />
          </button>
        </div>
        <div className="skill-install-dialog__body space-y-4">
          {error && (
            <div className="settings-error">
              {error}
            </div>
          )}
          <div>
            <label className="settings-form__label">
              Skill URL or skills.sh identifier
            </label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://... or skills.sh/skill-name"
              className="settings-form__input"
            />
            <p className="settings-form__hint">
              Enter a URL to a skill markdown file or a skills.sh identifier.
            </p>
          </div>
        </div>
        <div className="skill-install-dialog__footer">
          <button
            onClick={onClose}
            className="skill-install-dialog__cancel-btn"
          >
            Cancel
          </button>
          <button
            onClick={handleInstall}
            disabled={!url.trim() || loading}
            className="skill-install-dialog__submit-btn flex items-center gap-2"
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
        <p className="settings-section__description">
          Connect your bot to messaging platforms to send and receive messages.
        </p>
        <BotConnectionsPanel botId={botId} />
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
      <div className="settings-danger__panel">
        <h3 className="settings-danger__title">Export Bot</h3>
        <p className="settings-danger__text">
          Download this bot's configuration as a JSON file. You can import it later to recreate the bot.
        </p>
        {exportError && (
          <p className="mt-2 text-sm text-red-400">{exportError}</p>
        )}
        <button
          onClick={handleExport}
          disabled={isExporting}
          className="settings-danger__export-btn flex items-center gap-2"
        >
          <Download className="h-4 w-4" />
          {isExporting ? 'Exporting...' : 'Export Configuration'}
        </button>
      </div>

      {/* Delete section */}
      {isDefault ? (
        <div className="settings-danger__panel">
          <h3 className="settings-danger__title--disabled">Delete this bot</h3>
          <p className="settings-danger__text">
            The default bot cannot be deleted.
          </p>
        </div>
      ) : (
        <div className="settings-danger__panel--delete">
          <h3 className="settings-danger__title--delete">Delete this bot</h3>
          <p className="settings-danger__text">
            Once you delete <strong className="settings-modal__strong">{botName}</strong>, there is no going back.
            All chats, jobs, and tasks will be permanently deleted.
          </p>
          <button
            onClick={onDelete}
            className="settings-danger__delete-btn flex items-center gap-2"
          >
            <Trash2 className="h-4 w-4" />
            Delete Bot
          </button>
        </div>
      )}
    </div>
  )
}

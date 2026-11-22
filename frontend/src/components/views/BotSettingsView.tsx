import { useState, useEffect, useRef, useCallback } from 'react'
import { useNavigate, useLocation, Navigate } from 'react-router-dom'
import { toast } from 'sonner'
import {
  ChevronLeft,
  X,
  Pencil,
  Plus,
  RefreshCw,
  RotateCcw,
  AlertTriangle,
} from 'lucide-react'
import { useBotStore, DEFAULT_BOT_SETTINGS, getEffectiveModels } from '../../stores/bots'
import { useModelsStore } from '../../stores/models'
import { useProvidersStore } from '../../stores/providers'
import { usePlatformToolsStore } from '../../stores/platform-tools'
import { usePluginsStore } from '../../stores/plugins'
import { useKnowledgeStore, type DocumentResponse } from '../../stores/knowledge'
import { getCodingAgents, exportBot, clearBotPlatformData } from '../../api/client'
import { getConnections, getPlatforms, type Connection } from '../../api/connections'
import { listNotes } from '../../api/knowledge'
import * as skillsApi from '../../api/skills'
import { useBotAccess } from '../../hooks/useBotAccess'
import { BotAvatar } from '../common/Avatar'
import { ModelSelect } from '../common/ModelSelect'
import { BotEnvironmentPanel } from '../settings/BotEnvironmentPanel'
import { DeveloperPanel } from '../settings/DeveloperPanel'
import { BotConnectionsPanel } from '../settings/BotConnectionsPanel'
import {
  AppearanceSection,
  ModelsCapabilitiesSection,
  SkillInstallDialog,
} from './SettingsView'
import { PluginDetailPanel } from './PluginsView'
import {
  DocumentUploader,
  DocumentList,
  NotesManager,
  NoteEditorDialog,
  KnowledgeStats as KnowledgeStatsComponent,
  KnowledgeSearch,
  InstructionsEditor,
  DocumentChunksDialog,
} from '../knowledge'
import { cn } from '../../lib/utils'
import type { Bot as BotType, CodingAgentInfo, SkillDefinition, ExternalPluginInfo } from '../../types'

/**
 * Bot settings page (design view 18) — one column of anchored sections:
 * General, Knowledge, Skills, What it can use (capability switches + plugins),
 * Connections, Advanced (models, environment, API & webhooks, danger zone).
 * The design's "Computer" section is omitted entirely: the computer backend
 * does not exist (see UI_V2_PLAN.md "Phase D3 - not backed yet").
 *
 * Everything is real data:
 * - Knowledge rows: documents/notes from the knowledge API (full management
 *   in sheets hosting the existing components).
 * - Skills: skills API activate/deactivate switches + the existing install
 *   ("New skill") and refresh flows.
 * - What it can use: per-bot `capabilities` switches (live updateBot) +
 *   external plugins (configure/install/reload via the plugins API). The old
 *   per-tool manager stays reachable at /:botId/tools.
 * - Connections: platform connections (+ live WS status), unconnected
 *   platforms, coding agents, configured provider keys.
 * - Advanced: model slots (General holds the default model), environment
 *   variables, API keys & webhooks (Developer panel), export / clear chats /
 *   delete (real endpoints).
 *
 * Role gating (design view 12): settings is Editor+ — users without edit
 * access are redirected to the bot's chat; nothing is shown greyed out.
 * Sections have ids so other pages can deep-link (/:botId/settings#knowledge).
 *
 * Save keeps the legacy behavior: updateBot (bot store → PUT /api/bots/{id})
 * for name/title/instructions/avatar/model; everything else toggles live.
 */

const connectionStatusText = (status: Connection['status']): string => {
  switch (status) {
    case 'connected':
      return 'Connected'
    case 'connecting':
      return 'Connecting...'
    case 'error':
      return 'Error'
    default:
      return 'Disconnected'
  }
}

/** Per-bot capability switches for "What it can use" (live `capabilities`). */
const CAPABILITY_ROWS: { key: string; label: string; description: string }[] = [
  { key: 'fileOperations', label: 'Files', description: 'Read and write in its /workspace' },
  { key: 'codeExecution', label: 'Code', description: 'Run Python in a sandbox; risky code is blocked' },
  { key: 'gitOperations', label: 'Git', description: 'Status, diff, log, commit and branch management' },
  { key: 'webAccess', label: 'Web', description: 'Fetch pages, search the web, make HTTP requests' },
  { key: 'dataOperations', label: 'Data', description: 'SQLite queries and ZIP/TAR archives' },
  { key: 'shellAccess', label: 'This PC', description: 'Run commands on your machine. Asks first every time' },
  { key: 'workManagement', label: 'Work', description: 'Create tasks and routines for itself' },
  { key: 'contacts', label: 'Contacts', description: 'Access to contacts in its system prompt context' },
]

// Section anchors — nav chip targets and deep-link hashes.
// "Computer" is intentionally absent (no computer backend).
const SECTIONS = [
  { id: 'general', label: 'General' },
  { id: 'knowledge', label: 'Knowledge' },
  { id: 'skills', label: 'Skills' },
  { id: 'what-it-can-use', label: 'What it can use' },
  { id: 'connections', label: 'Connections' },
  { id: 'advanced', label: 'Advanced' },
] as const

type SheetKind = 'docs' | 'notes' | 'connections' | 'plugin' | null

// Stable fallback for the document selector (never[] shared reference —
// the store's getDocuments() returns a fresh `[]` per call, which must not
// be used inside a zustand selector).
const NO_DOCUMENTS: DocumentResponse[] = []

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

function formatAdded(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

// -----------------------------------------------------------------------------
// Small building blocks matching design view 18
// -----------------------------------------------------------------------------

function Section({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    <section id={id} className="bot-settings__section">
      <div className="bot-settings__section-head">
        <h2>{title}</h2>
        {description && <p>{description}</p>}
      </div>
      {children}
    </section>
  )
}

/** Two-line list row: title / subtitle, optional right-side action. */
function Row({
  title,
  sub,
  action,
}: {
  title: React.ReactNode
  sub?: React.ReactNode
  action?: React.ReactNode
}) {
  return (
    <div className="bot-settings__row">
      <span className="bot-settings__row-main">
        <span className="bot-settings__row-title">{title}</span>
        {sub && <span className="bot-settings__row-sub">{sub}</span>}
      </span>
      {action && <span className="bot-settings__row-action">{action}</span>}
    </div>
  )
}

/** Design switch row (14px/600 label + 13px description + switch). */
function ToggleRow({
  title,
  description,
  checked,
  onToggle,
  switchLabel,
}: {
  title: string
  description: string
  checked: boolean
  onToggle: () => void
  switchLabel: string
}) {
  return (
    <div className="bot-settings__toggle-row">
      <span className="bot-settings__toggle-row-text">
        <span className="bot-settings__toggle-row-title">{title}</span>
        <span className="bot-settings__toggle-row-sub">{description}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={switchLabel}
        className="v2-switch"
        onClick={onToggle}
      >
        <span className="v2-switch__knob" />
      </button>
    </div>
  )
}

/** Right-aligned 28px row action (Remove/Edit/Manage/... in the design). */
function RowAction({
  children,
  onClick,
  danger,
}: {
  children: React.ReactNode
  onClick: () => void
  danger?: boolean
}) {
  return (
    <button
      type="button"
      className={cn('bot-settings__row-btn', danger && 'bot-settings__row-btn--danger')}
      onClick={onClick}
    >
      {children}
    </button>
  )
}

/** Bordered ghost button ("Add documents", "New skill", "Add plugin"). */
function GhostButton({ children, onClick }: { children: React.ReactNode; onClick: () => void }) {
  return (
    <button type="button" className="bot-settings__ghost" onClick={onClick}>
      {children}
    </button>
  )
}

/** v2 sheet wrapper (backdrop + panel + header) for the management sheets. */
function Sheet({
  title,
  onClose,
  children,
}: {
  title: string
  onClose: () => void
  children: React.ReactNode
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', handler)
    return () => document.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div className="v2-sheet-backdrop" onClick={onClose}>
      <div
        className="v2-sheet"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
      >
        <div className="v2-sheet__header">
          <h2>{title}</h2>
          <span style={{ marginLeft: 'auto' }}>
            <button type="button" className="v2-icon-btn" aria-label="Close" title="Close" onClick={onClose}>
              <X size={17} strokeWidth={1.8} />
            </button>
          </span>
        </div>
        <div className="v2-sheet__body">{children}</div>
      </div>
    </div>
  )
}

// -----------------------------------------------------------------------------
// VIEW
// -----------------------------------------------------------------------------

export function BotSettingsView() {
  const navigate = useNavigate()
  const location = useLocation()
  const { getActiveBot, updateBot, deleteBot } = useBotStore()
  const { fetchConfig: fetchPlatformConfig, isCapabilityDisabled } = usePlatformToolsStore()
  const { providers, refresh: refreshProviders } = useProvidersStore()
  const { plugins: externalPlugins, fetchPlugins, reloadPlugins, installPlugin } = usePluginsStore()

  const activeBot = getActiveBot()
  const botId = activeBot?.id ?? null
  const { canEdit } = useBotAccess(botId)

  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showResetConfirm, setShowResetConfirm] = useState(false)
  const [saved, setSaved] = useState(false)
  const [sheet, setSheet] = useState<SheetKind>(null)
  const [selectedPlugin, setSelectedPlugin] = useState<ExternalPluginInfo | null>(null)
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false)

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeBot?.id])

  // Preload platform tool config (capability/skill filtering) and providers
  useEffect(() => {
    fetchPlatformConfig()
  }, [fetchPlatformConfig])
  useEffect(() => {
    if (providers.length === 0) refreshProviders()
  }, [providers.length, refreshProviders])

  // Plugins (What it can use › Plugins)
  useEffect(() => {
    fetchPlugins()
  }, [fetchPlugins])
  const pluginFileInputRef = useRef<HTMLInputElement>(null)

  const handlePluginInstall = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const ok = await installPlugin(file)
    if (ok) toast.success(`Plugin installed from ${file.name}`)
    else toast.error('Failed to install plugin')
    e.target.value = ''
  }

  const handlePluginReload = async () => {
    const result = await reloadPlugins()
    if (result) {
      const errorCount = Object.keys(result.errors).length
      toast.success(
        `Reloaded ${result.loaded}/${result.total} plugin(s)` +
          (errorCount > 0 ? ` (${errorCount} error${errorCount > 1 ? 's' : ''})` : '')
      )
    }
  }

  // Knowledge: documents (store) + notes count (real; null = hidden).
  // Select the raw slice — the store's getDocuments() returns `docs || []`,
  // a fresh array per call, which would loop useSyncExternalStore.
  const loadDocuments = useKnowledgeStore((s) => s.loadDocuments)
  const deleteDocument = useKnowledgeStore((s) => s.deleteDocument)
  const documents = useKnowledgeStore((s) => (botId ? s.documents[botId] : undefined)) ?? NO_DOCUMENTS
  useEffect(() => {
    if (botId) loadDocuments(botId)
  }, [botId, loadDocuments])
  const [notesCount, setNotesCount] = useState<number | null>(null)
  useEffect(() => {
    if (!botId) return
    let cancelled = false
    listNotes(botId)
      .then((notes) => {
        if (!cancelled) setNotesCount(notes.length)
      })
      .catch(() => {
        if (!cancelled) setNotesCount(null)
      })
    return () => {
      cancelled = true
    }
  }, [botId])

  const handleRemoveDocument = (docId: string, filename: string) => {
    if (!botId) return
    if (!confirm(`Delete "${filename}"? This cannot be undone.`)) return
    void deleteDocument(botId, docId)
  }

  // Notes sheet state (editor + chunks dialog live at the view level)
  const [editingNoteId, setEditingNoteId] = useState<string | null>(null)
  const [showNoteEditor, setShowNoteEditor] = useState(false)
  const [chunksDoc, setChunksDoc] = useState<{ id: string; filename: string } | null>(null)

  // Skills
  const [allSkills, setAllSkills] = useState<SkillDefinition[]>([])
  const [activeSkillIds, setActiveSkillIds] = useState<Set<string>>(new Set())
  const [skillsLoaded, setSkillsLoaded] = useState(false)
  const [skillsError, setSkillsError] = useState<string | null>(null)
  const [showInstallSkill, setShowInstallSkill] = useState(false)
  const [refreshingSkills, setRefreshingSkills] = useState(false)

  const loadSkills = useCallback(async () => {
    if (!botId) return
    try {
      setSkillsError(null)
      const [skills, botSkillIds] = await Promise.all([
        skillsApi.getSkills(),
        skillsApi.getBotSkillIds(botId),
      ])
      setAllSkills(skills)
      setActiveSkillIds(new Set(botSkillIds))
    } catch (e) {
      setSkillsError(e instanceof Error ? e.message : 'Failed to load skills')
    } finally {
      setSkillsLoaded(true)
    }
  }, [botId])

  useEffect(() => {
    loadSkills()
  }, [loadSkills])

  const handleToggleSkill = async (skillId: string, activate: boolean) => {
    if (!botId) return
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
      toast.error(e instanceof Error ? e.message : 'Failed to toggle skill')
    }
  }

  const handleRefreshSkills = async () => {
    setRefreshingSkills(true)
    try {
      const skills = await skillsApi.refreshSkills()
      setAllSkills(skills)
      setSkillsError(null)
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to refresh skills')
    } finally {
      setRefreshingSkills(false)
    }
  }

  // Deleting a skill file is only offered for local/installed skills
  // (same rule as the old Skills section)
  const handleDeleteSkill = async (skill: SkillDefinition) => {
    if (!confirm(`Are you sure you want to delete the skill "${skill.name}"?`)) return
    try {
      await skillsApi.deleteSkill(skill.id)
      setAllSkills((prev) => prev.filter((s) => s.id !== skill.id))
      setActiveSkillIds((prev) => {
        const next = new Set(prev)
        next.delete(skill.id)
        return next
      })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to delete skill')
    }
  }

  const sortedSkills = [...allSkills].sort((a, b) => {
    const aActive = activeSkillIds.has(a.id)
    const bActive = activeSkillIds.has(b.id)
    if (aActive && !bActive) return -1
    if (!aActive && bActive) return 1
    return a.name.localeCompare(b.name)
  })

  // Capability switches (What it can use) — live updateBot, hidden when the
  // platform globally disables the capability (same rule as the old toggles).
  const capabilities = (activeBot?.capabilities ?? {}) as Record<string, boolean | undefined>
  const handleToggleCapability = (key: string) => {
    if (!activeBot) return
    const newCaps = { ...capabilities, [key]: !capabilities[key] }
    updateBot(activeBot.id, { capabilities: newCaps as BotType['capabilities'] })
  }

  // Platform connections with real status (null = API unreachable → hidden)
  const [connections, setConnections] = useState<Connection[] | null>(null)
  const [platforms, setPlatforms] = useState<Record<string, { display_name: string }>>({})
  useEffect(() => {
    if (!botId) return
    let cancelled = false
    Promise.all([getConnections(botId), getPlatforms()])
      .then(([conns, plats]) => {
        if (cancelled) return
        setConnections(conns)
        setPlatforms(plats)
      })
      .catch(() => {
        if (!cancelled) setConnections(null)
      })
    return () => {
      cancelled = true
    }
  }, [botId])

  // Live connection status updates (same WS event as the management panel)
  useEffect(() => {
    if (!botId) return
    const handler = (event: Event) => {
      const detail = (event as CustomEvent).detail as {
        connectionId: string
        botId: string
        status: string
        error?: string
      }
      if (detail.botId !== botId) return
      setConnections((prev) =>
        prev?.map((c) =>
          c.id === detail.connectionId
            ? { ...c, status: detail.status as Connection['status'], error: detail.error || null }
            : c
        ) ?? prev
      )
    }
    window.addEventListener('connection-status-change', handler)
    return () => window.removeEventListener('connection-status-change', handler)
  }, [botId])

  // Coding agents (real availability), only when the bot can use them
  const codingAgentEnabled = !!capabilities.codingAgent
  const [codingAgents, setCodingAgents] = useState<CodingAgentInfo[]>([])
  useEffect(() => {
    if (!codingAgentEnabled) {
      setCodingAgents([])
      return
    }
    let cancelled = false
    getCodingAgents()
      .then((res) => {
        if (!cancelled) setCodingAgents(res.agents)
      })
      .catch(() => {
        if (!cancelled) setCodingAgents([])
      })
    return () => {
      cancelled = true
    }
  }, [codingAgentEnabled])

  const configuredProviders = providers.filter((p) => p.configured)

  // Deep links: /:botId/settings#<section> scrolls to the anchored section
  useEffect(() => {
    const id = location.hash.replace('#', '')
    if (!id) return
    const timer = setTimeout(() => {
      document.getElementById(id)?.scrollIntoView({ block: 'start' })
    }, 50)
    return () => clearTimeout(timer)
  }, [location.hash])

  if (!activeBot) return null

  // Role gating (design view 12): settings is Editor+; hide, don't grey out.
  if (!canEdit) {
    return <Navigate to={`/${activeBot.id}/chats`} replace />
  }

  const handleSave = () => {
    // Exclude capabilities from form save — those are toggled live above
    const { capabilities: _caps, ...formWithoutCaps } = form
    void _caps
    updateBot(activeBot.id, formWithoutCaps)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  const handleDelete = () => {
    setShowDeleteConfirm(false)
    navigate('/dashboard')
    deleteBot(activeBot.id)
  }

  const handleBack = () => {
    navigate(`/${activeBot.id}/chats`)
  }

  const handleClose = () => {
    // Return to where the user came from when possible, else the bot's chat
    if (window.history.state?.idx > 0) {
      navigate(-1)
    } else {
      navigate(`/${activeBot.id}/chats`)
    }
  }

  const handleExport = async () => {
    try {
      const data = await exportBot(activeBot.id)
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${activeBot.name.toLowerCase().replace(/\s+/g, '-')}-export.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to export bot')
    }
  }

  const handleClearChats = async () => {
    if (!confirm(`Clear all chats for ${activeBot.name}? This cannot be undone.`)) return
    try {
      const result = await clearBotPlatformData(activeBot.id)
      toast.success(`Cleared ${result.chats_deleted} chat(s), ${result.messages_deleted} message(s)`)
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to clear chats')
    }
  }

  const scrollToAdvanced = () => {
    document.getElementById('advanced')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
  }

  const unconnectedPlatforms = Object.entries(platforms).filter(
    ([id]) => !(connections ?? []).some((c) => c.platform === id)
  )
  const showConnectionsSection =
    connections !== null || codingAgents.length > 0 || configuredProviders.length > 0

  return (
    <div className="bot-settings">
      <div className="bot-settings__column">
        {/* Header */}
        <div className="bot-settings__header">
          <button
            type="button"
            className="v2-icon-btn"
            aria-label="Back to chat"
            title="Back to chat"
            onClick={handleBack}
          >
            <ChevronLeft size={18} strokeWidth={1.8} />
          </button>
          <h1>{activeBot.name} settings</h1>
          <button
            type="button"
            className="v2-icon-btn"
            aria-label="Close"
            title="Close"
            onClick={handleClose}
          >
            <X size={18} strokeWidth={1.8} />
          </button>
        </div>

        {/* Section nav (design chips; Computer omitted — no computer backend) */}
        <nav className="bot-settings__sections-nav" aria-label="Sections">
          {SECTIONS.map((s) => (
            <a key={s.id} href={`#${s.id}`}>
              {s.label}
            </a>
          ))}
        </nav>

        {/* General */}
        <Section id="general" title="General">
          <div className="bot-settings__avatar">
            <BotAvatar color={form.color} name={form.name || activeBot.name} size={72} />
            <button
              type="button"
              className="bot-settings__avatar-edit"
              aria-label="Change avatar"
              title="Change avatar"
              onClick={() => setAvatarPickerOpen((v) => !v)}
            >
              <Pencil size={13} strokeWidth={1.8} />
            </button>
            {avatarPickerOpen && (
              <>
                <div
                  className="bot-settings__avatar-popover-backdrop"
                  onClick={() => setAvatarPickerOpen(false)}
                />
                <div className="bot-settings__avatar-popover">
                  <AppearanceSection form={form} setForm={setForm} />
                </div>
              </>
            )}
          </div>

          <label className="bot-settings__field">
            <span className="bot-settings__label">Name</span>
            <input
              type="text"
              className="bot-settings__input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
            />
          </label>

          <label className="bot-settings__field">
            <span className="bot-settings__label">Title</span>
            <input
              type="text"
              className="bot-settings__input"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
            />
          </label>

          <label className="bot-settings__field">
            <span className="bot-settings__label">Instructions</span>
            <textarea
              rows={4}
              className="bot-settings__textarea"
              value={form.systemPrompt}
              onChange={(e) => setForm({ ...form, systemPrompt: e.target.value })}
            />
          </label>

          <label className="bot-settings__field">
            <span className="bot-settings__label">Model</span>
            <ModelSelect
              value={form.models?.default || form.model || ''}
              onChange={(model) => {
                const models = { ...(form.models || { default: '' }), default: model }
                setForm({ ...form, model, models })
              }}
              placeholder="Use the default from Settings"
              filter={(m) => !m.supports_image_generation && !m.supports_audio}
            />
          </label>
          {/* Notifications toggle omitted — no per-bot notification setting exists
              (UI_V2_PLAN.md "Phase D3 - not backed yet"). */}
        </Section>

        {/* Knowledge */}
        <Section
          id="knowledge"
          title="Knowledge"
          description="Documents and notes it looks up when answering."
        >
          {documents.map((doc) => (
            <Row
              key={doc.id}
              title={doc.filename}
              sub={
                (doc.status === 'processing'
                  ? 'Processing · '
                  : doc.status === 'failed'
                    ? 'Failed · '
                    : '') +
                formatSize(doc.file_size) +
                (doc.chunk_count > 0 ? ` · ${doc.chunk_count} chunks` : '') +
                ` · added ${formatAdded(doc.uploaded_at)}`
              }
              action={
                <RowAction onClick={() => handleRemoveDocument(doc.id, doc.filename)}>
                  Remove
                </RowAction>
              }
            />
          ))}
          {notesCount !== null && notesCount > 0 && (
            <Row
              title="Notes"
              sub={`${notesCount} note${notesCount === 1 ? '' : 's'} you wrote for it`}
              action={<RowAction onClick={() => setSheet('notes')}>Edit</RowAction>}
            />
          )}
          <GhostButton onClick={() => setSheet('docs')}>
            <Plus size={15} strokeWidth={1.8} />
            Add documents
          </GhostButton>
        </Section>

        {/* Skills */}
        <Section
          id="skills"
          title="Skills"
          description="Reusable instructions it can pick up when they fit."
        >
          {skillsError && <p className="bot-settings__section-error">{skillsError}</p>}
          {!skillsLoaded && !skillsError && (
            <p className="bot-settings__section-note">Loading skills...</p>
          )}
          {sortedSkills.map((skill) => (
            <div key={skill.id} className="bot-settings__toggle-row">
              <span className="bot-settings__toggle-row-text">
                <span className="bot-settings__toggle-row-title">{skill.name}</span>
                <span className="bot-settings__toggle-row-sub">{skill.description}</span>
              </span>
              {(skill.source === 'local' || skill.source === 'installed') && (
                <RowAction onClick={() => void handleDeleteSkill(skill)}>Delete</RowAction>
              )}
              <button
                type="button"
                role="switch"
                aria-checked={activeSkillIds.has(skill.id)}
                aria-label={skill.name}
                className="v2-switch"
                onClick={() => void handleToggleSkill(skill.id, !activeSkillIds.has(skill.id))}
              >
                <span className="v2-switch__knob" />
              </button>
            </div>
          ))}
          <div className="bot-settings__ghost-row">
            <GhostButton onClick={() => setShowInstallSkill(true)}>
              <Plus size={15} strokeWidth={1.8} />
              New skill
            </GhostButton>
            <button
              type="button"
              className="bot-settings__ghost"
              onClick={() => void handleRefreshSkills()}
              disabled={refreshingSkills}
              title="Rescan skill directories"
            >
              <RefreshCw size={15} strokeWidth={1.8} className={cn(refreshingSkills && 'animate-spin')} />
              Refresh
            </button>
          </div>
        </Section>

        {/* What it can use */}
        <Section
          id="what-it-can-use"
          title="What it can use"
          description="Switch tools on or off. Plugins add more."
        >
          {CAPABILITY_ROWS.filter((row) => !isCapabilityDisabled(row.key)).map((row) => (
            <ToggleRow
              key={row.key}
              title={row.label}
              description={row.description}
              checked={capabilities[row.key] === true}
              onToggle={() => handleToggleCapability(row.key)}
              switchLabel={row.label}
            />
          ))}

          <button
            type="button"
            className="bot-settings__manage-tools"
            onClick={() => navigate(`/${activeBot.id}/tools`)}
          >
            Manage individual tools
          </button>

          <h3 className="bot-settings__subhead">Plugins</h3>
          {externalPlugins.map((plugin) => (
            <Row
              key={plugin.name}
              title={plugin.displayName}
              sub={
                `v${plugin.version}` +
                (plugin.type ? ` · ${plugin.type}` : '') +
                (plugin.loaded ? '' : ' · Not loaded') +
                (plugin.error ? ` · ${plugin.error}` : '')
              }
              action={
                <RowAction
                  onClick={() => {
                    setSelectedPlugin(plugin)
                    setSheet('plugin')
                  }}
                >
                  Configure
                </RowAction>
              }
            />
          ))}
          <div className="bot-settings__ghost-row">
            <GhostButton onClick={() => pluginFileInputRef.current?.click()}>
              <Plus size={15} strokeWidth={1.8} />
              Add plugin
            </GhostButton>
            <button
              type="button"
              className="bot-settings__ghost"
              onClick={() => void handlePluginReload()}
              title="Reload all plugins"
            >
              <RefreshCw size={15} strokeWidth={1.8} />
              Reload
            </button>
          </div>
          <input
            ref={pluginFileInputRef}
            type="file"
            accept=".zip,.tar.gz,.tgz"
            onChange={(e) => void handlePluginInstall(e)}
            className="hidden"
          />
        </Section>

        {/* Connections */}
        {showConnectionsSection && (
          <Section
            id="connections"
            title="Connections"
            description="Where else people can talk to it, and the coding agents it can hand work to."
          >
            {connections?.map((connection) => (
              <Row
                key={connection.id}
                title={connection.name}
                sub={connectionStatusText(connection.status)}
                action={<RowAction onClick={() => setSheet('connections')}>Manage</RowAction>}
              />
            ))}
            {connections !== null &&
              unconnectedPlatforms.map(([id, meta]) => (
                <Row
                  key={id}
                  title={meta.display_name}
                  sub="Not connected"
                  action={<RowAction onClick={() => setSheet('connections')}>Connect</RowAction>}
                />
              ))}
            {codingAgents.map((agent) => (
              <Row
                key={agent.id}
                title={agent.name}
                sub={agent.available ? 'Installed' : 'Not installed'}
                action={
                  agent.available ? (
                    <RowAction onClick={scrollToAdvanced}>Manage</RowAction>
                  ) : undefined
                }
              />
            ))}
            {configuredProviders.map((provider) => (
              <Row
                key={provider.name}
                title={provider.name}
                sub="Key added"
                action={<RowAction onClick={() => navigate('/settings/keys')}>Change</RowAction>}
              />
            ))}
            <GhostButton onClick={() => setSheet('connections')}>
              <Plus size={15} strokeWidth={1.8} />
              Add connection
            </GhostButton>
          </Section>
        )}

        {/* Computer section omitted — the computer backend does not exist
            (UI_V2_PLAN.md "Phase D3 - not backed yet"). */}

        {/* Advanced */}
        <Section id="advanced" title="Advanced">
          <h3 className="bot-settings__subhead">Model</h3>
          <div className="bot-settings__panels">
            <ModelsCapabilitiesSection form={form} setForm={setForm} showDefault={false} />
          </div>

          <h3 className="bot-settings__subhead">Environment</h3>
          <div className="bot-settings__panels">
            <BotEnvironmentPanel botId={activeBot.id} />
          </div>

          <h3 className="bot-settings__subhead">API &amp; webhooks</h3>
          <div className="bot-settings__panels">
            <DeveloperPanel botId={activeBot.id} />
          </div>

          <h3 className="bot-settings__subhead">Danger zone</h3>
          <Row
            title="Export this bot"
            sub="Settings, knowledge and skills as one file"
            action={<RowAction onClick={() => void handleExport()}>Export</RowAction>}
          />
          <Row
            title="Clear all chats"
            sub="Can't be undone"
            action={<RowAction onClick={() => void handleClearChats()}>Clear</RowAction>}
          />
          {activeBot.id !== 'default' && (
            <Row
              title={<span className="bot-settings__danger-title">Delete {activeBot.name}</span>}
              sub="Removes the bot, its chats and its routines"
              action={
                <RowAction danger onClick={() => setShowDeleteConfirm(true)}>
                  Delete
                </RowAction>
              }
            />
          )}
          <button
            type="button"
            className="bot-settings__reset"
            onClick={() => setShowResetConfirm(true)}
          >
            <RotateCcw size={14} strokeWidth={1.8} />
            Reset to default settings
          </button>
        </Section>

        {/* Save */}
        <div className="bot-settings__save">
          <button type="button" className="v2-btn v2-btn--primary" onClick={handleSave}>
            {saved ? 'Saved!' : 'Save'}
          </button>
        </div>
      </div>

      {/* Documents sheet (existing management components) */}
      {sheet === 'docs' && (
        <Sheet title="Documents" onClose={() => setSheet(null)}>
          <DocumentUploader botId={activeBot.id} />
          <div style={{ marginTop: 16 }}>
            <DocumentList
              botId={activeBot.id}
              onViewChunks={(documentId, filename) => setChunksDoc({ id: documentId, filename })}
            />
          </div>
        </Sheet>
      )}

      {/* Notes sheet */}
      {sheet === 'notes' && (
        <Sheet title="Notes & memory" onClose={() => setSheet(null)}>
          <KnowledgeStatsComponent botId={activeBot.id} />
          <div style={{ marginTop: 16 }}>
            <NotesManager
              botId={activeBot.id}
              onEditNote={(noteId) => {
                setEditingNoteId(noteId)
                setShowNoteEditor(true)
              }}
              onNewNote={() => {
                setEditingNoteId(null)
                setShowNoteEditor(true)
              }}
            />
          </div>
          <div style={{ marginTop: 16 }}>
            <h3 className="bot-settings__subhead">Search knowledge</h3>
            <KnowledgeSearch botId={activeBot.id} />
          </div>
          <div style={{ marginTop: 16 }}>
            <InstructionsEditor botId={activeBot.id} />
          </div>
        </Sheet>
      )}

      {/* Connection management sheet (existing panel) */}
      {sheet === 'connections' && (
        <Sheet title="Connections" onClose={() => setSheet(null)}>
          <BotConnectionsPanel botId={activeBot.id} />
        </Sheet>
      )}

      {/* Plugin config sheet (existing detail panel) */}
      {sheet === 'plugin' && selectedPlugin && (
        <Sheet
          title={selectedPlugin.displayName}
          onClose={() => {
            setSheet(null)
            setSelectedPlugin(null)
          }}
        >
          <PluginDetailPanel plugin={selectedPlugin} />
        </Sheet>
      )}

      {/* Note editor + document chunks dialogs (opened from the sheets above) */}
      {showNoteEditor && (
        <NoteEditorDialog
          botId={activeBot.id}
          noteId={editingNoteId}
          open={showNoteEditor}
          onClose={() => {
            setShowNoteEditor(false)
            setEditingNoteId(null)
          }}
        />
      )}
      {chunksDoc && (
        <DocumentChunksDialog
          botId={activeBot.id}
          documentId={chunksDoc.id}
          filename={chunksDoc.filename}
          open={!!chunksDoc}
          onClose={() => setChunksDoc(null)}
        />
      )}

      {/* Skill install dialog */}
      {showInstallSkill && (
        <SkillInstallDialog
          onClose={() => setShowInstallSkill(false)}
          onInstalled={(skill) => {
            setAllSkills((prev) => [...prev, skill])
            setShowInstallSkill(false)
          }}
        />
      )}

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

      {/* Reset confirmation modal */}
      {showResetConfirm && (
        <div className="settings-modal">
          <div className="settings-modal__panel">
            <div className="settings-modal__header settings-modal__header--warning">
              <RotateCcw className="h-6 w-6" />
              <h2 className="settings-modal__header-title">Reset Settings</h2>
            </div>
            <p className="settings-modal__body">
              This will reset the bot's name, description, icon, color, model, and instructions to
              their default values.
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
    </div>
  )
}

import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Settings,
  Moon,
  Sun,
  Monitor,
  Eye as EyeIcon,
  Keyboard,
  Shield,
  Database,
  Trash2,
  Download,
  Upload,
  RefreshCw,
  ExternalLink,
  Info,
  Palette,
  Sliders,
  FolderOpen,
  Code,
  AlertTriangle,
  Brain,
  Users,
  UserPlus,
  User as UserIcon,
  MoreVertical,
  Check,
  X,
  Mail,
  AtSign,
  Loader2,
  ChevronRight,
  ChevronDown,
  Bot,
  MessageSquare,
  Briefcase,
  CheckSquare,
  BarChart3,
  Key,
  EyeOff,
  Save,
  Cloud,
  Server,
  Star,
  Sparkles,
  Search,
  Plus,
} from 'lucide-react'
import { toast } from 'sonner'
import { useUIStore, Theme, AccentColor, PresetColor, accentColors, generatePalette } from '../../stores/ui'
import { useOnboardingStore } from '../../stores/onboarding'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { useProvidersStore } from '../../stores/providers'
import { useAuthStore } from '../../stores/auth'
import { useBotStore, useChatStore, useJobStore, useTaskStore } from '../../stores/bots'
import { useUsageStore } from '../../stores/connections'
import { useUpdateStore } from '../../stores/update'
import { useTelemetryStore } from '../../stores/telemetry'
import {
  updateTelemetrySettings,
  resetTelemetryId,
  getTelemetryPreview,
} from '../../api/telemetry'
import { listUsers, createUser, updateUser, deactivateUser } from '../../api/auth'
import {
  listGroups,
  createGroup,
  getGroup,
  deleteGroup,
  addMember,
  removeMember,
} from '../../api/groups'
import { checkHealth, type HealthInfo } from '../../api/client'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { ModelSelect } from '../common/ModelSelect'
import { Button } from '../common/Button'
import { cn } from '../../lib/utils'
import type { Config, User, UserRole, Group, GroupWithMembers, GroupMember, GroupRole } from '../../types'

type SettingsTab = 'general' | 'appearance' | 'models' | 'keys' | 'advanced' | 'data' | 'users' | 'groups'

const VALID_TABS: SettingsTab[] = ['general', 'appearance', 'models', 'keys', 'advanced', 'data', 'users', 'groups']

export function AppSettingsView() {
  const { settingsTab: urlTab } = useParams<{ settingsTab?: string }>()
  const navigate = useNavigate()
  const {
    theme,
    setTheme,
    accentColor,
    setAccentColor,
    customHex,
    setCustomHex,
    showThinking,
    setShowThinking,
    showCost,
    setShowCost,
    sidebarCollapsed,
    setSidebarCollapsed,
  } = useUIStore()
  const { config } = useConfigStore()
  const { user: currentUser } = useAuthStore()

  const isAdmin = currentUser?.role === 'admin'
  const isManagerOrAdmin = currentUser?.role === 'admin' || currentUser?.role === 'manager'

  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null)

  useEffect(() => {
    checkHealth()
      .then(setHealthInfo)
      .catch(() => {})
  }, [])

  // Determine active tab from URL, with validation
  const getActiveTab = (): SettingsTab => {
    if (!urlTab) return 'general'
    if (!VALID_TABS.includes(urlTab as SettingsTab)) return 'general'
    // Non-admins can't access users tab
    if (urlTab === 'users' && !isAdmin) return 'general'
    // Non-managers can't access groups tab
    if (urlTab === 'groups' && !isManagerOrAdmin) return 'general'
    return urlTab as SettingsTab
  }

  const activeTab = getActiveTab()

  // Redirect if URL tab is invalid or unauthorized
  useEffect(() => {
    if (urlTab && activeTab !== urlTab) {
      navigate('/settings/general', { replace: true })
    }
  }, [urlTab, activeTab, navigate])

  const handleTabChange = (tabId: SettingsTab) => {
    navigate(`/settings/${tabId}`)
  }

  const tabs = [
    { id: 'general' as SettingsTab, label: 'General', icon: Settings },
    { id: 'appearance' as SettingsTab, label: 'Appearance', icon: Palette },
    { id: 'models' as SettingsTab, label: 'Models', icon: Brain },
    { id: 'keys' as SettingsTab, label: 'API Keys', icon: Key },
    { id: 'advanced' as SettingsTab, label: 'Advanced', icon: Sliders },
    { id: 'data' as SettingsTab, label: 'Data & Privacy', icon: Database },
    ...(isManagerOrAdmin ? [{ id: 'groups' as SettingsTab, label: 'Groups', icon: Users }] : []),
    ...(isAdmin ? [{ id: 'users' as SettingsTab, label: 'Users', icon: UserPlus }] : []),
  ]

  return (
    <div className="app-settings">
      {/* Header */}
      <div className="app-settings__header">
        <div>
          <h1 className="app-settings__title">Settings</h1>
          <p className="app-settings__subtitle">Configure CachiBot preferences</p>
        </div>
      </div>

      <div className="app-settings__body">
        {/* Sidebar */}
        <nav className="settings-nav">
          <div className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={cn(
                  'settings-nav__item',
                  activeTab === tab.id && 'settings-nav__item--active'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="app-settings__content">
          <div className="app-settings__content-inner space-y-8">
            {activeTab === 'general' && (
              <GeneralSettings
                showThinking={showThinking}
                setShowThinking={setShowThinking}
                showCost={showCost}
                setShowCost={setShowCost}
                config={config}
                healthInfo={healthInfo}
              />
            )}
            {activeTab === 'appearance' && (
              <AppearanceSettings
                theme={theme}
                setTheme={setTheme}
                accentColor={accentColor}
                setAccentColor={setAccentColor}
                customHex={customHex}
                setCustomHex={setCustomHex}
                sidebarCollapsed={sidebarCollapsed}
                setSidebarCollapsed={setSidebarCollapsed}
              />
            )}
            {activeTab === 'models' && <ModelsSettings />}
            {activeTab === 'keys' && <ApiKeysSettings />}
            {activeTab === 'advanced' && <AdvancedSettings config={config} />}
            {activeTab === 'data' && <DataSettings />}
            {activeTab === 'groups' && isManagerOrAdmin && <GroupsSettings currentUser={currentUser} />}
            {activeTab === 'users' && isAdmin && <UsersSettings currentUser={currentUser} />}
          </div>
        </div>
      </div>
    </div>
  )
}

// =============================================================================
// GENERAL SETTINGS
// =============================================================================

function GeneralSettings({
  showThinking,
  setShowThinking,
  showCost,
  setShowCost,
  config,
  healthInfo,
}: {
  showThinking: boolean
  setShowThinking: (show: boolean) => void
  showCost: boolean
  setShowCost: (show: boolean) => void
  config: Config | null
  healthInfo: HealthInfo | null
}) {
  return (
    <>
      <Section icon={EyeIcon} title="Display Options">
        <div className="space-y-4">
          <ToggleField
            label="Show Thinking Process"
            description="Display the AI's reasoning and thought process"
            checked={showThinking}
            onChange={setShowThinking}
          />
          <ToggleField
            label="Show Token Costs"
            description="Display estimated costs for API calls"
            checked={showCost}
            onChange={setShowCost}
          />
        </div>
      </Section>


      <Section icon={FolderOpen} title="Workspace">
        <div className="space-y-4">
          <Field label="Workspace Path">
            <div className="flex gap-2">
              <input
                type="text"
                value={config?.workspacePath || './workspace'}
                readOnly
                className="settings-input settings-input--readonly flex-1"
              />
              <button className="settings-btn-secondary">
                Browse
              </button>
            </div>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              Directory where bots can read and write files
            </p>
          </Field>
        </div>
      </Section>

      <Section icon={Info} title="About">
        <div className="space-y-3">
          <div className="settings-info-row">
            <span className="settings-info-row__label">Version</span>
            <span className="settings-info-row__value">
              {window.electronAPI?.appVersion ?? healthInfo?.version ?? '...'}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="settings-info-row__label">Build</span>
            <span className="settings-info-row__value">
              {healthInfo?.build ?? '...'}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="settings-info-row__label">Python</span>
            <span className="settings-info-row__value">
              {healthInfo?.python ?? '...'}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="settings-info-row__label">Platform</span>
            <span className="settings-info-row__value">
              {healthInfo?.platform ?? '...'}
            </span>
          </div>
          <div className="settings-info-row">
            <span className="settings-info-row__label">Documentation</span>
            <a
              href="https://github.com/jhd3197/CachiBot"
              target="_blank"
              rel="noopener noreferrer"
              className="settings-info-row__link"
            >
              GitHub
              <ExternalLink className="h-3 w-3" />
            </a>
          </div>
        </div>
      </Section>

      <SetupWizardButton />
      <UpdatesSection healthInfo={healthInfo} />
    </>
  )
}

function SetupWizardButton() {
  const navigate = useNavigate()

  const handleRunWizard = () => {
    useOnboardingStore.getState().resetStep()
    navigate('/onboarding')
  }

  return (
    <Section icon={RefreshCw} title="Setup">
      <div className="settings-card-row">
        <div>
          <h4 className="settings-card-row__title">Run Setup Wizard</h4>
          <p className="settings-card-row__desc">
            Re-run the initial setup to configure API keys, models, and preferences
          </p>
        </div>
        <button
          onClick={handleRunWizard}
          className="settings-btn-accent flex items-center gap-2"
        >
          <RefreshCw className="h-4 w-4" />
          Run Wizard
        </button>
      </div>
    </Section>
  )
}

function UpdatesSection({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const isElectron = window.electronAPI?.isDesktop || healthInfo?.desktop
  if (isElectron) return <ElectronUpdatesSection healthInfo={healthInfo} />
  return <PipUpdatesSection healthInfo={healthInfo} />
}

function ElectronUpdatesSection({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const [checking, setChecking] = useState(false)
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResult | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState<UpdateDownloadProgress | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const [updateError, setUpdateError] = useState<string | null>(null)
  const [autoUpdateEnabled, setAutoUpdateEnabled] = useState(true)
  const [updateChannel, setUpdateChannel] = useState<'stable' | 'beta'>('stable')

  const currentVersion = healthInfo?.version || '...'

  // Listen for startup / periodic auto-check push from main process
  useEffect(() => {
    const api = window.electronAPI
    if (!api) return
    const cleanup = api.onUpdateAvailable((info) => {
      setUpdateInfo(info)
    })
    return cleanup
  }, [])

  // Listen for download progress
  useEffect(() => {
    const api = window.electronAPI
    if (!api) return
    const cleanup = api.onUpdateProgress((progress) => {
      setDownloadProgress(progress)
      if (progress.percent >= 100) {
        setDownloading(false)
        setDownloaded(true)
      }
    })
    return cleanup
  }, [])

  // Listen for update errors
  useEffect(() => {
    const api = window.electronAPI
    if (!api?.onUpdateError) return
    const cleanup = api.onUpdateError((error) => {
      setUpdateError(error.message)
    })
    return cleanup
  }, [])

  // Load auto-update toggle setting
  useEffect(() => {
    window.electronAPI?.getSetting?.('autoUpdateEnabled', true).then((val) => {
      setAutoUpdateEnabled(val as boolean)
    })
  }, [])

  // Load update channel setting
  useEffect(() => {
    window.electronAPI?.getSetting?.('updateChannel', 'stable').then((val) => {
      setUpdateChannel(val as 'stable' | 'beta')
    })
  }, [])

  const handleCheck = async () => {
    const api = window.electronAPI
    if (!api) return
    setChecking(true)
    setUpdateError(null)
    try {
      const result = await api.checkForUpdate()
      setUpdateInfo(result)
    } finally {
      setChecking(false)
    }
  }

  const handleDownload = async () => {
    const api = window.electronAPI
    if (!api) return
    setDownloading(true)
    setDownloadProgress(null)
    const result = await api.downloadUpdate()
    if (!result.success) {
      setDownloading(false)
      toast.error('Failed to download update')
    }
  }

  const handleInstall = () => {
    window.electronAPI?.installUpdate()
  }

  const handleToggleAutoUpdate = async () => {
    const newValue = !autoUpdateEnabled
    await window.electronAPI?.setSetting?.('autoUpdateEnabled', newValue)
    setAutoUpdateEnabled(newValue)
  }

  const handleToggleChannel = async () => {
    const newChannel = updateChannel === 'stable' ? 'beta' : 'stable'
    await window.electronAPI?.setSetting?.('updateChannel', newChannel)
    setUpdateChannel(newChannel)
  }

  // Normalize release notes — electron-updater may return a string or an array
  const releaseNotes = (() => {
    const notes = updateInfo?.releaseNotes
    if (!notes) return null
    if (typeof notes === 'string') return notes
    if (Array.isArray(notes)) {
      return notes.map((n: { version?: string; note?: string }) => n.note || '').join('\n\n')
    }
    return null
  })()

  const buildBadge = healthInfo?.build ? (
    <span
      className={cn(
        'build-badge',
        healthInfo.build === 'release'
          ? 'build-badge--release'
          : healthInfo.build === 'dev'
            ? 'build-badge--dev'
            : 'build-badge--other'
      )}
    >
      {healthInfo.build}
    </span>
  ) : null

  return (
    <Section icon={Download} title="Updates">
      <div className="space-y-4">
        <div className="settings-info-row">
          <span className="settings-info-row__label">Automatic Update Checks</span>
          <button
            onClick={handleToggleAutoUpdate}
            className={cn('settings-btn-secondary text-sm', autoUpdateEnabled ? 'text-green-400' : 'text-zinc-400')}
          >
            {autoUpdateEnabled ? 'Enabled' : 'Disabled'}
          </button>
        </div>

        <div className="settings-info-row">
          <span className="settings-info-row__label">Update Channel</span>
          <button
            onClick={handleToggleChannel}
            className={cn('settings-btn-secondary text-sm', updateChannel === 'beta' ? 'text-yellow-400' : 'text-zinc-400')}
          >
            {updateChannel === 'beta' ? 'Beta' : 'Stable'}
          </button>
        </div>

        <div className="settings-info-row">
          <span className="settings-info-row__label">Current Version</span>
          <span className="settings-info-row__value">
            {currentVersion}
            {buildBadge}
          </span>
        </div>

        {updateInfo?.available && (
          <div className="settings-info-row">
            <span className="settings-info-row__label">Available Version</span>
            <span className="font-mono text-accent-500">{updateInfo.version}</span>
          </div>
        )}

        {updateInfo && !updateInfo.available && (
          <div className="settings-info-row">
            <span className="settings-info-row__label">Status</span>
            <span className="text-green-400">Up to date</span>
          </div>
        )}

        {updateError && (
          <div className="settings-info-row">
            <span className="settings-info-row__label">Last Error</span>
            <span className="text-red-400 text-sm">{updateError}</span>
          </div>
        )}

        {updateInfo?.available && releaseNotes && (
          <details className="mt-2">
            <summary className="cursor-pointer text-sm text-[var(--color-text-secondary)] hover:text-[var(--color-text-primary)]">
              Release notes
            </summary>
            <div className="mt-2 rounded-lg border border-[var(--color-border-primary)] bg-[var(--color-bg-app)] p-4">
              <MarkdownRenderer content={releaseNotes} />
            </div>
          </details>
        )}

        {downloading && downloadProgress && (
          <div className="space-y-1">
            <div className="flex justify-between text-sm text-[var(--color-text-secondary)]">
              <span>Downloading...</span>
              <span>{Math.round(downloadProgress.percent)}%</span>
            </div>
            <div className="h-2 overflow-hidden rounded-full bg-[var(--color-bg-tertiary)]">
              <div
                className="h-full rounded-full bg-accent-500 transition-all"
                style={{ width: `${downloadProgress.percent}%` }}
              />
            </div>
          </div>
        )}

        <div className="flex gap-2">
          {!downloaded && !downloading && (
            <>
              <button
                onClick={handleCheck}
                disabled={checking}
                className="settings-btn-secondary flex items-center gap-2"
              >
                {checking ? (
                  <Loader2 className="h-4 w-4 animate-spin" />
                ) : (
                  <RefreshCw className="h-4 w-4" />
                )}
                Check for Updates
              </button>
              {updateInfo?.available && (
                <button
                  onClick={handleDownload}
                  className="settings-btn-accent flex items-center gap-2"
                >
                  <Download className="h-4 w-4" />
                  Download Update
                </button>
              )}
            </>
          )}
          {downloaded && (
            <button
              onClick={handleInstall}
              className="settings-btn-accent flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Restart &amp; Install
            </button>
          )}
        </div>
      </div>
    </Section>
  )
}

function PipUpdatesSection({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const {
    checkResult,
    isChecking,
    optIntoBeta,
    setOptIntoBeta,
    checkForUpdate,
    openDialog,
    lastCheckAt,
  } = useUpdateStore()

  useEffect(() => {
    checkForUpdate()
  }, [checkForUpdate])

  const currentVersion = window.electronAPI?.appVersion || checkResult?.current_version || healthInfo?.version || '...'
  const latestStable = checkResult?.latest_stable
  const latestPrerelease = checkResult?.latest_prerelease
  const hasUpdate = checkResult?.update_available || checkResult?.prerelease_available

  const formatRelativeTime = (timestamp: number) => {
    if (!timestamp) return 'Never'
    const seconds = Math.floor((Date.now() - timestamp) / 1000)
    if (seconds < 60) return 'Just now'
    const minutes = Math.floor(seconds / 60)
    if (minutes < 60) return `${minutes}m ago`
    const hours = Math.floor(minutes / 60)
    if (hours < 24) return `${hours}h ago`
    const days = Math.floor(hours / 24)
    return `${days}d ago`
  }

  const buildBadge = healthInfo?.build ? (
    <span
      className={cn(
        'build-badge',
        healthInfo.build === 'release'
          ? 'build-badge--release'
          : healthInfo.build === 'dev'
            ? 'build-badge--dev'
            : 'build-badge--other'
      )}
    >
      {healthInfo.build}
    </span>
  ) : null

  return (
    <Section icon={Download} title="Updates">
      <div className="space-y-4">
        <div className="settings-info-row">
          <span className="settings-info-row__label">Current Version</span>
          <span className="settings-info-row__value">
            {currentVersion}
            {buildBadge}
          </span>
        </div>

        <div className="settings-info-row">
          <span className="settings-info-row__label">Latest Version</span>
          {latestStable ? (
            <span
              className={cn(
                'font-mono',
                checkResult?.update_available
                  ? 'text-accent-500'
                  : 'text-green-400'
              )}
            >
              {latestStable}
              {!checkResult?.update_available && ' (up to date)'}
            </span>
          ) : (
            <span className="text-[var(--color-text-secondary)]">—</span>
          )}
        </div>

        {latestPrerelease && optIntoBeta && (
          <div className="settings-info-row">
            <span className="settings-info-row__label">Latest Pre-release</span>
            <span className="font-mono text-amber-400">{latestPrerelease}</span>
          </div>
        )}

        <ToggleField
          label="Include Pre-release Versions"
          description="Opt into beta and development builds"
          checked={optIntoBeta}
          onChange={setOptIntoBeta}
        />

        <div className="flex items-center justify-between">
          <span className="text-sm text-[var(--color-text-secondary)]">
            Last checked: {formatRelativeTime(lastCheckAt)}
          </span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => checkForUpdate(true)}
            disabled={isChecking}
            className="settings-btn-secondary flex items-center gap-2"
          >
            {isChecking ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <RefreshCw className="h-4 w-4" />
            )}
            Check Now
          </button>
          {hasUpdate && (
            <button
              onClick={openDialog}
              className="flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-500"
            >
              <Download className="h-4 w-4" />
              Update Available — View Details
            </button>
          )}
        </div>
      </div>
    </Section>
  )
}

// =============================================================================
// APPEARANCE SETTINGS
// =============================================================================

function AppearanceSettings({
  theme,
  setTheme,
  accentColor,
  setAccentColor,
  customHex,
  setCustomHex,
  sidebarCollapsed,
  setSidebarCollapsed,
}: {
  theme: Theme
  setTheme: (theme: Theme) => void
  accentColor: AccentColor
  setAccentColor: (color: AccentColor) => void
  customHex: string
  setCustomHex: (hex: string) => void
  sidebarCollapsed: boolean
  setSidebarCollapsed: (collapsed: boolean) => void
}) {
  const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ]

  const colorOptions = Object.entries(accentColors) as [PresetColor, typeof accentColors[PresetColor]][]
  const customPalette = generatePalette(customHex)

  return (
    <>
      <Section icon={Palette} title="Theme">
        <div className="space-y-4">
          <Field label="Color Theme">
            <div className="flex gap-2">
              {themeOptions.map((option) => (
                <button
                  key={option.value}
                  onClick={() => setTheme(option.value)}
                  className={cn(
                    'settings-theme-btn',
                    theme === option.value && 'settings-theme-btn--active'
                  )}
                >
                  <option.icon className="h-4 w-4" />
                  {option.label}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Accent Color">
            <div className="settings-color-grid">
              {colorOptions.map(([value, { palette }]) => (
                <button
                  key={value}
                  onClick={() => setAccentColor(value)}
                  className={cn(
                    'settings-color-circle',
                    accentColor === value && 'settings-color-circle--active'
                  )}
                  style={{
                    backgroundColor: palette[500],
                    boxShadow: accentColor === value ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${palette[500]}` : undefined,
                  }}
                  title={value.charAt(0).toUpperCase() + value.slice(1)}
                />
              ))}
              <label
                className={cn(
                  'settings-color-circle settings-color-circle--custom',
                  accentColor === 'custom' && 'settings-color-circle--active'
                )}
                style={{
                  backgroundColor: customPalette[500],
                  boxShadow: accentColor === 'custom' ? `0 0 0 2px var(--color-bg-primary), 0 0 0 4px ${customPalette[500]}` : undefined,
                }}
                title="Custom"
              >
                <Plus className="settings-color-circle__icon" />
                <input
                  type="color"
                  value={customHex}
                  onChange={(e) => setCustomHex(e.target.value)}
                  className="settings-color-circle__input"
                />
              </label>
            </div>
          </Field>
        </div>
      </Section>

      <Section icon={Sliders} title="Layout">
        <div className="space-y-4">
          <ToggleField
            label="Collapse Sidebar by Default"
            description="Start with sidebar in compact mode"
            checked={sidebarCollapsed}
            onChange={setSidebarCollapsed}
          />
          <Field label="Chat Message Style">
            <select className="settings-select w-full">
              <option value="detailed">Detailed (with metadata)</option>
              <option value="compact">Compact</option>
              <option value="minimal">Minimal</option>
            </select>
          </Field>
        </div>
      </Section>

      <Section icon={Code} title="Code Display">
        <div className="space-y-4">
          <Field label="Code Font">
            <select className="settings-select w-full">
              <option value="jetbrains-mono">JetBrains Mono</option>
              <option value="fira-code">Fira Code</option>
              <option value="monaco">Monaco</option>
              <option value="consolas">Consolas</option>
            </select>
          </Field>
          <ToggleField
            label="Enable Ligatures"
            description="Display programming ligatures in code"
            checked={true}
            onChange={() => {}}
          />
        </div>
      </Section>
    </>
  )
}

// =============================================================================
// MODELS SETTINGS
// =============================================================================

const MODEL_PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  anthropic: 'Anthropic',
  google: 'Google',
  groq: 'Groq',
  grok: 'xAI Grok',
  openrouter: 'OpenRouter',
  moonshot: 'Moonshot AI',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  azure: 'Azure OpenAI',
  zai: 'Z.ai (Zhipu)',
  modelscope: 'ModelScope',
  local_http: 'Local HTTP',
}

const MODEL_PROVIDER_COLORS: Record<string, string> = {
  openai: 'bg-green-500',
  anthropic: 'bg-orange-500',
  google: 'bg-blue-500',
  groq: 'bg-purple-500',
  grok: 'bg-red-500',
  openrouter: 'bg-indigo-500',
  moonshot: 'bg-cyan-500',
  ollama: 'bg-zinc-500',
  lmstudio: 'bg-yellow-500',
  azure: 'bg-sky-500',
  zai: 'bg-emerald-500',
  modelscope: 'bg-pink-500',
  local_http: 'bg-zinc-600',
}

function formatModelNum(n: number | null) {
  if (!n) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(0)}K`
  return n.toString()
}

function formatModelPrice(rate: number | null) {
  if (rate == null) return '—'
  if (rate === 0) return 'Free'
  if (rate >= 1) return `$${rate.toFixed(2)}`
  return `$${rate.toFixed(4)}`.replace(/0+$/, '')
}

function ModelsSettings() {
  const {
    groups,
    embeddingGroups,
    defaultModel,
    defaultEmbeddingModel,
    loading,
    updateDefaultModel,
    updateDefaultEmbeddingModel,
    refresh,
  } = useModelsStore()
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleDefaultModelChange = async (model: string) => {
    if (model) {
      await updateDefaultModel(model)
    }
  }

  const handleEmbeddingModelChange = async (model: string) => {
    if (model) {
      await updateDefaultEmbeddingModel(model)
      toast.success('Embedding model updated')
    }
  }

  // Filter models by search
  const filteredGroups: Record<string, import('../../api/models').ModelInfo[]> = {}
  for (const [provider, modelList] of Object.entries(groups)) {
    const filtered = search
      ? modelList.filter((m) => m.id.toLowerCase().includes(search.toLowerCase()))
      : modelList
    if (filtered.length > 0) {
      filteredGroups[provider] = filtered
    }
  }

  const totalModels = Object.values(groups).reduce((s, g) => s + g.length, 0)
  const filteredTotal = Object.values(filteredGroups).reduce((s, g) => s + g.length, 0)
  const providerCount = Object.keys(filteredGroups).length

  const toggleProvider = (provider: string) =>
    setExpanded((prev) => ({ ...prev, [provider]: !prev[provider] }))

  // Auto-expand all when searching
  const isSearching = search.length > 0

  return (
    <>
      {/* Default model */}
      <Section icon={Brain} title="Default Model">
        <div className="space-y-4">
          <Field label="System Default Model">
            <ModelSelect
              value={defaultModel}
              onChange={handleDefaultModelChange}
              placeholder="Select default model..."
              className="w-full"
            />
            <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
              Used when no specific model is configured for a bot.
            </p>
          </Field>
        </div>
      </Section>

      {/* Embedding model */}
      <Section icon={Database} title="Embedding Model">
        <div className="space-y-4">
          <Field label="Document Embedding Model">
            <ModelSelect
              value={defaultEmbeddingModel}
              onChange={handleEmbeddingModelChange}
              placeholder="Select embedding model..."
              className="w-full"
              groups={embeddingGroups}
              filter={(m) => m.supports_embedding}
            />
            <p className="mt-2 text-xs text-[var(--color-text-secondary)]">
              Used for knowledge base document indexing and retrieval. Changing this model requires re-indexing existing documents.
            </p>
          </Field>
        </div>
      </Section>

      {/* Available models - collapsible providers */}
      <Section icon={Brain} title="Available Models">
        <div className="space-y-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--color-text-secondary)]" />
            <input
              type="text"
              placeholder="Search models..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="settings-input settings-input--search w-full"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 settings-modal__close-btn"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Summary */}
          <p className="text-xs text-[var(--color-text-secondary)]">
            {isSearching
              ? `${filteredTotal} result${filteredTotal !== 1 ? 's' : ''} across ${providerCount} provider${providerCount !== 1 ? 's' : ''}`
              : `${totalModels} model${totalModels !== 1 ? 's' : ''} from ${providerCount} provider${providerCount !== 1 ? 's' : ''}`}
          </p>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center gap-2 py-6 text-[var(--color-text-secondary)]">
              <Loader2 className="h-4 w-4 animate-spin" />
              Discovering models...
            </div>
          )}

          {/* Empty */}
          {!loading && totalModels === 0 && (
            <div className="text-center py-6">
              <Brain className="h-7 w-7 text-[var(--color-text-tertiary)] mx-auto mb-2" />
              <p className="text-sm text-[var(--color-text-secondary)]">No models available</p>
              <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
                Configure API keys to discover models.
              </p>
            </div>
          )}

          {/* No search results */}
          {!loading && totalModels > 0 && filteredTotal === 0 && (
            <div className="text-center py-6 text-[var(--color-text-secondary)] text-sm">
              No models match your search
            </div>
          )}

          {/* Provider accordions */}
          {!loading && (
            <div className="space-y-1.5">
              {Object.entries(filteredGroups)
                .sort(([a], [b]) => a.localeCompare(b))
                .map(([provider, modelList]) => {
                  const label =
                    MODEL_PROVIDER_LABELS[provider] ||
                    provider.charAt(0).toUpperCase() + provider.slice(1)
                  const dotColor = MODEL_PROVIDER_COLORS[provider] || 'bg-zinc-500'
                  const isOpen = isSearching || expanded[provider]

                  return (
                    <div
                      key={provider}
                      className="model-provider"
                    >
                      {/* Provider header - clickable */}
                      <button
                        onClick={() => toggleProvider(provider)}
                        className="model-provider__header"
                      >
                        <ChevronRight
                          className={cn(
                            'h-3.5 w-3.5 text-[var(--color-text-secondary)] transition-transform',
                            isOpen && 'rotate-90'
                          )}
                        />
                        <span className={cn('h-2 w-2 rounded-full shrink-0', dotColor)} />
                        <span className="model-provider__label">
                          {label}
                        </span>
                        <span className="model-provider__count">
                          {modelList.length}
                        </span>
                      </button>

                      {/* Model list */}
                      {isOpen && (
                        <div className="model-provider__list">
                          {modelList.map((m) => {
                            const isDefault = m.id === defaultModel
                            return (
                              <div
                                key={m.id}
                                className={cn(
                                  'model-row group',
                                  isDefault && 'model-row--default'
                                )}
                              >
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className="model-row__name truncate"
                                      title={m.id}
                                    >
                                      {m.id}
                                    </span>
                                    {isDefault && (
                                      <Star className="h-3 w-3 shrink-0 fill-current text-accent-500" />
                                    )}
                                    {m.is_reasoning && (
                                      <Sparkles className="h-3 w-3 shrink-0 text-purple-400" />
                                    )}
                                  </div>
                                  <div className="model-row__meta">
                                    <span>{formatModelNum(m.context_window)} ctx</span>
                                    {m.pricing && (
                                      <>
                                        <span className="model-row__separator">/</span>
                                        <span className="model-row__price-in">
                                          {formatModelPrice(m.pricing.input)}
                                        </span>
                                        <span className="model-row__separator">&middot;</span>
                                        <span className="model-row__price-out">
                                          {formatModelPrice(m.pricing.output)}
                                        </span>
                                      </>
                                    )}
                                  </div>
                                </div>
                                {!isDefault && (
                                  <button
                                    onClick={() => handleDefaultModelChange(m.id)}
                                    className="model-row__star-btn"
                                    title="Set as default"
                                  >
                                    <Star className="h-3.5 w-3.5" />
                                  </button>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
                    </div>
                  )
                })}
            </div>
          )}
        </div>
      </Section>
    </>
  )
}

// =============================================================================
// API KEYS SETTINGS
// =============================================================================

const CLOUD_PROVIDERS = new Set([
  'openai', 'claude', 'google', 'groq', 'grok',
  'openrouter', 'moonshot', 'zai', 'modelscope', 'azure',
  'stability', 'elevenlabs',
])

const PROVIDER_LABELS: Record<string, string> = {
  openai: 'OpenAI',
  claude: 'Anthropic / Claude',
  google: 'Google AI',
  groq: 'Groq',
  grok: 'Grok (xAI)',
  openrouter: 'OpenRouter',
  moonshot: 'Moonshot',
  zai: 'Zhipu AI',
  modelscope: 'ModelScope',
  azure: 'Azure OpenAI',
  stability: 'Stability AI',
  elevenlabs: 'ElevenLabs',
  ollama: 'Ollama',
  lmstudio: 'LM Studio',
  local_http: 'Local HTTP',
}

function ApiKeysSettings() {
  const { providers, loading, refresh, update, remove } = useProvidersStore()
  const { refresh: refreshModels } = useModelsStore()
  const [editValues, setEditValues] = useState<Record<string, string>>({})
  const [visibleKeys, setVisibleKeys] = useState<Set<string>>(new Set())
  const [saving, setSaving] = useState<string | null>(null)

  useEffect(() => {
    refresh()
  }, [refresh])

  const cloudProviders = providers.filter((p) => CLOUD_PROVIDERS.has(p.name))
  const localProviders = providers.filter((p) => !CLOUD_PROVIDERS.has(p.name))

  const handleSave = async (name: string) => {
    const value = editValues[name]
    if (!value?.trim()) return

    setSaving(name)
    try {
      await update(name, value.trim())
      setEditValues((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
      setVisibleKeys((prev) => {
        const next = new Set(prev)
        next.delete(name)
        return next
      })
      // Refresh models so newly available models show up
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key saved`)
    } catch {
      toast.error(`Failed to save ${PROVIDER_LABELS[name] || name} key`)
    } finally {
      setSaving(null)
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await remove(name)
      setEditValues((prev) => {
        const next = { ...prev }
        delete next[name]
        return next
      })
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key removed`)
    } catch {
      toast.error(`Failed to remove ${PROVIDER_LABELS[name] || name} key`)
    }
  }

  const toggleVisibility = (name: string) => {
    setVisibleKeys((prev) => {
      const next = new Set(prev)
      if (next.has(name)) {
        next.delete(name)
      } else {
        next.add(name)
      }
      return next
    })
  }

  const renderProviderCard = (provider: typeof providers[0]) => {
    const isEditing = provider.name in editValues
    const inputValue = editValues[provider.name] ?? ''
    const isVisible = visibleKeys.has(provider.name)
    const isSaving = saving === provider.name
    const label = PROVIDER_LABELS[provider.name] || provider.name
    const isEndpoint = provider.type === 'endpoint'

    return (
      <div
        key={provider.name}
        className="provider-card"
      >
        <div className="provider-card__header">
          <div className="flex items-center gap-2">
            <h4 className="provider-card__name">{label}</h4>
            <span
              className={cn(
                'provider-card__badge',
                provider.configured
                  ? 'provider-card__badge--active'
                  : 'provider-card__badge--inactive'
              )}
            >
              {provider.configured ? 'Active' : 'Not set'}
            </span>
          </div>
          {provider.configured && (
            <button
              onClick={() => handleDelete(provider.name)}
              className="provider-card__delete-btn"
              title="Remove key"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>

        <p className="provider-card__env-key">
          {isEndpoint ? 'Endpoint URL' : 'API Key'}: <code className="text-[var(--color-text-secondary)]">{provider.env_key}</code>
          {provider.default && (
            <span className="ml-1 text-[var(--color-text-secondary)]">(default: {provider.default})</span>
          )}
        </p>

        {/* Show masked value if configured and not editing */}
        {provider.configured && !isEditing && (
          <div className="flex items-center gap-2">
            <div className="provider-card__masked">
              {isVisible ? provider.masked_value : provider.masked_value.replace(/./g, '*').slice(0, 20) + '****'}
            </div>
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="provider-card__visibility-btn"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
            </button>
          </div>
        )}

        {/* Input for new/updated key */}
        <div className="flex gap-2">
          <input
            type={isVisible || isEndpoint ? 'text' : 'password'}
            value={inputValue}
            onChange={(e) =>
              setEditValues((prev) => ({ ...prev, [provider.name]: e.target.value }))
            }
            placeholder={isEndpoint ? (provider.default || 'Enter endpoint URL...') : 'Enter API key...'}
            className="provider-card__key-input flex-1"
          />
          {!isEndpoint && (
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="provider-card__visibility-btn-bordered"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
            </button>
          )}
          <button
            onClick={() => handleSave(provider.name)}
            disabled={!inputValue.trim() || isSaving}
            className="provider-card__save-btn"
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Save className="h-4 w-4" />
            )}
            Save
          </button>
        </div>
      </div>
    )
  }

  if (loading && providers.length === 0) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-accent-500" />
      </div>
    )
  }

  return (
    <>
      <Section icon={Cloud} title="Cloud Providers">
        <div className="space-y-4">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Configure API keys for cloud-based AI providers. Models will be automatically discovered
            once a valid key is saved.
          </p>
          {cloudProviders.map(renderProviderCard)}
        </div>
      </Section>

      <Section icon={Server} title="Local Providers">
        <div className="space-y-4">
          <p className="text-sm text-[var(--color-text-secondary)]">
            Configure endpoints for locally-running model servers.
          </p>
          {localProviders.map(renderProviderCard)}
        </div>
      </Section>
    </>
  )
}

// =============================================================================
// ADVANCED SETTINGS
// =============================================================================

function AdvancedSettings({
  config,
}: {
  config: Config | null
}) {
  return (
    <>
      <Section icon={Shield} title="Security">
        <div className="space-y-4">
          <ToggleField
            label="Require Approval for Actions"
            description="Ask before executing potentially dangerous operations"
            checked={config?.agent.approveActions ?? true}
            onChange={() => {}}
          />
          <Field label="Sandbox Timeout">
            <div className="flex items-center gap-3">
              <input
                type="number"
                value={config?.sandbox.timeoutSeconds ?? 30}
                className="settings-input w-24"
              />
              <span className="text-sm text-[var(--color-text-secondary)]">seconds</span>
            </div>
          </Field>
        </div>
      </Section>

      <Section icon={Sliders} title="AI Configuration">
        <div className="space-y-4">
          <Field label="Default Temperature">
            <div className="flex items-center gap-4">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                defaultValue={config?.agent.temperature ?? 0.7}
                className="flex-1"
              />
              <span className="w-12 text-center text-sm text-[var(--color-text-secondary)]">
                {config?.agent.temperature ?? 0.7}
              </span>
            </div>
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              Controls randomness in responses (0 = deterministic, 1 = creative)
            </p>
          </Field>

          <Field label="Max Iterations">
            <input
              type="number"
              value={config?.agent.maxIterations ?? 20}
              min={1}
              max={100}
              className="settings-input w-32"
            />
            <p className="mt-1 text-xs text-[var(--color-text-secondary)]">
              Maximum tool calls per conversation turn
            </p>
          </Field>
        </div>
      </Section>

      <Section icon={Keyboard} title="Keyboard Shortcuts">
        <div className="space-y-3">
          <ShortcutItem label="New Chat" shortcut="Ctrl + N" />
          <ShortcutItem label="Toggle Sidebar" shortcut="Ctrl + B" />
          <ShortcutItem label="Command Palette" shortcut="Ctrl + K" />
          <ShortcutItem label="Settings" shortcut="Ctrl + ," />
          <ShortcutItem label="Send Message" shortcut="Enter" />
          <ShortcutItem label="New Line" shortcut="Shift + Enter" />
        </div>
      </Section>
    </>
  )
}

// =============================================================================
// DATA SETTINGS
// =============================================================================

function DataSettings() {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showTelemetryPreview, setShowTelemetryPreview] = useState(false)
  const [telemetryPayload, setTelemetryPayload] = useState<Record<string, unknown> | null>(null)
  const [showResetIdConfirm, setShowResetIdConfirm] = useState(false)
  const { status: telemetryStatus, refresh: refreshTelemetry } = useTelemetryStore()

  useEffect(() => {
    refreshTelemetry()
  }, [refreshTelemetry])

  const handleToggleTelemetry = async () => {
    try {
      await updateTelemetrySettings({ enabled: !telemetryStatus?.enabled })
      await refreshTelemetry()
      toast.success(telemetryStatus?.enabled ? 'Telemetry disabled' : 'Telemetry enabled')
    } catch {
      toast.error('Failed to update telemetry settings')
    }
  }

  const handleViewTelemetryReport = async () => {
    try {
      const payload = await getTelemetryPreview()
      setTelemetryPayload(payload)
      setShowTelemetryPreview(true)
    } catch {
      toast.error('Failed to load telemetry preview')
    }
  }

  const handleResetId = async () => {
    try {
      await resetTelemetryId()
      await refreshTelemetry()
      setShowResetIdConfirm(false)
      toast.success('Install ID has been reset')
    } catch {
      toast.error('Failed to reset install ID')
    }
  }

  const handleExport = () => {
    const data = {
      bots: localStorage.getItem('cachibot-bots'),
      chats: localStorage.getItem('cachibot-chats'),
      jobs: localStorage.getItem('cachibot-jobs'),
      tasks: localStorage.getItem('cachibot-tasks'),
      connections: localStorage.getItem('cachibot-connections'),
      ui: localStorage.getItem('cachibot-ui'),
      usage: localStorage.getItem('cachibot-usage'),
      exportedAt: new Date().toISOString(),
    }

    const blob = new Blob([JSON.stringify(data, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `cachibot-backup-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  const handleClearAll = () => {
    localStorage.removeItem('cachibot-bots')
    localStorage.removeItem('cachibot-chats')
    localStorage.removeItem('cachibot-jobs')
    localStorage.removeItem('cachibot-tasks')
    localStorage.removeItem('cachibot-connections')
    localStorage.removeItem('cachibot-usage')
    window.location.reload()
  }

  return (
    <>
      <Section icon={Shield} title="Privacy & Telemetry">
        <div className="space-y-4">
          {/* Telemetry toggle */}
          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">Anonymous Analytics</h4>
              <p className="settings-card-row__desc">
                Send anonymous usage statistics to help improve CachiBot
              </p>
            </div>
            <button
              onClick={handleToggleTelemetry}
              className={cn(
                'settings-toggle__switch',
                telemetryStatus?.enabled
                  ? 'settings-toggle__switch--on'
                  : 'settings-toggle__switch--off'
              )}
            >
              <span
                className={cn(
                  'settings-toggle__knob',
                  telemetryStatus?.enabled ? 'settings-toggle__knob--on' : 'settings-toggle__knob--off'
                )}
              />
            </button>
          </div>

          {/* View report */}
          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">View Telemetry Report</h4>
              <p className="settings-card-row__desc">
                See exactly what data would be sent
              </p>
            </div>
            <button
              onClick={handleViewTelemetryReport}
              className="settings-btn-secondary flex items-center gap-2"
            >
              <EyeIcon className="h-4 w-4" />
              View
            </button>
          </div>

          {/* Reset ID */}
          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">Reset Install ID</h4>
              <p className="settings-card-row__desc">
                Generate a new anonymous identifier{telemetryStatus?.install_id && (
                  <span className="ml-1 font-mono text-xs text-[var(--color-text-secondary)]">
                    ({telemetryStatus.install_id.slice(0, 8)}...)
                  </span>
                )}
              </p>
            </div>
            <button
              onClick={() => setShowResetIdConfirm(true)}
              className="settings-btn-secondary flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Reset
            </button>
          </div>

          {/* Last sent */}
          {telemetryStatus?.last_sent && (
            <p className="text-xs text-[var(--color-text-secondary)]">
              Last sent: {new Date(telemetryStatus.last_sent).toLocaleString()}
            </p>
          )}

          {/* Telemetry info link */}
          <a
            href="https://cachibot.ai/telemetry"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs text-accent-500 hover:text-accent-400"
          >
            Learn more about what we collect
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </Section>

      {/* Telemetry preview modal */}
      {showTelemetryPreview && telemetryPayload && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '32rem' }}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="settings-modal__heading">Telemetry Report Preview</h2>
              <button
                onClick={() => setShowTelemetryPreview(false)}
                className="settings-modal__close-btn"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <pre className="settings-modal__pre">
              {JSON.stringify(telemetryPayload, null, 2)}
            </pre>
            <div className="settings-modal__footer">
              <button
                onClick={() => setShowTelemetryPreview(false)}
                className="settings-modal__cancel-btn"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset ID confirmation modal */}
      {showResetIdConfirm && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '28rem' }}>
            <div className="mb-4 flex items-center gap-3 text-[var(--color-text-secondary)]">
              <RefreshCw className="h-6 w-6" />
              <h2 className="settings-modal__heading">Reset Install ID?</h2>
            </div>
            <p className="mb-6 text-sm settings-modal__body-text">
              This will generate a new anonymous identifier. Your previous telemetry data
              will no longer be associated with this installation.
            </p>
            <div className="settings-modal__footer">
              <button
                onClick={() => setShowResetIdConfirm(false)}
                className="settings-modal__cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleResetId}
                className="settings-modal__confirm-btn"
              >
                Reset ID
              </button>
            </div>
          </div>
        </div>
      )}

      <Section icon={Database} title="Data Management">
        <div className="space-y-4">
          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">Export Data</h4>
              <p className="settings-card-row__desc">
                Download all your data as a JSON file
              </p>
            </div>
            <button
              onClick={handleExport}
              className="settings-btn-accent flex items-center gap-2"
            >
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>

          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">Import Data</h4>
              <p className="settings-card-row__desc">
                Restore from a previous backup
              </p>
            </div>
            <button className="settings-btn-secondary flex items-center gap-2">
              <Upload className="h-4 w-4" />
              Import
            </button>
          </div>
        </div>
      </Section>

      {/* Bot Data Manager */}
      <BotDataManager />

      <Section icon={RefreshCw} title="Cache">
        <div className="space-y-4">
          <div className="settings-card-row">
            <div>
              <h4 className="settings-card-row__title">Clear Cache</h4>
              <p className="settings-card-row__desc">
                Remove cached responses and temporary data
              </p>
            </div>
            <button
              onClick={async () => {
                try {
                  if (window.electronAPI?.clearCache) {
                    const result = await window.electronAPI.clearCache()
                    if (result.success) {
                      toast.success('Cache cleared')
                    } else {
                      toast.error(result.error || 'Failed to clear cache')
                    }
                  } else {
                    // Browser mode: clear marketplace cache from localStorage
                    const keys = Object.keys(localStorage).filter(k =>
                      k.startsWith('cachibot_marketplace_cache_')
                    )
                    keys.forEach(k => localStorage.removeItem(k))
                    toast.success(`Cleared ${keys.length} cached entries`)
                    window.location.reload()
                  }
                } catch {
                  toast.error('Failed to clear cache')
                }
              }}
              className="settings-btn-secondary flex items-center gap-2"
            >
              <RefreshCw className="h-4 w-4" />
              Clear
            </button>
          </div>
        </div>
      </Section>

      <Section icon={AlertTriangle} title="Danger Zone" danger>
        <div className="settings-danger-zone">
          <h4 className="settings-danger-zone__title">Delete All Data</h4>
          <p className="settings-danger-zone__desc">
            Permanently delete all bots, chats, jobs, tasks, and settings. This
            cannot be undone.
          </p>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="settings-btn-danger mt-3"
          >
            <Trash2 className="h-4 w-4" />
            Delete Everything
          </button>
        </div>
      </Section>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '28rem' }}>
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="settings-modal__heading">Delete All Data</h2>
            </div>
            <p className="mb-6 settings-modal__body-text">
              Are you sure you want to delete all your data? This will remove all
              bots, chats, jobs, tasks, connections, and settings.
            </p>
            <div className="settings-modal__footer">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="settings-modal__cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleClearAll}
                className="settings-modal__confirm-btn--danger"
              >
                Delete Everything
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

// =============================================================================
// BOT DATA MANAGER
// =============================================================================

type DataCategory = 'chats' | 'jobs' | 'tasks' | 'usage' | 'platform'

interface BotDataInfo {
  botId: string
  botName: string
  botColor: string
  chatsCount: number
  messagesCount: number
  jobsCount: number
  tasksCount: number
  hasUsageData: boolean
  platformChatsCount: number
}

function BotDataManager() {
  const { bots } = useBotStore()
  const { chats, messages } = useChatStore()
  const { jobs } = useJobStore()
  const { tasks } = useTaskStore()
  const { stats, clearBotStats } = useUsageStore()

  const [expandedBots, setExpandedBots] = useState<Set<string>>(new Set())
  const [selectedItems, setSelectedItems] = useState<Map<string, Set<DataCategory>>>(new Map())
  const [showConfirmModal, setShowConfirmModal] = useState(false)
  const [clearing, setClearing] = useState(false)
  const [platformCounts, setPlatformCounts] = useState<Record<string, number>>({})
  const [loadingPlatform, setLoadingPlatform] = useState(false)

  // Load platform chat counts from backend
  useEffect(() => {
    const loadPlatformCounts = async () => {
      setLoadingPlatform(true)
      const counts: Record<string, number> = {}

      for (const bot of bots) {
        try {
          const { getPlatformChats } = await import('../../api/client')
          const platformChats = await getPlatformChats(bot.id)
          counts[bot.id] = platformChats.length
        } catch {
          counts[bot.id] = 0
        }
      }

      setPlatformCounts(counts)
      setLoadingPlatform(false)
    }

    loadPlatformCounts()
  }, [bots])

  // Compute data info for each bot
  const botDataInfos = useMemo((): BotDataInfo[] => {
    return bots.map((bot) => {
      const allBotChats = chats.filter((c) => c.botId === bot.id)
      // Local chats = chats WITHOUT platform field (pure local conversations)
      const localChats = allBotChats.filter((c) => !c.platform)
      // Platform chats in local storage (synced from Telegram/Discord)
      const localPlatformChats = allBotChats.filter((c) => c.platform)

      const localMessagesCount = localChats.reduce(
        (acc, chat) => acc + (messages[chat.id]?.length || 0),
        0
      )
      const botJobs = jobs.filter((j) => j.botId === bot.id)
      const botTasks = tasks.filter((t) => t.botId === bot.id)
      const hasUsageData = !!stats.byBot[bot.id]

      // Platform count: max of backend count and local platform chats
      // (they should be the same, but take max to ensure we show something)
      const backendPlatformCount = platformCounts[bot.id] || 0
      const effectivePlatformCount = Math.max(backendPlatformCount, localPlatformChats.length)

      return {
        botId: bot.id,
        botName: bot.name,
        botColor: bot.color || '#22c55e',
        chatsCount: localChats.length,
        messagesCount: localMessagesCount,
        jobsCount: botJobs.length,
        tasksCount: botTasks.length,
        hasUsageData,
        platformChatsCount: effectivePlatformCount,
      }
    })
  }, [bots, chats, messages, jobs, tasks, stats.byBot, platformCounts])

  // Toggle bot expansion
  const toggleBot = (botId: string) => {
    setExpandedBots((prev) => {
      const next = new Set(prev)
      if (next.has(botId)) {
        next.delete(botId)
      } else {
        next.add(botId)
      }
      return next
    })
  }

  // Toggle category selection for a bot
  const toggleCategory = (botId: string, category: DataCategory) => {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      const botCategories = next.get(botId) || new Set()
      const newBotCategories = new Set(botCategories)

      if (newBotCategories.has(category)) {
        newBotCategories.delete(category)
      } else {
        newBotCategories.add(category)
      }

      if (newBotCategories.size === 0) {
        next.delete(botId)
      } else {
        next.set(botId, newBotCategories)
      }
      return next
    })
  }

  // Select all categories for a bot
  const selectAllForBot = (botId: string, info: BotDataInfo) => {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      const categories = new Set<DataCategory>()
      if (info.chatsCount > 0) categories.add('chats')
      if (info.jobsCount > 0) categories.add('jobs')
      if (info.tasksCount > 0) categories.add('tasks')
      if (info.hasUsageData) categories.add('usage')
      if (info.platformChatsCount > 0) categories.add('platform')

      if (categories.size > 0) {
        next.set(botId, categories)
      }
      return next
    })
  }

  // Clear selection for a bot
  const clearSelectionForBot = (botId: string) => {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      next.delete(botId)
      return next
    })
  }

  // Check if anything is selected
  const hasSelection = selectedItems.size > 0

  // Get total items selected
  const getTotalSelectedItems = () => {
    let total = 0
    selectedItems.forEach((categories, botId) => {
      const info = botDataInfos.find((b) => b.botId === botId)
      if (!info) return
      if (categories.has('chats')) total += info.chatsCount
      if (categories.has('jobs')) total += info.jobsCount
      if (categories.has('tasks')) total += info.tasksCount
      if (categories.has('usage')) total += 1
      if (categories.has('platform')) total += info.platformChatsCount
    })
    return total
  }

  // Perform the actual deletion
  const handleClearSelected = async () => {
    setClearing(true)

    // Get stores directly for mutations
    const chatStore = useChatStore.getState()
    const jobStore = useJobStore.getState()
    const taskStore = useTaskStore.getState()

    // Process each bot's selected categories
    for (const [botId, categories] of selectedItems) {
      // Clear local chats and messages (non-platform only)
      if (categories.has('chats')) {
        const localOnlyChats = chats.filter((c) => c.botId === botId && !c.platform)
        localOnlyChats.forEach((chat) => {
          chatStore.deleteChat(chat.id)
        })
      }

      // Clear jobs
      if (categories.has('jobs')) {
        const botJobs = jobs.filter((j) => j.botId === botId)
        botJobs.forEach((job) => {
          jobStore.deleteJob(job.id)
        })
      }

      // Clear tasks
      if (categories.has('tasks')) {
        const botTasks = tasks.filter((t) => t.botId === botId)
        botTasks.forEach((task) => {
          taskStore.deleteTask(task.id)
        })
      }

      // Clear usage stats for this bot
      if (categories.has('usage')) {
        clearBotStats(botId)
      }

      // Clear platform data (Telegram/Discord messages from backend AND local synced copies)
      if (categories.has('platform')) {
        // First, delete local platform chats (synced copies)
        const localPlatformChats = chats.filter((c) => c.botId === botId && c.platform)
        localPlatformChats.forEach((chat) => {
          chatStore.deleteChat(chat.id)
        })

        // Then, delete from backend database
        try {
          const { clearBotPlatformData } = await import('../../api/client')
          await clearBotPlatformData(botId)
          // Update local platform count
          setPlatformCounts((prev) => ({ ...prev, [botId]: 0 }))
        } catch (err) {
          console.error('Failed to clear platform data:', err)
          toast.error(`Failed to clear platform data for bot`)
        }
      }
    }

    // Small delay for UX
    await new Promise((resolve) => setTimeout(resolve, 300))

    setClearing(false)
    setShowConfirmModal(false)
    setSelectedItems(new Map())
    toast.success('Selected data cleared successfully')
  }

  // Category icons and labels
  const categoryConfig: Record<DataCategory, { icon: typeof MessageSquare; label: string; color: string }> = {
    chats: { icon: MessageSquare, label: 'Local Chats', color: 'text-blue-400' },
    jobs: { icon: Briefcase, label: 'Jobs', color: 'text-purple-400' },
    tasks: { icon: CheckSquare, label: 'Tasks', color: 'text-green-400' },
    usage: { icon: BarChart3, label: 'Usage Stats', color: 'text-amber-400' },
    platform: { icon: MessageSquare, label: 'Platform Messages', color: 'text-cyan-400' },
  }

  return (
    <Section icon={Bot} title="Bot Data Manager">
      <div className="space-y-4">
        <p className="text-sm text-[var(--color-text-secondary)]">
          Clear specific data for each bot while keeping bot settings and connections intact.
          {loadingPlatform && (
            <span className="ml-2 text-[var(--color-text-secondary)]">
              <Loader2 className="inline h-3 w-3 animate-spin mr-1" />
              Loading platform data...
            </span>
          )}
        </p>

        {/* Bot list */}
        <div className="space-y-2">
          {botDataInfos.map((info) => {
            const isExpanded = expandedBots.has(info.botId)
            const botSelected = selectedItems.get(info.botId)
            const hasData =
              info.chatsCount > 0 ||
              info.jobsCount > 0 ||
              info.tasksCount > 0 ||
              info.hasUsageData ||
              info.platformChatsCount > 0

            return (
              <div
                key={info.botId}
                className="bot-data-card"
              >
                {/* Bot header */}
                <button
                  onClick={() => toggleBot(info.botId)}
                  className="bot-data-card__header"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-[var(--color-text-secondary)]" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-[var(--color-text-secondary)]" />
                  )}
                  <div
                    className="h-8 w-8 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: info.botColor + '20' }}
                  >
                    <Bot className="h-4 w-4" style={{ color: info.botColor }} />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="bot-data-card__name">{info.botName}</div>
                    <div className="bot-data-card__stats">
                      {info.chatsCount} local chats · {info.jobsCount} jobs · {info.tasksCount} tasks
                      {info.platformChatsCount > 0 && (
                        <span className="text-cyan-400"> · {info.platformChatsCount} platform chats</span>
                      )}
                    </div>
                  </div>
                  {botSelected && botSelected.size > 0 && (
                    <span className="bot-data-card__selected-badge">
                      {botSelected.size} selected
                    </span>
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="bot-data-card__content">
                    {!hasData ? (
                      <p className="text-sm text-[var(--color-text-secondary)] text-center py-2">
                        No data to clear for this bot
                      </p>
                    ) : (
                      <>
                        {/* Quick actions */}
                        <div className="bot-data-card__quick-actions">
                          <button
                            onClick={() => selectAllForBot(info.botId, info)}
                            className="bot-data-card__quick-btn"
                          >
                            Select all
                          </button>
                          <span className="bot-data-card__separator">&middot;</span>
                          <button
                            onClick={() => clearSelectionForBot(info.botId)}
                            className="bot-data-card__quick-btn"
                          >
                            Clear selection
                          </button>
                        </div>

                        {/* Data categories */}
                        <div className="grid grid-cols-2 gap-2">
                          {/* Chats */}
                          {info.chatsCount > 0 && (
                            <DataCategoryItem
                              category="chats"
                              config={categoryConfig.chats}
                              count={info.chatsCount}
                              detail={`${info.messagesCount} messages`}
                              selected={botSelected?.has('chats') || false}
                              onToggle={() => toggleCategory(info.botId, 'chats')}
                            />
                          )}

                          {/* Jobs */}
                          {info.jobsCount > 0 && (
                            <DataCategoryItem
                              category="jobs"
                              config={categoryConfig.jobs}
                              count={info.jobsCount}
                              selected={botSelected?.has('jobs') || false}
                              onToggle={() => toggleCategory(info.botId, 'jobs')}
                            />
                          )}

                          {/* Tasks */}
                          {info.tasksCount > 0 && (
                            <DataCategoryItem
                              category="tasks"
                              config={categoryConfig.tasks}
                              count={info.tasksCount}
                              selected={botSelected?.has('tasks') || false}
                              onToggle={() => toggleCategory(info.botId, 'tasks')}
                            />
                          )}

                          {/* Usage */}
                          {info.hasUsageData && (
                            <DataCategoryItem
                              category="usage"
                              config={categoryConfig.usage}
                              count={1}
                              detail="statistics"
                              selected={botSelected?.has('usage') || false}
                              onToggle={() => toggleCategory(info.botId, 'usage')}
                            />
                          )}

                          {/* Platform Messages (Telegram/Discord) */}
                          {info.platformChatsCount > 0 && (
                            <DataCategoryItem
                              category="platform"
                              config={categoryConfig.platform}
                              count={info.platformChatsCount}
                              detail="Telegram/Discord"
                              selected={botSelected?.has('platform') || false}
                              onToggle={() => toggleCategory(info.botId, 'platform')}
                            />
                          )}
                        </div>

                      </>
                    )}
                  </div>
                )}
              </div>
            )
          })}
        </div>

        {/* Clear button */}
        {hasSelection && (
          <div className="settings-delete-bar">
            <div className="text-sm">
              <span className="settings-delete-bar__count">{getTotalSelectedItems()}</span>
              <span className="settings-delete-bar__label"> items selected for deletion</span>
            </div>
            <button
              onClick={() => setShowConfirmModal(true)}
              className="settings-modal__confirm-btn--danger flex items-center gap-2"
            >
              <Trash2 className="h-4 w-4" />
              Clear Selected
            </button>
          </div>
        )}
      </div>

      {/* Confirmation modal */}
      {showConfirmModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '28rem' }}>
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="settings-modal__heading">Clear Bot Data</h2>
            </div>
            <p className="mb-4 settings-modal__body-text">
              Are you sure you want to clear the selected data? This action cannot be undone.
            </p>

            {/* Summary of what will be deleted */}
            <div className="mb-6 settings-modal__summary space-y-2">
              {Array.from(selectedItems.entries()).map(([botId, categories]) => {
                const info = botDataInfos.find((b) => b.botId === botId)
                if (!info) return null
                return (
                  <div key={botId} className="text-sm">
                    <span className="font-medium text-[var(--color-text-primary)]">{info.botName}:</span>
                    <span className="text-[var(--color-text-secondary)] ml-2">
                      {Array.from(categories).map((cat) => categoryConfig[cat].label).join(', ')}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className="settings-modal__footer">
              <button
                onClick={() => setShowConfirmModal(false)}
                disabled={clearing}
                className="settings-modal__cancel-btn"
              >
                Cancel
              </button>
              <button
                onClick={handleClearSelected}
                disabled={clearing}
                className="settings-modal__confirm-btn--danger flex items-center gap-2"
              >
                {clearing ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Clearing...
                  </>
                ) : (
                  <>
                    <Trash2 className="h-4 w-4" />
                    Clear Data
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </Section>
  )
}

// Data category item component
interface DataCategoryItemProps {
  category: DataCategory
  config: { icon: typeof MessageSquare; label: string; color: string }
  count: number
  detail?: string
  selected: boolean
  onToggle: () => void
}

function DataCategoryItem({ config, count, detail, selected, onToggle }: DataCategoryItemProps) {
  const Icon = config.icon

  return (
    <button
      onClick={onToggle}
      className={cn(
        'data-category',
        selected && 'data-category--selected'
      )}
    >
      <div
        className={cn(
          'data-category__icon-box',
          selected && 'data-category__icon-box--selected'
        )}
      >
        {selected ? (
          <Check className="h-3.5 w-3.5 text-red-400" />
        ) : (
          <Icon className={cn('h-3.5 w-3.5', config.color)} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className={cn('data-category__label', selected && 'data-category__label--selected')}>
          {config.label}
        </div>
        <div className="data-category__count">
          {count} {detail || (count === 1 ? 'item' : 'items')}
        </div>
      </div>
    </button>
  )
}

// =============================================================================
// GROUPS SETTINGS (Manager+)
// =============================================================================

function GroupsSettings({ currentUser }: { currentUser: User | null }) {
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)

  // Create group modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({ name: '', description: '' })
  const [creating, setCreating] = useState(false)

  // Group detail panel state
  const [activeGroupId, setActiveGroupId] = useState<string | null>(null)
  const [activeGroup, setActiveGroup] = useState<GroupWithMembers | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  // Add member modal state
  const [showAddMemberModal, setShowAddMemberModal] = useState(false)
  const [addMemberForm, setAddMemberForm] = useState({ userId: '', role: 'member' as GroupRole })
  const [addingMember, setAddingMember] = useState(false)

  // Context menu state
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  useEffect(() => {
    fetchGroupsList()
  }, [])

  useEffect(() => {
    if (activeGroupId) {
      fetchGroupDetail(activeGroupId)
    } else {
      setActiveGroup(null)
    }
  }, [activeGroupId])

  const fetchGroupsList = async () => {
    try {
      const response = await listGroups()
      setGroups(response)
    } catch {
      toast.error('Failed to load groups')
    } finally {
      setLoading(false)
    }
  }

  const fetchGroupDetail = async (groupId: string) => {
    setLoadingDetail(true)
    try {
      const group = await getGroup(groupId)
      setActiveGroup(group)
    } catch {
      toast.error('Failed to load group details')
      setActiveGroupId(null)
    } finally {
      setLoadingDetail(false)
    }
  }

  const handleCreateGroup = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.name) {
      toast.error('Group name is required')
      return
    }
    setCreating(true)
    try {
      const newGroup = await createGroup({
        name: createForm.name,
        description: createForm.description || undefined,
      })
      setGroups([newGroup, ...groups])
      setShowCreateModal(false)
      setCreateForm({ name: '', description: '' })
      toast.success('Group created successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create group'
      toast.error(message)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteGroup = async (groupId: string) => {
    if (!confirm('Are you sure you want to delete this group?')) return
    try {
      await deleteGroup(groupId)
      setGroups(groups.filter((g) => g.id !== groupId))
      if (activeGroupId === groupId) setActiveGroupId(null)
      toast.success('Group deleted')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete group'
      toast.error(message)
    }
    setMenuOpen(null)
  }

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!activeGroupId || !addMemberForm.userId) {
      toast.error('User ID is required')
      return
    }
    setAddingMember(true)
    try {
      const newMember = await addMember(activeGroupId, {
        user_id: addMemberForm.userId,
        role: addMemberForm.role,
      })
      if (activeGroup) {
        setActiveGroup({
          ...activeGroup,
          members: [...activeGroup.members, newMember],
          member_count: activeGroup.member_count + 1,
        })
      }
      setGroups(
        groups.map((g) =>
          g.id === activeGroupId ? { ...g, member_count: g.member_count + 1 } : g
        )
      )
      setShowAddMemberModal(false)
      setAddMemberForm({ userId: '', role: 'member' })
      toast.success('Member added successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add member'
      toast.error(message)
    } finally {
      setAddingMember(false)
    }
  }

  const handleRemoveMember = async (userId: string) => {
    if (!activeGroupId) return
    if (!confirm('Are you sure you want to remove this member?')) return
    try {
      await removeMember(activeGroupId, userId)
      if (activeGroup) {
        setActiveGroup({
          ...activeGroup,
          members: activeGroup.members.filter((m) => m.user_id !== userId),
          member_count: activeGroup.member_count - 1,
        })
      }
      setGroups(
        groups.map((g) =>
          g.id === activeGroupId ? { ...g, member_count: g.member_count - 1 } : g
        )
      )
      toast.success('Member removed')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to remove member'
      toast.error(message)
    }
  }

  const isGroupOwnerOrAdmin = (group: Group): boolean => {
    if (!currentUser) return false
    if (currentUser.role === 'admin') return true
    return group.created_by === currentUser.id
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
      </div>
    )
  }

  return (
    <>
      <Section icon={Users} title="Groups">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[var(--color-text-secondary)]">
              {groups.length} group{groups.length !== 1 ? 's' : ''} total
            </p>
            <Button size="sm" onClick={() => setShowCreateModal(true)}>
              <UserPlus className="h-4 w-4 mr-1.5" />
              Create Group
            </Button>
          </div>

          {/* Groups Table */}
          <div className="settings-table">
            <div className="settings-table__header-row grid grid-cols-[1fr_1fr_80px_48px] gap-4 px-4 py-2.5">
              <div>Name</div>
              <div>Description</div>
              <div>Members</div>
              <div></div>
            </div>

            {groups.length === 0 ? (
              <div className="settings-table__empty py-8">
                No groups found
              </div>
            ) : (
              groups.map((group) => (
                <div
                  key={group.id}
                  className={cn(
                    'settings-table__row grid grid-cols-[1fr_1fr_80px_48px] gap-4 px-4 py-2.5 items-center cursor-pointer text-sm',
                    activeGroupId === group.id && 'settings-table__row--active'
                  )}
                  onClick={() => setActiveGroupId(activeGroupId === group.id ? null : group.id)}
                >
                  <div className="font-medium truncate">{group.name}</div>
                  <div className="text-[var(--color-text-secondary)] truncate">
                    {group.description || '\u2014'}
                  </div>
                  <div>{group.member_count}</div>
                  <div className="relative" onClick={(e) => e.stopPropagation()}>
                    <button
                      onClick={() => setMenuOpen(menuOpen === group.id ? null : group.id)}
                      className="settings-btn-ghost p-1.5"
                    >
                      <MoreVertical className="h-4 w-4 text-[var(--color-text-secondary)]" />
                    </button>
                    {menuOpen === group.id && (
                      <div className="settings-context-menu" style={{ width: '10rem' }}>
                        <button
                          onClick={() => { setActiveGroupId(group.id); setMenuOpen(null) }}
                          className="settings-context-menu__item w-full"
                        >
                          View Members
                        </button>
                        {isGroupOwnerOrAdmin(group) && (
                          <button
                            onClick={() => handleDeleteGroup(group.id)}
                            className="settings-context-menu__item settings-context-menu__item--danger w-full"
                          >
                            Delete Group
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </Section>

      {/* Group Detail Panel */}
      {activeGroupId && (
        <Section icon={Shield} title={activeGroup?.name || 'Group Details'}>
          {loadingDetail ? (
            <div className="flex items-center justify-center py-8">
              <Loader2 className="h-6 w-6 animate-spin text-blue-500" />
            </div>
          ) : activeGroup ? (
            <div className="space-y-4">
              {activeGroup.description && (
                <p className="text-sm text-[var(--color-text-secondary)]">{activeGroup.description}</p>
              )}

              <div className="flex items-center justify-between">
                <span className="text-sm font-medium text-[var(--color-text-secondary)]">
                  Members ({activeGroup.members.length})
                </span>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => setShowAddMemberModal(true)}
                    className="inline-flex items-center gap-1 text-xs text-blue-400 hover:text-blue-300 transition-colors"
                  >
                    <Plus className="h-3.5 w-3.5" />
                    Add Member
                  </button>
                  <button
                    onClick={() => setActiveGroupId(null)}
                    className="settings-btn-ghost p-1"
                  >
                    <X className="h-4 w-4 text-[var(--color-text-secondary)]" />
                  </button>
                </div>
              </div>

              <div className="settings-table">
                {activeGroup.members.length === 0 ? (
                  <div className="settings-table__empty py-6">
                    No members yet
                  </div>
                ) : (
                  activeGroup.members.map((member: GroupMember) => (
                    <div
                      key={member.user_id}
                      className="member-row"
                    >
                      <div className="flex items-center gap-3 min-w-0">
                        <div className="member-row__avatar">
                          {member.role === 'owner' ? (
                            <Shield className="h-3.5 w-3.5 text-purple-400" />
                          ) : (
                            <UserIcon className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="member-row__name truncate">
                            {member.username}
                            {member.user_id === currentUser?.id && (
                              <span className="member-row__you-tag">You</span>
                            )}
                          </div>
                          <div className="member-row__email truncate">
                            {member.email}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span
                          className={cn(
                            'role-badge',
                            member.role === 'owner'
                              ? 'role-badge--owner'
                              : 'role-badge--default'
                          )}
                        >
                          {member.role}
                        </span>
                        {member.user_id !== currentUser?.id && (
                          <button
                            onClick={() => handleRemoveMember(member.user_id)}
                            className="member-row__remove-btn"
                            title="Remove member"
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          ) : null}
        </Section>
      )}

      {/* Create Group Modal */}
      {showCreateModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Create New Group</h2>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="settings-modal__label">
                  Name
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) => setCreateForm({ ...createForm, name: e.target.value })}
                  className="settings-modal__input"
                  required
                  placeholder="Group name"
                />
              </div>
              <div>
                <label className="settings-modal__label">
                  Description
                </label>
                <input
                  type="text"
                  value={createForm.description}
                  onChange={(e) => setCreateForm({ ...createForm, description: e.target.value })}
                  className="settings-modal__input"
                  placeholder="Optional description"
                />
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="button" variant="ghost" className="flex-1" onClick={() => setShowCreateModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={creating}>
                  {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Create Group'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Add Member Modal */}
      {showAddMemberModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Add Member</h2>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="settings-modal__label">
                  User ID
                </label>
                <input
                  type="text"
                  value={addMemberForm.userId}
                  onChange={(e) => setAddMemberForm({ ...addMemberForm, userId: e.target.value })}
                  className="settings-modal__input"
                  required
                  placeholder="Enter user ID"
                />
              </div>
              <div>
                <label className="settings-modal__label">
                  Role
                </label>
                <select
                  value={addMemberForm.role}
                  onChange={(e) => setAddMemberForm({ ...addMemberForm, role: e.target.value as GroupRole })}
                  className="settings-modal__select"
                >
                  <option value="member">Member</option>
                  <option value="owner">Owner</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <Button type="button" variant="ghost" className="flex-1" onClick={() => setShowAddMemberModal(false)}>
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={addingMember}>
                  {addingMember ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Add Member'}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click outside to close menu */}
      {menuOpen && <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(null)} />}
    </>
  )
}

// =============================================================================
// USERS SETTINGS (Admin Only)
// =============================================================================

function UsersSettings({ currentUser }: { currentUser: User | null }) {
  const [users, setUsers] = useState<User[]>([])
  const [loading, setLoading] = useState(true)
  const [total, setTotal] = useState(0)

  // Create user modal state
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({
    email: '',
    username: '',
    password: '',
    role: 'user' as UserRole,
  })
  const [creating, setCreating] = useState(false)

  // Edit user state
  const [editingUser, setEditingUser] = useState<User | null>(null)
  const [editForm, setEditForm] = useState({
    email: '',
    username: '',
    role: 'user' as UserRole,
  })
  const [updating, setUpdating] = useState(false)

  // Context menu state
  const [menuOpen, setMenuOpen] = useState<string | null>(null)

  useEffect(() => {
    fetchUsers()
  }, [])

  const fetchUsers = async () => {
    try {
      const response = await listUsers()
      setUsers(response.users)
      setTotal(response.total)
    } catch {
      toast.error('Failed to load users')
    } finally {
      setLoading(false)
    }
  }

  const handleCreateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!createForm.email || !createForm.username || !createForm.password) {
      toast.error('All fields are required')
      return
    }
    if (createForm.password.length < 8) {
      toast.error('Password must be at least 8 characters')
      return
    }

    setCreating(true)
    try {
      const newUser = await createUser(createForm)
      setUsers([newUser, ...users])
      setTotal(total + 1)
      setShowCreateModal(false)
      setCreateForm({ email: '', username: '', password: '', role: 'user' })
      toast.success('User created successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create user'
      toast.error(message)
    } finally {
      setCreating(false)
    }
  }

  const handleUpdateUser = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingUser) return

    setUpdating(true)
    try {
      const updated = await updateUser(editingUser.id, editForm)
      setUsers(users.map((u) => (u.id === updated.id ? updated : u)))
      setEditingUser(null)
      toast.success('User updated successfully')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update user'
      toast.error(message)
    } finally {
      setUpdating(false)
    }
  }

  const handleDeactivateUser = async (userId: string) => {
    if (!confirm('Are you sure you want to deactivate this user?')) return

    try {
      await deactivateUser(userId)
      setUsers(users.map((u) => (u.id === userId ? { ...u, is_active: false } : u)))
      toast.success('User deactivated')
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to deactivate user'
      toast.error(message)
    }
    setMenuOpen(null)
  }

  const startEditing = (user: User) => {
    setEditingUser(user)
    setEditForm({
      email: user.email,
      username: user.username,
      role: user.role,
    })
    setMenuOpen(null)
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-8 w-8 animate-spin text-cachi-500" />
      </div>
    )
  }

  return (
    <>
      <Section icon={Users} title="User Management">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <p className="text-sm text-[var(--color-text-secondary)]">
              {total} user{total !== 1 ? 's' : ''} total
            </p>
            <Button onClick={() => setShowCreateModal(true)} size="sm">
              <UserPlus className="h-4 w-4 mr-2" />
              Add User
            </Button>
          </div>

          {/* Users Table */}
          <div className="settings-table">
            {/* Table Header */}
            <div className="settings-table__header-row grid grid-cols-[1fr_1fr_80px_80px_40px] gap-2 px-4 py-2">
              <div>User</div>
              <div>Email</div>
              <div>Role</div>
              <div>Status</div>
              <div></div>
            </div>

            {/* User Rows */}
            {users.length === 0 ? (
              <div className="settings-table__empty py-6">
                No users found
              </div>
            ) : (
              users.map((user) => (
                <div
                  key={user.id}
                  className="settings-table__row grid grid-cols-[1fr_1fr_80px_80px_40px] gap-2 px-4 py-2.5 items-center"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="user-avatar-circle">
                      <AtSign className="h-3.5 w-3.5 text-[var(--color-text-secondary)]" />
                    </div>
                    <div className="min-w-0">
                      <div className="member-row__name truncate">{user.username}</div>
                      {user.id === currentUser?.id && (
                        <div className="text-xs text-accent-500">You</div>
                      )}
                    </div>
                  </div>
                  <div className="member-row__email truncate">{user.email}</div>
                  <div>
                    <span
                      className={cn(
                        'role-badge',
                        user.role === 'admin'
                          ? 'role-badge--admin'
                          : user.role === 'manager'
                            ? 'role-badge--manager'
                            : 'role-badge--default'
                      )}
                    >
                      {user.role === 'admin' ? (
                        <Shield className="h-3 w-3" />
                      ) : (
                        <UserIcon className="h-3 w-3" />
                      )}
                      {user.role}
                    </span>
                  </div>
                  <div>
                    <span
                      className={cn(
                        'status-badge',
                        user.is_active
                          ? 'status-badge--active'
                          : 'status-badge--inactive'
                      )}
                    >
                      {user.is_active ? (
                        <Check className="h-3 w-3" />
                      ) : (
                        <X className="h-3 w-3" />
                      )}
                      {user.is_active ? 'Active' : 'Off'}
                    </span>
                  </div>
                  <div className="relative">
                    <button
                      onClick={() => setMenuOpen(menuOpen === user.id ? null : user.id)}
                      className="settings-btn-ghost p-1"
                      disabled={user.id === currentUser?.id}
                    >
                      <MoreVertical className="h-4 w-4 text-[var(--color-text-secondary)]" />
                    </button>
                    {menuOpen === user.id && (
                      <div className="settings-context-menu" style={{ width: '9rem' }}>
                        <button
                          onClick={() => startEditing(user)}
                          className="settings-context-menu__item w-full"
                        >
                          Edit User
                        </button>
                        {user.is_active && (
                          <button
                            onClick={() => handleDeactivateUser(user.id)}
                            className="settings-context-menu__item settings-context-menu__item--danger w-full"
                          >
                            Deactivate
                          </button>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </Section>

      {/* Create User Modal */}
      {showCreateModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Create New User</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="settings-modal__label">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
                  <input
                    type="email"
                    value={createForm.email}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, email: e.target.value })
                    }
                    className="settings-modal__input pl-10"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="settings-modal__label">
                  Username
                </label>
                <div className="relative">
                  <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
                  <input
                    type="text"
                    value={createForm.username}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, username: e.target.value })
                    }
                    className="settings-modal__input pl-10"
                    required
                    minLength={3}
                    maxLength={32}
                  />
                </div>
              </div>
              <div>
                <label className="settings-modal__label">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, password: e.target.value })
                  }
                  className="settings-modal__input"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                />
              </div>
              <div>
                <label className="settings-modal__label">
                  Role
                </label>
                <select
                  value={createForm.role}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      role: e.target.value as UserRole,
                    })
                  }
                  className="settings-modal__select"
                >
                  <option value="user">User</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => setShowCreateModal(false)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={creating}>
                  {creating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Create User'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit User Modal */}
      {editingUser && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Edit User</h2>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className="settings-modal__label">
                  Email
                </label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  className="settings-modal__input"
                  required
                />
              </div>
              <div>
                <label className="settings-modal__label">
                  Username
                </label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(e) =>
                    setEditForm({ ...editForm, username: e.target.value })
                  }
                  className="settings-modal__input"
                  required
                  minLength={3}
                  maxLength={32}
                />
              </div>
              <div>
                <label className="settings-modal__label">
                  Role
                </label>
                <select
                  value={editForm.role}
                  onChange={(e) =>
                    setEditForm({
                      ...editForm,
                      role: e.target.value as UserRole,
                    })
                  }
                  className="settings-modal__select"
                >
                  <option value="user">User</option>
                  <option value="manager">Manager</option>
                  <option value="admin">Admin</option>
                </select>
              </div>
              <div className="flex gap-3 pt-2">
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={() => setEditingUser(null)}
                >
                  Cancel
                </Button>
                <Button type="submit" className="flex-1" disabled={updating}>
                  {updating ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    'Save Changes'
                  )}
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Click outside to close menu */}
      {menuOpen && (
        <div
          className="fixed inset-0 z-10"
          onClick={() => setMenuOpen(null)}
        />
      )}
    </>
  )
}

// =============================================================================
// SHARED COMPONENTS
// =============================================================================

interface SectionProps {
  icon: React.ComponentType<{ className?: string }>
  title: string
  danger?: boolean
  children: React.ReactNode
}

function Section({ icon: Icon, title, danger, children }: SectionProps) {
  return (
    <div className="settings-section">
      <div
        className={cn(
          'settings-section__header',
          danger && 'settings-section__header--danger'
        )}
      >
        <Icon
          className={cn('settings-section__icon', danger && 'settings-section__icon--danger')}
        />
        <h3
          className={cn(
            'settings-section__title',
            danger && 'settings-section__title--danger'
          )}
        >
          {title}
        </h3>
      </div>
      <div className="settings-section__body">{children}</div>
    </div>
  )
}

interface FieldProps {
  label: string
  children: React.ReactNode
}

function Field({ label, children }: FieldProps) {
  return (
    <div>
      <label className="settings-field__label">
        {label}
      </label>
      {children}
    </div>
  )
}

interface ToggleFieldProps {
  label: string
  description: string
  checked: boolean
  onChange: (checked: boolean) => void
}

function ToggleField({ label, description, checked, onChange }: ToggleFieldProps) {
  return (
    <div className="settings-toggle">
      <div>
        <h4 className="settings-toggle__label">{label}</h4>
        <p className="settings-toggle__desc">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'settings-toggle__switch',
          checked ? 'settings-toggle__switch--on' : 'settings-toggle__switch--off'
        )}
      >
        <span
          className={cn(
            'settings-toggle__knob',
            checked ? 'settings-toggle__knob--on' : 'settings-toggle__knob--off'
          )}
        />
      </button>
    </div>
  )
}

function ShortcutItem({ label, shortcut }: { label: string; shortcut: string }) {
  return (
    <div className="shortcut-item">
      <span className="shortcut-item__label">{label}</span>
      <kbd className="shortcut-item__kbd">
        {shortcut}
      </kbd>
    </div>
  )
}

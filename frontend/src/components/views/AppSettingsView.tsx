import { useState, useEffect, useMemo } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  Settings,
  Moon,
  Sun,
  Monitor,
  Eye as EyeIcon,
  Keyboard,
  Bell,
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
} from 'lucide-react'
import { toast } from 'sonner'
import { useUIStore, Theme, AccentColor, accentColors } from '../../stores/ui'
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
import { checkHealth, type HealthInfo } from '../../api/client'
import { ModelSelect } from '../common/ModelSelect'
import { Button } from '../common/Button'
import { cn } from '../../lib/utils'
import type { Config, User, UserRole } from '../../types'

type SettingsTab = 'general' | 'appearance' | 'models' | 'keys' | 'advanced' | 'data' | 'users'

const VALID_TABS: SettingsTab[] = ['general', 'appearance', 'models', 'keys', 'advanced', 'data', 'users']

export function AppSettingsView() {
  const { settingsTab: urlTab } = useParams<{ settingsTab?: string }>()
  const navigate = useNavigate()
  const {
    theme,
    setTheme,
    accentColor,
    setAccentColor,
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
    ...(isAdmin ? [{ id: 'users' as SettingsTab, label: 'Users', icon: Users }] : []),
  ]

  return (
    <div className="flex h-full flex-col bg-zinc-50 dark:bg-zinc-950">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-zinc-300 px-6 py-4 dark:border-zinc-800">
        <div>
          <h1 className="text-xl font-bold text-zinc-900 dark:text-zinc-100">Settings</h1>
          <p className="text-sm text-zinc-500">Configure CachiBot preferences</p>
        </div>
      </div>

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <nav className="w-56 border-r border-zinc-300 p-4 dark:border-zinc-800">
          <div className="space-y-1">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => handleTabChange(tab.id)}
                className={cn(
                  'flex w-full items-center gap-3 rounded-lg px-3 py-2 text-left text-sm transition-colors',
                  activeTab === tab.id
                    ? 'bg-accent-600/20 text-accent-600 dark:text-accent-400'
                    : 'text-zinc-600 hover:bg-zinc-200 hover:text-zinc-900 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </div>
        </nav>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          <div className="mx-auto max-w-2xl space-y-8">
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
                sidebarCollapsed={sidebarCollapsed}
                setSidebarCollapsed={setSidebarCollapsed}
              />
            )}
            {activeTab === 'models' && <ModelsSettings />}
            {activeTab === 'keys' && <ApiKeysSettings />}
            {activeTab === 'advanced' && <AdvancedSettings config={config} />}
            {activeTab === 'data' && <DataSettings />}
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

      <Section icon={Bell} title="Notifications">
        <div className="space-y-4">
          <ToggleField
            label="Desktop Notifications"
            description="Get notified when tasks complete"
            checked={false}
            onChange={() => {}}
          />
          <ToggleField
            label="Sound Effects"
            description="Play sounds for important events"
            checked={false}
            onChange={() => {}}
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
                className="h-10 flex-1 rounded-lg border border-zinc-300 bg-zinc-100 px-4 text-zinc-900 outline-none dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
              <button className="rounded-lg bg-zinc-200 px-4 text-sm text-zinc-700 hover:bg-zinc-300 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:bg-zinc-700">
                Browse
              </button>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Directory where bots can read and write files
            </p>
          </Field>
        </div>
      </Section>

      <Section icon={Info} title="About">
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Version</span>
            <span className="font-mono text-zinc-800 dark:text-zinc-200">
              {healthInfo?.version ?? '...'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Build</span>
            <span className="font-mono text-zinc-800 dark:text-zinc-200">
              {healthInfo?.build ?? '...'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Python</span>
            <span className="font-mono text-zinc-800 dark:text-zinc-200">
              {healthInfo?.python ?? '...'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Platform</span>
            <span className="font-mono text-zinc-800 dark:text-zinc-200">
              {healthInfo?.platform ?? '...'}
            </span>
          </div>
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Documentation</span>
            <a
              href="https://github.com/jhd3197/CachiBot"
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 text-cachi-600 hover:text-cachi-500 dark:text-cachi-400 dark:hover:text-cachi-300"
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
  const { open } = useOnboardingStore()

  const handleRunWizard = () => {
    open()
  }

  return (
    <Section icon={RefreshCw} title="Setup">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Run Setup Wizard</h4>
          <p className="text-sm text-zinc-500">
            Re-run the initial setup to configure API keys, models, and preferences
          </p>
        </div>
        <button
          onClick={handleRunWizard}
          className="flex items-center gap-2 rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-500"
        >
          <RefreshCw className="h-4 w-4" />
          Run Wizard
        </button>
      </div>
    </Section>
  )
}

function UpdatesSection({ healthInfo }: { healthInfo: HealthInfo | null }) {
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

  const currentVersion = checkResult?.current_version || healthInfo?.version || '...'
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
        'ml-2 rounded-full px-2 py-0.5 text-xs font-medium',
        healthInfo.build === 'release'
          ? 'bg-green-500/20 text-green-400'
          : healthInfo.build === 'dev'
            ? 'bg-amber-500/20 text-amber-400'
            : 'bg-zinc-500/20 text-zinc-400'
      )}
    >
      {healthInfo.build}
    </span>
  ) : null

  return (
    <Section icon={Download} title="Updates">
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <span className="text-zinc-500 dark:text-zinc-400">Current Version</span>
          <span className="font-mono text-zinc-800 dark:text-zinc-200">
            {currentVersion}
            {buildBadge}
          </span>
        </div>

        <div className="flex items-center justify-between">
          <span className="text-zinc-500 dark:text-zinc-400">Latest Version</span>
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
            <span className="text-zinc-500">—</span>
          )}
        </div>

        {latestPrerelease && optIntoBeta && (
          <div className="flex items-center justify-between">
            <span className="text-zinc-500 dark:text-zinc-400">Latest Pre-release</span>
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
          <span className="text-sm text-zinc-500">
            Last checked: {formatRelativeTime(lastCheckAt)}
          </span>
        </div>

        <div className="flex gap-2">
          <button
            onClick={() => checkForUpdate(true)}
            disabled={isChecking}
            className="flex items-center gap-2 rounded-lg border border-zinc-300 px-4 py-2 text-sm font-medium text-zinc-700 transition-colors hover:bg-zinc-100 disabled:opacity-50 dark:border-zinc-700 dark:text-zinc-300 dark:hover:bg-zinc-800"
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
  sidebarCollapsed,
  setSidebarCollapsed,
}: {
  theme: Theme
  setTheme: (theme: Theme) => void
  accentColor: AccentColor
  setAccentColor: (color: AccentColor) => void
  sidebarCollapsed: boolean
  setSidebarCollapsed: (collapsed: boolean) => void
}) {
  const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ]

  const colorOptions = Object.entries(accentColors) as [AccentColor, typeof accentColors[AccentColor]][]

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
                    'flex flex-1 items-center justify-center gap-2 rounded-lg border py-3 transition-all',
                    theme === option.value
                      ? 'border-accent-500 bg-accent-500/20 text-accent-600 dark:text-accent-400'
                      : 'border-zinc-300 bg-zinc-100 text-zinc-600 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-300 dark:hover:border-zinc-600'
                  )}
                >
                  <option.icon className="h-4 w-4" />
                  {option.label}
                </button>
              ))}
            </div>
          </Field>

          <Field label="Accent Color">
            <div className="grid grid-cols-4 gap-2">
              {colorOptions.map(([value, { name, palette }]) => (
                <button
                  key={value}
                  onClick={() => setAccentColor(value)}
                  className={cn(
                    'flex items-center gap-2 rounded-lg border p-3 transition-all',
                    accentColor === value
                      ? 'border-2 ring-1 ring-offset-1 ring-offset-zinc-900'
                      : 'border-zinc-300 hover:border-zinc-400 dark:border-zinc-700 dark:hover:border-zinc-600'
                  )}
                  style={{
                    borderColor: accentColor === value ? palette[500] : undefined,
                    // @ts-expect-error - Tailwind CSS variable
                    '--tw-ring-color': accentColor === value ? palette[500] : undefined,
                  }}
                >
                  <div
                    className="h-5 w-5 rounded-full"
                    style={{ backgroundColor: palette[500] }}
                  />
                  <span className="text-sm text-zinc-700 dark:text-zinc-300">{name}</span>
                </button>
              ))}
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
            <select className="h-10 w-full rounded-lg border border-zinc-300 bg-zinc-100 px-4 text-zinc-900 outline-none focus:border-accent-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100">
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
            <select className="h-10 w-full rounded-lg border border-zinc-300 bg-zinc-100 px-4 text-zinc-900 outline-none focus:border-accent-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100">
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
  const { groups, defaultModel, loading, updateDefaultModel, refresh } = useModelsStore()
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
            <p className="mt-2 text-xs text-zinc-500">
              Used when no specific model is configured for a bot.
            </p>
          </Field>
        </div>
      </Section>

      {/* Available models - collapsible providers */}
      <Section icon={Brain} title="Available Models">
        <div className="space-y-3">
          {/* Search */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-zinc-500" />
            <input
              type="text"
              placeholder="Search models..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="h-9 w-full rounded-lg border border-zinc-300 bg-zinc-100 pl-10 pr-8 text-sm text-zinc-900 placeholder-zinc-500 outline-none focus:border-accent-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100 dark:placeholder-zinc-500"
            />
            {search && (
              <button
                onClick={() => setSearch('')}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
              >
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </div>

          {/* Summary */}
          <p className="text-xs text-zinc-500">
            {isSearching
              ? `${filteredTotal} result${filteredTotal !== 1 ? 's' : ''} across ${providerCount} provider${providerCount !== 1 ? 's' : ''}`
              : `${totalModels} model${totalModels !== 1 ? 's' : ''} from ${providerCount} provider${providerCount !== 1 ? 's' : ''}`}
          </p>

          {/* Loading */}
          {loading && (
            <div className="flex items-center justify-center gap-2 py-6 text-zinc-500">
              <Loader2 className="h-4 w-4 animate-spin" />
              Discovering models...
            </div>
          )}

          {/* Empty */}
          {!loading && totalModels === 0 && (
            <div className="text-center py-6">
              <Brain className="h-7 w-7 text-zinc-400 dark:text-zinc-600 mx-auto mb-2" />
              <p className="text-sm text-zinc-500">No models available</p>
              <p className="text-xs text-zinc-400 dark:text-zinc-600 mt-1">
                Configure API keys to discover models.
              </p>
            </div>
          )}

          {/* No search results */}
          {!loading && totalModels > 0 && filteredTotal === 0 && (
            <div className="text-center py-6 text-zinc-500 text-sm">
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
                      className="rounded-lg border border-zinc-200 overflow-hidden dark:border-zinc-700"
                    >
                      {/* Provider header - clickable */}
                      <button
                        onClick={() => toggleProvider(provider)}
                        className="flex w-full items-center gap-2.5 px-3 py-2 hover:bg-zinc-100/50 transition-colors dark:hover:bg-zinc-800/50"
                      >
                        <ChevronRight
                          className={cn(
                            'h-3.5 w-3.5 text-zinc-400 transition-transform',
                            isOpen && 'rotate-90'
                          )}
                        />
                        <span className={cn('h-2 w-2 rounded-full shrink-0', dotColor)} />
                        <span className="text-sm font-medium text-zinc-700 dark:text-zinc-300">
                          {label}
                        </span>
                        <span className="ml-auto text-xs text-zinc-400 dark:text-zinc-500">
                          {modelList.length}
                        </span>
                      </button>

                      {/* Model list */}
                      {isOpen && (
                        <div className="border-t border-zinc-200 dark:border-zinc-700 max-h-64 overflow-y-auto">
                          {modelList.map((m) => {
                            const isDefault = m.id === defaultModel
                            return (
                              <div
                                key={m.id}
                                className={cn(
                                  'group flex items-center gap-2 px-3 py-1.5 border-b border-zinc-100 last:border-b-0 hover:bg-zinc-50 transition-colors dark:border-zinc-800 dark:hover:bg-zinc-800/40',
                                  isDefault && 'bg-accent-500/5'
                                )}
                              >
                                <div className="flex-1 min-w-0">
                                  <div className="flex items-center gap-1.5">
                                    <span
                                      className="text-[13px] text-zinc-800 dark:text-zinc-200 truncate"
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
                                  <div className="flex items-center gap-1.5 text-[10px] text-zinc-400 dark:text-zinc-500">
                                    <span>{formatModelNum(m.context_window)} ctx</span>
                                    {m.pricing && (
                                      <>
                                        <span className="text-zinc-300 dark:text-zinc-700">/</span>
                                        <span className="text-emerald-600 dark:text-emerald-400">
                                          {formatModelPrice(m.pricing.input)}
                                        </span>
                                        <span className="text-zinc-300 dark:text-zinc-700">·</span>
                                        <span className="text-amber-600 dark:text-amber-400">
                                          {formatModelPrice(m.pricing.output)}
                                        </span>
                                      </>
                                    )}
                                  </div>
                                </div>
                                {!isDefault && (
                                  <button
                                    onClick={() => handleDefaultModelChange(m.id)}
                                    className="shrink-0 rounded p-1 text-zinc-300 opacity-0 transition-all hover:text-accent-500 group-hover:opacity-100 dark:text-zinc-600 dark:hover:text-accent-400"
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
        className="flex flex-col gap-3 rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <h4 className="font-medium text-zinc-800 dark:text-zinc-200">{label}</h4>
            <span
              className={cn(
                'inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium',
                provider.configured
                  ? 'bg-green-500/20 text-green-600 dark:text-green-400'
                  : 'bg-zinc-300 text-zinc-600 dark:bg-zinc-700 dark:text-zinc-400'
              )}
            >
              {provider.configured ? 'Active' : 'Not set'}
            </span>
          </div>
          {provider.configured && (
            <button
              onClick={() => handleDelete(provider.name)}
              className="rounded p-1 text-zinc-400 transition-colors hover:bg-red-500/10 hover:text-red-400"
              title="Remove key"
            >
              <Trash2 className="h-4 w-4" />
            </button>
          )}
        </div>

        <p className="text-xs text-zinc-500">
          {isEndpoint ? 'Endpoint URL' : 'API Key'}: <code className="text-zinc-400">{provider.env_key}</code>
          {provider.default && (
            <span className="ml-1 text-zinc-500">(default: {provider.default})</span>
          )}
        </p>

        {/* Show masked value if configured and not editing */}
        {provider.configured && !isEditing && (
          <div className="flex items-center gap-2">
            <div className="flex-1 rounded-lg border border-zinc-300 bg-zinc-200/50 px-3 py-2 font-mono text-sm text-zinc-500 dark:border-zinc-600 dark:bg-zinc-700/50 dark:text-zinc-400">
              {isVisible ? provider.masked_value : provider.masked_value.replace(/./g, '*').slice(0, 20) + '****'}
            </div>
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="rounded p-2 text-zinc-400 transition-colors hover:bg-zinc-200 hover:text-zinc-600 dark:hover:bg-zinc-700 dark:hover:text-zinc-300"
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
            className="h-10 flex-1 rounded-lg border border-zinc-300 bg-white px-3 font-mono text-sm text-zinc-900 outline-none transition-colors focus:border-accent-500 dark:border-zinc-600 dark:bg-zinc-800 dark:text-zinc-100"
          />
          {!isEndpoint && (
            <button
              onClick={() => toggleVisibility(provider.name)}
              className="rounded-lg border border-zinc-300 px-3 text-zinc-400 transition-colors hover:bg-zinc-200 hover:text-zinc-600 dark:border-zinc-600 dark:hover:bg-zinc-700 dark:hover:text-zinc-300"
              title={isVisible ? 'Hide' : 'Show'}
            >
              {isVisible ? <EyeOff className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
            </button>
          )}
          <button
            onClick={() => handleSave(provider.name)}
            disabled={!inputValue.trim() || isSaving}
            className="flex items-center gap-1.5 rounded-lg bg-accent-600 px-4 text-sm font-medium text-white transition-colors hover:bg-accent-500 disabled:opacity-50 disabled:cursor-not-allowed"
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
          <p className="text-sm text-zinc-500">
            Configure API keys for cloud-based AI providers. Models will be automatically discovered
            once a valid key is saved.
          </p>
          {cloudProviders.map(renderProviderCard)}
        </div>
      </Section>

      <Section icon={Server} title="Local Providers">
        <div className="space-y-4">
          <p className="text-sm text-zinc-500">
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
                className="h-10 w-24 rounded-lg border border-zinc-300 bg-zinc-100 px-4 text-zinc-900 outline-none focus:border-cachi-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
              />
              <span className="text-sm text-zinc-500 dark:text-zinc-400">seconds</span>
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
              <span className="w-12 text-center text-sm text-zinc-400">
                {config?.agent.temperature ?? 0.7}
              </span>
            </div>
            <p className="mt-1 text-xs text-zinc-500">
              Controls randomness in responses (0 = deterministic, 1 = creative)
            </p>
          </Field>

          <Field label="Max Iterations">
            <input
              type="number"
              value={config?.agent.maxIterations ?? 20}
              min={1}
              max={100}
              className="h-10 w-32 rounded-lg border border-zinc-300 bg-zinc-100 px-4 text-zinc-900 outline-none focus:border-cachi-500 dark:border-zinc-700 dark:bg-zinc-800 dark:text-zinc-100"
            />
            <p className="mt-1 text-xs text-zinc-500">
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
          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Anonymous Analytics</h4>
              <p className="text-sm text-zinc-500">
                Send anonymous usage statistics to help improve CachiBot
              </p>
            </div>
            <button
              onClick={handleToggleTelemetry}
              className={cn(
                'relative inline-flex h-6 w-11 items-center rounded-full transition-colors',
                telemetryStatus?.enabled
                  ? 'bg-accent-600'
                  : 'bg-zinc-300 dark:bg-zinc-600'
              )}
            >
              <span
                className={cn(
                  'inline-block h-4 w-4 rounded-full bg-white transition-transform',
                  telemetryStatus?.enabled ? 'translate-x-6' : 'translate-x-1'
                )}
              />
            </button>
          </div>

          {/* View report */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">View Telemetry Report</h4>
              <p className="text-sm text-zinc-500">
                See exactly what data would be sent
              </p>
            </div>
            <button
              onClick={handleViewTelemetryReport}
              className="flex items-center gap-2 rounded-lg bg-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-400 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
            >
              <EyeIcon className="h-4 w-4" />
              View
            </button>
          </div>

          {/* Reset ID */}
          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Reset Install ID</h4>
              <p className="text-sm text-zinc-500">
                Generate a new anonymous identifier{telemetryStatus?.install_id && (
                  <span className="ml-1 font-mono text-xs text-zinc-400">
                    ({telemetryStatus.install_id.slice(0, 8)}...)
                  </span>
                )}
              </p>
            </div>
            <button
              onClick={() => setShowResetIdConfirm(true)}
              className="flex items-center gap-2 rounded-lg bg-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-400 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600"
            >
              <RefreshCw className="h-4 w-4" />
              Reset
            </button>
          </div>

          {/* Last sent */}
          {telemetryStatus?.last_sent && (
            <p className="text-xs text-zinc-500">
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-lg rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Telemetry Report Preview</h2>
              <button
                onClick={() => setShowTelemetryPreview(false)}
                className="text-zinc-400 hover:text-zinc-600 dark:hover:text-zinc-300"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <pre className="max-h-96 overflow-auto rounded-lg bg-zinc-100 p-4 text-xs text-zinc-800 dark:bg-zinc-800 dark:text-zinc-200">
              {JSON.stringify(telemetryPayload, null, 2)}
            </pre>
            <div className="mt-4 flex justify-end">
              <button
                onClick={() => setShowTelemetryPreview(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-600 hover:bg-zinc-200 dark:text-zinc-400 dark:hover:bg-zinc-800"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Reset ID confirmation modal */}
      {showResetIdConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-zinc-600 dark:text-zinc-400">
              <RefreshCw className="h-6 w-6" />
              <h2 className="text-lg font-bold text-zinc-900 dark:text-zinc-100">Reset Install ID?</h2>
            </div>
            <p className="mb-6 text-sm text-zinc-500">
              This will generate a new anonymous identifier. Your previous telemetry data
              will no longer be associated with this installation.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowResetIdConfirm(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-200 dark:hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={handleResetId}
                className="rounded-lg bg-accent-600 px-4 py-2 text-sm font-medium text-white hover:bg-accent-500"
              >
                Reset ID
              </button>
            </div>
          </div>
        </div>
      )}

      <Section icon={Database} title="Data Management">
        <div className="space-y-4">
          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Export Data</h4>
              <p className="text-sm text-zinc-500">
                Download all your data as a JSON file
              </p>
            </div>
            <button
              onClick={handleExport}
              className="flex items-center gap-2 rounded-lg bg-cachi-600 px-4 py-2 text-sm font-medium text-white hover:bg-cachi-500"
            >
              <Download className="h-4 w-4" />
              Export
            </button>
          </div>

          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Import Data</h4>
              <p className="text-sm text-zinc-500">
                Restore from a previous backup
              </p>
            </div>
            <button className="flex items-center gap-2 rounded-lg bg-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-400 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600">
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
          <div className="flex items-center justify-between rounded-lg border border-zinc-300 bg-zinc-100/50 p-4 dark:border-zinc-700 dark:bg-zinc-800/50">
            <div>
              <h4 className="font-medium text-zinc-800 dark:text-zinc-200">Clear Cache</h4>
              <p className="text-sm text-zinc-500">
                Remove cached responses and temporary data
              </p>
            </div>
            <button className="flex items-center gap-2 rounded-lg bg-zinc-300 px-4 py-2 text-sm font-medium text-zinc-800 hover:bg-zinc-400 dark:bg-zinc-700 dark:text-zinc-200 dark:hover:bg-zinc-600">
              <RefreshCw className="h-4 w-4" />
              Clear
            </button>
          </div>
        </div>
      </Section>

      <Section icon={AlertTriangle} title="Danger Zone" danger>
        <div className="rounded-lg border border-red-500/30 bg-red-500/5 p-4">
          <h4 className="font-medium text-red-400">Delete All Data</h4>
          <p className="mt-1 text-sm text-zinc-500">
            Permanently delete all bots, chats, jobs, tasks, and settings. This
            cannot be undone.
          </p>
          <button
            onClick={() => setShowDeleteConfirm(true)}
            className="mt-3 flex items-center gap-2 rounded-lg bg-red-600/20 px-4 py-2 text-sm text-red-400 hover:bg-red-600/30"
          >
            <Trash2 className="h-4 w-4" />
            Delete Everything
          </button>
        </div>
      </Section>

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="text-lg font-bold">Delete All Data</h2>
            </div>
            <p className="mb-6 text-zinc-400">
              Are you sure you want to delete all your data? This will remove all
              bots, chats, jobs, tasks, connections, and settings.
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800"
              >
                Cancel
              </button>
              <button
                onClick={handleClearAll}
                className="rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500"
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
        <p className="text-sm text-zinc-500">
          Clear specific data for each bot while keeping bot settings and connections intact.
          {loadingPlatform && (
            <span className="ml-2 text-zinc-400">
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
                className="rounded-lg border border-zinc-300 bg-zinc-100/30 overflow-hidden dark:border-zinc-700 dark:bg-zinc-800/30"
              >
                {/* Bot header */}
                <button
                  onClick={() => toggleBot(info.botId)}
                  className="flex w-full items-center gap-3 p-3 hover:bg-zinc-200/50 transition-colors dark:hover:bg-zinc-800/50"
                >
                  {isExpanded ? (
                    <ChevronDown className="h-4 w-4 text-zinc-500" />
                  ) : (
                    <ChevronRight className="h-4 w-4 text-zinc-500" />
                  )}
                  <div
                    className="h-8 w-8 rounded-lg flex items-center justify-center"
                    style={{ backgroundColor: info.botColor + '20' }}
                  >
                    <Bot className="h-4 w-4" style={{ color: info.botColor }} />
                  </div>
                  <div className="flex-1 text-left">
                    <div className="font-medium text-zinc-800 dark:text-zinc-200">{info.botName}</div>
                    <div className="text-xs text-zinc-500">
                      {info.chatsCount} local chats · {info.jobsCount} jobs · {info.tasksCount} tasks
                      {info.platformChatsCount > 0 && (
                        <span className="text-cyan-400"> · {info.platformChatsCount} platform chats</span>
                      )}
                    </div>
                  </div>
                  {botSelected && botSelected.size > 0 && (
                    <span className="rounded-full bg-red-500/20 px-2 py-0.5 text-xs text-red-400">
                      {botSelected.size} selected
                    </span>
                  )}
                </button>

                {/* Expanded content */}
                {isExpanded && (
                  <div className="border-t border-zinc-300 p-3 dark:border-zinc-700">
                    {!hasData ? (
                      <p className="text-sm text-zinc-500 text-center py-2">
                        No data to clear for this bot
                      </p>
                    ) : (
                      <>
                        {/* Quick actions */}
                        <div className="flex gap-2 mb-3">
                          <button
                            onClick={() => selectAllForBot(info.botId, info)}
                            className="text-xs text-zinc-500 hover:text-zinc-800 transition-colors dark:text-zinc-400 dark:hover:text-zinc-200"
                          >
                            Select all
                          </button>
                          <span className="text-zinc-400 dark:text-zinc-600">·</span>
                          <button
                            onClick={() => clearSelectionForBot(info.botId)}
                            className="text-xs text-zinc-500 hover:text-zinc-800 transition-colors dark:text-zinc-400 dark:hover:text-zinc-200"
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
          <div className="flex items-center justify-between rounded-lg border border-red-500/30 bg-red-500/5 p-3">
            <div className="text-sm">
              <span className="text-red-400 font-medium">{getTotalSelectedItems()}</span>
              <span className="text-zinc-400"> items selected for deletion</span>
            </div>
            <button
              onClick={() => setShowConfirmModal(true)}
              className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              Clear Selected
            </button>
          </div>
        )}
      </div>

      {/* Confirmation modal */}
      {showConfirmModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-900 p-6 shadow-2xl">
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="text-lg font-bold">Clear Bot Data</h2>
            </div>
            <p className="mb-4 text-zinc-400">
              Are you sure you want to clear the selected data? This action cannot be undone.
            </p>

            {/* Summary of what will be deleted */}
            <div className="mb-6 rounded-lg border border-zinc-700 bg-zinc-800/50 p-3 space-y-2">
              {Array.from(selectedItems.entries()).map(([botId, categories]) => {
                const info = botDataInfos.find((b) => b.botId === botId)
                if (!info) return null
                return (
                  <div key={botId} className="text-sm">
                    <span className="font-medium text-zinc-200">{info.botName}:</span>
                    <span className="text-zinc-400 ml-2">
                      {Array.from(categories).map((cat) => categoryConfig[cat].label).join(', ')}
                    </span>
                  </div>
                )
              })}
            </div>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowConfirmModal(false)}
                disabled={clearing}
                className="rounded-lg px-4 py-2 text-sm text-zinc-400 hover:bg-zinc-800 disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleClearSelected}
                disabled={clearing}
                className="flex items-center gap-2 rounded-lg bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-500 disabled:opacity-50"
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
        'flex items-center gap-2 rounded-lg border p-2 transition-all text-left',
        selected
          ? 'border-red-500/50 bg-red-500/10'
          : 'border-zinc-300 bg-zinc-100/50 hover:border-zinc-400 dark:border-zinc-700 dark:bg-zinc-800/50 dark:hover:border-zinc-600'
      )}
    >
      <div
        className={cn(
          'h-6 w-6 rounded flex items-center justify-center transition-colors',
          selected ? 'bg-red-500/20' : 'bg-zinc-300 dark:bg-zinc-700'
        )}
      >
        {selected ? (
          <Check className="h-3.5 w-3.5 text-red-400" />
        ) : (
          <Icon className={cn('h-3.5 w-3.5', config.color)} />
        )}
      </div>
      <div className="flex-1 min-w-0">
        <div className={cn('text-sm font-medium', selected ? 'text-red-400' : 'text-zinc-800 dark:text-zinc-200')}>
          {config.label}
        </div>
        <div className="text-xs text-zinc-500">
          {count} {detail || (count === 1 ? 'item' : 'items')}
        </div>
      </div>
    </button>
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
            <p className="text-sm text-zinc-400">
              {total} user{total !== 1 ? 's' : ''} total
            </p>
            <Button onClick={() => setShowCreateModal(true)} size="sm">
              <UserPlus className="h-4 w-4 mr-2" />
              Add User
            </Button>
          </div>

          {/* Users Table */}
          <div className="rounded-lg border border-zinc-300 overflow-hidden dark:border-zinc-700">
            {/* Table Header */}
            <div className="grid grid-cols-[1fr_1fr_80px_80px_40px] gap-2 px-4 py-2 bg-zinc-100/50 text-xs text-zinc-500 font-medium dark:bg-zinc-800/50 dark:text-zinc-400">
              <div>User</div>
              <div>Email</div>
              <div>Role</div>
              <div>Status</div>
              <div></div>
            </div>

            {/* User Rows */}
            {users.length === 0 ? (
              <div className="px-4 py-6 text-center text-zinc-500 text-sm">
                No users found
              </div>
            ) : (
              users.map((user) => (
                <div
                  key={user.id}
                  className="grid grid-cols-[1fr_1fr_80px_80px_40px] gap-2 px-4 py-2.5 border-t border-zinc-300 items-center hover:bg-zinc-100/30 transition-colors dark:border-zinc-700 dark:hover:bg-zinc-800/30"
                >
                  <div className="flex items-center gap-2 min-w-0">
                    <div className="w-7 h-7 rounded-full bg-zinc-300 flex items-center justify-center flex-shrink-0 dark:bg-zinc-700">
                      <AtSign className="h-3.5 w-3.5 text-zinc-500 dark:text-zinc-400" />
                    </div>
                    <div className="min-w-0">
                      <div className="font-medium text-sm truncate text-zinc-800 dark:text-zinc-100">{user.username}</div>
                      {user.id === currentUser?.id && (
                        <div className="text-xs text-cachi-600 dark:text-cachi-400">You</div>
                      )}
                    </div>
                  </div>
                  <div className="text-zinc-500 text-sm truncate dark:text-zinc-400">{user.email}</div>
                  <div>
                    <span
                      className={cn(
                        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium',
                        user.role === 'admin'
                          ? 'bg-purple-500/20 text-purple-300'
                          : 'bg-zinc-700 text-zinc-300'
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
                        'inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-xs font-medium',
                        user.is_active
                          ? 'bg-green-500/20 text-green-300'
                          : 'bg-red-500/20 text-red-300'
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
                      className="p-1 hover:bg-zinc-200 rounded transition-colors disabled:opacity-50 dark:hover:bg-zinc-700"
                      disabled={user.id === currentUser?.id}
                    >
                      <MoreVertical className="h-4 w-4 text-zinc-500 dark:text-zinc-400" />
                    </button>
                    {menuOpen === user.id && (
                      <div className="absolute right-0 top-full mt-1 w-36 bg-white border border-zinc-300 rounded-lg shadow-lg py-1 z-20 dark:bg-zinc-800 dark:border-zinc-700">
                        <button
                          onClick={() => startEditing(user)}
                          className="w-full px-3 py-1.5 text-left text-sm hover:bg-zinc-100 transition-colors text-zinc-700 dark:text-zinc-100 dark:hover:bg-zinc-700"
                        >
                          Edit User
                        </button>
                        {user.is_active && (
                          <button
                            onClick={() => handleDeactivateUser(user.id)}
                            className="w-full px-3 py-1.5 text-left text-sm text-red-500 hover:bg-zinc-100 transition-colors dark:text-red-400 dark:hover:bg-zinc-700"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl border border-zinc-300 p-6 w-full max-w-md mx-4 dark:bg-zinc-900 dark:border-zinc-800">
            <h2 className="text-lg font-semibold mb-4 text-zinc-900 dark:text-zinc-100">Create New User</h2>
            <form onSubmit={handleCreateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
                  Email
                </label>
                <div className="relative">
                  <Mail className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                  <input
                    type="email"
                    value={createForm.email}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, email: e.target.value })
                    }
                    className="w-full pl-10 pr-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                    required
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
                  Username
                </label>
                <div className="relative">
                  <AtSign className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-zinc-500" />
                  <input
                    type="text"
                    value={createForm.username}
                    onChange={(e) =>
                      setCreateForm({ ...createForm, username: e.target.value })
                    }
                    className="w-full pl-10 pr-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                    required
                    minLength={3}
                    maxLength={32}
                  />
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
                  Password
                </label>
                <input
                  type="password"
                  value={createForm.password}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, password: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                  required
                  minLength={8}
                  placeholder="Min. 8 characters"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
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
                  className="w-full px-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                >
                  <option value="user">User</option>
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
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
          <div className="bg-white rounded-xl border border-zinc-300 p-6 w-full max-w-md mx-4 dark:bg-zinc-900 dark:border-zinc-800">
            <h2 className="text-lg font-semibold mb-4 text-zinc-900 dark:text-zinc-100">Edit User</h2>
            <form onSubmit={handleUpdateUser} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
                  Email
                </label>
                <input
                  type="email"
                  value={editForm.email}
                  onChange={(e) =>
                    setEditForm({ ...editForm, email: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
                  Username
                </label>
                <input
                  type="text"
                  value={editForm.username}
                  onChange={(e) =>
                    setEditForm({ ...editForm, username: e.target.value })
                  }
                  className="w-full px-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                  required
                  minLength={3}
                  maxLength={32}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-zinc-700 mb-1.5 dark:text-zinc-300">
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
                  className="w-full px-3 py-2 bg-zinc-100 border border-zinc-300 rounded-lg text-zinc-900 focus:outline-none focus:ring-2 focus:ring-cachi-500 dark:bg-zinc-800 dark:border-zinc-700 dark:text-white"
                >
                  <option value="user">User</option>
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
    <div className="rounded-xl border border-zinc-300 bg-white dark:border-zinc-800 dark:bg-zinc-900/30">
      <div
        className={cn(
          'flex items-center gap-2 border-b px-5 py-4',
          danger ? 'border-red-500/30' : 'border-zinc-300 dark:border-zinc-800'
        )}
      >
        <Icon
          className={cn('h-5 w-5', danger ? 'text-red-400' : 'text-zinc-500 dark:text-zinc-400')}
        />
        <h3
          className={cn(
            'font-semibold',
            danger ? 'text-red-400' : 'text-zinc-800 dark:text-zinc-200'
          )}
        >
          {title}
        </h3>
      </div>
      <div className="p-5">{children}</div>
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
      <label className="mb-2 block text-sm font-medium text-zinc-700 dark:text-zinc-300">
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
    <div className="flex items-center justify-between">
      <div>
        <h4 className="font-medium text-zinc-800 dark:text-zinc-200">{label}</h4>
        <p className="text-sm text-zinc-500">{description}</p>
      </div>
      <button
        onClick={() => onChange(!checked)}
        className={cn(
          'relative h-6 w-11 rounded-full transition-colors',
          checked ? 'bg-accent-600' : 'bg-zinc-300 dark:bg-zinc-700'
        )}
      >
        <span
          className={cn(
            'absolute top-1 h-4 w-4 rounded-full bg-white transition-transform',
            checked ? 'left-6' : 'left-1'
          )}
        />
      </button>
    </div>
  )
}

function ShortcutItem({ label, shortcut }: { label: string; shortcut: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-zinc-700 dark:text-zinc-300">{label}</span>
      <kbd className="rounded bg-zinc-200 px-2 py-1 font-mono text-xs text-zinc-600 dark:bg-zinc-800 dark:text-zinc-400">
        {shortcut}
      </kbd>
    </div>
  )
}

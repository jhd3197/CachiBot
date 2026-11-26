import { useState, useEffect, useMemo, useRef } from 'react'
import QRCode from 'qrcode'
import { useParams, useNavigate, Link } from 'react-router-dom'
import {
  Moon,
  Sun,
  Monitor,
  Eye as EyeIcon,
  Shield,
  Trash2,
  Download,
  RefreshCw,
  ExternalLink,
  AlertTriangle,
  Brain,
  UserPlus,
  User as UserIcon,
  MoreVertical,
  Check,
  X,
  ChevronRight,
  ChevronDown,
  Bot,
  MessageSquare,
  Briefcase,
  CheckSquare,
  BarChart3,
  EyeOff,
  Star,
  Sparkles,
  Search,
  Plus,
  Timer,
  ChevronLeft,
  Lock,
} from 'lucide-react'
import { toast } from 'sonner'
import { useUIStore, Theme, PresetColor, accentColors, generatePalette } from '../../stores/ui'
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
import { changePassword, listUsers } from '../../api/auth'
import {
  listGroups,
  createGroup,
  getGroup,
  deleteGroup,
  addMember,
  removeMember,
} from '../../api/groups'
import { getExecutionStats } from '../../api/execution-log'
import {
  updateConfig,
  checkHealth,
  createMobilePairToken,
  getFirewallStatus,
  enableFirewallRule,
  clearBotPlatformData,
  type HealthInfo,
  type PairTokenResponse,
  type FirewallStatus,
} from '../../api/client'
import { ModelSelect } from '../common/ModelSelect'
import { Button } from '../common/Button'
import { Spinner } from '../common/Spinner'
import { useDelayedFlag } from '../../hooks/useDelayedFlag'
import { useVelaCompanionStatus } from '../../hooks/useVelaCompanion'
import { updateVelaCompanionSettings } from '../../api/vela-companion'
import { cn, parseApiDate } from '../../lib/utils'
import type { Group, GroupWithMembers, GroupMember, GroupRole } from '../../types'

/**
 * App settings (design view 19): one narrow column, section pills deep-link to
 * /settings/<section>. Every option from the old tabbed settings is mapped
 * into the design's sections; items the design shows but no real source backs
 * (language picker, budget, developer mode, licenses…) are hidden — see
 * UI_V2_PLAN.md "Phase D5 - not backed yet".
 *
 * Section map (old tab -> new section): keys -> models, users/groups ->
 * people, everything else keeps its name. /settings/account scrolls to the
 * Your account block in General.
 */

type SettingsSection = 'general' | 'appearance' | 'models' | 'data' | 'people' | 'advanced' | 'about'

const SECTION_IDS: SettingsSection[] = ['general', 'appearance', 'models', 'data', 'people', 'advanced', 'about']

const SECTION_LABELS: Record<SettingsSection, string> = {
  general: 'General',
  appearance: 'Appearance',
  models: 'Models',
  data: 'Data',
  people: 'People',
  advanced: 'Advanced',
  about: 'About',
}

/** Old deep links keep working, mapped onto the new sections. */
const TAB_ALIASES: Record<string, SettingsSection> = {
  general: 'general',
  appearance: 'appearance',
  models: 'models',
  keys: 'models',
  data: 'data',
  people: 'people',
  users: 'people',
  groups: 'people',
  advanced: 'advanced',
  about: 'about',
  account: 'general',
}

export function AppSettingsView() {
  const { settingsTab: urlTab } = useParams<{ settingsTab?: string }>()
  const navigate = useNavigate()
  const { user: currentUser } = useAuthStore()
  const isAdmin = currentUser?.role === 'admin'
  const isManagerOrAdmin = isAdmin || currentUser?.role === 'manager'

  // Resolve the URL tab (with legacy aliases) to a visible section
  const resolveSection = (): { section: SettingsSection; valid: boolean } => {
    if (!urlTab) return { section: 'general', valid: true }
    const section = TAB_ALIASES[urlTab]
    if (!section) return { section: 'general', valid: false }
    // People holds admin (users) and manager+ (groups) content only
    if (section === 'people' && !isManagerOrAdmin) return { section: 'general', valid: false }
    return { section, valid: true }
  }
  const { section: activeSection, valid } = resolveSection()

  useEffect(() => {
    if (urlTab && !valid) navigate('/settings', { replace: true })
  }, [urlTab, valid, navigate])

  // Deep link scrolls to the target section (or the account block); bare
  // /settings stays at the top so the header and pills remain visible
  const firstScroll = useRef(true)
  useEffect(() => {
    if (!urlTab) return
    const target =
      urlTab === 'account'
        ? document.getElementById('v2s-account')
        : document.getElementById(`v2s-${activeSection}`)
    if (!target) return
    target.scrollIntoView({ behavior: firstScroll.current ? 'auto' : 'smooth', block: 'start' })
    firstScroll.current = false
  }, [activeSection, urlTab])

  const goSection = (section: SettingsSection) => {
    navigate(section === 'general' ? '/settings/general' : `/settings/${section}`)
  }

  const visibleSections = SECTION_IDS.filter((s) => s !== 'people' || isManagerOrAdmin)

  return (
    <div className="v2-settings">
      <div className="v2-settings__column">
        {/* Top bar per design: back · centered title · close */}
        <div className="v2-settings__topbar">
          <button
            type="button"
            className="v2-settings__top-btn"
            aria-label="Back"
            onClick={() => navigate(-1)}
          >
            <ChevronLeft size={18} strokeWidth={1.8} aria-hidden="true" />
          </button>
          <h1 className="v2-settings__title">Settings</h1>
          <button
            type="button"
            className="v2-settings__top-btn"
            aria-label="Close"
            onClick={() => navigate('/dashboard')}
          >
            <X size={18} strokeWidth={1.8} aria-hidden="true" />
          </button>
        </div>

        {/* Section pills (jump links) */}
        <nav className="v2-settings__nav" aria-label="Sections">
          {visibleSections.map((section) => (
            <button
              key={section}
              type="button"
              className={cn('v2-settings__pill', activeSection === section && 'v2-settings__pill--active')}
              onClick={() => goSection(section)}
            >
              {SECTION_LABELS[section]}
            </button>
          ))}
        </nav>

        <GeneralSection />
        <AppearanceSection />
        <ModelsSection />
        <DataSection />
        {isManagerOrAdmin && <PeopleSection isAdmin={isAdmin} />}
        <AdvancedSection isAdmin={isAdmin} />
        <AboutSection />
      </div>
    </div>
  )
}

// =============================================================================
// SHARED V2 PRIMITIVES
// =============================================================================

function V2Section({
  id,
  title,
  badge,
  desc,
  children,
}: {
  id: string
  title: string
  badge?: string
  desc?: string
  children: React.ReactNode
}) {
  return (
    <section id={`v2s-${id}`} className="v2-settings__section" aria-label={title}>
      <h2 className="v2-settings__heading">
        {title}
        {badge && <span className="v2-settings__badge">{badge}</span>}
      </h2>
      {desc && <p className="v2-settings__desc">{desc}</p>}
      {children}
    </section>
  )
}

/** 48px row: title (+optional subtitle) left, action button right. */
function V2Row({
  title,
  sub,
  danger,
  action,
  children,
}: {
  title: React.ReactNode
  sub?: React.ReactNode
  danger?: boolean
  /** Right-hand 28px action (button or link) */
  action?: React.ReactNode
  children?: React.ReactNode
}) {
  return (
    <div className="v2-settings__row">
      <span className="v2-settings__row-main">
        <span className={cn('v2-settings__row-title', danger && 'v2-settings__row-title--danger')}>
          {title}
        </span>
        {sub && <span className="v2-settings__row-sub">{sub}</span>}
        {children}
      </span>
      {action}
    </div>
  )
}

/** Toggle row with the design's 40x24 switch. */
function V2Toggle({
  title,
  sub,
  checked,
  onChange,
  disabled,
}: {
  title: string
  sub?: string
  checked: boolean
  onChange: (checked: boolean) => void
  disabled?: boolean
}) {
  return (
    <div className="v2-settings__toggle">
      <span className="v2-settings__toggle-main">
        <span className="v2-settings__toggle-title">{title}</span>
        {sub && <span className="v2-settings__toggle-sub">{sub}</span>}
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={title}
        className="v2-switch"
        disabled={disabled}
        onClick={() => onChange(!checked)}
      >
        <span />
      </button>
    </div>
  )
}

/** 40px select-style field: label above, bordered box with chevron. */
function V2Field({
  label,
  hint,
  children,
}: {
  label: string
  hint?: string
  children: React.ReactNode
}) {
  return (
    <label className="v2-settings__field">
      <span className="v2-settings__label">{label}</span>
      {children}
      {hint && <p className="v2-settings__hint">{hint}</p>}
    </label>
  )
}

// =============================================================================
// GENERAL
// =============================================================================

function GeneralSection() {
  const { showThinking, setShowThinking, showCost, setShowCost } = useUIStore()
  const { config } = useConfigStore()
  const { user } = useAuthStore()
  const [showChangePassword, setShowChangePassword] = useState(false)

  const handleDisplayToggle = async (key: 'showThinking' | 'showCost', value: boolean) => {
    if (key === 'showThinking') setShowThinking(value)
    else setShowCost(value)
    try {
      await updateConfig({ [key === 'showThinking' ? 'show_thinking' : 'show_cost']: value })
    } catch {
      console.error('Failed to update setting')
    }
  }

  return (
    <V2Section id="general" title="General">
      {/* Your account: real auth-store identity + the real change-password API */}
      <div id="v2s-account" style={{ display: 'contents' }}>
        <h3 className="v2-settings__sub">Your account</h3>
        <div className="v2-settings__rows">
          <V2Row title="Username" sub={user?.username || '—'} />
          <V2Row title="Email" sub={user?.email || '—'} />
          <V2Row
            title="Password"
            sub="Change the password you sign in with"
            action={
              <button type="button" className="v2-settings__action" onClick={() => setShowChangePassword(true)}>
                Change
              </button>
            }
          />
        </div>
      </div>

      <h3 className="v2-settings__sub">Display</h3>
      <V2Toggle
        title="Show thinking process"
        sub="Display the AI's reasoning and thought process"
        checked={showThinking}
        onChange={(v) => void handleDisplayToggle('showThinking', v)}
      />
      <V2Toggle
        title="Show token costs"
        sub="Display estimated costs for API calls"
        checked={showCost}
        onChange={(v) => void handleDisplayToggle('showCost', v)}
      />

      {/* Real server values (read-only — no endpoint changes them) */}
      {(config?.timezone || config?.workspacePath) && (
        <>
          <h3 className="v2-settings__sub">Server</h3>
          <div className="v2-settings__rows">
            {config?.timezone && <V2Row title="Time zone" sub={config.timezone} />}
            {config?.workspacePath && <V2Row title="Workspace" sub={config.workspacePath} />}
          </div>
        </>
      )}

      <StartOnBootSection />
      <MobilePairingSection />
      <VelaSection />
      <SetupWizardRow />
      {showChangePassword && <ChangePasswordDialog onClose={() => setShowChangePassword(false)} />}
    </V2Section>
  )
}

function ChangePasswordDialog({ onClose }: { onClose: () => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [confirm, setConfirm] = useState('')
  const [saving, setSaving] = useState(false)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (next.length < 8) {
      toast.error('New password must be at least 8 characters')
      return
    }
    if (next !== confirm) {
      toast.error('New passwords do not match')
      return
    }
    setSaving(true)
    try {
      await changePassword({ current_password: current, new_password: next })
      toast.success('Password changed')
      onClose()
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to change password')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="settings-modal">
      <div className="settings-modal__panel--sm mx-4">
        <h2 className="settings-modal__heading mb-4">Change password</h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="settings-modal__label">Current password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-[var(--color-text-secondary)]" />
              <input
                type="password"
                value={current}
                onChange={(e) => setCurrent(e.target.value)}
                className="settings-modal__input pl-10"
                required
                autoComplete="current-password"
              />
            </div>
          </div>
          <div>
            <label className="settings-modal__label">New password</label>
            <input
              type="password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              className="settings-modal__input"
              required
              minLength={8}
              placeholder="Min. 8 characters"
              autoComplete="new-password"
            />
          </div>
          <div>
            <label className="settings-modal__label">Confirm new password</label>
            <input
              type="password"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              className="settings-modal__input"
              required
              autoComplete="new-password"
            />
          </div>
          <div className="flex gap-3 pt-2">
            <Button type="button" variant="ghost" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit" className="flex-1" pending={saving}>
              Change password
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

function StartOnBootSection() {
  const [enabled, setEnabled] = useState(false)
  const isElectron = !!window.electronAPI?.isDesktop

  useEffect(() => {
    window.electronAPI?.getStartOnBoot?.().then((val) => {
      setEnabled(val as boolean)
    })
  }, [])

  if (!isElectron) return null

  const handleToggle = async (checked: boolean) => {
    await window.electronAPI?.setStartOnBoot?.(checked)
    setEnabled(checked)
  }

  return (
    <>
      <h3 className="v2-settings__sub">Startup</h3>
      <V2Toggle
        title="Start on boot"
        sub="Automatically launch CachiBot when you log in to your computer"
        checked={enabled}
        onChange={(v) => void handleToggle(v)}
      />
    </>
  )
}

function SetupWizardRow() {
  const navigate = useNavigate()

  const handleRunWizard = () => {
    useOnboardingStore.getState().resetStep()
    navigate('/onboarding')
  }

  return (
    <>
      <h3 className="v2-settings__sub">Setup</h3>
      <div className="v2-settings__rows">
        <V2Row
          title="Run setup wizard"
          sub="Re-run the initial setup to configure API keys, models, and preferences"
          action={
            <button type="button" className="v2-settings__action" onClick={handleRunWizard}>
              Run
            </button>
          }
        />
      </div>
    </>
  )
}

function MobilePairingSection() {
  const [showQr, setShowQr] = useState(false)
  const [pairData, setPairData] = useState<PairTokenResponse | null>(null)
  const [countdown, setCountdown] = useState(0)
  const [loading, setLoading] = useState(false)
  const [firewall, setFirewall] = useState<FirewallStatus | null>(null)
  const [firewallLoading, setFirewallLoading] = useState(false)

  useEffect(() => {
    getFirewallStatus().then(setFirewall).catch(() => {})
  }, [])

  const handleEnableFirewall = async () => {
    setFirewallLoading(true)
    try {
      const result = await enableFirewallRule()
      if (result.success) {
        toast.success(result.message)
        const updated = await getFirewallStatus()
        setFirewall(updated)
      }
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : 'Failed to create firewall rule. Try running the server as administrator.'
      toast.error(msg)
    } finally {
      setFirewallLoading(false)
    }
  }

  const fetchToken = async () => {
    setLoading(true)
    try {
      const data = await createMobilePairToken()
      setPairData(data)
      setCountdown(Math.floor(data.expires))
      setShowQr(true)
    } catch {
      toast.error('Failed to generate pairing token')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (!showQr || countdown <= 0) return
    const interval = setInterval(() => {
      setCountdown((prev) => {
        if (prev <= 1) {
          fetchToken()
          return 0
        }
        return prev - 1
      })
    }, 1000)
    return () => clearInterval(interval)
  }, [showQr, countdown > 0])

  const qrValue = pairData
    ? `cachibot://pair?url=${encodeURIComponent(pairData.url)}&token=${encodeURIComponent(pairData.token)}${pairData.urls.map((u) => `&urls=${encodeURIComponent(u)}`).join('')}`
    : ''

  return (
    <>
      <h3 className="v2-settings__sub">Mobile app</h3>
      <div className="v2-settings__rows">
        <V2Row
          title="Pair mobile device"
          sub="Open the CachiBot mobile app and scan the QR code"
          action={
            <button
              type="button"
              className="v2-settings__action"
              disabled={loading}
              onClick={() => void fetchToken()}
            >
              {loading ? <Spinner size="sm" delayMs={200} /> : 'Pair'}
            </button>
          }
        />
        {firewall?.needed && !firewall.enabled && (
          <V2Row
            title="LAN access blocked"
            sub={`Windows Firewall is blocking connections on port ${firewall.port}`}
            action={
              <button
                type="button"
                className="v2-settings__action"
                disabled={firewallLoading}
                onClick={() => void handleEnableFirewall()}
              >
                {firewallLoading ? <Spinner size="sm" delayMs={200} /> : 'Allow'}
              </button>
            }
          />
        )}
      </div>

      {showQr && pairData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60" onClick={() => setShowQr(false)}>
          <div className="bg-white rounded-xl p-6 max-w-sm w-full mx-4 shadow-2xl" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-gray-900">Scan QR Code</h3>
              <button onClick={() => setShowQr(false)} className="p-1 rounded hover:bg-gray-100">
                <X className="h-4 w-4 text-gray-500" />
              </button>
            </div>
            <p className="text-sm text-gray-600 mb-4">
              Open the CachiBot mobile app, tap &quot;Scan QR Code&quot; on the login screen, and point your camera at this code.
            </p>
            <div className="flex justify-center p-4 bg-gray-50 rounded-lg mb-4 border border-gray-200">
              <QrCodeDisplay value={qrValue} size={220} />
            </div>
            <div className="flex items-center justify-center gap-2 text-sm text-gray-500">
              <Timer className="h-4 w-4" />
              <span>Expires in {countdown}s</span>
            </div>
          </div>
        </div>
      )}
    </>
  )
}

function QrCodeDisplay({ value, size }: { value: string; size: number }) {
  const [dataUrl, setDataUrl] = useState<string | null>(null)

  useEffect(() => {
    QRCode.toDataURL(value, {
      width: size,
      margin: 2,
      color: { dark: '#000000', light: '#ffffff' },
    })
      .then(setDataUrl)
      .catch(() => {})
  }, [value, size])

  if (!dataUrl) {
    return (
      <div style={{ width: size, height: size }} className="flex items-center justify-center">
        <Spinner size="lg" delayMs={200} />
      </div>
    )
  }

  return <img src={dataUrl} width={size} height={size} alt="QR Code" className="rounded" />
}

// =============================================================================
// VELA (local Vela companion integration)
// =============================================================================

// Vela polls our loopback server every few seconds when connected; an answer
// older than this reads as "not connected yet".
const VELA_FRESH_MS = 60_000

function VelaSection() {
  const { user } = useAuthStore()
  const isAdmin = user?.role === 'admin'
  const { status, failed } = useVelaCompanionStatus()

  // Feature-detect: no local Vela (or an unreachable server) means no section
  // at all — never a disabled placeholder. Admin-only by design.
  if (!isAdmin || failed) return null
  if (!status || !status.detected) return null

  const lastSeenMs = status.lastSeenAt ? parseApiDate(status.lastSeenAt).getTime() : null
  const connected = lastSeenMs !== null && Date.now() - lastSeenMs <= VELA_FRESH_MS

  let line: string
  if (!status.enabled) {
    line = 'Turned off'
  } else if (connected) {
    line = 'Connected to Vela'
  } else if (status.registered) {
    line = 'Waiting for you to connect CachiBot in Vela > Marketplace > Found on this computer'
  } else {
    line = 'Starting…'
  }

  const handleToggle = async (checked: boolean) => {
    try {
      await updateVelaCompanionSettings({ enabled: checked })
    } catch {
      toast.error('Failed to update the Vela setting')
    }
  }

  return (
    <>
      <h3 className="v2-settings__sub">Vela</h3>
      <V2Toggle
        title="Show CachiBot on your Vela desk"
        sub={line}
        checked={status.enabled}
        onChange={(v) => void handleToggle(v)}
      />
    </>
  )
}

// =============================================================================
// APPEARANCE
// =============================================================================

function AppearanceSection() {
  const {
    theme,
    setTheme,
    accentColor,
    setAccentColor,
    customHex,
    setCustomHex,
    sidebarCollapsed,
    setSidebarCollapsed,
  } = useUIStore()

  const themeOptions: { value: Theme; label: string; icon: typeof Sun }[] = [
    { value: 'light', label: 'Light', icon: Sun },
    { value: 'dark', label: 'Dark', icon: Moon },
    { value: 'system', label: 'System', icon: Monitor },
  ]

  const colorOptions = Object.entries(accentColors) as [PresetColor, (typeof accentColors)[PresetColor]][]
  const customPalette = generatePalette(customHex)

  return (
    <V2Section id="appearance" title="Appearance">
      {/* Theme segmented control (exact geometry from the design) */}
      <div role="radiogroup" aria-label="Theme" className="v2-settings__segmented">
        {themeOptions.map((option) => (
          <button
            key={option.value}
            type="button"
            role="radio"
            aria-checked={theme === option.value}
            className="v2-settings__segment"
            onClick={() => setTheme(option.value)}
          >
            {option.label}
          </button>
        ))}
      </div>

      <V2Field label="Accent color">
        <div className="v2-settings__colors">
          {colorOptions.map(([value, { palette }]) => (
            <button
              key={value}
              type="button"
              onClick={() => setAccentColor(value)}
              className={cn(
                'settings-color-circle',
                accentColor === value && 'settings-color-circle--active'
              )}
              style={{
                backgroundColor: palette[500],
                boxShadow:
                  accentColor === value
                    ? `0 0 0 2px var(--v2-bg-main), 0 0 0 4px ${palette[500]}`
                    : undefined,
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
              boxShadow:
                accentColor === 'custom'
                  ? `0 0 0 2px var(--v2-bg-main), 0 0 0 4px ${customPalette[500]}`
                  : undefined,
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
      </V2Field>

      <V2Toggle
        title="Collapse sidebar by default"
        sub="Start with the sidebar in compact mode"
        checked={sidebarCollapsed}
        onChange={setSidebarCollapsed}
      />
    </V2Section>
  )
}

// =============================================================================
// MODELS
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

function ModelsSection() {
  const {
    groups,
    embeddingGroups,
    defaultModel,
    defaultEmbeddingModel,
    defaultUtilityModel,
    loading,
    updateDefaultModel,
    updateDefaultEmbeddingModel,
    updateDefaultUtilityModel,
    refresh,
  } = useModelsStore()
  const [search, setSearch] = useState('')
  const [expanded, setExpanded] = useState<Record<string, boolean>>({})

  useEffect(() => {
    refresh()
  }, [refresh])

  const handleDefaultModelChange = async (model: string) => {
    if (!model) return
    await updateDefaultModel(model)
    // Mirror the choice into the server config (same as the quick settings)
    try {
      await updateConfig({ model })
    } catch {
      console.error('Failed to update model in config')
    }
  }

  const handleEmbeddingModelChange = async (model: string) => {
    if (!model) return
    await updateDefaultEmbeddingModel(model)
    toast.success('Embedding model updated')
  }

  const handleUtilityModelChange = async (model: string) => {
    await updateDefaultUtilityModel(model)
    toast.success('Utility model updated')
  }

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

  const isSearching = search.length > 0

  return (
    <V2Section
      id="models"
      title="Models"
      desc="The default every bot uses unless its own settings say otherwise."
    >
      <V2Field label="Default model">
        <div className="v2-settings__box">
          <ModelSelect
            value={defaultModel}
            onChange={(m) => void handleDefaultModelChange(m)}
            placeholder="Pick a model"
            className="w-full"
          />
        </div>
      </V2Field>

      <V2Field label="Utility model" hint="Fast/cheap model for background tasks. Falls back to the default model if not set.">
        <div className="v2-settings__box">
          <ModelSelect
            value={defaultUtilityModel}
            onChange={(m) => void handleUtilityModelChange(m)}
            placeholder="Falls back to the default model"
            className="w-full"
            filter={(m) => !m.supports_image_generation && !m.supports_audio}
          />
        </div>
      </V2Field>

      <V2Field label="Embedding model" hint="Used for knowledge base indexing. Changing it requires re-indexing existing documents.">
        <div className="v2-settings__box">
          <ModelSelect
            value={defaultEmbeddingModel}
            onChange={(m) => void handleEmbeddingModelChange(m)}
            placeholder="Pick an embedding model"
            className="w-full"
            groups={embeddingGroups}
            filter={(m) => m.supports_embedding}
          />
        </div>
      </V2Field>

      <ProvidersList />

      <h3 className="v2-settings__sub">Available models</h3>
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
      <p className="text-xs text-[var(--color-text-secondary)]">
        {isSearching
          ? `${filteredTotal} result${filteredTotal !== 1 ? 's' : ''} across ${providerCount} provider${providerCount !== 1 ? 's' : ''}`
          : `${totalModels} model${totalModels !== 1 ? 's' : ''} from ${providerCount} provider${providerCount !== 1 ? 's' : ''}`}
      </p>
      {loading && (
        <div className="flex items-center justify-center gap-2 py-6 text-[var(--color-text-secondary)]">
          <Spinner size="sm" delayMs={200} />
          Discovering models...
        </div>
      )}
      {!loading && totalModels === 0 && (
        <div className="text-center py-6">
          <Brain className="h-7 w-7 text-[var(--color-text-tertiary)] mx-auto mb-2" />
          <p className="text-sm text-[var(--color-text-secondary)]">No models available</p>
          <p className="text-xs text-[var(--color-text-tertiary)] mt-1">
            Configure API keys to discover models.
          </p>
        </div>
      )}
      {!loading && totalModels > 0 && filteredTotal === 0 && (
        <div className="text-center py-6 text-[var(--color-text-secondary)] text-sm">
          No models match your search
        </div>
      )}
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
                <div key={provider} className="model-provider">
                  <button onClick={() => toggleProvider(provider)} className="model-provider__header">
                    <ChevronRight
                      className={cn(
                        'h-3.5 w-3.5 text-[var(--color-text-secondary)] transition-transform',
                        isOpen && 'rotate-90'
                      )}
                    />
                    <span className={cn('h-2 w-2 rounded-full shrink-0', dotColor)} />
                    <span className="model-provider__label">{label}</span>
                    <span className="model-provider__count">{modelList.length}</span>
                  </button>
                  {isOpen && (
                    <div className="model-provider__list">
                      {modelList.map((m) => {
                        const isDefault = m.id === defaultModel
                        return (
                          <div
                            key={m.id}
                            className={cn('model-row group', isDefault && 'model-row--default')}
                          >
                            <div className="flex-1 min-w-0">
                              <div className="flex items-center gap-1.5">
                                <span className="model-row__name truncate" title={m.id}>
                                  {m.id}
                                </span>
                                {isDefault && <Star className="h-3 w-3 shrink-0 fill-current text-accent-500" />}
                                {m.is_reasoning && <Sparkles className="h-3 w-3 shrink-0 text-purple-400" />}
                              </div>
                              <div className="model-row__meta">
                                <span>{formatModelNum(m.context_window)} ctx</span>
                                {m.pricing && (
                                  <>
                                    <span className="model-row__separator">/</span>
                                    <span className="model-row__price-in">{formatModelPrice(m.pricing.input)}</span>
                                    <span className="model-row__separator">&middot;</span>
                                    <span className="model-row__price-out">{formatModelPrice(m.pricing.output)}</span>
                                  </>
                                )}
                              </div>
                            </div>
                            {!isDefault && (
                              <button
                                onClick={() => void handleDefaultModelChange(m.id)}
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
    </V2Section>
  )
}

// =============================================================================
// PROVIDERS (Models section) — design rows: name + state, Add key / Change
// =============================================================================

const CLOUD_PROVIDERS = new Set([
  'cachibot', 'openai', 'claude', 'google', 'groq', 'grok',
  'openrouter', 'moonshot', 'zai', 'modelscope', 'azure',
  'stability', 'elevenlabs',
])

const PROVIDER_LABELS: Record<string, string> = {
  cachibot: 'CachiBot.ai',
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

interface ProviderState {
  editing: string | null // provider currently being added/replaced
  value: string
  visible: boolean
  saving: boolean
  showExtras: boolean
  extraEditing: string | null // "providerName:envKey"
  extraValue: string
  extraVisible: boolean
  extraSaving: boolean
}

function ProvidersList() {
  const { providers, loading, refresh, update, remove, updateKey, removeKey } = useProvidersStore()
  const { groups: modelGroups, refresh: refreshModels } = useModelsStore()
  const [state, setState] = useState<ProviderState>({
    editing: null,
    value: '',
    visible: false,
    saving: false,
    showExtras: false,
    extraEditing: null,
    extraValue: '',
    extraVisible: false,
    extraSaving: false,
  })

  useEffect(() => {
    refresh()
  }, [refresh])

  const cloudProviders = providers
    .filter((p) => CLOUD_PROVIDERS.has(p.name))
    .sort((a, b) => (a.name === 'cachibot' ? -1 : b.name === 'cachibot' ? 1 : 0))
  const localProviders = providers.filter((p) => !CLOUD_PROVIDERS.has(p.name))

  const beginEdit = (name: string, isConfigured: boolean) => {
    setState((s) => ({ ...s, editing: name, value: '', visible: false }))
    void isConfigured
  }

  const cancelEdit = () => setState((s) => ({ ...s, editing: null, value: '', visible: false }))

  const handleSave = async (name: string) => {
    if (!state.value.trim()) return
    setState((s) => ({ ...s, saving: true }))
    try {
      await update(name, state.value.trim())
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key saved`)
      cancelEdit()
    } catch {
      toast.error(`Failed to save ${PROVIDER_LABELS[name] || name} key`)
    } finally {
      setState((s) => ({ ...s, saving: false }))
    }
  }

  const handleDelete = async (name: string) => {
    try {
      await remove(name)
      refreshModels()
      toast.success(`${PROVIDER_LABELS[name] || name} key removed`)
    } catch {
      toast.error(`Failed to remove ${PROVIDER_LABELS[name] || name} key`)
    }
  }

  const extraKey = (providerName: string, envKey: string) => `${providerName}:${envKey}`

  const beginExtraEdit = (providerName: string, envKey: string) =>
    setState((s) => ({ ...s, extraEditing: extraKey(providerName, envKey), extraValue: '', extraVisible: false }))

  const cancelExtraEdit = () =>
    setState((s) => ({ ...s, extraEditing: null, extraValue: '', extraVisible: false }))

  const handleExtraSave = async (providerName: string, ek: { env_key: string }) => {
    if (!state.extraValue.trim()) return
    setState((s) => ({ ...s, extraSaving: true }))
    try {
      await updateKey(providerName, ek.env_key, state.extraValue.trim())
      toast.success(`${ek.env_key} saved`)
      cancelExtraEdit()
    } catch {
      toast.error(`Failed to save ${ek.env_key}`)
    } finally {
      setState((s) => ({ ...s, extraSaving: false }))
    }
  }

  const handleExtraDelete = async (providerName: string, envKey: string) => {
    try {
      await removeKey(providerName, envKey)
      toast.success(`${envKey} removed`)
    } catch {
      toast.error(`Failed to remove ${envKey}`)
    }
  }

  if (loading && providers.length === 0) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="lg" />
      </div>
    )
  }

  const renderProvider = (provider: (typeof providers)[0]) => {
    const label = PROVIDER_LABELS[provider.name] || provider.name
    const isEndpoint = provider.type === 'endpoint'
    const isCachibot = provider.name === 'cachibot'
    const isEditing = state.editing === provider.name
    const hasExtras = !!provider.extra_keys && provider.extra_keys.length > 0
    const configuredExtras = hasExtras ? provider.extra_keys.filter((ek) => ek.configured).length : 0
    const modelCount = modelGroups[provider.name]?.length ?? null

    const subtitle = (() => {
      const parts: string[] = []
      if (isEndpoint) {
        parts.push(provider.configured ? 'Endpoint set' : 'No endpoint')
      } else {
        parts.push(provider.configured ? 'Key added' : 'No key')
      }
      if (isEndpoint && provider.configured && modelCount != null && modelCount > 0) {
        parts.push(`${modelCount} model${modelCount !== 1 ? 's' : ''}`)
      }
      if (hasExtras) parts.push(`${configuredExtras}/${provider.extra_keys.length} extra keys`)
      return parts.join(' · ')
    })()

    return (
      <div key={provider.name} className="v2-settings__row" style={{ flexWrap: 'wrap' }}>
        <span className="v2-settings__row-main">
          <span className={cn('v2-settings__row-title', !provider.configured && 'text-[var(--v2-text-secondary)]')}>
            {label}
            {isCachibot && (
              <>
                {' '}
                <a
                  href={provider.configured ? 'https://cachibot.ai/dashboard' : 'https://cachibot.ai/register'}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="v2-settings__action"
                  style={{ display: 'inline-flex', height: 22, verticalAlign: 'middle' }}
                >
                  {provider.configured ? 'Dashboard' : 'Get a key'} <ExternalLink className="h-2.5 w-2.5" />
                </a>
              </>
            )}
          </span>
          <span className="v2-settings__row-sub">{subtitle}</span>
        </span>

        {isEditing ? (
          <span className="v2-settings__edit">
            <input
              type={state.visible || isEndpoint ? 'text' : 'password'}
              value={state.value}
              onChange={(e) => setState((s) => ({ ...s, value: e.target.value }))}
              placeholder={isEndpoint ? 'Enter endpoint URL...' : 'Enter API key...'}
              className="v2-settings__input"
              autoFocus
            />
            {!isEndpoint && (
              <button
                type="button"
                className="v2-settings__action"
                title={state.visible ? 'Hide' : 'Show'}
                onClick={() => setState((s) => ({ ...s, visible: !s.visible }))}
              >
                {state.visible ? <EyeOff className="h-3.5 w-3.5" /> : <EyeIcon className="h-3.5 w-3.5" />}
              </button>
            )}
            <button
              type="button"
              className="v2-settings__action"
              disabled={!state.value.trim() || state.saving}
              onClick={() => void handleSave(provider.name)}
            >
              {state.saving ? <Spinner size="sm" delayMs={200} /> : 'Save'}
            </button>
            <button type="button" className="v2-settings__action" onClick={cancelEdit}>
              <X className="h-3.5 w-3.5" />
            </button>
          </span>
        ) : (
          <>
            {isEndpoint ? (
              <button type="button" className="v2-settings__action" onClick={() => beginEdit(provider.name, provider.configured)}>
                {provider.configured ? 'Change' : 'Add endpoint'}
              </button>
            ) : (
              <button type="button" className="v2-settings__action" onClick={() => beginEdit(provider.name, provider.configured)}>
                {provider.configured ? 'Change' : 'Add key'}
              </button>
            )}
            {provider.configured && (
              <button
                type="button"
                className="v2-settings__action"
                title="Remove key"
                onClick={() => void handleDelete(provider.name)}
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            )}
          </>
        )}

        {/* Extra keys (e.g. Azure deployment configuration) */}
        {hasExtras && !isEditing && (
          <div style={{ flexBasis: '100%' }}>
            <button
              type="button"
              className="v2-settings__action"
              onClick={() => setState((s) => ({ ...s, showExtras: !s.showExtras }))}
            >
              {state.showExtras ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
              Additional configuration
              <span className="v2-settings__row-sub" style={{ marginLeft: 4 }}>
                {configuredExtras}/{provider.extra_keys.length} set
              </span>
            </button>
            {state.showExtras && (
              <div className="space-y-3" style={{ padding: '8px 0 4px' }}>
                {provider.extra_keys.map((ek) => {
                  const ck = extraKey(provider.name, ek.env_key)
                  const isExtraEditing = state.extraEditing === ck
                  const isApiKey = ek.type === 'api_key'
                  return (
                    <div key={ek.env_key} className="provider-card__extra-field">
                      <div className="provider-card__extra-field-label">
                        <span className="text-sm font-medium text-[var(--color-text-primary)]">{ek.label}</span>
                        <code className="provider-card__extra-field-env">{ek.env_key}</code>
                        {ek.configured && !isExtraEditing && (
                          <span className="provider-card__badge provider-card__badge--active" style={{ marginLeft: 4 }}>
                            Set
                          </span>
                        )}
                      </div>
                      {isExtraEditing ? (
                        <div className="flex gap-2 items-center">
                          <input
                            type={state.extraVisible || !isApiKey ? 'text' : 'password'}
                            value={state.extraValue}
                            onChange={(e) => setState((s) => ({ ...s, extraValue: e.target.value }))}
                            placeholder={isApiKey ? 'Enter key...' : 'Enter value...'}
                            className="v2-settings__input"
                            autoFocus
                          />
                          {isApiKey && (
                            <button
                              type="button"
                              className="v2-settings__action"
                              title={state.extraVisible ? 'Hide' : 'Show'}
                              onClick={() => setState((s) => ({ ...s, extraVisible: !s.extraVisible }))}
                            >
                              {state.extraVisible ? <EyeOff className="h-3.5 w-3.5" /> : <EyeIcon className="h-3.5 w-3.5" />}
                            </button>
                          )}
                          <button
                            type="button"
                            className="v2-settings__action"
                            disabled={!state.extraValue.trim() || state.extraSaving}
                            onClick={() => void handleExtraSave(provider.name, ek)}
                          >
                            {state.extraSaving ? <Spinner size="sm" delayMs={200} /> : 'Save'}
                          </button>
                          <button type="button" className="v2-settings__action" onClick={cancelExtraEdit}>
                            <X className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      ) : (
                        <div className="flex gap-2 items-center">
                          <span className="provider-card__masked">
                            {ek.masked_value}
                          </span>
                          <button
                            type="button"
                            className="v2-settings__action"
                            title="Replace"
                            onClick={() => beginExtraEdit(provider.name, ek.env_key)}
                          >
                            <RefreshCw className="h-3.5 w-3.5" />
                          </button>
                          <button
                            type="button"
                            className="v2-settings__action"
                            title="Remove"
                            onClick={() => void handleExtraDelete(provider.name, ek.env_key)}
                          >
                            <Trash2 className="h-3.5 w-3.5" />
                          </button>
                        </div>
                      )}
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}
      </div>
    )
  }

  return (
    <>
      <h3 className="v2-settings__sub">Providers</h3>
      <div className="v2-settings__rows">
        {cloudProviders.map(renderProvider)}
        {localProviders.map(renderProvider)}
      </div>
    </>
  )
}

// =============================================================================
// DATA
// =============================================================================

function DataSection() {
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false)
  const [showTelemetryPreview, setShowTelemetryPreview] = useState(false)
  const [telemetryPayload, setTelemetryPayload] = useState<Record<string, unknown> | null>(null)
  const [showResetIdConfirm, setShowResetIdConfirm] = useState(false)
  const { status: telemetryStatus, refresh: refreshTelemetry } = useTelemetryStore()
  const { bots } = useBotStore()
  const [retentionDays, setRetentionDays] = useState<number | null>(null)
  const importRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    refreshTelemetry()
  }, [refreshTelemetry])

  // Real retention setting (same value the server's log retention enforces)
  useEffect(() => {
    let cancelled = false
    const firstBot = bots[0]
    if (!firstBot) return
    getExecutionStats(firstBot.id, '30d')
      .then((stats) => {
        if (!cancelled && typeof stats.retentionDays === 'number') setRetentionDays(stats.retentionDays)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [bots])

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

  /** Real restore of a file produced by Export (same localStorage keys). */
  const handleImportFile = async (file: File) => {
    try {
      const parsed = JSON.parse(await file.text()) as Record<string, unknown>
      const keys = ['bots', 'chats', 'jobs', 'tasks', 'connections', 'ui', 'usage'] as const
      let restored = 0
      for (const key of keys) {
        const value = parsed[key]
        if (typeof value === 'string') {
          localStorage.setItem(`cachibot-${key}`, value)
          restored++
        }
      }
      if (restored === 0) {
        toast.error('This file does not look like a CachiBot backup')
        return
      }
      toast.success(`Restored ${restored} data set${restored !== 1 ? 's' : ''} — reloading…`)
      setTimeout(() => window.location.reload(), 600)
    } catch {
      toast.error('Failed to read the backup file')
    }
  }

  const handleClearCache = async () => {
    try {
      if (window.electronAPI?.clearCache) {
        const result = await window.electronAPI.clearCache()
        if (result.success) {
          toast.success('Cache cleared')
        } else {
          toast.error(result.error || 'Failed to clear cache')
        }
      } else {
        const keys = Object.keys(localStorage).filter((k) => k.startsWith('cachibot_marketplace_cache_'))
        keys.forEach((k) => localStorage.removeItem(k))
        toast.success(`Cleared ${keys.length} cached entries`)
        window.location.reload()
      }
    } catch {
      toast.error('Failed to clear cache')
    }
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
    <V2Section id="data" title="Data">
      {retentionDays != null && (
        <>
          <h3 className="v2-settings__sub">Runs and logs</h3>
          <div className="v2-settings__rows">
            <V2Row title="Keep runs and logs" sub={`${retentionDays} days`} />
          </div>
        </>
      )}

      <h3 className="v2-settings__sub">Backups</h3>
      <div className="v2-settings__rows">
        <V2Row
          title="Export everything"
          sub="Download your bots, chats, jobs and settings as JSON"
          action={
            <button type="button" className="v2-settings__action" onClick={handleExport}>
              Export
            </button>
          }
        />
        <V2Row
          title="Import from backup"
          sub="Restore a previous export on this device"
          action={
            <button type="button" className="v2-settings__action" onClick={() => importRef.current?.click()}>
              Import
            </button>
          }
        />
        <input
          ref={importRef}
          type="file"
          accept="application/json,.json"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) void handleImportFile(file)
            e.target.value = ''
          }}
        />
      </div>

      <h3 className="v2-settings__sub">Privacy and telemetry</h3>
      <V2Toggle
        title="Anonymous analytics"
        sub="Send anonymous usage statistics to help improve CachiBot"
        checked={!!telemetryStatus?.enabled}
        onChange={() => void handleToggleTelemetry()}
      />
      <div className="v2-settings__rows">
        <V2Row
          title="View telemetry report"
          sub="See exactly what data would be sent"
          action={
            <button type="button" className="v2-settings__action" onClick={() => void handleViewTelemetryReport()}>
              View
            </button>
          }
        />
        <V2Row
          title="Reset install ID"
          sub={
            <>
              Generate a new anonymous identifier
              {telemetryStatus?.install_id && (
                <span className="ml-1 font-mono text-xs">({telemetryStatus.install_id.slice(0, 8)}…)</span>
              )}
            </>
          }
          action={
            <button type="button" className="v2-settings__action" onClick={() => setShowResetIdConfirm(true)}>
              Reset
            </button>
          }
        />
        {telemetryStatus?.last_sent && (
          <V2Row title="Last sent" sub={parseApiDate(telemetryStatus.last_sent).toLocaleString()} />
        )}
        <div style={{ padding: '6px 0' }}>
          <a
            href="https://cachibot.ai/telemetry"
            target="_blank"
            rel="noopener noreferrer"
            className="v2-settings__action"
          >
            Learn more about what we collect
            <ExternalLink className="h-3 w-3" />
          </a>
        </div>
      </div>

      <h3 className="v2-settings__sub">Bot data</h3>
      <BotDataManager />

      <h3 className="v2-settings__sub">Cache</h3>
      <div className="v2-settings__rows">
        <V2Row
          title="Clear cache"
          sub="Remove cached responses and temporary data"
          action={
            <button type="button" className="v2-settings__action" onClick={() => void handleClearCache()}>
              Clear
            </button>
          }
        />
      </div>

      <h3 className="v2-settings__sub">Danger zone</h3>
      <div className="v2-settings__rows">
        <V2Row
          title="Delete all data"
          sub="Permanently delete local bots, chats, jobs, tasks and usage. Can't be undone."
          danger
          action={
            <button type="button" className="v2-settings__action" onClick={() => setShowDeleteConfirm(true)}>
              Delete
            </button>
          }
        />
      </div>

      {/* Telemetry preview modal */}
      {showTelemetryPreview && telemetryPayload && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '32rem' }}>
            <div className="mb-4 flex items-center justify-between">
              <h2 className="settings-modal__heading">Telemetry Report Preview</h2>
              <button onClick={() => setShowTelemetryPreview(false)} className="settings-modal__close-btn">
                <X className="h-5 w-5" />
              </button>
            </div>
            <pre className="settings-modal__pre">{JSON.stringify(telemetryPayload, null, 2)}</pre>
            <div className="settings-modal__footer">
              <button onClick={() => setShowTelemetryPreview(false)} className="settings-modal__cancel-btn">
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
              This will generate a new anonymous identifier. Your previous telemetry data will no longer be
              associated with this installation.
            </p>
            <div className="settings-modal__footer">
              <button onClick={() => setShowResetIdConfirm(false)} className="settings-modal__cancel-btn">
                Cancel
              </button>
              <button onClick={() => void handleResetId()} className="settings-modal__confirm-btn">
                Reset ID
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation modal */}
      {showDeleteConfirm && (
        <div className="settings-modal">
          <div className="settings-modal__panel" style={{ maxWidth: '28rem' }}>
            <div className="mb-4 flex items-center gap-3 text-red-400">
              <AlertTriangle className="h-6 w-6" />
              <h2 className="settings-modal__heading">Delete All Data</h2>
            </div>
            <p className="mb-6 settings-modal__body-text">
              Are you sure you want to delete all your local data? This will remove bots, chats, jobs, tasks,
              connections, and usage stored in this browser.
            </p>
            <div className="settings-modal__footer">
              <button onClick={() => setShowDeleteConfirm(false)} className="settings-modal__cancel-btn">
                Cancel
              </button>
              <button onClick={handleClearAll} className="settings-modal__confirm-btn--danger">
                Delete Everything
              </button>
            </div>
          </div>
        </div>
      )}
    </V2Section>
  )
}

// =============================================================================
// BOT DATA MANAGER (kept from the previous settings; inner markup unchanged)
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

  const botDataInfos = useMemo((): BotDataInfo[] => {
    return bots.map((bot) => {
      const allBotChats = chats.filter((c) => c.botId === bot.id)
      const localChats = allBotChats.filter((c) => !c.platform)
      const platformChats = allBotChats.filter((c) => c.platform)

      const localMessagesCount = localChats.reduce((acc, chat) => acc + (messages[chat.id]?.length || 0), 0)
      const botJobs = jobs.filter((j) => j.botId === bot.id)
      const botTasks = tasks.filter((t) => t.botId === bot.id)
      const hasUsageData = !!stats.byBot[bot.id]

      return {
        botId: bot.id,
        botName: bot.name,
        botColor: bot.color || '#22c55e',
        chatsCount: localChats.length,
        messagesCount: localMessagesCount,
        jobsCount: botJobs.length,
        tasksCount: botTasks.length,
        hasUsageData,
        platformChatsCount: platformChats.length,
      }
    })
  }, [bots, chats, messages, jobs, tasks, stats.byBot])

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

  const clearSelectionForBot = (botId: string) => {
    setSelectedItems((prev) => {
      const next = new Map(prev)
      next.delete(botId)
      return next
    })
  }

  const hasSelection = selectedItems.size > 0

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

  const handleClearSelected = async () => {
    setClearing(true)

    const chatStore = useChatStore.getState()
    const jobStore = useJobStore.getState()
    const taskStore = useTaskStore.getState()

    for (const [botId, categories] of selectedItems) {
      if (categories.has('chats')) {
        const localOnlyChats = chats.filter((c) => c.botId === botId && !c.platform)
        localOnlyChats.forEach((chat) => {
          chatStore.deleteChat(chat.id)
        })
      }

      if (categories.has('jobs')) {
        const botJobs = jobs.filter((j) => j.botId === botId)
        botJobs.forEach((job) => {
          jobStore.deleteJob(job.id)
        })
      }

      if (categories.has('tasks')) {
        const botTasks = tasks.filter((t) => t.botId === botId)
        botTasks.forEach((task) => {
          taskStore.deleteTask(task.id)
        })
      }

      if (categories.has('usage')) {
        clearBotStats(botId)
      }

      if (categories.has('platform')) {
        const localPlatformChats = chats.filter((c) => c.botId === botId && c.platform)
        localPlatformChats.forEach((chat) => {
          chatStore.deleteChat(chat.id)
        })

        try {
          await clearBotPlatformData(botId)
        } catch {
          console.error('Failed to clear platform data')
          toast.error('Failed to clear platform data for bot')
        }
      }
    }

    await new Promise((resolve) => setTimeout(resolve, 300))

    setClearing(false)
    setShowConfirmModal(false)
    setSelectedItems(new Map())
    toast.success('Selected data cleared successfully')
  }

  const categoryConfig: Record<DataCategory, { icon: typeof MessageSquare; label: string; color: string }> = {
    chats: { icon: MessageSquare, label: 'Local Chats', color: 'text-blue-400' },
    jobs: { icon: Briefcase, label: 'Jobs', color: 'text-purple-400' },
    tasks: { icon: CheckSquare, label: 'Tasks', color: 'text-green-400' },
    usage: { icon: BarChart3, label: 'Usage Stats', color: 'text-amber-400' },
    platform: { icon: MessageSquare, label: 'Platform Messages', color: 'text-cyan-400' },
  }

  return (
    <>
      <div className="space-y-2">
        {botDataInfos.length === 0 && (
          <p className="text-sm text-[var(--color-text-secondary)]">No bots yet.</p>
        )}
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
            <div key={info.botId} className="bot-data-card">
              <button onClick={() => toggleBot(info.botId)} className="bot-data-card__header">
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
                  <span className="bot-data-card__selected-badge">{botSelected.size} selected</span>
                )}
              </button>

              {isExpanded && (
                <div className="bot-data-card__content">
                  {!hasData ? (
                    <p className="text-sm text-[var(--color-text-secondary)] text-center py-2">
                      No data to clear for this bot
                    </p>
                  ) : (
                    <>
                      <div className="bot-data-card__quick-actions">
                        <button onClick={() => selectAllForBot(info.botId, info)} className="bot-data-card__quick-btn">
                          Select all
                        </button>
                        <span className="bot-data-card__separator">&middot;</span>
                        <button onClick={() => clearSelectionForBot(info.botId)} className="bot-data-card__quick-btn">
                          Clear selection
                        </button>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
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
                        {info.jobsCount > 0 && (
                          <DataCategoryItem
                            category="jobs"
                            config={categoryConfig.jobs}
                            count={info.jobsCount}
                            selected={botSelected?.has('jobs') || false}
                            onToggle={() => toggleCategory(info.botId, 'jobs')}
                          />
                        )}
                        {info.tasksCount > 0 && (
                          <DataCategoryItem
                            category="tasks"
                            config={categoryConfig.tasks}
                            count={info.tasksCount}
                            selected={botSelected?.has('tasks') || false}
                            onToggle={() => toggleCategory(info.botId, 'tasks')}
                          />
                        )}
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

      {hasSelection && (
        <div className="settings-delete-bar">
          <div className="text-sm">
            <span className="settings-delete-bar__count">{getTotalSelectedItems()}</span>
            <span className="settings-delete-bar__label"> items selected for deletion</span>
          </div>
          <button onClick={() => setShowConfirmModal(true)} className="settings-modal__confirm-btn--danger flex items-center gap-2">
            <Trash2 className="h-4 w-4" />
            Clear Selected
          </button>
        </div>
      )}

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
              <button onClick={() => setShowConfirmModal(false)} disabled={clearing} className="settings-modal__cancel-btn">
                Cancel
              </button>
              <button onClick={() => void handleClearSelected()} disabled={clearing} className="settings-modal__confirm-btn--danger flex items-center gap-2">
                {clearing ? (
                  <>
                    <Spinner size="sm" delayMs={200} />
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
    </>
  )
}

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
    <button onClick={onToggle} className={cn('data-category', selected && 'data-category--selected')}>
      <div className={cn('data-category__icon-box', selected && 'data-category__icon-box--selected')}>
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
// PEOPLE (Manager+; the badge matches the admin-only parts)
// =============================================================================

function PeopleSection({ isAdmin }: { isAdmin: boolean }) {
  const [userCount, setUserCount] = useState<number | null>(null)
  const [groupCount, setGroupCount] = useState<number | null>(null)
  const [manageGroups, setManageGroups] = useState(false)

  useEffect(() => {
    let cancelled = false
    if (isAdmin) {
      listUsers(1, 0)
        .then((res) => { if (!cancelled) setUserCount(res.total) })
        .catch(() => {})
    }
    listGroups()
      .then((groups) => { if (!cancelled) setGroupCount(groups.length) })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [isAdmin])

  return (
    <V2Section id="people" title="People" badge={isAdmin ? 'Admins' : undefined}>
      <div className="v2-settings__rows">
        {isAdmin && (
          <V2Row
            title="Users"
            sub={userCount != null ? `${userCount} ${userCount === 1 ? 'person' : 'people'}` : 'User accounts and roles'}
            action={
              <Link to="/users" className="v2-settings__action">
                Manage
              </Link>
            }
          />
        )}
        <V2Row
          title="Groups"
          sub={
            groupCount != null
              ? `${groupCount} ${groupCount === 1 ? 'group' : 'groups'} · who can use which bots`
              : 'Who can use which bots'
          }
          action={
            <button type="button" className="v2-settings__action" onClick={() => setManageGroups((v) => !v)}>
              {manageGroups ? 'Close' : 'Manage'}
            </button>
          }
        />
      </div>
      {manageGroups && <GroupsManager />}
    </V2Section>
  )
}

function GroupsManager() {
  const { user: currentUser } = useAuthStore()
  const [groups, setGroups] = useState<Group[]>([])
  const [loading, setLoading] = useState(true)

  const [showCreateModal, setShowCreateModal] = useState(false)
  const [createForm, setCreateForm] = useState({ name: '', description: '' })
  const [creating, setCreating] = useState(false)

  const [activeGroupId, setActiveGroupId] = useState<string | null>(null)
  const [activeGroup, setActiveGroup] = useState<GroupWithMembers | null>(null)
  const [loadingDetail, setLoadingDetail] = useState(false)

  const [showAddMemberModal, setShowAddMemberModal] = useState(false)
  const [addMemberForm, setAddMemberForm] = useState({ userId: '', role: 'member' as GroupRole })
  const [addingMember, setAddingMember] = useState(false)

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
      toast.error(err instanceof Error ? err.message : 'Failed to create group')
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
      toast.error(err instanceof Error ? err.message : 'Failed to delete group')
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
      setGroups(groups.map((g) => (g.id === activeGroupId ? { ...g, member_count: g.member_count + 1 } : g)))
      setShowAddMemberModal(false)
      setAddMemberForm({ userId: '', role: 'member' })
      toast.success('Member added successfully')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to add member')
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
      setGroups(groups.map((g) => (g.id === activeGroupId ? { ...g, member_count: g.member_count - 1 } : g)))
      toast.success('Member removed')
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to remove member')
    }
  }

  const isGroupOwnerOrAdmin = (group: Group): boolean => {
    if (!currentUser) return false
    if (currentUser.role === 'admin') return true
    return group.created_by === currentUser.id
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <Spinner size="lg" />
      </div>
    )
  }

  return (
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

      <div className="settings-table">
        <div className="settings-table__header-row grid grid-cols-[1fr_1fr_80px_48px] gap-4 px-4 py-2.5">
          <div>Name</div>
          <div>Description</div>
          <div>Members</div>
          <div></div>
        </div>

        {groups.length === 0 ? (
          <div className="settings-table__empty py-8">No groups found</div>
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
                {group.description || '—'}
              </div>
              <div>{group.member_count}</div>
              <div className="relative" onClick={(e) => e.stopPropagation()}>
                <button onClick={() => setMenuOpen(menuOpen === group.id ? null : group.id)} className="settings-btn-ghost p-1.5">
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
                        onClick={() => void handleDeleteGroup(group.id)}
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

      {activeGroupId && (
        <div className="border border-[var(--color-border-primary)] rounded-xl p-4">
          {loadingDetail ? (
            <div className="flex items-center justify-center py-6">
              <Spinner size="lg" />
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
                  <button onClick={() => setActiveGroupId(null)} className="settings-btn-ghost p-1">
                    <X className="h-4 w-4 text-[var(--color-text-secondary)]" />
                  </button>
                </div>
              </div>
              <div className="settings-table">
                {activeGroup.members.length === 0 ? (
                  <div className="settings-table__empty py-6">No members yet</div>
                ) : (
                  activeGroup.members.map((member: GroupMember) => (
                    <div key={member.user_id} className="member-row">
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
                            {member.user_id === currentUser?.id && <span className="member-row__you-tag">You</span>}
                          </div>
                          <div className="member-row__email truncate">{member.email}</div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2 shrink-0">
                        <span className={cn('role-badge', member.role === 'owner' ? 'role-badge--owner' : 'role-badge--default')}>
                          {member.role}
                        </span>
                        {member.user_id !== currentUser?.id && (
                          <button onClick={() => void handleRemoveMember(member.user_id)} className="member-row__remove-btn" title="Remove member">
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
        </div>
      )}

      {showCreateModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Create New Group</h2>
            <form onSubmit={handleCreateGroup} className="space-y-4">
              <div>
                <label className="settings-modal__label">Name</label>
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
                <label className="settings-modal__label">Description</label>
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
                <Button type="submit" className="flex-1" pending={creating}>
                  Create Group
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {showAddMemberModal && (
        <div className="settings-modal">
          <div className="settings-modal__panel--sm mx-4">
            <h2 className="settings-modal__heading mb-4">Add Member</h2>
            <form onSubmit={handleAddMember} className="space-y-4">
              <div>
                <label className="settings-modal__label">User ID</label>
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
                <label className="settings-modal__label">Role</label>
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
                <Button type="submit" className="flex-1" pending={addingMember}>
                  Add Member
                </Button>
              </div>
            </form>
          </div>
        </div>
      )}

      {menuOpen && <div className="fixed inset-0 z-10" onClick={() => setMenuOpen(null)} />}
    </div>
  )
}

// =============================================================================
// ADVANCED
// =============================================================================

function AdvancedSection({ isAdmin }: { isAdmin: boolean }) {
  const { config, updateConfig: updateLocalConfig } = useConfigStore()
  const navigate = useNavigate()

  // Server-backed agent settings (PUT /api/config — same calls the quick
  // settings dialog makes). Hidden until the config loads.
  const handleApproveActions = async (value: boolean) => {
    updateLocalConfig({ approveActions: value })
    try {
      await updateConfig({ approve_actions: value })
    } catch {
      toast.error('Failed to update setting')
    }
  }

  const handleTemperature = async (value: number) => {
    updateLocalConfig({ temperature: value })
    try {
      await updateConfig({ temperature: value })
    } catch {
      toast.error('Failed to update setting')
    }
  }

  const handleMaxIterations = async (value: number) => {
    updateLocalConfig({ maxIterations: value })
    try {
      await updateConfig({ max_iterations: value })
    } catch {
      toast.error('Failed to update setting')
    }
  }

  return (
    <V2Section id="advanced" title="Advanced">
      <div className="v2-settings__rows">
        {isAdmin && (
          <V2Row
            title={
              <>
                Activity log <span className="v2-settings__badge">Admins</span>
              </>
            }
            sub="Every tool and code run, across all bots"
            action={
              <button type="button" className="v2-settings__action" onClick={() => navigate('/admin/logs')}>
                Open
              </button>
            }
          />
        )}
        <V2Row title="Server" sub={window.location.host} />
      </div>

      {config && (
        <>
          <h3 className="v2-settings__sub">Agent</h3>
          <V2Toggle
            title="Require approval for actions"
            sub="Ask before executing potentially dangerous operations"
            checked={config.agent.approveActions}
            onChange={(v) => void handleApproveActions(v)}
          />
          <V2Field label={`Default temperature · ${config.agent.temperature}`}>
            <div className="v2-settings__range">
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={config.agent.temperature}
                onChange={(e) => void handleTemperature(Number(e.target.value))}
              />
            </div>
            <p className="v2-settings__hint">Controls randomness in responses (0 = deterministic, 1 = creative)</p>
          </V2Field>
          <V2Field label="Max iterations">
            <div className="v2-settings__box v2-settings__box--readonly">
              <input
                type="number"
                min={1}
                max={100}
                value={config.agent.maxIterations}
                onChange={(e) => {
                  const v = Number(e.target.value)
                  if (Number.isFinite(v) && v >= 1) void handleMaxIterations(v)
                }}
                className="v2-settings__input"
                style={{ border: 0, padding: 0, height: 30 }}
              />
            </div>
            <p className="v2-settings__hint">Maximum tool calls per conversation turn</p>
          </V2Field>
        </>
      )}

      <h3 className="v2-settings__sub">Keyboard shortcuts</h3>
      <div className="v2-settings__shortcuts">
        <ShortcutItem label="New chat" shortcut="Ctrl + N" />
        <ShortcutItem label="Toggle sidebar" shortcut="Ctrl + B" />
        <ShortcutItem label="Command palette" shortcut="Ctrl + K" />
        <ShortcutItem label="Settings" shortcut="Ctrl + ," />
        <ShortcutItem label="Send message" shortcut="Enter" />
        <ShortcutItem label="New line" shortcut="Shift + Enter" />
      </div>
    </V2Section>
  )
}

function ShortcutItem({ label, shortcut }: { label: string; shortcut: string }) {
  return (
    <div className="v2-settings__shortcut">
      <span>{label}</span>
      <kbd className="v2-settings__kbd">{shortcut}</kbd>
    </div>
  )
}

// =============================================================================
// ABOUT
// =============================================================================

function AboutSection() {
  const [healthInfo, setHealthInfo] = useState<HealthInfo | null>(null)

  useEffect(() => {
    checkHealth()
      .then(setHealthInfo)
      .catch(() => {})
  }, [])

  return (
    <V2Section id="about" title="About">
      <UpdatesRows healthInfo={healthInfo} />
      <div className="v2-settings__rows">
        <V2Row
          title="Source code"
          sub="github.com/jhd3197/CachiBot"
          action={
            <a href="https://github.com/jhd3197/CachiBot" target="_blank" rel="noopener noreferrer" className="v2-settings__action">
              Open
            </a>
          }
        />
        {healthInfo?.build && <V2Row title="Build" sub={healthInfo.build} />}
        {healthInfo?.python && <V2Row title="Python" sub={healthInfo.python} />}
        {healthInfo?.platform && <V2Row title="Platform" sub={healthInfo.platform} />}
      </div>
    </V2Section>
  )
}

function UpdatesRows({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const isElectron = window.electronAPI?.isDesktop || healthInfo?.desktop
  return isElectron ? (
    <ElectronUpdatesRows healthInfo={healthInfo} />
  ) : (
    <PipUpdatesRows healthInfo={healthInfo} />
  )
}

function ElectronUpdatesRows({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const [checking, setChecking] = useState(false)
  const showChecking = useDelayedFlag(checking)
  const [updateInfo, setUpdateInfo] = useState<UpdateCheckResult | null>(null)
  const [downloading, setDownloading] = useState(false)
  const [downloadProgress, setDownloadProgress] = useState<UpdateDownloadProgress | null>(null)
  const [downloaded, setDownloaded] = useState(false)
  const [updateError, setUpdateError] = useState<string | null>(null)

  const currentVersion = healthInfo?.version || window.electronAPI?.appVersion || '...'

  useEffect(() => {
    const api = window.electronAPI
    if (!api) return
    const cleanups = [
      api.onUpdateAvailable?.((info) => setUpdateInfo(info)),
      api.onUpdateProgress?.((progress) => setDownloadProgress(progress)),
      api.onUpdateDownloaded?.(() => {
        setDownloading(false)
        setDownloaded(true)
      }),
      api.onUpdateError?.((error) => {
        setUpdateError(error.message)
        setDownloading(false)
        setDownloaded(false)
      }),
    ]
    return () => cleanups.forEach((c) => c?.())
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

  const versionSub = updateInfo
    ? updateInfo.available
      ? `${currentVersion} · update available (v${updateInfo.version})`
      : `${currentVersion} · up to date`
    : `${currentVersion}`

  return (
    <>
      <div className="v2-settings__rows">
        <V2Row
          title="Version"
          sub={versionSub}
          action={
            downloaded ? (
              <button type="button" className="v2-settings__action" onClick={() => window.electronAPI?.installUpdate()}>
                Restart &amp; install
              </button>
            ) : downloading ? (
              <span className="v2-settings__action" aria-busy="true">
                {downloadProgress ? `${Math.round(downloadProgress.percent)}%` : 'Downloading…'}
              </span>
            ) : (
              <button
                type="button"
                className="v2-settings__action"
                disabled={checking}
                aria-busy={checking || undefined}
                onClick={() => void handleCheck()}
              >
                {showChecking ? <Spinner size="sm" /> : 'Check again'}
              </button>
            )
          }
        />
        {updateError && <V2Row title="Last error" sub={updateError} />}
      </div>
      {updateInfo?.available && !downloaded && !downloading && (
        <button type="button" className="v2-btn v2-btn--primary" onClick={() => void handleDownload()}>
          <Download className="h-4 w-4" />
          Download update
        </button>
      )}
    </>
  )
}

function PipUpdatesRows({ healthInfo }: { healthInfo: HealthInfo | null }) {
  const { checkResult, isChecking, checkForUpdate } = useUpdateStore()
  const showChecking = useDelayedFlag(isChecking)

  useEffect(() => {
    checkForUpdate()
  }, [checkForUpdate])

  const currentVersion = window.electronAPI?.appVersion || checkResult?.current_version || healthInfo?.version || '...'
  const latestStable = checkResult?.latest_stable
  const upToDate = !!latestStable && !checkResult?.update_available

  const versionSub = upToDate
    ? `${currentVersion} · up to date`
    : latestStable
      ? `${currentVersion} · v${latestStable} available`
      : currentVersion

  return (
    <div className="v2-settings__rows">
      <V2Row
        title="Version"
        sub={versionSub}
        action={
          <button
            type="button"
            className="v2-settings__action"
            disabled={isChecking}
            aria-busy={isChecking || undefined}
            onClick={() => checkForUpdate(true)}
          >
            {showChecking ? <Spinner size="sm" /> : 'Check again'}
          </button>
        }
      />
    </div>
  )
}

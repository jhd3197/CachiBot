import { useEffect } from 'react'
import { useLocation, useParams, useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { BotRail } from './BotRail'
import { BotSidebar } from './BotSidebar'
import {
  ChatView,
  RoomsView,
  ToolsView,
  SettingsView,
  DashboardView,
  AppSettingsView,
  WorkView,
  VoiceView,
  AutomationsView,
  ScriptEditorView,
  GlobalLogView,
} from '../views'
import { CreateBotDialog } from '../dialogs/CreateBotDialog'
import { SettingsDialog } from '../dialogs/SettingsDialog'
import { ApprovalDialog } from '../dialogs/ApprovalDialog'
import { UpdateDialog } from '../dialogs/UpdateDialog'
import { UpdateBanner } from '../common/UpdateBanner'
import { useUpdateStore } from '../../stores/update'
import { useBotStore, useChatStore, useTaskStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { useProvidersStore } from '../../stores/providers'
import { useOnboardingStore } from '../../stores/onboarding'
import { getConfig } from '../../api/client'
import { cn } from '../../lib/utils'
import type { AppView, BotView, Config } from '../../types'

// Map URL paths to app views
const pathToAppView: Record<string, AppView> = {
  '/dashboard': 'dashboard',
  '/settings': 'settings',
  '/admin/logs': 'admin-logs',
}

// Check if path matches an app view (including sub-paths like /settings/users)
function getAppViewFromPath(pathname: string): AppView | null {
  // Exact match first
  if (pathToAppView[pathname]) {
    return pathToAppView[pathname]
  }
  // Check for sub-paths (e.g., /settings/users -> settings)
  for (const [path, view] of Object.entries(pathToAppView)) {
    if (pathname.startsWith(path + '/')) {
      return view
    }
  }
  return null
}

export function MainLayout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { botId: urlBotId, chatId: urlChatId, taskId: urlTaskId, roomId: urlRoomId } = useParams<{
    botId?: string
    chatId?: string
    taskId?: string
    roomId?: string
  }>()
  const { activeView, activeBotId, bots, setActiveBot, setActiveView } = useBotStore()
  const { activeChatId, chats, setActiveChat } = useChatStore()
  const { setActiveTask } = useTaskStore()
  const { activeRoomId, rooms, setActiveRoom } = useRoomStore()
  const { theme, accentColor, customHex, mobileMenuOpen, setMobileMenuOpen } = useUIStore()
  const { setConfig } = useConfigStore()
  const { refresh: refreshModels } = useModelsStore()
  const { providers, refresh: refreshProviders } = useProvidersStore()
  const { hasCompletedOnboarding } = useOnboardingStore()

  // Derive appView from URL path
  const appView = getAppViewFromPath(location.pathname)

  // Parse view from URL path: /:botId/view or /:botId/view/:itemId
  const pathParts = location.pathname.split('/').filter(Boolean)
  const viewSegment = pathParts[1] // Second segment is the view (chats, jobs, tasks, tools, settings)

  const viewMap: Record<string, BotView> = {
    chats: 'chats',
    rooms: 'rooms',
    work: 'work',
    automations: 'automations',
    voice: 'voice',
    tools: 'tools',
    developer: 'developer',
    settings: 'settings',
  }
  const botView = viewSegment ? viewMap[viewSegment] : null

  // Redirect legacy URLs
  useEffect(() => {
    if (viewSegment === 'schedules' && urlBotId) {
      navigate(`/${urlBotId}/automations`, { replace: true })
    }
    if (viewSegment === 'tasks' && urlBotId) {
      useUIStore.getState().setWorkSection('quick-tasks')
      navigate(`/${urlBotId}/work`, { replace: true })
    }
  }, [viewSegment, urlBotId, navigate])

  // Sync URL to store state (runs only when URL-derived values change)
  useEffect(() => {
    // Sync bot from URL
    if (urlBotId && urlBotId !== activeBotId) {
      const botExists = bots.some((b) => b.id === urlBotId)
      if (botExists) {
        setActiveBot(urlBotId)
      } else {
        // Bot doesn't exist, redirect to home
        navigate('/', { replace: true })
        return
      }
    }

    // Sync view from URL
    if (botView) {
      setActiveView(botView)
    }

    // Sync chat ID from URL
    // Support both UUID and platform names (telegram, discord) in URLs
    if (urlChatId && urlChatId !== activeChatId) {
      let chat = chats.find((c) => c.id === urlChatId)

      // If not found by ID, try finding by platform name
      if (!chat && (urlChatId === 'telegram' || urlChatId === 'discord')) {
        chat = chats.find((c) => c.platform === urlChatId && c.botId === urlBotId)
      }

      if (chat && chat.botId === urlBotId) {
        setActiveChat(chat.id)
      }
    }

    // Sync room ID from URL
    if (urlRoomId && urlRoomId !== activeRoomId) {
      setActiveRoom(urlRoomId)
    }

    // Sync task ID from URL
    if (urlTaskId) {
      setActiveTask(urlTaskId)
    }

    // Note: workId and scheduleId are handled by their respective views
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlBotId, botView, urlChatId, urlRoomId, urlTaskId, bots, chats, rooms, activeBotId, activeChatId, activeRoomId, setActiveBot, setActiveView, setActiveChat, setActiveRoom, setActiveTask, navigate])

  // Apply theme
  useEffect(() => {
    const applyTheme = (isDark: boolean) => {
      if (isDark) {
        document.documentElement.classList.add('dark')
      } else {
        document.documentElement.classList.remove('dark')
      }
    }

    if (theme === 'system') {
      const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)')
      applyTheme(mediaQuery.matches)

      const handler = (e: MediaQueryListEvent) => applyTheme(e.matches)
      mediaQuery.addEventListener('change', handler)
      return () => mediaQuery.removeEventListener('change', handler)
    } else {
      applyTheme(theme === 'dark')
    }
  }, [theme])

  // Apply accent color
  useEffect(() => {
    const palette = accentColor === 'custom'
      ? generatePalette(customHex)
      : accentColors[accentColor]?.palette
    if (palette) {
      const root = document.documentElement
      Object.entries(palette).forEach(([shade, color]) => {
        root.style.setProperty(`--accent-${shade}`, color)
        // Set RGB triplet variants for rgba() usage
        const hex = color.replace('#', '')
        const r = parseInt(hex.substring(0, 2), 16)
        const g = parseInt(hex.substring(2, 4), 16)
        const b = parseInt(hex.substring(4, 6), 16)
        root.style.setProperty(`--accent-${shade}-rgb`, `${r}, ${g}, ${b}`)
      })
    }
  }, [accentColor, customHex])

  // Load config on mount
  useEffect(() => {
    async function loadInitialData() {
      try {
        const configData = await getConfig()

        // Transform config from snake_case to camelCase
        const config: Config = {
          agent: {
            model: configData.agent.model,
            maxIterations: configData.agent.max_iterations,
            approveActions: configData.agent.approve_actions,
            temperature: configData.agent.temperature,
          },
          sandbox: {
            allowedImports: configData.sandbox.allowed_imports,
            timeoutSeconds: configData.sandbox.timeout_seconds,
            maxOutputLength: configData.sandbox.max_output_length,
          },
          display: {
            showThinking: configData.display.show_thinking,
            showCost: configData.display.show_cost,
            style: configData.display.style as 'detailed' | 'compact',
          },
          workspacePath: configData.workspace_path,
          timezone: configData.timezone || 'UTC',
        }

        setConfig(config)
      } catch (error) {
        console.error('Failed to load config:', error)
      }
    }

    loadInitialData()
    refreshModels()
    refreshProviders()
  }, [setConfig, refreshModels, refreshProviders])

  // Onboarding detection: redirect first-time users with no API keys
  useEffect(() => {
    if (hasCompletedOnboarding) return
    // Wait until providers have loaded
    if (providers.length === 0) return

    const hasConfigured = providers.some((p) => p.configured)
    if (hasConfigured) {
      // Existing user upgrading — silently mark as completed
      useOnboardingStore.getState().completeOnboarding()
    } else {
      navigate('/onboarding')
    }
  }, [hasCompletedOnboarding, providers, navigate])

  // Check for updates on mount (pip-based, skip in Electron)
  useEffect(() => {
    if (!window.electronAPI?.isDesktop) {
      useUpdateStore.getState().checkForUpdate()
    }
  }, [])

  const renderActiveView = () => {
    // App-level views take precedence (determined by URL)
    if (appView) {
      switch (appView) {
        case 'dashboard':
          return <DashboardView />
        case 'settings':
          return <AppSettingsView />
        case 'admin-logs':
          return <GlobalLogView />
      }
    }

    // Bot-specific views (from URL or store)
    const viewToRender = botView || activeView
    switch (viewToRender) {
      case 'chats':
        return <ChatView />
      case 'rooms':
        return <RoomsView />
      case 'work':
        return <WorkView />
      case 'automations': {
        // Sub-route: /:botId/automations/:id/edit -> ScriptEditorView
        const automationSubPath = pathParts[2]
        if (automationSubPath && pathParts[3] === 'edit') {
          return <ScriptEditorView />
        }
        return <AutomationsView />
      }
      case 'voice':
        return <VoiceView />
      case 'tools':
        return <ToolsView />
      case 'developer':
        return <SettingsView />
      case 'settings':
        return <SettingsView />
      default:
        return <ChatView />
    }
  }

  return (
    <div className="app-shell">
      <div className="app-shell__body">
      {/* Mobile overlay backdrop */}
      {mobileMenuOpen && (
        <div
          className="app-shell__overlay"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Bot Rail - leftmost sidebar (hidden on mobile unless menu open) */}
      <div
        className={cn(
          'app-shell__rail',
          mobileMenuOpen && 'app-shell__rail--open'
        )}
      >
        <BotRail onNavigate={() => setMobileMenuOpen(false)} />
      </div>

      {/* Bot Sidebar - secondary navigation (hide on app-level views, hidden on mobile unless menu open) */}
      {!appView && (
        <div
          className={cn(
            'app-shell__sidebar',
            mobileMenuOpen && 'app-shell__sidebar--open'
          )}
        >
          <BotSidebar onNavigate={() => setMobileMenuOpen(false)} />
        </div>
      )}

      {/* Main content area */}
      <main className="app-shell__main">
        {/* Mobile header with menu button */}
        <div className="app-shell__mobile-header">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="btn btn--ghost btn--icon btn--sm"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-600">
              <span className="text-sm font-bold text-white">C</span>
            </div>
            <span className="font-semibold text-zinc-900 dark:text-[var(--color-text-primary)]">CachiBot</span>
          </div>
        </div>
        <UpdateBanner />
        {renderActiveView()}
      </main>

      </div>

      {/* Dialogs */}
      <CreateBotDialog />
      <SettingsDialog />
      <ApprovalDialog onApprove={() => {}} />
      <UpdateDialog />
    </div>
  )
}

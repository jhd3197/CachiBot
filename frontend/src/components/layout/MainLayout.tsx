import { useEffect, useRef, useState } from 'react'
import { useLocation, useParams, useNavigate, Navigate } from 'react-router-dom'
import { Menu, X, LayoutGrid, Settings as SettingsIcon, Activity, History, MoreHorizontal } from 'lucide-react'
import { BotListSidebar } from './BotListSidebar'
import { ChatMoreMenu } from '../chat/ChatMoreMenu'
import {
  ChatView,
  RoomsView,
  ToolsView,
  SettingsView,
  BotSettingsView,
  DashboardView,
  WorkspaceView,
  RunsView,
  AppSettingsView,
  WorkView,
  VoiceView,
  RoutinesView,
  RoutineEditorView,
  ScriptEditorView,
  GlobalLogView,
  PluginsView,
  ExternalPluginView,
} from '../views'
import { CreateBotDialog } from '../dialogs/CreateBotDialog'
import { SettingsDialog } from '../dialogs/SettingsDialog'
import { ApprovalDialog } from '../dialogs/ApprovalDialog'
import { UpdateDialog } from '../dialogs/UpdateDialog'
import { UpdateBanner } from '../common/UpdateBanner'
import { BotAvatar } from '../common/Avatar'
import { ChatsSheet } from '../chat/ChatsSheet'
import { GlobalSearchDialog } from '../common/GlobalSearchDialog'
import { useUpdateStore } from '../../stores/update'
import { useBotStore, useChatStore, useTaskStore } from '../../stores/bots'
import { useRoomStore } from '../../stores/rooms'
import { useUIStore, accentColors, generatePalette } from '../../stores/ui'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { useProvidersStore } from '../../stores/providers'
import { useOnboardingStore } from '../../stores/onboarding'
import { useApprovalsStore } from '../../stores/approvals'
import { useWebSocket, setPendingApproval } from '../../hooks/useWebSocket'
import { wsClient } from '../../api/websocket'
import { cn } from '../../lib/utils'
import type { AppView, BotView } from '../../types'

// Map URL paths to app views
const pathToAppView: Record<string, AppView> = {
  '/dashboard': 'dashboard',
  '/dashboard/usage': 'dashboard-usage',
  '/runs': 'runs',
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
  const { config } = useConfigStore()
  const { refresh: refreshModels } = useModelsStore()
  const { providers, refresh: refreshProviders } = useProvidersStore()
  const { hasCompletedOnboarding } = useOnboardingStore()
  // App-level agent connection: one WebSocket for the whole shell, so agent
  // runs (and their approvals) stay alive while navigating to Workspace etc.
  const { sendMessage, cancel, isConnected, runContext } = useWebSocket()

  // Answer approval requests from the global dialog (any view)
  const handleApprove = (id: string, approved: boolean) => {
    wsClient.sendApproval(id, approved)
    setPendingApproval(null)
    useApprovalsStore.getState().resolveApproval(id)
  }

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
    routines: 'routines',
    voice: 'voice',
    tools: 'tools',
    plugins: 'plugins',
    developer: 'developer',
    settings: 'settings',
  }
  const botView = viewSegment ? viewMap[viewSegment] : null

  // Redirect legacy URLs
  useEffect(() => {
    if (viewSegment === 'schedules' && urlBotId) {
      const legacyScheduleId = pathParts[2]
      navigate(
        legacyScheduleId
          ? `/${urlBotId}/routines/${legacyScheduleId}`
          : `/${urlBotId}/routines`,
        { replace: true }
      )
    }
    if (viewSegment === 'tasks' && urlBotId) {
      useUIStore.getState().setWorkSection('quick-tasks')
      navigate(`/${urlBotId}/work`, { replace: true })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pathParts is derived from the URL above
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

  // Fallback: re-fetch if stores are empty (e.g. direct navigation edge case)
  useEffect(() => {
    if (!config) refreshModels() // models depend on config being available
    if (providers.length === 0) refreshProviders()
  }, [config, providers.length, refreshModels, refreshProviders])

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

  // Mobile drawer: Escape closes it, focus moves into the drawer when opened
  const navRef = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!mobileMenuOpen) return
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setMobileMenuOpen(false)
    }
    document.addEventListener('keydown', handler)
    navRef.current?.focus()
    return () => document.removeEventListener('keydown', handler)
  }, [mobileMenuOpen, setMobileMenuOpen])

  // Global search (design 12): Ctrl/Cmd+K anywhere opens the search dialog
  const [showGlobalSearch, setShowGlobalSearch] = useState(false)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setShowGlobalSearch(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])
  const searchBotId = urlBotId ?? activeBotId ?? bots[0]?.id ?? null

  const renderActiveView = () => {
    // App-level views take precedence (determined by URL)
    if (appView) {
      switch (appView) {
        case 'dashboard':
          return <WorkspaceView activeRun={runContext} />
        case 'dashboard-usage':
          return <DashboardView />
        case 'runs':
          return <RunsView />
        case 'settings':
          return <AppSettingsView />
        case 'admin-logs':
          return <GlobalLogView />
      }
    }

    const renderChatView = () => (
      <ChatView
        onSendMessage={sendMessage}
        onCancel={cancel}
        isConnected={isConnected}
        runChatId={runContext?.chatId ?? null}
      />
    )

    // Bot-specific views (from URL or store)
    const viewToRender = botView || activeView
    switch (viewToRender) {
      case 'chats':
        return renderChatView()
      case 'rooms':
        return <RoomsView />
      case 'work':
        return <WorkView />
      case 'automations': {
        // Sub-route: /:botId/automations/:id/edit -> ScriptEditorView (scripts
        // are an advanced building block; the base page moved to /routines)
        const automationSubPath = pathParts[2]
        if (automationSubPath && pathParts[3] === 'edit') {
          return <ScriptEditorView />
        }
        return <Navigate to={`/${urlBotId}/routines`} replace />
      }
      case 'routines': {
        // /:botId/routines -> list; /new or /:routineId -> editor
        if (pathParts[2]) {
          return <RoutineEditorView />
        }
        return <RoutinesView />
      }
      case 'voice':
        return <VoiceView />
      case 'tools':
        return <ToolsView />
      case 'plugins': {
        // Sub-route: /:botId/plugins/:pluginName -> ExternalPluginView
        const pluginName = pathParts[2]
        if (pluginName) {
          return <ExternalPluginView pluginName={pluginName} />
        }
        return <PluginsView />
      }
      case 'developer':
        return <SettingsView />
      case 'settings':
        return <BotSettingsView />
      default:
        return renderChatView()
    }
  }

  // Mobile top bar context: the bot when a bot route is active, otherwise
  // the app view name. Replaces the old letter avatar (design uses BotAvatar).
  const headerBot =
    (urlBotId ? bots.find((b) => b.id === urlBotId) : undefined) ??
    (appView ? undefined : bots.find((b) => b.id === activeBotId))
  const mobileTitle =
    appView === 'settings' ? 'Settings' : appView === 'admin-logs' ? 'Exec logs' : appView === 'runs' ? 'Runs' : 'Workspace'

  // Chat routes mount the chat header inline; the mobile top bar folds the
  // bot title + "Earlier chats" into one row (design 02, <1024px).
  const chatRouteActive = !appView && (!botView || botView === 'chats')
  const [showMobileChats, setShowMobileChats] = useState(false)
  const [showMobileMore, setShowMobileMore] = useState(false)

  return (
    <div className="app-shell ui-v2">
      <div className="app-shell__body">
      {/* Mobile overlay backdrop */}
      {mobileMenuOpen && (
        <div
          className="app-shell__overlay"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Bot-first sidebar (UI v2): single 300px nav, mobile slide-in drawer */}
      <div
        ref={navRef}
        tabIndex={-1}
        className={cn(
          'app-shell__nav',
          mobileMenuOpen && 'app-shell__nav--open'
        )}
      >
        <BotListSidebar onNavigate={() => setMobileMenuOpen(false)} onOpenSearch={() => setShowGlobalSearch(true)} />
      </div>

      {/* Main content area */}
      <main className="app-shell__main">
        {/* Mobile header with menu button */}
        <div className="app-shell__mobile-header">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="btn btn--ghost btn--icon btn--sm"
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          {headerBot ? (
            <button
              type="button"
              className="app-shell__mobile-title"
              onClick={() => navigate(`/${headerBot.id}/chats`)}
            >
              <BotAvatar color={headerBot.color} name={headerBot.name} size={26} />
              <span className="app-shell__mobile-title-text">{headerBot.name}</span>
            </button>
          ) : (
            <div className="app-shell__mobile-title">
              {appView === 'settings' ? (
                <SettingsIcon size={16} strokeWidth={1.8} />
              ) : appView === 'admin-logs' ? (
                <Activity size={16} strokeWidth={1.8} />
              ) : (
                <LayoutGrid size={16} strokeWidth={1.8} />
              )}
              <span className="app-shell__mobile-title-text">{mobileTitle}</span>
            </div>
          )}
          {chatRouteActive && headerBot && (
            <div className="app-shell__mobile-actions">
              <button
                type="button"
                className="v2-icon-btn"
                aria-label="Earlier chats"
                title="Earlier chats"
                onClick={() => setShowMobileChats(true)}
              >
                <History size={18} strokeWidth={1.8} />
              </button>
              <button
                type="button"
                className="v2-icon-btn"
                aria-label="More"
                title="More"
                aria-haspopup="menu"
                aria-expanded={showMobileMore}
                onClick={(e) => { e.stopPropagation(); setShowMobileMore((o) => !o) }}
              >
                <MoreHorizontal size={18} strokeWidth={1.8} />
              </button>
              {showMobileMore && (
                <ChatMoreMenu
                  bot={headerBot}
                  chat={chats.find((c) => c.id === activeChatId) ?? null}
                  onClose={() => setShowMobileMore(false)}
                />
              )}
            </div>
          )}
        </div>
        <UpdateBanner />
        {renderActiveView()}
      </main>

      </div>

      {/* Dialogs */}
      <CreateBotDialog />
      <SettingsDialog />
      <ApprovalDialog
        onApprove={handleApprove}
        // The inline chat ApprovalCard answers approvals for the visible
        // chat; the dialog remains the fallback for other/background chats.
        suppressChatId={chatRouteActive ? activeChatId : null}
      />
      <UpdateDialog />

      {/* "Earlier chats" from the mobile top bar (chat header is folded away) */}
      {showMobileChats && headerBot && (
        <ChatsSheet bot={headerBot} onClose={() => setShowMobileChats(false)} />
      )}

      {/* Global search (sidebar search icon + Ctrl/Cmd K, design 12/13) */}
      {showGlobalSearch && (
        <GlobalSearchDialog
          botId={searchBotId}
          onNavigate={(path) => { setShowGlobalSearch(false); navigate(path) }}
          onClose={() => setShowGlobalSearch(false)}
        />
      )}
    </div>
  )
}

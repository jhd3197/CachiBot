import { useEffect } from 'react'
import { useLocation, useParams, useNavigate } from 'react-router-dom'
import { Menu, X } from 'lucide-react'
import { BotRail } from './BotRail'
import { BotSidebar } from './BotSidebar'
import {
  ChatView,
  TasksView,
  ToolsView,
  SettingsView,
  DashboardView,
  AppSettingsView,
  ModelsView,
  WorkView,
  SchedulesView,
} from '../views'
import { CreateBotDialog } from '../dialogs/CreateBotDialog'
import { SettingsDialog } from '../dialogs/SettingsDialog'
import { ApprovalDialog } from '../dialogs/ApprovalDialog'
import { useBotStore, useChatStore, useTaskStore } from '../../stores/bots'
import { useUIStore, accentColors } from '../../stores/ui'
import { useConfigStore } from '../../stores/config'
import { useModelsStore } from '../../stores/models'
import { getConfig } from '../../api/client'
import type { AppView, BotView, Config } from '../../types'

// Map URL paths to app views
const pathToAppView: Record<string, AppView> = {
  '/dashboard': 'dashboard',
  '/models': 'models',
  '/settings': 'settings',
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
  const { botId: urlBotId, chatId: urlChatId, taskId: urlTaskId } = useParams<{
    botId?: string
    chatId?: string
    taskId?: string
  }>()
  const { activeView, activeBotId, bots, setActiveBot, setActiveView } = useBotStore()
  const { activeChatId, chats, setActiveChat } = useChatStore()
  const { setActiveTask } = useTaskStore()
  const { theme, accentColor, mobileMenuOpen, setMobileMenuOpen } = useUIStore()
  const { setConfig } = useConfigStore()
  const { refresh: refreshModels } = useModelsStore()

  // Derive appView from URL path
  const appView = getAppViewFromPath(location.pathname)

  // Parse view from URL path: /:botId/view or /:botId/view/:itemId
  const pathParts = location.pathname.split('/').filter(Boolean)
  const viewSegment = pathParts[1] // Second segment is the view (chats, jobs, tasks, tools, settings)

  const viewMap: Record<string, BotView> = {
    chats: 'chats',
    tasks: 'tasks',
    work: 'work',
    schedules: 'schedules',
    tools: 'tools',
    settings: 'settings',
  }
  const botView = viewSegment ? viewMap[viewSegment] : null

  // Sync URL to store state
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
    if (botView && botView !== activeView) {
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

    // Sync task ID from URL
    if (urlTaskId) {
      setActiveTask(urlTaskId)
    }

    // Note: workId and scheduleId are handled by their respective views
  }, [urlBotId, botView, urlChatId, urlTaskId, bots, chats, activeBotId, activeChatId, activeView, setActiveBot, setActiveView, setActiveChat, setActiveTask, navigate])

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
    const palette = accentColors[accentColor]?.palette
    if (palette) {
      const root = document.documentElement
      Object.entries(palette).forEach(([shade, color]) => {
        root.style.setProperty(`--accent-${shade}`, color)
      })
    }
  }, [accentColor])

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
        }

        setConfig(config)
      } catch (error) {
        console.error('Failed to load config:', error)
      }
    }

    loadInitialData()
    refreshModels()
  }, [setConfig, refreshModels])

  const renderActiveView = () => {
    // App-level views take precedence (determined by URL)
    if (appView) {
      switch (appView) {
        case 'dashboard':
          return <DashboardView />
        case 'settings':
          return <AppSettingsView />
        case 'models':
          return <ModelsView />
      }
    }

    // Bot-specific views (from URL or store)
    const viewToRender = botView || activeView
    switch (viewToRender) {
      case 'chats':
        return <ChatView />
      case 'tasks':
        return <TasksView />
      case 'work':
        return <WorkView />
      case 'schedules':
        return <SchedulesView />
      case 'tools':
        return <ToolsView />
      case 'settings':
        return <SettingsView />
      default:
        return <ChatView />
    }
  }

  return (
    <div className="flex h-screen bg-zinc-100 text-zinc-900 dark:bg-zinc-950 dark:text-zinc-100">
      {/* Mobile overlay backdrop */}
      {mobileMenuOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setMobileMenuOpen(false)}
        />
      )}

      {/* Bot Rail - leftmost sidebar (hidden on mobile unless menu open) */}
      <div
        className={`
          fixed inset-y-0 left-0 z-50 transition-transform duration-300 lg:static lg:translate-x-0
          ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-full'}
        `}
      >
        <BotRail onNavigate={() => setMobileMenuOpen(false)} />
      </div>

      {/* Bot Sidebar - secondary navigation (hide on app-level views, hidden on mobile unless menu open) */}
      {!appView && (
        <div
          className={`
            fixed inset-y-0 left-[72px] z-50 transition-transform duration-300 lg:static lg:translate-x-0
            ${mobileMenuOpen ? 'translate-x-0' : '-translate-x-[calc(100%+72px)]'}
          `}
        >
          <BotSidebar onNavigate={() => setMobileMenuOpen(false)} />
        </div>
      )}

      {/* Main content area */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Mobile header with menu button */}
        <div className="flex h-12 items-center gap-3 border-b border-zinc-200 bg-white px-3 dark:border-zinc-800 dark:bg-zinc-900 lg:hidden">
          <button
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
            className="flex h-9 w-9 items-center justify-center rounded-lg text-zinc-500 transition-colors hover:bg-zinc-100 hover:text-zinc-700 dark:text-zinc-400 dark:hover:bg-zinc-800 dark:hover:text-zinc-200"
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </button>
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-accent-600">
              <span className="text-sm font-bold text-white">C</span>
            </div>
            <span className="font-semibold text-zinc-900 dark:text-zinc-100">CachiBot</span>
          </div>
        </div>
        {renderActiveView()}
      </main>

      {/* Dialogs */}
      <CreateBotDialog />
      <SettingsDialog />
      <ApprovalDialog onApprove={() => {}} />
    </div>
  )
}

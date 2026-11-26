import { useRef, useEffect, useState, useCallback, useMemo } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import {
  Send,
  Square,
  Plus,
  Sparkles,
  ChevronDown,
  Check,
  XCircle,
  Reply,
  X,
  Cpu,
  History,
  ArrowDown,
  Mic,
  MoreHorizontal,
  FolderOpen,
  GitBranch,
  Paperclip,
  Monitor,
} from 'lucide-react'
import { useChatStore, useBotStore, getBotDefaultModel } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { useComputerStore } from '../../stores/computer'
import { useAuthStore } from '../../stores/auth'
import { useCreationFlowStore } from '../../stores/creation-flow'
import { useModelsStore } from '../../stores/models'
import { useApprovalsStore } from '../../stores/approvals'
import { useSideTasksStore } from '../../stores/side-tasks'
import { BotAvatar } from '../common/Avatar'
import { V2Menu, V2MenuItem } from '../common/V2Menu'
import { ChatsSheet } from '../chat/ChatsSheet'
import { FilesSheet } from '../chat/FilesSheet'
import {
  SideTaskGroupReplyView,
  SideTaskIndicator,
  SideTaskReplyView,
  sideTaskGroupReplyMetadata,
  sideTaskReplyMetadata,
} from '../side-tasks/SideTaskReply'
import { SideTaskChatView } from '../side-tasks/SideTaskChatView'
import { StartSideTaskDialog } from '../side-tasks/StartSideTaskDialog'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { ModelPill } from '../chat/ModelPill'
import { cn } from '../../lib/utils'
import { detectLanguage } from '../../lib/language-detector'
import { generateBotNames, getCodingAgents } from '../../api/client'
import { listArtifacts } from '../../api/artifacts'
import { uploadChatAsset } from '../../api/assets'
import { getChatMessages } from '../../api/side-tasks'
import { generateSystemPrompt } from '../../lib/prompt-generator'
import { setPendingChatId, setPendingApproval, expectUserEcho } from '../../hooks/useWebSocket'
import { wsClient } from '../../api/websocket'
import { useCommands } from '../../hooks/useCommands'
import { useBotAccess } from '../../hooks/useBotAccess'
import { MessageBubbleV2, isMediaResult } from '../chat/MessageBubble'
import { ErrorCard, ApprovalCard, StoppedLine, ComputerNeedsYouCard, ComputerDrivingLine } from '../chat/ChatCards'
import { ThinkingIndicator } from '../chat/ThinkingIndicator'
import { StatusLine } from '../common/StatusLine'
import { Spinner } from '../common/Spinner'
import { ChatMoreMenu } from '../chat/ChatMoreMenu'
import { VoiceMode } from '../chat/VoiceMode'
import { FindInChatBar } from '../chat/FindInChatBar'
import { ArtifactPanel } from '../artifacts/ArtifactPanel'
import { useArtifactsStore } from '../../stores/artifacts'
import { useWorkspaceStore } from '../../stores/workspace'
import { WorkspaceSelector } from '../chat/WorkspaceSelector'
import { TaskProgress } from '../chat/TaskProgress'
import type { ToolCall, BotIcon, BotModels, BotCapabilities, ToolConfigs, Chat, Bot, CodingAgentInfo, ChatMessage, SideTask } from '../../types'

// =============================================================================
// BOT CREATION HELPERS
// =============================================================================

const BOT_ICONS: BotIcon[] = ['bot', 'brain', 'zap', 'sparkles', 'rocket', 'star', 'gem', 'flame']
const BOT_COLORS: string[] = ['#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#22c55e', '#06b6d4']

function pickRandomIcon(): BotIcon {
  return BOT_ICONS[Math.floor(Math.random() * BOT_ICONS.length)]
}

function pickRandomColor(): string {
  return BOT_COLORS[Math.floor(Math.random() * BOT_COLORS.length)]
}

interface ChatViewSendOptions {
  systemPrompt?: string
  botId?: string
  chatId?: string
  model?: string
  models?: BotModels
  capabilities?: BotCapabilities
  toolConfigs?: ToolConfigs
  replyToId?: string
  workspace?: string | null
}

interface ChatViewProps {
  onSendMessage: (message: string, options?: ChatViewSendOptions) => void
  onCancel: () => void
  isConnected: boolean
  /** Chat that owns the in-flight run (null when idle); gates run-scoped UI */
  runChatId?: string | null
}

// Day separators from real message timestamps (design 02 "Today 9:14 AM")
function dayKeyOf(timestamp: string): string {
  return new Date(timestamp).toDateString()
}

function dayLabel(timestamp: string): string {
  const d = new Date(timestamp)
  const now = new Date()
  const yesterday = new Date(now)
  yesterday.setDate(now.getDate() - 1)
  if (dayKeyOf(timestamp) === dayKeyOf(now.toISOString())) {
    const time = d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' })
    return `Today ${time}`
  }
  if (dayKeyOf(timestamp) === yesterday.toDateString()) {
    return 'Yesterday'
  }
  return d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })
}

// Unwrap find highlights, restoring the original text nodes.
function clearFindMarks(root: HTMLElement) {
  const marks = root.querySelectorAll<HTMLElement>('.v2-find-mark')
  for (const mark of marks) {
    const parent = mark.parentNode
    if (!parent) continue
    parent.replaceChild(document.createTextNode(mark.textContent || ''), mark)
    parent.normalize()
  }
}

export function ChatView({ onSendMessage, onCancel, isConnected, runChatId }: ChatViewProps) {
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const { activeChatId, chats, messages: messagesByChat, thinking, toolCalls, isLoading, error: runError, addMessage, addChat, setActiveChat, updateMessage, upsertMessage, replyToMessage, setReplyTo } = useChatStore()
  const { getActiveBot, activeBotId, bots, addBot, setActiveBot } = useBotStore()
  const { showThinking } = useUIStore()
  const creationFlow = useCreationFlowStore()
  const { isCommand, isPrefixedCommand, handleCommand, remoteCommands } = useCommands()
  const { canOperate, canEdit: canEditBot } = useBotAccess(activeBotId)
  const { activeWorkspace, workspaceConfig, taskProgress, availableWorkspaces, setActiveWorkspace, clearWorkspace, setAvailableWorkspaces } = useWorkspaceStore()
  // Computer surfaces (C4): the Docker probe decides whether any of it may
  // appear; the per-bot record is live from GET + `computer_update` WS.
  const computerAvailable = useComputerStore((s) => s.status?.available === true)
  const inspectorOpen = useUIStore((s) => s.inspectorOpen)
  const botComputer = useComputerStore((s) => (activeBotId ? s.byBot[activeBotId] : undefined))
  const currentUserId = useAuthStore((s) => s.user?.id)
  const botDriver = botComputer?.driver

  useEffect(() => {
    if (!computerAvailable || !activeBotId) return
    void useComputerStore.getState().ensureForBot(activeBotId)
    void useComputerStore.getState().fetchViews(activeBotId)
  }, [computerAvailable, activeBotId])

  // Run-scoped UI (typing/thinking/tool calls) only shows in the chat that
  // owns the in-flight run — the connection lives at the app level now.
  const runVisibleHere = !runChatId || runChatId === activeChatId
  const handleCancel = onCancel
  const [input, setInput] = useState('')
  const [selectedModel, setSelectedModel] = useState(() => {
    const bot = useBotStore.getState().getActiveBot()
    return bot ? getBotDefaultModel(bot) : ''
  })
  const [flowUserInputs, setFlowUserInputs] = useState<string[]>([])
  const justCreatedChatRef = useRef(false)
  const [animateIsland, setAnimateIsland] = useState(false)
  const [showCommandMenu, setShowCommandMenu] = useState(false)
  const [showChats, setShowChats] = useState(false)
  const [showFiles, setShowFiles] = useState(false)
  const [showMoreMenu, setShowMoreMenu] = useState(false)
  const [voiceMode, setVoiceMode] = useState(false)
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const scrollContainerRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const stickToBottomRef = useRef(true)
  const prevMsgCountRef = useRef(0)
  const [scrolledUp, setScrolledUp] = useState(false)
  const [newCount, setNewCount] = useState(0)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [attachStatus, setAttachStatus] = useState<string | null>(null)
  const modelPillOpenRef = useRef<(() => void) | null>(null)
  const [stoppedUserMessageId, setStoppedUserMessageId] = useState<string | null>(null)
  const [findOpen, setFindOpen] = useState(false)
  const [findQuery, setFindQuery] = useState('')
  const [findCursor, setFindCursor] = useState(0)
  const [findCount, setFindCount] = useState(0)
  const listRef = useRef<HTMLDivElement>(null)

  // Side tasks (principle 9): the parent chat's replies/indicators and the
  // side-task chat view both read from the store, fed by the list endpoint +
  // side_task_update.
  const [plusMenuOpen, setPlusMenuOpen] = useState(false)
  const [sideTaskPrefill, setSideTaskPrefill] = useState<string | null>(null)
  const ensureSideTasks = useSideTasksStore((s) => s.ensureForBot)
  useEffect(() => {
    if (activeBotId) void ensureSideTasks(activeBotId)
  }, [activeBotId, ensureSideTasks])

  // Side-task replies are persisted server-side. Merge any this browser
  // missed (offline when it was written, or a fresh browser profile) into
  // the local history; only reply-kind messages are merged, so locally
  // echoed bubbles are never duplicated.
  useEffect(() => {
    if (!activeBotId || !activeChatId) return
    let cancelled = false
    getChatMessages(activeBotId, activeChatId, 200)
      .then((rows) => {
        if (cancelled) return
        for (const row of rows) {
          const kind = row.metadata?.kind
          if (kind !== 'side_task_reply' && kind !== 'side_task_group_reply') continue
          upsertMessage(activeChatId, {
            id: row.id,
            role: row.role as ChatMessage['role'],
            content: row.content,
            timestamp: row.timestamp,
            metadata: row.metadata,
            replyToId: row.replyToId ?? undefined,
          })
        }
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [activeBotId, activeChatId, upsertMessage])

  // Server-side artifacts are the source of truth once edits are saved
  // there: merge this chat's stored artifacts into the local cache (adds
  // ones this browser never saw, lets a >= server version win). A failed
  // fetch leaves the local cache as-is — it is only a cache.
  useEffect(() => {
    if (!activeBotId || !activeChatId) return
    let cancelled = false
    listArtifacts(activeBotId, activeChatId)
      .then((rows) => {
        if (cancelled) return
        useArtifactsStore.getState().mergeServerArtifacts(rows)
      })
      .catch(() => {})
    return () => {
      cancelled = true
    }
  }, [activeBotId, activeChatId])

  // @mention coding agent autocomplete state
  const [showAgentMentions, setShowAgentMentions] = useState(false)
  const [agentMentionFilter, setAgentMentionFilter] = useState('')
  const [selectedAgentIndex, setSelectedAgentIndex] = useState(0)
  const [availableAgents, setAvailableAgents] = useState<CodingAgentInfo[]>([])

  // Local command definitions for autocomplete
  const LOCAL_COMMANDS = [
    { name: 'new', description: 'Create a new bot', icon: '✨', source: 'local' as const },
    { name: 'list', description: 'View all your bots', icon: '📋', source: 'local' as const },
    { name: 'help', description: 'Show available commands', icon: '❓', source: 'local' as const },
    { name: 'settings', description: 'Open settings', icon: '⚙️', source: 'local' as const },
    { name: 'start', description: 'Welcome message', icon: '👋', source: 'local' as const },
  ]

  // Build prefix groups from remote commands for two-stage autocomplete
  const prefixGroups = remoteCommands.reduce<Record<string, { count: number; icon: string }>>((acc, cmd) => {
    if (!acc[cmd.prefix]) {
      acc[cmd.prefix] = { count: 0, icon: cmd.icon || '🔧' }
    }
    acc[cmd.prefix].count++
    return acc
  }, {})

  // Two-stage filtering for command autocomplete
  const filteredCommands = (() => {
    if (!input.startsWith('/')) return []
    const afterSlash = input.slice(1).toLowerCase()

    // Stage 2: Typing "/prefix:" → show commands under that prefix
    const colonIdx = afterSlash.indexOf(':')
    if (colonIdx > 0) {
      const prefix = afterSlash.slice(0, colonIdx)
      const subFilter = afterSlash.slice(colonIdx + 1)
      return remoteCommands
        .filter(cmd => cmd.prefix === prefix && cmd.name.startsWith(subFilter))
        .map(cmd => ({
          name: `${cmd.prefix}:${cmd.name}`,
          description: cmd.description,
          icon: cmd.icon === 'terminal' ? '🖥️' : cmd.icon === 'sparkles' ? '✨' : cmd.icon === 'cpu' ? '🤖' : cmd.icon === 'book-open' ? '📖' : '🔧',
          source: cmd.source,
        }))
    }

    // Stage 1: Typing "/" → show local commands + prefix groups
    const localMatches = LOCAL_COMMANDS.filter(cmd =>
      cmd.name.startsWith(afterSlash)
    )

    // Add prefix group entries (e.g. "skill:", "gsd:", "bot:")
    const groupEntries = Object.entries(prefixGroups)
      .filter(([prefix]) => prefix.startsWith(afterSlash) || afterSlash === '')
      .map(([prefix, info]) => ({
        name: `${prefix}:`,
        description: `${info.count} command${info.count > 1 ? 's' : ''} available`,
        icon: info.icon === 'terminal' ? '🖥️' : info.icon === 'sparkles' ? '✨' : info.icon === 'cpu' ? '🤖' : '🔧',
        source: 'group' as const,
      }))

    return [...localMatches, ...groupEntries]
  })()

  // Show command menu when typing "/"
  useEffect(() => {
    if (input === '/' || (input.startsWith('/') && input.length > 1 && filteredCommands.length > 0)) {
      setShowCommandMenu(true)
      setSelectedCommandIndex(0)
    } else {
      setShowCommandMenu(false)
    }
  }, [input, filteredCommands.length])

  const activeBot = getActiveBot()

  // ?voice=1 deep link (the /:botId/voice route redirects here): enter voice
  // mode once the view is mounted, then strip the param from the URL.
  useEffect(() => {
    if (searchParams.get('voice') === '1') {
      setVoiceMode(true)
      const next = new URLSearchParams(searchParams)
      next.delete('voice')
      setSearchParams(next, { replace: true })
    }
  }, [searchParams, setSearchParams])

  // Sync selectedModel when the active bot changes
  useEffect(() => {
    const bot = useBotStore.getState().getActiveBot()
    setSelectedModel(bot ? getBotDefaultModel(bot) : '')
  }, [activeBotId])

  // Fetch available coding agents when codingAgent capability is on
  const codingAgentEnabled = activeBot?.capabilities?.codingAgent ?? false
  useEffect(() => {
    if (!codingAgentEnabled) {
      setAvailableAgents([])
      return
    }
    let cancelled = false
    getCodingAgents()
      .then((res) => {
        if (!cancelled) setAvailableAgents(res.agents)
      })
      .catch(() => {
        if (!cancelled) setAvailableAgents([])
      })
    return () => { cancelled = true }
  }, [codingAgentEnabled])

  // Fetch available workspaces when bot changes
  useEffect(() => {
    if (!activeBotId) {
      setAvailableWorkspaces([])
      return
    }
    let cancelled = false
    fetch(`/api/bots/${activeBotId}/workspaces`)
      .then((r) => r.json())
      .then((data) => {
        if (!cancelled) setAvailableWorkspaces(data.workspaces || [])
      })
      .catch(() => {
        if (!cancelled) setAvailableWorkspaces([])
      })
    return () => { cancelled = true }
  }, [activeBotId, setAvailableWorkspaces])

  // Filter agents by text typed after @
  const filteredAgents = availableAgents.filter(
    (a) => a.id.startsWith(agentMentionFilter) || a.name.toLowerCase().startsWith(agentMentionFilter)
  )

  const messages = useMemo(
    () => (activeChatId ? messagesByChat[activeChatId] ?? [] : []),
    [messagesByChat, activeChatId]
  )
  const isInCreationFlow = creationFlow.step !== 'idle'

  // The open chat may itself BE a side task's chat (design 11b). Derived
  // from the stable byId map (a selecting selector that builds a new array
  // every call trips getSnapshot caching in zustand v5).
  const sideTasksById = useSideTasksStore((s) => s.byId)
  const sideTaskForChat = useMemo(
    () =>
      activeChatId
        ? Object.values(sideTasksById).find((t) => t.chatId === activeChatId)
        : undefined,
    [sideTasksById, activeChatId]
  )
  // Quiet indicators: side tasks of THIS chat that only wait or run are
  // shown as one small line under their source message (grouped helpers are
  // covered by their persisted group reply instead). Keyed by source message.
  const activeSinglesBySource = useMemo(() => {
    const map: Record<string, SideTask[]> = {}
    if (!activeChatId) return map
    for (const task of Object.values(sideTasksById)) {
      if (task.parentChatId !== activeChatId || task.groupId) continue
      if (task.status !== 'running' && task.status !== 'waiting_for_slot') continue
      if (!task.sourceMessageId) continue
      const list = map[task.sourceMessageId] ?? []
      list.push(task)
      map[task.sourceMessageId] = list
    }
    return map
  }, [sideTasksById, activeChatId])

  // Pending approvals for THIS chat — rendered inline (design 03 Approval card)
  const pendingApprovals = useApprovalsStore((s) => s.pending)
  const chatApprovals = useMemo(
    () => (activeChatId ? pendingApprovals.filter((a) => a.chatId === activeChatId) : []),
    [pendingApprovals, activeChatId]
  )

  // Real WS error attributed to this chat — rendered as the failed-turn card
  const showErrorCard = !!runError && (runError.chatId == null || runError.chatId === activeChatId) && !isLoading

  // Get existing bot names for uniqueness validation
  const existingBotNames = bots.map((bot) => bot.name)

  // Format name suggestions as a numbered list for display
  const formatNameSuggestions = useCallback((names: string[]) => {
    return names.map((name, i) => `${i + 1}. ${name}`).join('\n')
  }, [])

  // Fetch and display name suggestions
  const fetchAndDisplayNames = useCallback(async (chatId: string) => {
    creationFlow.setLoadingNames(true)
    try {
      const names = await generateBotNames(existingBotNames)
      creationFlow.setNameSuggestions(names)

      // Add CachiBot's response with suggestions
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Here are some name ideas:\n\n${formatNameSuggestions(names)}\n\nType a number to pick one, your own name, or "more" for new suggestions.`,
        timestamp: new Date().toISOString(),
      })
    } catch {
      // Fallback message if name generation fails
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: 'I had trouble generating names. Please type a name for your new bot:',
        timestamp: new Date().toISOString(),
      })
    } finally {
      creationFlow.setLoadingNames(false)
    }
  }, [creationFlow, existingBotNames, formatNameSuggestions, addMessage])

  // Handle name selection/input during creation flow
  const handleNameInput = useCallback((input: string, chatId: string) => {
    const trimmed = input.trim()
    const lower = trimmed.toLowerCase()

    // Handle "more" command
    if (lower === 'more') {
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        timestamp: new Date().toISOString(),
      })
      fetchAndDisplayNames(chatId)
      return true
    }

    // Check if it's a number selection (1-4)
    const num = parseInt(trimmed)
    const suggestions = creationFlow.data.nameSuggestions
    if (!isNaN(num) && num >= 1 && num <= suggestions.length) {
      const selectedName = suggestions[num - 1]

      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'user',
        content: trimmed,
        timestamp: new Date().toISOString(),
      })

      try {
        creationFlow.setName(selectedName)
        addMessage(chatId, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `Great, ${selectedName} it is!\n\nWhat kind of bot is this? Pick a category:\n\n1. Work - Professional tasks, productivity, business\n2. Personal - Daily life, reminders, personal assistant\n3. Creative - Writing, art, brainstorming, ideas\n4. Learning - Education, research, studying\n5. Other - Something else entirely\n\nJust type the number or describe it in your own words.`,
          timestamp: new Date().toISOString(),
        })
      } catch {
        // Name already exists (shouldn't happen with suggestions, but just in case)
        addMessage(chatId, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: `That name is already taken. Please choose another name or type "more" for new suggestions.`,
          timestamp: new Date().toISOString(),
        })
      }
      return true
    }

    // Treat as custom name - validate uniqueness
    const nameLower = trimmed.toLowerCase()
    const nameExists = existingBotNames.some(
      (name) => name.toLowerCase() === nameLower
    )

    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    if (nameExists) {
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `That name is already taken. Please choose a different name or type "more" for new suggestions.`,
        timestamp: new Date().toISOString(),
      })
      return true
    }

    // Valid custom name
    try {
      creationFlow.setName(trimmed)
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Great, ${trimmed} it is!\n\nWhat kind of bot is this? Pick a category:\n\n1. Work - Professional tasks, productivity, business\n2. Personal - Daily life, reminders, personal assistant\n3. Creative - Writing, art, brainstorming, ideas\n4. Learning - Education, research, studying\n5. Other - Something else entirely\n\nJust type the number or describe it in your own words.`,
        timestamp: new Date().toISOString(),
      })
    } catch {
      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `Something went wrong. Please try a different name.`,
        timestamp: new Date().toISOString(),
      })
    }
    return true
  }, [creationFlow, existingBotNames, fetchAndDisplayNames, addMessage])

  // Handle purpose category input
  const handlePurposeCategoryInput = useCallback((userInput: string, chatId: string) => {
    const trimmed = userInput.trim()
    const botName = creationFlow.data.name || 'your bot'

    // Add user message
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // Track for language detection
    const newInputs = [...flowUserInputs, trimmed]
    setFlowUserInputs(newInputs)
    const detected = detectLanguage(newInputs)
    if (detected) {
      creationFlow.setDetectedLanguage(detected)
    }

    // Map numbered selections to category names
    const categories: Record<string, string> = {
      '1': 'Work',
      '2': 'Personal',
      '3': 'Creative',
      '4': 'Learning',
      '5': 'Other',
    }

    const category = categories[trimmed] || trimmed
    creationFlow.setPurposeCategory(category)

    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `Got it! Now, describe what ${botName} should help you with.\n\nFor example: "Help me write professional emails" or "Be my coding buddy for Python projects"\n\nBe as specific as you like - this helps shape ${botName}'s personality.`,
      timestamp: new Date().toISOString(),
    })

    return true
  }, [creationFlow, flowUserInputs, addMessage])

  // Handle purpose description input
  const handlePurposeDescriptionInput = useCallback((userInput: string, chatId: string) => {
    const trimmed = userInput.trim()
    const botName = creationFlow.data.name || 'your bot'

    // Add user message
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // Track for language detection (description is often the longest text)
    const newInputs = [...flowUserInputs, trimmed]
    setFlowUserInputs(newInputs)
    const detected = detectLanguage(newInputs)
    if (detected) {
      creationFlow.setDetectedLanguage(detected)
    }

    creationFlow.setPurposeDescription(trimmed)

    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `Nice! How should ${botName} communicate?\n\n1. Professional - Business-appropriate, clear and concise\n2. Casual - Friendly and approachable, everyday language\n3. Playful - Fun, energetic, lighthearted\n4. Technical - Precise, detailed, uses domain terminology\n\nOr describe the style you want in your own words, like "Warm but concise" or "Like a patient teacher"`,
      timestamp: new Date().toISOString(),
    })

    return true
  }, [creationFlow, flowUserInputs, addMessage])

  // Handle communication style input
  const handleStyleInput = useCallback((userInput: string, chatId: string) => {
    const trimmed = userInput.trim()
    const botName = creationFlow.data.name || 'your bot'

    // Add user message
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // Track for language detection
    const newInputs = [...flowUserInputs, trimmed]
    setFlowUserInputs(newInputs)
    const detected = detectLanguage(newInputs)
    if (detected) {
      creationFlow.setDetectedLanguage(detected)
    }

    // Map numbered selections to style names
    const styles: Record<string, string> = {
      '1': 'Professional',
      '2': 'Casual',
      '3': 'Playful',
      '4': 'Technical',
    }

    const style = styles[trimmed] || trimmed
    creationFlow.setStyle(style)

    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `Almost done! Should ${botName} use emojis?\n\n1. Yes - Express yourself freely with emojis\n2. No - Keep it emoji-free\n3. Sometimes - Use them sparingly when they add value\n\nType 1, 2, or 3.`,
      timestamp: new Date().toISOString(),
    })

    return true
  }, [creationFlow, flowUserInputs, addMessage])

  // Handle emoji preference input
  const handleEmojiInput = useCallback((userInput: string, chatId: string) => {
    const trimmed = userInput.trim()
    const lower = trimmed.toLowerCase()
    const botName = creationFlow.data.name || 'your bot'

    // Add user message
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // Parse emoji preference (be lenient)
    let preference: 'yes' | 'no' | 'sometimes' = 'sometimes'
    if (lower === '1' || lower === 'yes' || lower === 'y') {
      preference = 'yes'
    } else if (lower === '2' || lower === 'no' || lower === 'n') {
      preference = 'no'
    } else if (lower === '3' || lower === 'sometimes' || lower === 'sparingly') {
      preference = 'sometimes'
    }

    creationFlow.setEmoji(preference)

    // Show summary with collected data
    const data = creationFlow.data
    const emojiText = preference === 'yes' ? 'Yes' : preference === 'no' ? 'No' : 'Sometimes'

    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `Perfect! Here's a summary of ${botName}:\n\n**Name:** ${data.name}\n**Category:** ${data.purposeCategory}\n**Purpose:** ${data.purposeDescription}\n**Style:** ${data.communicationStyle}\n**Emojis:** ${emojiText}\n\nType "confirm" to create ${botName}, or "back" to make changes.`,
      timestamp: new Date().toISOString(),
    })

    return true
  }, [creationFlow, addMessage])

  // Handle summary confirmation/cancellation
  const handleSummaryInput = useCallback((userInput: string, chatId: string) => {
    const trimmed = userInput.trim()
    const lower = trimmed.toLowerCase()
    const data = creationFlow.data
    const botName = data.name || 'your bot'

    // Add user message
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'user',
      content: trimmed,
      timestamp: new Date().toISOString(),
    })

    // Handle cancellation
    if (lower === 'cancel' || lower === 'no' || lower === 'n') {
      creationFlow.cancelFlow()
      setFlowUserInputs([])

      addMessage(chatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: "No worries! Type /create when you're ready to try again.",
        timestamp: new Date().toISOString(),
      })

      return true
    }

    // Handle confirmation
    if (lower === 'confirm' || lower === 'yes' || lower === 'y' || lower === 'create') {
      // Generate system prompt from flow data
      const systemPrompt = generateSystemPrompt(data)

      // Create the new bot
      const newBot: Bot = {
        id: crypto.randomUUID(),
        name: data.name!,
        description: data.purposeDescription || `A ${data.purposeCategory} assistant`,
        icon: pickRandomIcon(),
        color: pickRandomColor(),
        model: useModelsStore.getState().defaultModel,
        systemPrompt,
        tools: ['file_read', 'file_write', 'python_execute'],
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        personality: {
          purposeCategory: data.purposeCategory!,
          purposeDescription: data.purposeDescription!,
          communicationStyle: data.communicationStyle!,
          useEmojis: data.useEmojis!,
        },
      }

      // Add bot to store and set as active
      addBot(newBot)
      setActiveBot(newBot.id)

      // Mark flow complete and reset
      creationFlow.confirmAndCreate()
      creationFlow.completeFlow()
      setFlowUserInputs([])

      // Create a new chat for the new bot
      const newChatId = crypto.randomUUID()
      const newChat: Chat = {
        id: newChatId,
        botId: newBot.id,
        title: `Chat with ${newBot.name}`,
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        messageCount: 0,
      }
      addChat(newChat)
      setActiveChat(newChatId)

      // Add welcome message in the new bot's chat
      addMessage(newChatId, {
        id: crypto.randomUUID(),
        role: 'assistant',
        content: `**${newBot.name}** has been created! You're now chatting with your new bot.\n\nSay hello to see ${newBot.name}'s personality in action!`,
        timestamp: new Date().toISOString(),
      })

      return true
    }

    // Unrecognized input - prompt again
    addMessage(chatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content: `Type "confirm" to create ${botName}, or "cancel" to start over.`,
      timestamp: new Date().toISOString(),
    })

    return true
  }, [creationFlow, flowUserInputs, addMessage, addBot, setActiveBot, addChat, setActiveChat])

  // Auto-create a chat when needed (send or attach); returns the chat id
  const ensureChatId = useCallback((): string | null => {
    if (activeChatId) return activeChatId
    if (!activeBotId) return null
    const newChatId = crypto.randomUUID()
    const newChat: Chat = {
      id: newChatId,
      botId: activeBotId,
      title: 'New chat',
      createdAt: new Date().toISOString(),
      updatedAt: new Date().toISOString(),
      messageCount: 0,
    }
    addChat(newChat)
    setActiveChat(newChatId)
    // Set pending chat ID for WebSocket messages that arrive before state updates
    setPendingChatId(newChatId)
    // Navigate to the new chat URL for persistence on refresh
    navigate(`/${activeBotId}/chats/${newChatId}`)
    return newChatId
  }, [activeChatId, activeBotId, addChat, setActiveChat, navigate])

  // Normal send path shared by the composer, Continue, regenerate and
  // edit-and-resend: auto-create the chat, add the user bubble locally
  // (exactly once — the matching server echo is swallowed in useWebSocket,
  // and runs that error out still show the message), then hand off to the
  // app-level WS.
  const sendUserMessage = useCallback((text: string, opts?: { skipLocalUserMessage?: boolean }) => {
    const chatIdToUse = ensureChatId()
    if (chatIdToUse) {
      // Arm the echo swallow first so a fast server echo can't slip through.
      expectUserEcho(chatIdToUse, text)
      if (!opts?.skipLocalUserMessage) {
        addMessage(chatIdToUse, {
          id: crypto.randomUUID(),
          role: 'user',
          content: text,
          timestamp: new Date().toISOString(),
        })
      }
    }

    // Default capabilities for backwards compatibility
    const defaultCapabilities = {
      codeExecution: true,
      fileOperations: true,
      gitOperations: false,
      shellAccess: false,
      webAccess: false,
      dataOperations: false,
      contacts: false,
      connections: false,
      workManagement: true,
      imageGeneration: false,
      audioGeneration: false,
      codingAgent: false,
    }

    const effectiveModels: BotModels = {
      ...(activeBot?.models || {}),
      default: selectedModel || getBotDefaultModel(activeBot!) || '',
    }
    onSendMessage(text, {
      systemPrompt: activeBot?.systemPrompt,
      botId: activeBot?.id,
      chatId: chatIdToUse ?? undefined,
      model: selectedModel || activeBot?.model,
      models: effectiveModels,
      capabilities: activeBot?.capabilities || defaultCapabilities,
      toolConfigs: activeBot?.toolConfigs,
      replyToId: replyToMessage?.id,
      workspace: activeWorkspace,
    })
    setStoppedUserMessageId(null)
  }, [ensureChatId, activeBot, selectedModel, onSendMessage, replyToMessage, activeWorkspace])

  // Auto-scroll: follow the stream only while pinned to the bottom; when the
  // user scrolls up, count the new messages and offer the "Jump to latest" pill.
  useEffect(() => {
    const count = messages.length
    if (stickToBottomRef.current) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    } else if (count > prevMsgCountRef.current) {
      setNewCount((c) => c + count - prevMsgCountRef.current)
    }
    prevMsgCountRef.current = count
  }, [messages, thinking, toolCalls])

  // Switching chats pins back to the bottom
  useEffect(() => {
    stickToBottomRef.current = true
    setScrolledUp(false)
    setNewCount(0)
    setStoppedUserMessageId(null)
    prevMsgCountRef.current = useChatStore.getState().getMessages(activeChatId || '').length
    messagesEndRef.current?.scrollIntoView({ behavior: 'auto' })
  }, [activeChatId])

  const handleScroll = useCallback(() => {
    const el = scrollContainerRef.current
    if (!el) return
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 80
    stickToBottomRef.current = nearBottom
    setScrolledUp(!nearBottom)
    if (nearBottom) setNewCount(0)
  }, [])

  const jumpToLatest = useCallback(() => {
    stickToBottomRef.current = true
    setScrolledUp(false)
    setNewCount(0)
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  // Trigger dock-in animation when transitioning from hero → active chat
  useEffect(() => {
    if (messages.length > 0 && justCreatedChatRef.current) {
      justCreatedChatRef.current = false
      setAnimateIsland(true)
      const timer = setTimeout(() => setAnimateIsland(false), 500)
      return () => clearTimeout(timer)
    }
  }, [messages.length])

  // Ctrl/Cmd+F opens find-in-chat (design 03)
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'f') {
        e.preventDefault()
        setFindOpen(true)
      }
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [])

  useEffect(() => {
    setFindCursor(0)
  }, [findQuery])

  // Highlight matched text in place — the walk runs over the rendered DOM so
  // markdown bubbles highlight too. The current match is more prominent and
  // scrolls into view. The still-streaming message is skipped (its text nodes
  // change every token; it gets marked once the run finishes).
  useEffect(() => {
    const root = listRef.current
    if (!root) return
    clearFindMarks(root)
    if (!findOpen) {
      setFindCount(0)
      return
    }
    const q = findQuery.trim()
    if (!q) {
      setFindCount(0)
      return
    }
    const lower = q.toLowerCase()
    const streamingEl = isLoading && runVisibleHere && messages.length > 0
      ? root.querySelector(`#msg-${CSS.escape(messages[messages.length - 1].id)}`)
      : null
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT)
    const textNodes: Text[] = []
    let node: Node | null
    while ((node = walker.nextNode())) {
      const el = (node as Text).parentElement
      if (!el || el.closest('textarea, input, script, style')) continue
      if (streamingEl && streamingEl.contains(el)) continue
      textNodes.push(node as Text)
    }
    const marks: HTMLElement[] = []
    for (const textNode of textNodes) {
      const text = textNode.nodeValue || ''
      const lowerText = text.toLowerCase()
      const fragments: Array<Text | HTMLElement> = []
      let last = 0
      let idx = lowerText.indexOf(lower)
      while (idx !== -1) {
        if (idx > last) fragments.push(document.createTextNode(text.slice(last, idx)))
        const mark = document.createElement('span')
        mark.className = 'v2-find-mark'
        mark.textContent = text.slice(idx, idx + q.length)
        fragments.push(mark)
        marks.push(mark)
        last = idx + q.length
        idx = lowerText.indexOf(lower, last)
      }
      if (fragments.length === 0) continue
      if (last < text.length) fragments.push(document.createTextNode(text.slice(last)))
      const parent = textNode.parentNode
      if (!parent) continue
      for (const frag of fragments) parent.insertBefore(frag, textNode)
      parent.removeChild(textNode)
    }
    setFindCount(marks.length)
    if (marks.length === 0) return
    const current = ((findCursor % marks.length) + marks.length) % marks.length
    marks[current].classList.add('v2-find-mark--current')
    marks[current].scrollIntoView({ behavior: 'smooth', block: 'center' })
  }, [findOpen, findQuery, findCursor, messages, isLoading, runVisibleHere])

  const findTotal = findCount
  const findCurrent = findTotal === 0 ? 0 : ((findCursor % findTotal) + findTotal) % findTotal + 1

  const handleFindPrev = useCallback(() => {
    setFindCursor((c) => (findTotal === 0 ? 0 : c - 1))
  }, [findTotal])

  const handleFindNext = useCallback(() => {
    setFindCursor((c) => (findTotal === 0 ? 0 : c + 1))
  }, [findTotal])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    // Flag for dock-in animation when transitioning from hero → active chat
    if (messages.length === 0) {
      justCreatedChatRef.current = true
    }

    const trimmedInput = input.trim()
    const lowerInput = trimmedInput.toLowerCase()

    // Prefixed commands (/skill:X, /gsd:X, etc.) → send directly to backend via WS
    if (isPrefixedCommand(trimmedInput)) {
      // Falls through to normal message sending below — backend handles routing
    }
    // Handle local slash commands (except /create which uses the special flow)
    else if (isCommand(trimmedInput) && lowerInput !== '/create' && !isInCreationFlow) {
      // Add user message first
      if (activeChatId) {
        addMessage(activeChatId, {
          id: crypto.randomUUID(),
          role: 'user',
          content: trimmedInput,
          timestamp: new Date().toISOString(),
        })
      }

      const result = handleCommand(trimmedInput)
      if (result.handled) {
        setInput('')
        return
      }
    }

    // Handle /create command
    if (lowerInput === '/create') {
      let chatId = activeChatId

      // Create a new chat if none is active
      if (!chatId && activeBotId) {
        const newChat: Chat = {
          id: crypto.randomUUID(),
          botId: activeBotId,
          title: 'New Bot Creation',
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messageCount: 0,
        }
        addChat(newChat)
        setActiveChat(newChat.id)
        chatId = newChat.id
      }

      if (chatId) {
        // Start the creation flow
        creationFlow.startFlow(chatId)
        setFlowUserInputs([]) // Reset language detection inputs

        // Add user message
        addMessage(chatId, {
          id: crypto.randomUUID(),
          role: 'user',
          content: '/create',
          timestamp: new Date().toISOString(),
        })

        // Add CachiBot's initial response
        addMessage(chatId, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: "Let's create a new bot! I'm generating some name ideas...",
          timestamp: new Date().toISOString(),
        })

        // Fetch and display name suggestions
        fetchAndDisplayNames(chatId)
      }

      setInput('')
      return
    }

    // Handle cancel command during creation flow
    if (isInCreationFlow && lowerInput === 'cancel') {
      creationFlow.cancelFlow()
      setFlowUserInputs([]) // Reset language detection inputs

      if (activeChatId) {
        // Add user message
        addMessage(activeChatId, {
          id: crypto.randomUUID(),
          role: 'user',
          content: 'cancel',
          timestamp: new Date().toISOString(),
        })

        // Add CachiBot's response
        addMessage(activeChatId, {
          id: crypto.randomUUID(),
          role: 'assistant',
          content: 'Bot creation cancelled. Type /create to start again.',
          timestamp: new Date().toISOString(),
        })
      }

      setInput('')
      return
    }

    // Handle input during creation flow steps
    if (isInCreationFlow && activeChatId) {
      let handled = false

      switch (creationFlow.step) {
        case 'name':
          handled = handleNameInput(trimmedInput, activeChatId)
          break
        case 'purpose-category':
          handled = handlePurposeCategoryInput(trimmedInput, activeChatId)
          break
        case 'purpose-description':
          handled = handlePurposeDescriptionInput(trimmedInput, activeChatId)
          break
        case 'style':
          handled = handleStyleInput(trimmedInput, activeChatId)
          break
        case 'emoji':
          handled = handleEmojiInput(trimmedInput, activeChatId)
          break
        case 'summary':
          handled = handleSummaryInput(trimmedInput, activeChatId)
          break
      }

      if (handled) {
        setInput('')
        return
      }
    }

    // Normal message handling - send through the app-level WebSocket with
    // the bot's systemPrompt and per-message context
    sendUserMessage(trimmedInput)
    setInput('')
    setReplyTo(null)
  }

  // Stop the run; remember the interrupted user message for "Continue"
  const handleStop = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUser) {
      setStoppedUserMessageId(lastUser.id)
    }
    handleCancel()
  }, [messages, handleCancel])

  // Continue a stopped turn by resending the interrupted message
  const handleContinueStopped = useCallback(() => {
    const stopped = messages.find((m) => m.id === stoppedUserMessageId)
    if (stopped) {
      sendUserMessage(stopped.content)
    }
    setStoppedUserMessageId(null)
  }, [messages, stoppedUserMessageId, sendUserMessage])

  // Regenerate: resend the user message that led to this bot reply
  const regenerateFrom = useCallback((index: number) => {
    for (let j = index - 1; j >= 0; j--) {
      if (messages[j].role === 'user') {
        sendUserMessage(messages[j].content)
        return
      }
    }
  }, [messages, sendUserMessage])

  // Edit-and-resend: update the bubble in place, resend without adding a new
  // bubble (skipLocalUserMessage), and swallow the server's echo of the resend.
  const handleEditSend = useCallback((messageId: string, newContent: string) => {
    if (!activeChatId) return
    updateMessage(activeChatId, messageId, newContent)
    sendUserMessage(newContent, { skipLocalUserMessage: true })
  }, [activeChatId, updateMessage, sendUserMessage])

  // More › "Do this on the side" (design 11c): prefill the start dialog
  // with the message's text and remember the message (the reply quotes it).
  // Operator+ only (the start API requires it).
  const [sideTaskSource, setSideTaskSource] = useState<string | null>(null)
  const handleDoOnSide = useCallback((content: string, messageId: string) => {
    setSideTaskPrefill(content)
    setSideTaskSource(messageId)
  }, [])

  // Failed-turn card actions
  const handleTryAgain = useCallback(() => {
    const lastUser = [...messages].reverse().find((m) => m.role === 'user')
    if (lastUser) {
      sendUserMessage(lastUser.content)
    }
  }, [messages, sendUserMessage])

  const handleChangeModel = useCallback(() => {
    modelPillOpenRef.current?.()
  }, [])

  // Answer an inline approval — same path as the dialog: real WS approve,
  // clear the pending dialog state and the Workspace "Needs you" entry.
  const answerApproval = useCallback((id: string, approved: boolean) => {
    wsClient.sendApproval(id, approved)
    setPendingApproval(null)
    useApprovalsStore.getState().resolveApproval(id)
  }, [])

  // Attach a file to the chat via the real chat-assets API
  const handleFilePicked = useCallback(async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    e.target.value = ''
    if (!file || !activeBotId) return
    const chatId = ensureChatId()
    if (!chatId) return
    setAttachStatus(`Uploading ${file.name}…`)
    try {
      await uploadChatAsset(activeBotId, chatId, file)
      setAttachStatus(`Uploaded ${file.name}`)
    } catch {
      setAttachStatus(`Failed to upload ${file.name}`)
    }
    window.setTimeout(() => setAttachStatus(null), 4000)
  }, [activeBotId, ensureChatId])

  // Select a command from the autocomplete menu
  const selectCommand = (commandName: string) => {
    setInput(`/${commandName}`)
    // If selecting a prefix group (ends with ":"), keep menu open for sub-commands
    if (!commandName.endsWith(':')) {
      setShowCommandMenu(false)
    }
    textareaRef.current?.focus()
  }

  // Handle workspace selection — creates a new chat and activates workspace
  const handleWorkspaceSelect = useCallback((ws: import('../../stores/workspace').WorkspaceInfo) => {
    if (activeWorkspace === ws.pluginName) {
      clearWorkspace()
      return
    }
    // If no chat exists, create one
    if (!activeChatId && activeBotId) {
      const newChatId = `chat-${Date.now()}`
      addChat({ id: newChatId, botId: activeBotId, title: ws.displayName, createdAt: new Date().toISOString(), updatedAt: new Date().toISOString(), messageCount: 0 })
      setActiveChat(newChatId)
    }
    setActiveWorkspace(ws)
    textareaRef.current?.focus()
  }, [activeWorkspace, activeChatId, activeBotId, addChat, setActiveChat, setActiveWorkspace, clearWorkspace])

  // Handle input changes — detects @mentions for coding agents
  const handleInputChange = useCallback((value: string) => {
    setInput(value)

    // @mention detection (only when coding agents are available)
    if (availableAgents.length > 0) {
      const lastAtIndex = value.lastIndexOf('@')
      if (lastAtIndex >= 0) {
        const afterAt = value.slice(lastAtIndex + 1)
        const beforeAt = lastAtIndex > 0 ? value[lastAtIndex - 1] : ' '
        // Only trigger if @ is at start of input or preceded by a space
        if (beforeAt === ' ' || lastAtIndex === 0) {
          if (!afterAt.includes(' ') || afterAt.length < 20) {
            setShowAgentMentions(true)
            setAgentMentionFilter(afterAt.toLowerCase())
            setSelectedAgentIndex(0)
          } else {
            setShowAgentMentions(false)
          }
        }
      } else {
        setShowAgentMentions(false)
      }
    }
  }, [availableAgents.length])

  // Insert an @mention into the input
  const insertAgentMention = useCallback((agentId: string) => {
    const lastAtIndex = input.lastIndexOf('@')
    if (lastAtIndex >= 0) {
      const before = input.slice(0, lastAtIndex)
      setInput(`${before}@${agentId} `)
    }
    setShowAgentMentions(false)
    textareaRef.current?.focus()
  }, [input])

  // Render the @mention popup
  const renderAgentMentionPopup = () => {
    if (!showAgentMentions || filteredAgents.length === 0) return null
    return (
      <div className="chat-input-mention-popup">
        {filteredAgents.map((agent, index) => (
          <button
            key={agent.id}
            type="button"
            onClick={() => insertAgentMention(agent.id)}
            className={cn(
              'chat-input-mention-item',
              index === selectedAgentIndex && 'chat-input-mention-item--selected'
            )}
          >
            <Cpu className="h-4 w-4 text-[var(--color-text-secondary)]" />
            <div className="flex-1 min-w-0">
              <div className="font-medium">@{agent.id}</div>
              <div className="text-xs text-[var(--color-text-secondary)] truncate">
                {agent.name}{!agent.available && ' (not installed)'}
              </div>
            </div>
            {index === selectedAgentIndex && (
              <span className="text-xs text-[var(--color-text-secondary)]">↵</span>
            )}
          </button>
        ))}
      </div>
    )
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    // Handle @mention agent popup navigation
    if (showAgentMentions && filteredAgents.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedAgentIndex(prev =>
          prev < filteredAgents.length - 1 ? prev + 1 : 0
        )
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedAgentIndex(prev =>
          prev > 0 ? prev - 1 : filteredAgents.length - 1
        )
        return
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault()
        insertAgentMention(filteredAgents[selectedAgentIndex].id)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setShowAgentMentions(false)
        return
      }
    }

    // Handle command menu navigation
    if (showCommandMenu && filteredCommands.length > 0) {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedCommandIndex(prev =>
          prev < filteredCommands.length - 1 ? prev + 1 : 0
        )
        return
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedCommandIndex(prev =>
          prev > 0 ? prev - 1 : filteredCommands.length - 1
        )
        return
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault()
        selectCommand(filteredCommands[selectedCommandIndex].name)
        return
      }
      if (e.key === 'Escape') {
        e.preventDefault()
        setShowCommandMenu(false)
        return
      }
    }

    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSubmit(e)
    }
  }

  // Source badge label for command menu items
  const sourceBadgeLabel = (source: string) => {
    switch (source) {
      case 'user_skill': return 'skill'
      case 'bot_instruction': return 'bot'
      case 'cli': return 'cli'
      case 'group': return ''
      default: return ''
    }
  }

  // Shared command menu renderer
  const renderCommandMenu = () => {
    if (!showCommandMenu || filteredCommands.length === 0) return null
    return (
      <div className="chat-command-menu">
        <div className="chat-command-menu__header">Commands</div>
        <div className="chat-command-menu__list">
          {filteredCommands.map((cmd, index) => {
            const badge = sourceBadgeLabel(cmd.source)
            return (
              <button
                key={cmd.name}
                type="button"
                onClick={() => selectCommand(cmd.name)}
                className={cn(
                  'chat-command-menu__item',
                  index === selectedCommandIndex && 'chat-command-menu__item--selected'
                )}
              >
                <span className="text-lg">{cmd.icon}</span>
                <div className="flex-1 min-w-0">
                  <div className="font-medium flex items-center gap-1.5">
                    /{cmd.name}
                    {badge && (
                      <span className={cn('chat-command-badge', `chat-command-badge--${cmd.source}`)}>{badge}</span>
                    )}
                  </div>
                  <div className="text-xs text-[var(--color-text-secondary)] truncate">{cmd.description}</div>
                </div>
                {index === selectedCommandIndex && (
                  <span className="text-xs text-[var(--color-text-secondary)]">↵</span>
                )}
              </button>
            )
          })}
        </div>
      </div>
    )
  }

  // Shared composer renderer (hero omnibox and docked bar)
  const renderComposer = (placeholder: string) => (
    <>
      <div className="chat-input-container chat-input-container--island v2-composer">
        <input
          ref={fileInputRef}
          type="file"
          className="v2-composer__file"
          onChange={handleFilePicked}
          tabIndex={-1}
          aria-hidden="true"
        />
        {renderCommandMenu()}
        {renderAgentMentionPopup()}
        <button
          type="button"
          className={cn('v2-composer__plus', plusMenuOpen && 'v2-composer__plus--menu-open')}
          title="Attach or add"
          aria-label="Attach or add"
          aria-haspopup="menu"
          aria-expanded={plusMenuOpen}
          disabled={!canOperate}
          onClick={() => setPlusMenuOpen((o) => !o)}
        >
          <Plus size={17} strokeWidth={1.8} />
        </button>
        {plusMenuOpen && (
          <V2Menu className="v2-composer-menu" onClose={() => setPlusMenuOpen(false)}>
            <V2MenuItem
              icon={<Paperclip size={16} strokeWidth={1.8} />}
              onClick={() => {
                setPlusMenuOpen(false)
                fileInputRef.current?.click()
              }}
            >
              Attach file
            </V2MenuItem>
            {canOperate && (
              <V2MenuItem
                icon={<GitBranch size={16} strokeWidth={1.8} />}
                onClick={() => {
                  setPlusMenuOpen(false)
                  // Prefill from what was typed in the composer (if anything)
                  // and hand it to the side task instead of the main chat.
                  // No source message: the backend quotes the latest user
                  // message of the chat (documented fallback).
                  setSideTaskPrefill(input)
                  setSideTaskSource(null)
                  setInput('')
                }}
              >
                Side task
              </V2MenuItem>
            )}
          </V2Menu>
        )}
        <textarea
          ref={textareaRef}
          value={input}
          onChange={(e) => handleInputChange(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={!isConnected || creationFlow.isLoadingNames || !canOperate}
          rows={1}
          className="v2-composer__input"
        />
        {canOperate && !isInCreationFlow && (
          <button
            type="button"
            className="v2-composer__talk"
            title="Talk"
            aria-label="Talk"
            onClick={() => setVoiceMode(true)}
          >
            <Mic size={18} strokeWidth={1.8} />
          </button>
        )}
        {isLoading ? (
          <button
            type="button"
            onClick={handleStop}
            className="v2-composer__send v2-composer__send--stop"
            title="Stop"
            aria-label="Stop"
          >
            <Square size={15} strokeWidth={1.8} />
          </button>
        ) : (
          <button
            type="submit"
            disabled={!input.trim() || !isConnected || !canOperate}
            className="v2-composer__send"
            title="Send message"
            aria-label="Send message"
          >
            <Send size={17} strokeWidth={1.8} />
          </button>
        )}
      </div>
      {/* Island footer — model pill + status + hint */}
      <div className="chat-island__footer">
        <ModelPill
          value={selectedModel}
          onChange={setSelectedModel}
          placeholder={getBotDefaultModel(activeBot!) || 'System Default'}
          openRef={modelPillOpenRef}
        />
        <span className="chat-island__status">
          <span
            className={cn(
              'chat-status-bar__dot',
              isConnected ? 'chat-status-bar__dot--connected' : 'chat-status-bar__dot--disconnected'
            )}
          />
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
        <span className="chat-island__hint">Press Enter to send, Shift+Enter for new line</span>
      </div>
      {attachStatus && <div className="v2-attach-status">{attachStatus}</div>}
    </>
  )

  // Artifact panel state (must be before any early returns)
  const activeArtifactId = useArtifactsStore((s) => s.activeArtifactId)
  const panelOpen = useArtifactsStore((s) => s.panelOpen)
  const activeArtifact = useArtifactsStore((s) => activeArtifactId ? s.artifacts[activeArtifactId] : undefined)
  const closeArtifactPanel = useArtifactsStore((s) => s.closePanel)
  const panelWidthRatio = useArtifactsStore((s) => s.panelWidthRatio)
  const setPanelWidthRatio = useArtifactsStore((s) => s.setPanelWidthRatio)

  // Resize drag state
  const wrapperRef = useRef<HTMLDivElement>(null)
  const isDraggingRef = useRef(false)

  const handleDividerMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault()
    isDraggingRef.current = true
    document.body.style.cursor = 'col-resize'
    document.body.style.userSelect = 'none'

    const onMouseMove = (ev: MouseEvent) => {
      if (!isDraggingRef.current || !wrapperRef.current) return
      const rect = wrapperRef.current.getBoundingClientRect()
      const ratio = 1 - (ev.clientX - rect.left) / rect.width
      setPanelWidthRatio(ratio)
    }

    const onMouseUp = () => {
      isDraggingRef.current = false
      document.body.style.cursor = ''
      document.body.style.userSelect = ''
      document.removeEventListener('mousemove', onMouseMove)
      document.removeEventListener('mouseup', onMouseUp)
    }

    document.addEventListener('mousemove', onMouseMove)
    document.addEventListener('mouseup', onMouseUp)
  }, [setPanelWidthRatio])

  const showPanel = panelOpen && activeArtifact

  // Chat header — just the bot (design views 02/14): the bot name opens Bot
  // settings, Files opens the Files sheet (design 10), the history icon keeps
  // "Earlier chats", and the "..." menu holds Runs / Routines / Knowledge /
  // plugin pages / Export / Clear. Rendered in every chat state, including
  // the empty hero. Below 1024px the whole row is hidden (mobile top bar
  // carries avatar/name/history; Files lives in its More menu).
  const chatHeader = (
    <>
      <div className="chat-header">
        <div className="chat-header__bot-info">
          {activeBot && (
            <>
              <BotAvatar color={activeBot.color} name={activeBot.name} size={30} />
              {canEditBot ? (
                <button
                  type="button"
                  className="chat-header__name chat-header__name--link"
                  title="Bot settings"
                  onClick={() => {
                    useUIStore.getState().setSettingsSection('general')
                    navigate(`/${activeBot.id}/settings`)
                  }}
                >
                  {activeBot.name}
                </button>
              ) : (
                <h2 className="chat-header__name">{activeBot.name}</h2>
              )}
            </>
          )}
        </div>
        {activeBot && (
          <div className="chat-header__actions">
            {computerAvailable && (
              <button
                type="button"
                className="v2-files-btn"
                aria-label="Computer"
                title="Computer"
                aria-pressed={inspectorOpen}
                onClick={() => useUIStore.getState().toggleInspector()}
              >
                <Monitor size={15} strokeWidth={1.8} />
                Computer
              </button>
            )}
            <button
              type="button"
              className="v2-files-btn"
              aria-label="Files"
              title="Files"
              onClick={() => setShowFiles(true)}
            >
              <FolderOpen size={15} strokeWidth={1.8} />
              Files
            </button>
            <button
              type="button"
              className="v2-icon-btn"
              aria-label="Earlier chats"
              title="Earlier chats"
              onClick={() => setShowChats(true)}
            >
              <History size={18} strokeWidth={1.8} />
            </button>
            <button
              type="button"
              className="v2-icon-btn"
              aria-label="More"
              title="More"
              aria-haspopup="menu"
              aria-expanded={showMoreMenu}
              onClick={(e) => { e.stopPropagation(); setShowMoreMenu((o) => !o) }}
            >
              <MoreHorizontal size={18} strokeWidth={1.8} />
            </button>
            {showMoreMenu && (
              <ChatMoreMenu
                bot={activeBot}
                chat={activeChatId ? chats.find((c) => c.id === activeChatId) ?? null : null}
                onClose={() => setShowMoreMenu(false)}
              />
            )}
          </div>
        )}
      </div>
      {showChats && activeBot && (
        <ChatsSheet bot={activeBot} onClose={() => setShowChats(false)} />
      )}
      {showFiles && activeBot && (
        <FilesSheet bot={activeBot} onClose={() => setShowFiles(false)} />
      )}
    </>
  )

  const composerPlaceholder = !canOperate
    ? 'View-only access'
    : creationFlow.step === 'name'
      ? 'Type a number (1-4), your own name, or "more"...'
      : `Message ${activeBot?.name || 'CachiBot'} or type / for commands...`

  // Start-a-side-task dialog (message More / composer +), rendered over both
  // the hero and the docked chat so the flow works from either composer.
  const sideTaskDialog =
    sideTaskPrefill !== null && activeBotId && activeChatId ? (
      <StartSideTaskDialog
        botId={activeBotId}
        chatId={activeChatId}
        initialPrompt={sideTaskPrefill}
        sourceMessageId={sideTaskSource}
        onClose={() => {
          setSideTaskPrefill(null)
          setSideTaskSource(null)
        }}
      />
    ) : null

  // The open chat is a side task's own chat (design 11b): child header,
  // backend history, state card. No composer — there is no backend path to
  // resume a needs-you side task from a reply (documented in UI_V2_PLAN).
  if (sideTaskForChat && activeBot) {
    return (
      <div className="chat-view">
        {sideTaskDialog}
        <SideTaskChatView task={sideTaskForChat} bot={activeBot} canOperate={canOperate} />
      </div>
    )
  }

  // Voice mode (design 15): the same chat switches to voice — big avatar,
  // live transcript lines, bottom bar with mic/waveform/Interrupt/Back.
  // Transcripts are saved into this chat by the voice pipeline.
  if (voiceMode && activeBot && canOperate) {
    return (
      <div className="chat-view">
        {chatHeader}
        <VoiceMode bot={activeBot} ensureChat={ensureChatId} onExit={() => setVoiceMode(false)} />
      </div>
    )
  }

  // Empty state — hero omnibox start state (no chat or chat with no messages)
  if (messages.length === 0) {
    return (
      <div className="chat-view chat-view--hero">
        {chatHeader}
        {sideTaskDialog}
        <div className="chat-view--hero__body">
        {/* Hero title */}
        <div className="chat-hero">
          <h2 className="chat-hero__title">
            What can {activeBot?.name || 'CachiBot'} help you with today?
          </h2>
          <p className="chat-hero__subtitle">
            {activeBot?.description || 'Start a conversation to get help with coding, analysis, and more.'}
          </p>
        </div>

        {/* Omnibox island */}
        <div className="chat-island">
          <form onSubmit={handleSubmit} className="chat-island__form">
            {renderComposer(composerPlaceholder)}
          </form>

          {availableWorkspaces.length > 0 && (
            <WorkspaceSelector
              workspaces={availableWorkspaces}
              activeWorkspace={activeWorkspace}
              onSelect={handleWorkspaceSelect}
            />
          )}
        </div>
        </div>
      </div>
    )
  }

  return (
    <div ref={wrapperRef} className={cn('chat-view-wrapper', showPanel && 'chat-view-wrapper--split')}>
    <div className={cn('chat-view', showPanel && 'chat-view--with-panel')} style={showPanel ? { flex: `0 0 ${(1 - panelWidthRatio) * 100}%` } : undefined}>
      {chatHeader}
      {sideTaskDialog}

      {/* Messages area */}
      <div className="chat-messages" ref={scrollContainerRef} onScroll={handleScroll}>
        <div className="chat-messages__inner">
          {findOpen && (
            <FindInChatBar
              query={findQuery}
              onQueryChange={setFindQuery}
              current={findCurrent}
              total={findTotal}
              onPrev={handleFindPrev}
              onNext={handleFindNext}
              onClose={() => setFindOpen(false)}
            />
          )}

          <div className="chat-messages__list" ref={listRef}>
            {(() => {
              const out: React.ReactNode[] = []
              let lastDayKey: string | null = null
              messages.forEach((msg, index) => {
                const key = dayKeyOf(msg.timestamp)
                if (key !== lastDayKey) {
                  lastDayKey = key
                  out.push(
                    <p key={`sep-${key}-${out.length}`} className="v2-day-sep">
                      {dayLabel(msg.timestamp)}
                    </p>
                  )
                }
                const singleReply = sideTaskReplyMetadata(msg.metadata)
                const groupReply = singleReply ? null : sideTaskGroupReplyMetadata(msg.metadata)
                if (singleReply && activeBotId) {
                  // A settled side task: the thread reply persisted by the
                  // backend (quotes this message, opens the child chat).
                  out.push(
                    <SideTaskReplyView
                      key={msg.id}
                      metadata={singleReply}
                      content={msg.content}
                      chatId={activeChatId || ''}
                      replyToId={msg.replyToId ?? null}
                      botId={activeBotId}
                      canOperate={canOperate}
                    />
                  )
                } else if (groupReply && activeBotId) {
                  out.push(
                    <SideTaskGroupReplyView
                      key={msg.id}
                      metadata={groupReply}
                      content={msg.content}
                      chatId={activeChatId || ''}
                      replyToId={msg.replyToId ?? null}
                      botId={activeBotId}
                    />
                  )
                } else {
                  out.push(
                    <MessageBubbleV2
                      key={msg.id}
                      message={{
                        id: msg.id,
                        content: msg.content,
                        timestamp: msg.timestamp,
                        isUser: msg.role === 'user',
                        isSystem: msg.role === 'system',
                        toolCalls: msg.toolCalls,
                        metadata: msg.metadata,
                        replyToId: msg.replyToId,
                        thinking: msg.thinking,
                      }}
                      botName={activeBot?.name || 'CachiBot'}
                      botColor={activeBot?.color}
                      chatId={activeChatId || ''}
                      isStreaming={isLoading && runVisibleHere && index === messages.length - 1 && msg.role === 'assistant'}
                      onReply={() => setReplyTo(msg)}
                      onRegenerate={msg.role === 'assistant' ? () => regenerateFrom(index) : undefined}
                      onEditSend={(text) => handleEditSend(msg.id, text)}
                      onDoOnSide={canOperate ? () => handleDoOnSide(msg.content, msg.id) : undefined}
                    />
                  )
                }
                // Quiet one-line indicator while side tasks from this message
                // wait or run (design 11a "Side-task replies").
                const activeHere = activeSinglesBySource[msg.id]
                if (activeHere && activeHere.length > 0) {
                  out.push(<SideTaskIndicator key={`st-${msg.id}`} tasks={activeHere} />)
                }
              })
              return out
            })()}
          </div>

          {/* Inline approval cards for this chat (design 03 — never block) */}
          {chatApprovals.map((approval) => (
            <ApprovalCard key={approval.id} approval={approval} onAnswer={answerApproval} />
          ))}

          {/* The bot's computer needs a person (design 08) — real C2 state */}
          {computerAvailable && activeBot && botComputer?.state === 'needs_you' && (
            <ComputerNeedsYouCard
              reason={botComputer.needsYou || `${activeBot.name} needs you on its computer.`}
              onTakeOver={
                canOperate
                  ? () => void useComputerStore.getState().respondNeedsYou(activeBot.id, 'takeover')
                  : undefined
              }
              onSkip={
                canOperate
                  ? () => void useComputerStore.getState().respondNeedsYou(activeBot.id, 'skip')
                  : undefined
              }
            />
          )}

          {/* You hold the take-over — the hand-back line (design 08) */}
          {computerAvailable && activeBot && botDriver && botDriver.userId === currentUserId && (
            <ComputerDrivingLine
              since={botDriver.since}
              onHandBack={() => void useComputerStore.getState().handback(activeBot.id)}
            />
          )}

          {/* Failed-turn card from the real WS error event */}
          {showErrorCard && (
            <ErrorCard
              message={runError!.message}
              code={runError!.code}
              onTryAgain={handleTryAgain}
              onChangeModel={handleChangeModel}
            />
          )}

          {/* Stopped line — you pressed stop, not an error (design 03) */}
          {!isLoading && !runError && stoppedUserMessageId && (
            <StoppedLine onContinue={handleContinueStopped} />
          )}

          {/* Tool calls in progress */}
          {toolCalls.length > 0 && runVisibleHere && (
            <div className="mt-6 space-y-2">
              {toolCalls.map((call) => (
                <ToolCallDisplay key={call.id} call={call} />
              ))}
            </div>
          )}

          {/* Typing indicator (when loading but no thinking content) — quiet
              v2 status line with the bot's real color as the small mark */}
          {isLoading && !thinking && toolCalls.length === 0 && runVisibleHere && (
            <div className="mt-6">
              <StatusLine pending markColor={activeBot?.color}>
                {activeBot?.name ? `${activeBot.name} is working` : 'Generating response'}
              </StatusLine>
            </div>
          )}

          {/* Thinking indicator */}
          {thinking && showThinking && runVisibleHere && (
            <div className="mt-6">
              <ThinkingIndicator
                content={thinking}
                label={activeBot?.name ? `${activeBot.name} is thinking` : 'Thinking'}
                markColor={activeBot?.color}
              />
            </div>
          )}

          {/* Workspace task progress */}
          {taskProgress && (
            <div className="mt-6">
              <TaskProgress progress={taskProgress} />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Jump to latest (design 03) */}
        {scrolledUp && (newCount > 0 || isLoading) && (
          <button type="button" className="v2-jump-pill" onClick={jumpToLatest}>
            <ArrowDown size={14} strokeWidth={1.8} />
            {newCount > 0 ? `${newCount} new message${newCount === 1 ? '' : 's'}` : 'Jump to latest'}
          </button>
        )}
      </div>

      {/* Input island — docked at bottom */}
      <div className={cn(
        'chat-island chat-island--docked',
        animateIsland && 'chat-island--animate-in'
      )}>
        <form onSubmit={handleSubmit} className="chat-island__form">
          {/* Reply composer bar */}
          {replyToMessage && (
            <div className="chat-reply-bar">
              <Reply className="chat-reply-bar__icon" />
              <div className="chat-reply-bar__content">
                <span className="chat-reply-bar__label">
                  Replying to {replyToMessage.role === 'user' ? 'You' : (activeBot?.name || 'Assistant')}
                </span>
                <p className="chat-reply-bar__text">
                  {replyToMessage.content.slice(0, 100)}{replyToMessage.content.length > 100 ? '...' : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReplyTo(null)}
                className="chat-reply-bar__close"
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          )}

          {/* Workspace badge */}
          {workspaceConfig && (
            <div
              className="workspace-badge"
              style={workspaceConfig.accentColor ? { borderColor: workspaceConfig.accentColor } : undefined}
            >
              <span className="workspace-badge__name">{workspaceConfig.displayName}</span>
              <button
                type="button"
                className="workspace-badge__close"
                onClick={clearWorkspace}
              >
                <X className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Workspace selector (shown when chat is empty) */}
          {messages.length === 0 && availableWorkspaces.length > 0 && (
            <WorkspaceSelector
              workspaces={availableWorkspaces}
              activeWorkspace={activeWorkspace}
              onSelect={handleWorkspaceSelect}
            />
          )}

          {renderComposer(composerPlaceholder)}

          {/* Creation flow indicator */}
          {isInCreationFlow && (
            <div className="chat-creation-flow">
              {creationFlow.isLoadingNames ? (
                <>
                  <Spinner size="sm" label="" aria-hidden="true" />
                  <span>Generating name suggestions...</span>
                </>
              ) : (
                <>
                  <Sparkles className="h-3 w-3" />
                  <span>
                    Creating a new bot (Step: {creationFlow.step})... Type &apos;cancel&apos; to stop
                  </span>
                </>
              )}
            </div>
          )}
        </form>
      </div>

    </div>
    {/* Artifact side panel */}
    {showPanel && (
      <>
        <div
          className="artifact-divider"
          onMouseDown={handleDividerMouseDown}
        />
        <ArtifactPanel
          artifact={activeArtifact}
          onClose={closeArtifactPanel}
          style={{ flex: `0 0 ${panelWidthRatio * 100}%` }}
        />
      </>
    )}
    </div>
  )
}

// =============================================================================
// TOOL CALL DISPLAY (Active/streaming tool calls)
// =============================================================================

// Map tool names to bot model slots
const TOOL_MODEL_SLOTS: Record<string, string> = {
  generate_image: 'image',
  generate_audio: 'audio',
  transcribe_audio: 'audio',
}

function getToolModel(toolName: string): string | undefined {
  const slot = TOOL_MODEL_SLOTS[toolName]
  if (!slot) return undefined
  const bot = useBotStore.getState().getActiveBot()
  return bot?.models?.[slot as keyof BotModels] || undefined
}

function ToolCallDisplay({ call }: { call: ToolCall }) {
  const resultStr = typeof call.result === 'string' ? call.result : JSON.stringify(call.result ?? '', null, 2)
  const hasMedia = isMediaResult(call.result)
  const [expanded, setExpanded] = useState(hasMedia)
  const isComplete = call.endTime !== undefined
  const isSuccess = call.success === true
  const toolModel = getToolModel(call.tool)

  // Live elapsed while the tool runs, measured from the call's real
  // startTime (design 03 work line "… · 0:42"); stops when the call ends.
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (isComplete) return
    const id = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(id)
  }, [isComplete])

  // Auto-expand when media result arrives
  useEffect(() => {
    if (hasMedia && !expanded) setExpanded(true)
  }, [hasMedia, expanded])

  return (
    <div className="chat-tool-call">
      <button
        onClick={() => setExpanded(!expanded)}
        className="chat-tool-call__header"
        aria-expanded={expanded}
      >
        {!isComplete ? (
          <Spinner size="sm" label="" aria-hidden="true" />
        ) : isSuccess ? (
          <Check className="chat-tool-call__status chat-tool-call__status--success" />
        ) : (
          <XCircle className="chat-tool-call__status chat-tool-call__status--error" />
        )}

        <span className="chat-tool-call__name">
          {isComplete ? call.tool : `Running ${call.tool} · ${formatToolElapsed(call.startTime, now)}`}
        </span>
        {toolModel && (
          <span className="chat-tool-call__model">
            {toolModel}
          </span>
        )}

        <ChevronDown
          className={cn(
            'chat-tool-call__chevron',
            expanded && 'chat-tool-call__chevron--open'
          )}
        />
      </button>

      {expanded && (
        <div className="chat-tool-call__body">
          <div className="space-y-3 text-xs">
            <div className="font-mono">
              <span className="text-[var(--color-text-secondary)]">Arguments:</span>
              <pre className="chat-tool-call__code">
                {JSON.stringify(call.args, null, 2)}
              </pre>
            </div>
            {call.result !== undefined && (
              <div>
                <span className="font-mono text-[var(--color-text-secondary)]">Result:</span>
                {hasMedia ? (
                  <div className="mt-1">
                    <MarkdownRenderer content={resultStr} />
                  </div>
                ) : (
                  <pre className="chat-tool-call__code">
                    {resultStr}
                  </pre>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

/** "0:42" / "1:52" elapsed, measured from a real start timestamp (ms). */
function formatToolElapsed(startTime: number, now: number): string {
  const secs = Math.max(0, Math.floor((now - startTime) / 1000))
  return `${Math.floor(secs / 60)}:${String(secs % 60).padStart(2, '0')}`
}

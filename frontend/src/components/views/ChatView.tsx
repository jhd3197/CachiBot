import { useRef, useEffect, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Send,
  Square,
  Paperclip,
  Sparkles,
  ChevronDown,
  Code,
  Zap,
  CheckCircle,
  XCircle,
  Loader2,
  Reply,
  X,
} from 'lucide-react'
import { useChatStore, useBotStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { useCreationFlowStore } from '../../stores/creation-flow'
import { useModelsStore } from '../../stores/models'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { MarkdownRenderer } from '../common/MarkdownRenderer'
import { cn } from '../../lib/utils'
import { detectLanguage } from '../../lib/language-detector'
import { generateBotNames } from '../../api/client'
import { generateSystemPrompt } from '../../lib/prompt-generator'
import { useWebSocket, setPendingChatId } from '../../hooks/useWebSocket'
import { useCommands } from '../../hooks/useCommands'
import { useBotAccess } from '../../hooks/useBotAccess'
import { MessageBubble, isMediaResult } from '../chat/MessageBubble'
import type { ToolCall, BotIcon, BotModels, Chat, Bot } from '../../types'

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

interface ChatViewProps {
  onSendMessage?: (message: string) => void
  onCancel?: () => void
  isConnected?: boolean
}

export function ChatView({ onSendMessage, onCancel, isConnected: isConnectedProp }: ChatViewProps) {
  const navigate = useNavigate()
  const { activeChatId, getMessages, thinking, toolCalls, isLoading, addMessage, addChat, setActiveChat, replyToMessage, setReplyTo } = useChatStore()
  const { getActiveBot, activeBotId, bots, addBot, setActiveBot } = useBotStore()
  const { showThinking } = useUIStore()
  const creationFlow = useCreationFlowStore()
  const { sendMessage: wsSendMessage, cancel: wsCancel, isConnected: wsIsConnected } = useWebSocket()
  const { isCommand, handleCommand } = useCommands()
  const { canOperate } = useBotAccess(activeBotId)

  // Use prop values if provided, otherwise fall back to WebSocket hook values
  const isConnected = isConnectedProp ?? wsIsConnected
  const handleCancel = onCancel ?? wsCancel
  const [input, setInput] = useState('')
  const [flowUserInputs, setFlowUserInputs] = useState<string[]>([])
  const [showCommandMenu, setShowCommandMenu] = useState(false)
  const [selectedCommandIndex, setSelectedCommandIndex] = useState(0)
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  // Command definitions for autocomplete
  const SLASH_COMMANDS = [
    { name: 'new', description: 'Create a new bot', icon: '✨' },
    { name: 'list', description: 'View all your bots', icon: '📋' },
    { name: 'help', description: 'Show available commands', icon: '❓' },
    { name: 'settings', description: 'Open settings', icon: '⚙️' },
    { name: 'start', description: 'Welcome message', icon: '👋' },
  ]

  // Filter commands based on input
  const filteredCommands = input.startsWith('/')
    ? SLASH_COMMANDS.filter(cmd =>
        cmd.name.toLowerCase().startsWith(input.slice(1).toLowerCase())
      )
    : []

  // Show command menu when typing "/"
  useEffect(() => {
    if (input === '/' || (input.startsWith('/') && input.length > 1 && filteredCommands.length > 0)) {
      setShowCommandMenu(true)
      setSelectedCommandIndex(0)
    } else {
      setShowCommandMenu(false)
    }
  }, [input, filteredCommands.length])

  const messages = activeChatId ? getMessages(activeChatId) : []
  const activeBot = getActiveBot()
  const isInCreationFlow = creationFlow.step !== 'idle'

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

  // Auto-scroll to bottom
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, thinking, toolCalls])

  // Auto-resize textarea
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto'
      textareaRef.current.style.height = Math.min(textareaRef.current.scrollHeight, 200) + 'px'
    }
  }, [input])

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault()
    if (!input.trim() || isLoading) return

    const trimmedInput = input.trim()
    const lowerInput = trimmedInput.toLowerCase()

    // Handle slash commands (except /create which uses the special flow)
    if (isCommand(trimmedInput) && lowerInput !== '/create' && !isInCreationFlow) {
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

    // Normal message handling - use WebSocket with bot's systemPrompt
    if (onSendMessage) {
      onSendMessage(trimmedInput)
    } else {
      // Auto-create a chat if none is active
      let chatIdToUse = activeChatId
      if (!chatIdToUse && activeBotId) {
        const newChatId = crypto.randomUUID()
        const newChat: Chat = {
          id: newChatId,
          botId: activeBotId,
          title: trimmedInput.slice(0, 50) + (trimmedInput.length > 50 ? '...' : ''),
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
          messageCount: 0,
        }
        addChat(newChat)
        setActiveChat(newChatId)
        chatIdToUse = newChatId
        // Set pending chat ID for WebSocket messages that arrive before state updates
        setPendingChatId(newChatId)
        // Navigate to the new chat URL for persistence on refresh
        navigate(`/${activeBotId}/chats/${newChatId}`)
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
      }

      wsSendMessage(trimmedInput, {
        systemPrompt: activeBot?.systemPrompt,
        botId: activeBot?.id,
        chatId: chatIdToUse ?? undefined,
        model: activeBot?.model,
        models: activeBot?.models,
        capabilities: activeBot?.capabilities || defaultCapabilities,
        toolConfigs: activeBot?.toolConfigs,
        replyToId: replyToMessage?.id,
      })
    }
    setInput('')
    setReplyTo(null)
  }

  // Select a command from the autocomplete menu
  const selectCommand = (commandName: string) => {
    setInput(`/${commandName}`)
    setShowCommandMenu(false)
    textareaRef.current?.focus()
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
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

  // Shared command menu renderer
  const renderCommandMenu = () => {
    if (!showCommandMenu || filteredCommands.length === 0) return null
    return (
      <div className="chat-command-menu">
        <div className="chat-command-menu__header">Commands</div>
        <div className="chat-command-menu__list">
          {filteredCommands.map((cmd, index) => (
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
                <div className="font-medium">/{cmd.name}</div>
                <div className="text-xs text-[var(--color-text-secondary)] truncate">{cmd.description}</div>
              </div>
              {index === selectedCommandIndex && (
                <span className="text-xs text-[var(--color-text-secondary)]">↵</span>
              )}
            </button>
          ))}
        </div>
      </div>
    )
  }

  // Empty state when no chat is selected - but still allow sending messages
  if (!activeChatId) {
    return (
      <div className="chat-view">
        {/* Welcome content */}
        <div className="flex flex-1 items-center justify-center p-8">
          <div className="max-w-md text-center">
            <div
              className="chat-empty__icon mx-auto"
              style={{ backgroundColor: (activeBot?.color || '#22c55e') + '30' }}
            >
              <BotIconRenderer
                icon={activeBot?.icon || 'shield'}
                size={48}
                className="text-[var(--color-text-primary)]"
              />
            </div>
            <h2 className="chat-empty__title">
              Welcome to {activeBot?.name || 'CachiBot'}
            </h2>
            <p className="chat-empty__description">
              {activeBot?.description || 'Start a new chat to begin working with your AI assistant.'}
            </p>
            <div className="chat-prompt-suggestions">
              {['Write a Python script', 'Analyze this codebase', 'Help me debug an error'].map((prompt) => (
                <button
                  key={prompt}
                  onClick={() => {
                    setInput(prompt)
                    textareaRef.current?.focus()
                  }}
                  className="chat-prompt-suggestions__item"
                >
                  <Sparkles className="h-4 w-4 text-cachi-500" />
                  {prompt}
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Input area - allows starting a new chat */}
        <div className="chat-panel__input-area">
          <form onSubmit={handleSubmit} className="chat-panel__input-inner">
            <div className="chat-input-container">
              {renderCommandMenu()}
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={`Message ${activeBot?.name || 'CachiBot'} or type / for commands...`}
                disabled={!isConnected || isLoading || !canOperate}
                rows={1}
                className="chat-textarea"
              />
              <div className="chat-input-btns">
                <button
                  type="button"
                  className="chat-input-btn chat-input-btn--attach"
                  title="Attach file"
                  disabled={!canOperate}
                >
                  <Paperclip className="h-4 w-4" />
                </button>
                <button
                  type="submit"
                  disabled={!input.trim() || !isConnected || !canOperate}
                  className="chat-input-btn chat-input-btn--send"
                  title="Send message"
                >
                  <Send className="h-4 w-4" />
                </button>
              </div>
            </div>
            <div className="chat-status-bar">
              <div className="chat-status-bar__indicator">
                <span
                  className={cn(
                    'chat-status-bar__dot',
                    isConnected ? 'chat-status-bar__dot--connected' : 'chat-status-bar__dot--disconnected'
                  )}
                />
                {isConnected ? 'Connected' : 'Disconnected'}
              </div>
              <span className="chat-status-bar__hint">Press Enter to send, Shift+Enter for new line</span>
            </div>
          </form>
        </div>
      </div>
    )
  }

  return (
    <div className="chat-view">
      {/* Chat header with bot info and settings */}
      <div className="chat-header">
        <div className="chat-header__bot-info">
          <div
            className="chat-header__avatar"
            style={{ backgroundColor: (activeBot?.color || '#22c55e') + '30' }}
          >
            <BotIconRenderer
              icon={activeBot?.icon || 'shield'}
              size={18}
              className="text-[var(--color-text-primary)]"
            />
          </div>
          <div>
            <h2 className="chat-header__name">
              {activeBot?.name || 'CachiBot'}
            </h2>
            <p className="chat-header__model">{activeBot?.model || useModelsStore.getState().defaultModel || 'No model set'}</p>
          </div>
        </div>
      </div>

      {/* Messages area */}
      <div className="chat-messages">
        <div className="chat-messages__inner">
          {messages.length === 0 ? (
            <div className="py-12 text-center">
              <Sparkles className="mx-auto mb-4 h-8 w-8 text-cachi-500" />
              <p className="text-[var(--color-text-secondary)]">Start the conversation...</p>
            </div>
          ) : (
            <div className="chat-messages__list">
              {messages.map((msg) => (
                <MessageBubble
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
                  }}
                  botIcon={activeBot?.icon}
                  botColor={activeBot?.color}
                  chatId={activeChatId || ''}
                  onReply={() => setReplyTo(msg)}
                />
              ))}
            </div>
          )}

          {/* Tool calls in progress */}
          {toolCalls.length > 0 && (
            <div className="mt-6 space-y-2">
              {toolCalls.map((call) => (
                <ToolCallDisplay key={call.id} call={call} />
              ))}
            </div>
          )}

          {/* Typing indicator (when loading but no thinking content) */}
          {isLoading && !thinking && toolCalls.length === 0 && (
            <div className="mt-6">
              <TypingIndicator botColor={activeBot?.color} />
            </div>
          )}

          {/* Thinking indicator */}
          {thinking && showThinking && (
            <div className="mt-6">
              <ThinkingIndicator content={thinking} />
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="chat-panel__input-area">
        <form onSubmit={handleSubmit} className="chat-panel__input-inner">
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
          <div className="chat-input-container">
            {renderCommandMenu()}
            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={
                !canOperate
                  ? 'View-only access'
                  : creationFlow.step === 'name'
                    ? 'Type a number (1-4), your own name, or "more"...'
                    : `Message ${activeBot?.name || 'CachiBot'} or type / for commands...`
              }
              disabled={!isConnected || isLoading || creationFlow.isLoadingNames || !canOperate}
              rows={1}
              className="chat-textarea"
            />

            {/* Actions */}
            <div className="chat-input-btns">
              <button
                type="button"
                className="chat-input-btn chat-input-btn--attach"
                title="Attach file"
                disabled={!canOperate}
              >
                <Paperclip className="h-4 w-4" />
              </button>

              {isLoading ? (
                <button
                  type="button"
                  onClick={handleCancel}
                  className="chat-input-btn chat-input-btn--stop"
                  title="Stop"
                >
                  <Square className="h-4 w-4" />
                </button>
              ) : (
                <button
                  type="submit"
                  disabled={!input.trim() || !isConnected || !canOperate}
                  className="chat-input-btn chat-input-btn--send"
                  title="Send message"
                >
                  <Send className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>

          {/* Status bar */}
          <div className="chat-status-bar">
            <div className="chat-status-bar__left">
              <span className="chat-status-bar__indicator">
                <span
                  className={cn(
                    'chat-status-bar__dot',
                    isConnected ? 'chat-status-bar__dot--connected' : 'chat-status-bar__dot--disconnected'
                  )}
                />
                <span className="chat-status-bar__label">{isConnected ? 'Connected' : 'Disconnected'}</span>
              </span>
              <span className="chat-status-bar__model">{activeBot?.model}</span>
            </div>
            <span className="chat-status-bar__hint">Press Enter to send, Shift+Enter for new line</span>
          </div>

          {/* Creation flow indicator */}
          {isInCreationFlow && (
            <div className="chat-creation-flow">
              {creationFlow.isLoadingNames ? (
                <>
                  <Loader2 className="h-3 w-3 animate-spin" />
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

  // Auto-expand when media result arrives
  useEffect(() => {
    if (hasMedia && !expanded) setExpanded(true)
  }, [hasMedia, expanded])

  return (
    <div className="chat-tool-call">
      <button
        onClick={() => setExpanded(!expanded)}
        className="chat-tool-call__header"
      >
        {!isComplete ? (
          <Loader2 className="h-4 w-4 animate-spin text-blue-400" />
        ) : isSuccess ? (
          <CheckCircle className="h-4 w-4 text-green-400" />
        ) : (
          <XCircle className="h-4 w-4 text-red-400" />
        )}

        <Code className="h-4 w-4 text-[var(--color-text-secondary)]" />
        <span className="chat-tool-call__name">{call.tool}</span>
        {toolModel && (
          <span className="chat-tool-call__model">
            {toolModel}
          </span>
        )}

        <ChevronDown
          className={cn(
            'h-4 w-4 text-[var(--color-text-secondary)] transition-transform',
            expanded && 'rotate-180'
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

// =============================================================================
// THINKING INDICATOR
// =============================================================================

function ThinkingIndicator({ content }: { content: string }) {
  return (
    <div className="chat-thinking">
      <div className="chat-thinking__icon">
        <Zap className="h-5 w-5 animate-pulse text-purple-400" />
      </div>
      <div className="chat-thinking__body">
        <div className="chat-thinking__label">Thinking...</div>
        <div className="chat-thinking__content">{content}</div>
      </div>
    </div>
  )
}

// =============================================================================
// TYPING INDICATOR (Clean loading state)
// =============================================================================

function TypingIndicator({ botColor }: { botColor?: string }) {
  return (
    <div className="chat-typing">
      <div
        className="chat-typing__icon"
        style={{ backgroundColor: (botColor || '#22c55e') + '30' }}
      >
        <Loader2 className="h-5 w-5 animate-spin" style={{ color: botColor || '#22c55e' }} />
      </div>
      <div className="chat-typing__body">
        <div className="chat-typing__text">
          <span>Generating response</span>
          <span className="chat-typing__dots">
            <span className="animate-pulse" style={{ animationDelay: '0ms' }}>.</span>
            <span className="animate-pulse" style={{ animationDelay: '200ms' }}>.</span>
            <span className="animate-pulse" style={{ animationDelay: '400ms' }}>.</span>
          </span>
        </div>
      </div>
    </div>
  )
}

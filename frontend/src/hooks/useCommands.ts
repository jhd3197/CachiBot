import { useCallback, useEffect, useState } from 'react'
import { useUIStore } from '../stores/ui'
import { useBotStore, useChatStore } from '../stores/bots'
import { getAvailableCommands } from '../api/commands'
import type { CommandDescriptor } from '../types'

export interface CommandResult {
  handled: boolean
  message?: string
}

/** Regex matching /prefix:name patterns (backend-routed commands). */
const PREFIXED_RE = /^\/\w+:\S+/

/**
 * Hook for handling slash commands in the web UI.
 *
 * Local commands (/new, /help, etc.) are handled client-side.
 * Prefixed commands (/skill:X, /gsd:X, etc.) are sent to the backend via WebSocket.
 */
export function useCommands() {
  const { setCreateBotOpen, setSettingsOpen, setSidebarCollapsed } = useUIStore()
  const { bots, activeBotId } = useBotStore()
  const { addMessage, activeChatId } = useChatStore()

  // Remote commands fetched from backend
  const [remoteCommands, setRemoteCommands] = useState<CommandDescriptor[]>([])

  // Fetch remote commands when bot changes
  useEffect(() => {
    let cancelled = false
    getAvailableCommands(activeBotId ?? undefined)
      .then((cmds) => {
        if (!cancelled) setRemoteCommands(cmds)
      })
      .catch(() => {
        if (!cancelled) setRemoteCommands([])
      })
    return () => { cancelled = true }
  }, [activeBotId])

  /**
   * Check if a message is a command.
   */
  const isCommand = useCallback((text: string): boolean => {
    return text.trim().startsWith('/')
  }, [])

  /**
   * Check if the message is a prefixed command that the backend should handle.
   */
  const isPrefixedCommand = useCallback((text: string): boolean => {
    return PREFIXED_RE.test(text.trim())
  }, [])

  /**
   * Add a system message to the current chat.
   */
  const addSystemMessage = useCallback((content: string) => {
    if (!activeChatId) return

    addMessage(activeChatId, {
      id: crypto.randomUUID(),
      role: 'assistant',
      content,
      timestamp: new Date().toISOString(),
    })
  }, [activeChatId, addMessage])

  /**
   * Handle a slash command.
   *
   * @returns true if the command was handled locally, false if it should be sent to backend
   */
  const handleCommand = useCallback((input: string): CommandResult => {
    const trimmed = input.trim()
    if (!trimmed.startsWith('/')) {
      return { handled: false }
    }

    // Prefixed commands (/skill:X, /gsd:X, /bot:X, etc.) → let backend handle
    if (PREFIXED_RE.test(trimmed)) {
      return { handled: false }
    }

    // Parse command and arguments
    const parts = trimmed.slice(1).split(/\s+/)
    const cmd = parts[0].toLowerCase()

    switch (cmd) {
      case 'new':
      case 'create':
        setCreateBotOpen(true)
        return { handled: true }

      case 'settings':
        setSettingsOpen(true)
        return { handled: true }

      case 'list':
      case 'bots': {
        // Show the bot list by expanding sidebar and displaying bot info
        setSidebarCollapsed(false)
        const botList = bots.length > 0
          ? bots.map((b, i) => `${i + 1}. **${b.name}**${b.description ? ` - ${b.description}` : ''}`).join('\n')
          : 'No bots yet. Use `/new` to create your first bot!'
        addSystemMessage(`**Your Bots:**\n\n${botList}`)
        return { handled: true }
      }

      case 'help':
        addSystemMessage(
          '**Available Commands:**\n\n' +
          '`/new` or `/create` - Create a new bot\n' +
          '`/list` or `/bots` - View all your bots\n' +
          '`/settings` - Open settings\n' +
          '`/help` - Show this help message\n\n' +
          'You can also just type your message to chat with the active bot!'
        )
        return { handled: true, message: 'help' }

      case 'start':
        addSystemMessage(
          'Welcome to CachiBot! I\'m your AI assistant platform.\n\n' +
          'Here\'s what you can do:\n' +
          '- `/new` - Create a new bot\n' +
          '- `/list` - See your bots\n' +
          '- `/help` - Show all commands\n\n' +
          'Or just type a message to start chatting!'
        )
        return { handled: true, message: 'start' }

      case 'cancel':
        // Cancel is handled by the creation flow in ChatView
        return { handled: false }

      default:
        // Unknown local command - let backend handle it or show error
        addSystemMessage(
          `Unknown command: \`/${cmd}\`\n\nType \`/help\` to see available commands.`
        )
        return { handled: true, message: 'unknown' }
    }
  }, [setCreateBotOpen, setSettingsOpen, setSidebarCollapsed, bots, addSystemMessage])

  return {
    isCommand,
    isPrefixedCommand,
    handleCommand,
    remoteCommands,
  }
}

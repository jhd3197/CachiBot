import { useCallback } from 'react'
import { useUIStore } from '../stores/ui'
import { useBotStore, useChatStore } from '../stores/bots'

export interface CommandResult {
  handled: boolean
  message?: string
}

/**
 * Hook for handling slash commands in the web UI.
 *
 * Commands trigger dialogs/actions instead of being sent to the backend.
 */
export function useCommands() {
  const { setCreateBotOpen, setSettingsOpen, setSidebarCollapsed } = useUIStore()
  const { bots } = useBotStore()
  const { addMessage, activeChatId } = useChatStore()

  /**
   * Check if a message is a command.
   */
  const isCommand = useCallback((text: string): boolean => {
    return text.trim().startsWith('/')
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
   * @returns true if the command was handled, false if it should be sent to backend
   */
  const handleCommand = useCallback((input: string): CommandResult => {
    const trimmed = input.trim()
    if (!trimmed.startsWith('/')) {
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
      case 'bots':
        // Show the bot list by expanding sidebar and displaying bot info
        setSidebarCollapsed(false)
        const botList = bots.length > 0
          ? bots.map((b, i) => `${i + 1}. **${b.name}**${b.description ? ` - ${b.description}` : ''}`).join('\n')
          : 'No bots yet. Use `/new` to create your first bot!'
        addSystemMessage(`**Your Bots:**\n\n${botList}`)
        return { handled: true }

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
        // Unknown command - let backend handle it or show error
        addSystemMessage(
          `Unknown command: \`/${cmd}\`\n\nType \`/help\` to see available commands.`
        )
        return { handled: true, message: 'unknown' }
    }
  }, [setCreateBotOpen, setSettingsOpen, setSidebarCollapsed, bots, addSystemMessage])

  return {
    isCommand,
    handleCommand,
  }
}

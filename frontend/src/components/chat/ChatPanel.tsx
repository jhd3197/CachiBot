import { MessageList } from './MessageList'
import { InputArea } from './InputArea'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallList } from './ToolCallList'
// import { UsageDisplay } from './UsageDisplay'
import { useChatStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { BotIconRenderer } from '../common/BotIconRenderer'

interface ChatPanelProps {
  onSendMessage: (message: string) => void
  onCancel: () => void
  isConnected: boolean
}

export function ChatPanel({ onSendMessage, onCancel, isConnected }: ChatPanelProps) {
  const { activeChatId, getMessages, thinking, toolCalls, isLoading, error } = useChatStore()
  const { showThinking, showCost } = useUIStore()

  const messages = activeChatId ? getMessages(activeChatId) : []

  return (
    <div className="flex h-full flex-col">
      {/* Messages area */}
      <div className="flex-1 overflow-y-auto scrollbar-thin">
        <div className="mx-auto max-w-3xl px-4 py-6">
          {messages.length === 0 ? (
            <EmptyState />
          ) : (
            <MessageList messages={messages} />
          )}

          {/* Active tool calls */}
          {toolCalls.length > 0 && (
            <div className="mt-4">
              <ToolCallList toolCalls={toolCalls} />
            </div>
          )}

          {/* Thinking indicator */}
          {showThinking && thinking && (
            <div className="mt-4">
              <ThinkingIndicator content={thinking} />
            </div>
          )}

          {/* Error display */}
          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700 dark:border-red-900 dark:bg-red-900/20 dark:text-red-400">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Usage display - not currently tracked in new store */}
      {showCost && (
        <div className="border-t border-zinc-200 dark:border-zinc-800">
          {/* Usage display placeholder */}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-zinc-200 bg-white dark:border-zinc-800 dark:bg-zinc-950">
        <div className="mx-auto max-w-3xl px-4 py-4">
          <InputArea
            onSend={onSendMessage}
            onCancel={onCancel}
            isLoading={isLoading}
            disabled={!isConnected}
          />
        </div>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="flex h-full flex-col items-center justify-center py-12 text-center">
      <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-cachi-100 dark:bg-cachi-900/30">
        <BotIconRenderer icon="shield" size={32} className="text-cachi-600 dark:text-cachi-400" />
      </div>
      <h2 className="mb-2 text-xl font-semibold text-zinc-900 dark:text-zinc-100">
        Welcome to CachiBot
      </h2>
      <p className="max-w-md text-sm text-zinc-500 dark:text-zinc-400">
        The Armored AI Agent. I can help you with coding tasks, run Python code
        safely, read and write files in your workspace.
      </p>
    </div>
  )
}

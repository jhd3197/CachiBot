import { MessageList } from './MessageList'
import { InputArea } from './InputArea'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallList } from './ToolCallList'
// import { UsageDisplay } from './UsageDisplay'
import { useChatStore, useBotStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { useBotAccess } from '../../hooks/useBotAccess'
import { BotIconRenderer } from '../common/BotIconRenderer'

interface ChatPanelProps {
  onSendMessage: (message: string) => void
  onCancel: () => void
  isConnected: boolean
}

export function ChatPanel({ onSendMessage, onCancel, isConnected }: ChatPanelProps) {
  const { activeChatId, getMessages, thinking, toolCalls, isLoading, error } = useChatStore()
  const { activeBotId } = useBotStore()
  const { showThinking, showCost } = useUIStore()
  const { canOperate } = useBotAccess(activeBotId)

  const messages = activeChatId ? getMessages(activeChatId) : []

  return (
    <div className="chat-panel">
      {/* Messages area */}
      <div className="chat-panel__messages">
        <div className="chat-panel__messages-inner">
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
            <div className="chat-panel__error">
              {error}
            </div>
          )}
        </div>
      </div>

      {/* Usage display - not currently tracked in new store */}
      {showCost && (
        <div className="chat-panel__usage">
          {/* Usage display placeholder */}
        </div>
      )}

      {/* Input area */}
      <div className="chat-panel__input-area">
        <div className="chat-panel__input-inner">
          <InputArea
            onSend={onSendMessage}
            onCancel={onCancel}
            isLoading={isLoading}
            disabled={!isConnected || !canOperate}
          />
        </div>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div className="chat-empty">
      <div className="chat-empty__icon">
        <BotIconRenderer icon="shield" size={32} className="text-cachi-600 dark:text-cachi-400" />
      </div>
      <h2 className="chat-empty__title">
        Welcome to CachiBot
      </h2>
      <p className="chat-empty__description">
        The Armored AI Agent. I can help you with coding tasks, run Python code
        safely, read and write files in your workspace.
      </p>
    </div>
  )
}

import { useState } from 'react'
import { Paperclip, MessageSquare } from 'lucide-react'
import { MessageList } from './MessageList'
import { InputArea } from './InputArea'
import { ThinkingIndicator } from './ThinkingIndicator'
import { ToolCallList } from './ToolCallList'
// import { UsageDisplay } from './UsageDisplay'
import { useChatStore, useBotStore } from '../../stores/bots'
import { useUIStore } from '../../stores/ui'
import { useBotAccess } from '../../hooks/useBotAccess'
import { BotIconRenderer } from '../common/BotIconRenderer'
import { AssetsView } from '../common/AssetsView'

interface ChatPanelProps {
  onSendMessage: (message: string) => void
  onCancel: () => void
  isConnected: boolean
}

export function ChatPanel({ onSendMessage, onCancel, isConnected }: ChatPanelProps) {
  const { activeChatId, getMessages, thinking, toolCalls, instructionDeltas, isLoading, error } = useChatStore()
  const { activeBotId } = useBotStore()
  const { showThinking, showCost } = useUIStore()
  const { canOperate } = useBotAccess(activeBotId)
  const [chatView, setChatView] = useState<'chat' | 'assets'>('chat')

  const messages = activeChatId ? getMessages(activeChatId) : []

  return (
    <div className="chat-panel">
      {/* View tabs */}
      {activeChatId && (
        <div style={{ display: 'flex', gap: '0.25rem', padding: '0.5rem 0.75rem', borderBottom: '1px solid var(--color-border-primary)' }}>
          <button
            onClick={() => setChatView('chat')}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.25rem',
              padding: '0.25rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.75rem',
              background: chatView === 'chat' ? 'var(--accent-600)' : 'transparent',
              color: chatView === 'chat' ? 'white' : 'var(--color-text-secondary)',
              border: 'none', cursor: 'pointer',
            }}
          >
            <MessageSquare size={12} /> Chat
          </button>
          <button
            onClick={() => setChatView('assets')}
            style={{
              display: 'flex', alignItems: 'center', gap: '0.25rem',
              padding: '0.25rem 0.5rem', borderRadius: '0.375rem', fontSize: '0.75rem',
              background: chatView === 'assets' ? 'var(--accent-600)' : 'transparent',
              color: chatView === 'assets' ? 'white' : 'var(--color-text-secondary)',
              border: 'none', cursor: 'pointer',
            }}
          >
            <Paperclip size={12} /> Assets
          </button>
        </div>
      )}

      {chatView === 'assets' && activeChatId ? (
        <AssetsView ownerType="chat" ownerId={activeChatId} botId={activeBotId || undefined} />
      ) : (
        <>
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
                  <ToolCallList toolCalls={toolCalls} instructionDeltas={instructionDeltas} />
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
        </>
      )}

      {/* Input area */}
      <InputArea
        onSend={onSendMessage}
        onCancel={onCancel}
        isLoading={isLoading}
        isConnected={isConnected}
        disabled={!canOperate}
      />
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

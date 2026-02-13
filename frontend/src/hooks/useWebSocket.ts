/**
 * React hook for WebSocket connection management
 */

import { useEffect, useState, useCallback, useRef } from 'react'
import { wsClient } from '../api/websocket'
import { useChatStore, useBotStore } from '../stores/bots'
import { useUsageStore } from '../stores/connections'
import { useKnowledgeStore } from '../stores/knowledge'
import type {
  WSMessage,
  ThinkingPayload,
  ToolStartPayload,
  ToolEndPayload,
  MessagePayload,
  PlatformMessagePayload,
  ScheduledNotificationPayload,
  DocumentStatusPayload,
  ApprovalPayload,
  ErrorPayload,
  UsagePayload,
  ToolCall,
  ToolConfigs,
  BotCapabilities,
  BotModels,
} from '../types'

// Pending approval store (simple module-level state for now)
let pendingApproval: ApprovalPayload | null = null
let pendingApprovalListeners: ((approval: ApprovalPayload | null) => void)[] = []

export function getPendingApproval() {
  return pendingApproval
}

export function setPendingApproval(approval: ApprovalPayload | null) {
  pendingApproval = approval
  pendingApprovalListeners.forEach(fn => fn(approval))
}

export function onPendingApprovalChange(fn: (approval: ApprovalPayload | null) => void) {
  pendingApprovalListeners.push(fn)
  return () => {
    pendingApprovalListeners = pendingApprovalListeners.filter(f => f !== fn)
  }
}

// Track the pending chat ID for messages sent before chat is set
let pendingChatId: string | null = null

export function setPendingChatId(chatId: string | null) {
  pendingChatId = chatId
}

export function useWebSocket() {
  const [isConnected, setIsConnected] = useState(false)
  const { addMessage, updateMessage, setThinking, appendThinking, addToolCall, updateToolCall, clearToolCalls, attachToolCallsToLastMessage, setLoading, setError, updateLastAssistantMessageMetadata, updateLastAssistantMessage } = useChatStore()

  // Use a ref to always have access to the current activeChatId without re-creating the handler
  const activeChatIdRef = useRef<string | null>(null)

  // Keep the ref in sync with the store
  useEffect(() => {
    // Subscribe to store changes
    const unsubscribe = useChatStore.subscribe((state) => {
      activeChatIdRef.current = state.activeChatId
    })
    // Initialize with current value
    activeChatIdRef.current = useChatStore.getState().activeChatId
    return unsubscribe
  }, [])

  // Handle incoming messages - stable callback that uses refs
  const handleMessage = useCallback(
    (msg: WSMessage) => {
      switch (msg.type) {
        case 'thinking': {
          const payload = msg.payload as ThinkingPayload
          appendThinking(payload.content)
          break
        }

        case 'tool_start': {
          const payload = msg.payload as ToolStartPayload
          // Clear thinking when a new tool starts (model decided on action)
          setThinking(null)
          addToolCall({
            id: payload.id,
            tool: payload.tool,
            args: payload.args,
          })
          break
        }

        case 'tool_end': {
          const payload = msg.payload as ToolEndPayload
          updateToolCall(payload.id, payload.result, payload.success)
          break
        }

        case 'message': {
          const payload = msg.payload as MessagePayload
          // Use ref for current chat, or fall back to pending chat ID
          const chatId = activeChatIdRef.current || pendingChatId
          console.log('[WS] Message received:', { role: payload.role, chatId, refValue: activeChatIdRef.current, pendingChatId })
          if (chatId) {
            const messageId = payload.messageId || `msg-${Date.now()}-${Math.random().toString(36).slice(2)}`
            // Accumulate assistant messages by messageId (streaming)
            if (payload.messageId && payload.role === 'assistant') {
              const existingMessages = useChatStore.getState().getMessages(chatId)
              const existing = existingMessages.find(m => m.id === payload.messageId)
              if (existing) {
                updateMessage(chatId, payload.messageId, existing.content + payload.content)
              } else {
                addMessage(chatId, {
                  id: messageId,
                  role: payload.role,
                  content: payload.content,
                  timestamp: new Date().toISOString(),
                })
              }
            } else {
              addMessage(chatId, {
                id: messageId,
                role: payload.role,
                content: payload.content,
                timestamp: new Date().toISOString(),
              })
            }
          } else {
            console.warn('[WS] No chatId available for message, dropping:', payload)
          }
          break
        }

        case 'approval_needed': {
          const payload = msg.payload as ApprovalPayload
          setPendingApproval(payload)
          break
        }

        case 'platform_message': {
          // Real-time platform message sync (Telegram/Discord)
          const payload = msg.payload as PlatformMessagePayload & { metadata?: Record<string, unknown> }

          // Extract tool calls from metadata if present (sent by message_processor)
          const platformToolCalls = payload.metadata?.toolCalls as ToolCall[] | undefined
          const { toolCalls: _tc, ...metadataWithoutToolCalls } = payload.metadata || {}
          void _tc

          // Add message to the appropriate chat with usage metadata and tool calls
          addMessage(payload.chatId, {
            id: payload.messageId,
            role: payload.role,
            content: payload.content,
            timestamp: new Date().toISOString(),
            metadata: {
              platform: payload.platform,
              ...metadataWithoutToolCalls,
            },
            ...(platformToolCalls && platformToolCalls.length > 0 ? { toolCalls: platformToolCalls } : {}),
          })

          // Record usage to dashboard stats for assistant messages with usage data
          if (payload.role === 'assistant' && payload.metadata) {
            const tokens = payload.metadata.tokens as number | undefined
            const cost = payload.metadata.cost as number | undefined
            const model = payload.metadata.model as string | undefined

            if (tokens !== undefined && cost !== undefined) {
              useUsageStore.getState().recordUsage({
                botId: payload.botId,
                model: model || 'unknown',
                tokens,
                cost,
              })
            }
          }
          break
        }

        case 'scheduled_notification': {
          const payload = msg.payload as ScheduledNotificationPayload
          console.log('[WS] Scheduled notification:', payload)
          if (payload.chatId) {
            addMessage(payload.chatId, {
              id: `sched-${Date.now()}-${Math.random().toString(36).slice(2)}`,
              role: 'assistant',
              content: `[Scheduled] ${payload.content}`,
              timestamp: new Date().toISOString(),
            })
          }
          break
        }

        case 'document_status': {
          const payload = msg.payload as DocumentStatusPayload
          const knowledgeStore = useKnowledgeStore.getState()
          const botDocs = knowledgeStore.documents[payload.botId]
          if (botDocs) {
            const updated = botDocs.map((d) =>
              d.id === payload.documentId
                ? {
                    ...d,
                    status: payload.status,
                    ...(payload.chunkCount !== undefined ? { chunk_count: payload.chunkCount } : {}),
                  }
                : d
            )
            useKnowledgeStore.setState((state) => ({
              documents: { ...state.documents, [payload.botId]: updated },
            }))
          }
          break
        }

        case 'usage': {
          const payload = msg.payload as UsagePayload
          const currentBotId = useBotStore.getState().activeBotId
          const currentBot = useBotStore.getState().getActiveBot()
          const chatId = activeChatIdRef.current || pendingChatId

          // Record to dashboard usage stats
          useUsageStore.getState().recordUsage({
            botId: currentBotId || 'unknown',
            model: currentBot?.model || 'unknown',
            tokens: payload.totalTokens,
            cost: payload.totalCost,
          })

          // Update last assistant message with metadata
          if (chatId) {
            updateLastAssistantMessageMetadata(chatId, {
              tokens: payload.totalTokens,
              promptTokens: payload.promptTokens,
              completionTokens: payload.completionTokens,
              cost: payload.totalCost,
              model: currentBot?.model,
              iterations: payload.iterations,
              elapsedMs: payload.elapsedMs,
              tokensPerSecond: payload.tokensPerSecond,
              callCount: payload.callCount,
              errors: payload.errors,
              perModel: payload.perModel,
              latencyStats: payload.latencyStats,
            })
          }
          break
        }

        case 'error': {
          const payload = msg.payload as ErrorPayload
          setError(payload.message)
          setLoading(false)
          setThinking(null)

          // Attach any in-progress tool calls to the last message (same as done)
          const errChatId = activeChatIdRef.current || pendingChatId
          const errToolCalls = useChatStore.getState().toolCalls
          if (errChatId && errToolCalls.length > 0) {
            attachToolCallsToLastMessage(errChatId, errToolCalls)
          }
          clearToolCalls()
          pendingChatId = null
          break
        }

        case 'done': {
          setLoading(false)
          setThinking(null)

          // Attach tool calls to last assistant message before clearing
          const doneChatId = activeChatIdRef.current || pendingChatId
          const currentToolCalls = useChatStore.getState().toolCalls
          if (doneChatId && currentToolCalls.length > 0) {
            attachToolCallsToLastMessage(doneChatId, currentToolCalls)
          }
          clearToolCalls()

          // If the server sent a replyToId in the done payload, set it on the last assistant message
          const doneReplyToId = (msg.payload as Record<string, unknown>).replyToId as string | undefined
          if (doneReplyToId && doneChatId) {
            updateLastAssistantMessage(doneChatId, { replyToId: doneReplyToId })
          }

          // Clear pending chat ID when done
          pendingChatId = null
          break
        }
      }
    },
    [addMessage, updateMessage, setThinking, appendThinking, addToolCall, updateToolCall, clearToolCalls, attachToolCallsToLastMessage, setLoading, setError, updateLastAssistantMessageMetadata, updateLastAssistantMessage]
  )

  // Connect on mount - only runs once since handleMessage is now stable
  useEffect(() => {
    const unsubMessage = wsClient.onMessage(handleMessage)
    const unsubConnect = wsClient.onConnect(() => setIsConnected(true))
    const unsubDisconnect = wsClient.onDisconnect(() => setIsConnected(false))
    const unsubError = wsClient.onError(() => {
      setError('WebSocket connection error')
    })

    // Small delay to avoid React StrictMode double-mount issues
    const timeoutId = setTimeout(() => {
      wsClient.connect()
    }, 100)

    return () => {
      clearTimeout(timeoutId)
      unsubMessage()
      unsubConnect()
      unsubDisconnect()
      unsubError()
      wsClient.disconnect()
    }
  }, [handleMessage, setError])

  // Send message
  const sendMessage = useCallback(
    (
      message: string,
      options?: {
        systemPrompt?: string
        botId?: string
        chatId?: string
        model?: string
        models?: BotModels
        capabilities?: BotCapabilities
        toolConfigs?: ToolConfigs
        replyToId?: string
      }
    ) => {
      const { setLoading, setError, clearToolCalls } = useChatStore.getState()
      setLoading(true)
      setError(null)
      clearToolCalls()
      wsClient.sendChat(message, options)
    },
    []
  )

  // Cancel operation
  const cancel = useCallback(() => {
    wsClient.sendCancel()
    setLoading(false)
    setThinking(null)
  }, [setLoading, setThinking])

  // Handle approval
  const approve = useCallback(
    (id: string, approved: boolean) => {
      wsClient.sendApproval(id, approved)
      setPendingApproval(null)
    },
    []
  )

  return {
    isConnected,
    sendMessage,
    cancel,
    approve,
  }
}

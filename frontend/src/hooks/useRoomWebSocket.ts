/**
 * React hook that wires a RoomWebSocketClient to the room Zustand store.
 *
 * Provides optimistic rendering for user messages: the message is added to the
 * local store immediately (with a frontend-generated ID) and sent to the
 * backend in the same call. When the backend broadcasts the message back, the
 * handler skips it (same ID already in store) to avoid duplicates.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { RoomWebSocketClient } from '../api/room-websocket'
import { useRoomStore } from '../stores/rooms'
import { useAuthStore } from '../stores/auth'
import type { RoomMessage, RoomWSMessage, ToolCall } from '../types'

export function useRoomWebSocket(roomId: string | null) {
  const clientRef = useRef<RoomWebSocketClient | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  // Track current bot message ID per bot (botId → messageId)
  const lastBotMessageIdRef = useRef<Record<string, string>>({})

  // Rapid double-send guard
  const lastSentRef = useRef<{ content: string; time: number }>({ content: '', time: 0 })

  const {
    addMessage,
    setBotState,
    setTyping,
    addOnlineUser,
    removeOnlineUser,
    setError,
    addToolCall,
    completeToolCall,
    finalizeToolCalls,
    updateMessageMetadata,
    setChainStep,
    setRouteDecision,
    setBotThinking,
    clearBotThinking,
    attachThinkingToMessage,
    appendInstructionDelta,
    setBotActivity,
    clearBotActivity,
    setMessageToolCalls,
    addReactionToMessage,
    removeReactionFromMessage,
    addPinnedMessage,
    removePinnedMessage,
    setConsensusState,
    setInterviewState,
    addTimelineEntry,
    resetTimeline,
  } = useRoomStore()

  useEffect(() => {
    if (!roomId) {
      // Disconnect if no room
      if (clientRef.current) {
        clientRef.current.disconnect()
        clientRef.current = null
      }
      setIsConnected(false)
      lastBotMessageIdRef.current = {}
      return
    }

    // Create new client for this room
    const client = new RoomWebSocketClient()
    clientRef.current = client

    client.onConnect(() => setIsConnected(true))
    client.onDisconnect(() => setIsConnected(false))

    client.onMessage((msg: RoomWSMessage) => {
      const p = msg.payload

      // DEBUG: log raw message for bot_done
      if (msg.type === 'room_bot_done') {
        console.log('[RoomWS] RAW room_bot_done:', JSON.stringify(msg))
      }

      switch (msg.type) {
        case 'room_message': {
          const messageId = (p.messageId as string) || crypto.randomUUID()
          const senderType = p.senderType as RoomMessage['senderType']

          // For user messages, skip if already in store (optimistic render)
          if (senderType === 'user') {
            const existing = useRoomStore.getState().messages[roomId] || []
            if (existing.some((m) => m.id === messageId)) break
          }

          // Track bot message IDs for tool call association
          if (senderType === 'bot') {
            lastBotMessageIdRef.current[p.senderId as string] = messageId
          }

          const roomMsg: RoomMessage = {
            id: messageId,
            roomId: p.roomId as string,
            senderType,
            senderId: p.senderId as string,
            senderName: p.senderName as string,
            content: p.content as string,
            metadata: {},
            timestamp: new Date().toISOString(),
          }
          addMessage(roomId, roomMsg)
          break
        }

        case 'room_bot_thinking':
          setBotState(roomId, p.botId as string, 'thinking')
          if (p.content) {
            setBotThinking(roomId, p.botId as string, p.content as string)
          }
          break

        case 'room_bot_tool_start': {
          setBotState(roomId, p.botId as string, 'responding')
          setBotActivity(roomId, p.botId as string, p.toolName as string)
          // Persist accumulated thinking before clearing
          const tsBotId = p.botId as string
          const tsMsgId = (p.messageId as string) || lastBotMessageIdRef.current[tsBotId]
          const tsThinking = useRoomStore.getState().thinkingContent[roomId]?.[tsBotId]
          if (tsThinking && tsMsgId) {
            attachThinkingToMessage(roomId, tsMsgId, tsThinking)
          }
          clearBotThinking(roomId, p.botId as string)
          const botId = p.botId as string
          // Use messageId from payload if available, otherwise fall back to tracked ID
          const msgId = (p.messageId as string) || lastBotMessageIdRef.current[botId]
          if (msgId) {
            addToolCall(roomId, msgId, {
              id: p.toolId as string,
              tool: p.toolName as string,
              args: (p.args as Record<string, unknown>) || {},
              startTime: Date.now(),
            })
          }
          break
        }

        case 'room_bot_tool_end': {
          const botId = p.botId as string
          const msgId = (p.messageId as string) || lastBotMessageIdRef.current[botId]
          if (msgId) {
            completeToolCall(
              roomId,
              msgId,
              p.toolId as string,
              p.result,
              (p.success as boolean) ?? true
            )
          }
          break
        }

        case 'room_bot_instruction_delta':
          appendInstructionDelta(roomId, p.toolId as string, p.text as string)
          break

        case 'room_bot_done': {
          const botId = p.botId as string
          const msgId = (p.messageId as string) || lastBotMessageIdRef.current[botId]
          // DEBUG: trace bot_done
          console.log('[RoomWS] bot_done payload keys=', Object.keys(p))
          console.log('[RoomWS] bot_done msgId=', msgId, 'p.messageId=', p.messageId, 'lastRef=', lastBotMessageIdRef.current[botId])
          console.log('[RoomWS] bot_done toolCalls count=', (p.toolCalls as unknown[])?.length ?? 'none')
          // Persist accumulated thinking before clearing
          const doneThinking = useRoomStore.getState().thinkingContent[roomId]?.[botId]
          if (doneThinking && msgId) {
            attachThinkingToMessage(roomId, msgId, doneThinking)
          }
          clearBotThinking(roomId, botId)
          if (msgId) {
            // Try streaming-based finalization first
            finalizeToolCalls(roomId, msgId)
            const msgAfterFinalize = useRoomStore.getState().messages[roomId]?.find(m => m.id === msgId)
            console.log('[RoomWS] after finalize: toolCalls=', msgAfterFinalize?.toolCalls?.length ?? 0)
            // Fallback: if bot_done carries tool_calls (backend always sends them),
            // attach directly when streaming tracking missed them
            const payloadCalls = p.toolCalls as Array<Record<string, unknown>> | undefined
            if (payloadCalls?.length && (!msgAfterFinalize?.toolCalls || msgAfterFinalize.toolCalls.length === 0)) {
              console.log('[RoomWS] using fallback: attaching', payloadCalls.length, 'tool calls from payload')
              setMessageToolCalls(roomId, msgId, payloadCalls as unknown as ToolCall[])
            }
            const finalMsg = useRoomStore.getState().messages[roomId]?.find(m => m.id === msgId)
            console.log('[RoomWS] final msg toolCalls=', finalMsg?.toolCalls?.length, 'content length=', finalMsg?.content.length)
          } else {
            console.log('[RoomWS] bot_done: NO msgId — cannot attach tool calls')
          }
          setBotState(roomId, botId, 'idle')
          clearBotActivity(roomId, botId)
          // Clear chain step if this was the last bot
          const currentChain = useRoomStore.getState().chainStep[roomId]
          if (currentChain && currentChain.step === currentChain.totalSteps) {
            setChainStep(roomId, null)
          }
          // Clear route decision
          setRouteDecision(roomId, null)
          delete lastBotMessageIdRef.current[botId]
          break
        }

        case 'room_typing_indicator':
          setTyping(
            roomId,
            p.userId as string,
            p.username as string,
            p.isTyping as boolean
          )
          break

        case 'room_presence':
          if (p.status === 'online') {
            addOnlineUser(roomId, p.userId as string)
          } else {
            removeOnlineUser(roomId, p.userId as string)
            // Clear typing when user goes offline
            setTyping(roomId, p.userId as string, p.username as string, false)
          }
          break

        case 'room_error':
          setError(p.message as string)
          // If error is bot-specific, mark bot as idle
          if (p.botId) {
            setBotState(roomId, p.botId as string, 'idle')
          }
          break

        case 'room_usage': {
          const botId = p.botId as string
          const msgId = (p.messageId as string) || lastBotMessageIdRef.current[botId]
          if (msgId) {
            updateMessageMetadata(roomId, msgId, {
              model: p.model,
              tokens: p.totalTokens ?? p.tokens,
              cost: p.totalCost ?? p.cost,
              promptTokens: p.promptTokens,
              completionTokens: p.completionTokens,
              elapsedMs: p.elapsedMs,
              tokensPerSecond: p.tokensPerSecond,
            })
          }
          break
        }

        case 'room_chain_step':
          setChainStep(roomId, {
            step: p.step as number,
            totalSteps: p.totalSteps as number,
            botName: p.botName as string,
          })
          break

        case 'room_route_decision':
          setRouteDecision(roomId, {
            botName: p.botName as string,
            reason: p.reason as string,
          })
          break

        // Social features
        case 'room_reaction_add':
          addReactionToMessage(
            roomId,
            p.messageId as string,
            p.emoji as string,
            p.userId as string
          )
          break

        case 'room_reaction_remove':
          removeReactionFromMessage(
            roomId,
            p.messageId as string,
            p.emoji as string,
            p.userId as string
          )
          break

        case 'room_pin_add':
          addPinnedMessage(roomId, {
            id: '',
            roomId,
            messageId: p.messageId as string,
            pinnedBy: p.pinnedBy as string,
            pinnedAt: new Date().toISOString(),
            senderName: '',
            content: '',
            timestamp: '',
          })
          break

        case 'room_pin_remove':
          removePinnedMessage(roomId, p.messageId as string)
          break

        // Consensus mode
        case 'room_consensus_synthesizing':
          setConsensusState(roomId, {
            phase: 'synthesizing',
            collected: p.responseCount as number,
            total: p.responseCount as number,
            synthesizerName: p.botName as string,
          })
          break

        case 'room_consensus_complete':
          setConsensusState(roomId, null)
          break

        // Interview mode
        case 'room_interview_question':
          setInterviewState(roomId, {
            questionCount: p.questionNum as number,
            maxQuestions: p.maxQuestions as number,
            handoffTriggered: false,
          })
          break

        case 'room_interview_handoff':
          setInterviewState(roomId, {
            questionCount: 0,
            maxQuestions: 0,
            handoffTriggered: true,
          })
          break
      }
    })

    client.connect(roomId)

    return () => {
      client.disconnect()
      clientRef.current = null
      setIsConnected(false)
      lastBotMessageIdRef.current = {}
    }
  }, [roomId, addMessage, setBotState, setTyping, addOnlineUser, removeOnlineUser, setError, addToolCall, completeToolCall, finalizeToolCalls, updateMessageMetadata, setChainStep, setRouteDecision, setBotThinking, clearBotThinking, attachThinkingToMessage, appendInstructionDelta, addReactionToMessage, removeReactionFromMessage, addPinnedMessage, removePinnedMessage, setConsensusState, setInterviewState, addTimelineEntry, resetTimeline])

  const sendMessage = useCallback((message: string) => {
    if (!roomId) return

    // Rapid double-send guard (same content within 500ms)
    const now = Date.now()
    if (message === lastSentRef.current.content && now - lastSentRef.current.time < 500) return
    lastSentRef.current = { content: message, time: now }

    // Generate a stable ID shared between local store and backend
    const messageId = crypto.randomUUID()
    const user = useAuthStore.getState().user

    // Optimistically render the message immediately
    addMessage(roomId, {
      id: messageId,
      roomId,
      senderType: 'user',
      senderId: user?.id || '',
      senderName: user?.username || '',
      content: message,
      metadata: {},
      timestamp: new Date().toISOString(),
    })

    // Send via WebSocket (backend will use the same ID)
    clientRef.current?.sendChat(message, messageId)
  }, [roomId, addMessage])

  const sendTyping = useCallback((isTyping: boolean) => {
    clientRef.current?.sendTyping(isTyping)
  }, [])

  const sendCancel = useCallback((botId: string) => {
    clientRef.current?.sendCancel(botId)
  }, [])

  return { isConnected, sendMessage, sendTyping, sendCancel }
}

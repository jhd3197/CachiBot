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
import type { RoomMessage, RoomWSMessage } from '../types'

export function useRoomWebSocket(roomId: string | null) {
  const clientRef = useRef<RoomWebSocketClient | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  // Track current bot message ID per bot (botId → messageId)
  const lastBotMessageIdRef = useRef<Record<string, string>>({})

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
          break

        case 'room_bot_tool_start': {
          setBotState(roomId, p.botId as string, 'responding')
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
          // Instruction deltas stream during tool use — no store action needed yet
          break

        case 'room_bot_done': {
          const botId = p.botId as string
          const msgId = lastBotMessageIdRef.current[botId]
          if (msgId) {
            finalizeToolCalls(roomId, msgId)
          }
          setBotState(roomId, botId, 'idle')
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
      }
    })

    client.connect(roomId)

    return () => {
      client.disconnect()
      clientRef.current = null
      setIsConnected(false)
      lastBotMessageIdRef.current = {}
    }
  }, [roomId, addMessage, setBotState, setTyping, addOnlineUser, removeOnlineUser, setError, addToolCall, completeToolCall, finalizeToolCalls, updateMessageMetadata])

  const sendMessage = useCallback((message: string) => {
    if (!roomId) return

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

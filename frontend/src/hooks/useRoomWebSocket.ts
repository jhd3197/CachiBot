/**
 * React hook that wires a RoomWebSocketClient to the room Zustand store.
 */

import { useEffect, useRef, useState, useCallback } from 'react'
import { RoomWebSocketClient } from '../api/room-websocket'
import { useRoomStore } from '../stores/rooms'
import type { RoomMessage, RoomWSMessage } from '../types'

export function useRoomWebSocket(roomId: string | null) {
  const clientRef = useRef<RoomWebSocketClient | null>(null)
  const [isConnected, setIsConnected] = useState(false)

  const {
    addMessage,
    setBotState,
    setTyping,
    addOnlineUser,
    removeOnlineUser,
    setError,
  } = useRoomStore()

  useEffect(() => {
    if (!roomId) {
      // Disconnect if no room
      if (clientRef.current) {
        clientRef.current.disconnect()
        clientRef.current = null
      }
      setIsConnected(false)
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
          const roomMsg: RoomMessage = {
            id: (p.messageId as string) || crypto.randomUUID(),
            roomId: p.roomId as string,
            senderType: p.senderType as RoomMessage['senderType'],
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

        case 'room_bot_tool_start':
          setBotState(roomId, p.botId as string, 'responding')
          break

        case 'room_bot_tool_end':
          // Stay in responding state until done
          break

        case 'room_bot_done':
          setBotState(roomId, p.botId as string, 'idle')
          break

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

        case 'room_usage':
          // Could be extended to track per-bot usage
          break
      }
    })

    client.connect(roomId)

    return () => {
      client.disconnect()
      clientRef.current = null
      setIsConnected(false)
    }
  }, [roomId, addMessage, setBotState, setTyping, addOnlineUser, removeOnlineUser, setError])

  const sendMessage = useCallback((message: string) => {
    clientRef.current?.sendChat(message)
  }, [])

  const sendTyping = useCallback((isTyping: boolean) => {
    clientRef.current?.sendTyping(isTyping)
  }, [])

  const sendCancel = useCallback((botId: string) => {
    clientRef.current?.sendCancel(botId)
  }, [])

  return { isConnected, sendMessage, sendTyping, sendCancel }
}

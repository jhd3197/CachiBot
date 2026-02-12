/**
 * WebSocket client for room communication.
 *
 * NOT a singleton — one instance per active room.
 */

import type { RoomWSMessage, RoomWSMessageType } from '../types'
import { useAuthStore } from '../stores/auth'

type MessageHandler = (message: RoomWSMessage) => void
type ConnectionHandler = () => void

export class RoomWebSocketClient {
  private ws: WebSocket | null = null
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isIntentionalClose = false
  private roomId: string | null = null

  private messageHandlers: MessageHandler[] = []
  private connectHandlers: ConnectionHandler[] = []
  private disconnectHandlers: ConnectionHandler[] = []

  connect(roomId: string): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return
    }

    const { accessToken } = useAuthStore.getState()
    if (!accessToken) {
      console.error('Cannot connect room WebSocket: not authenticated')
      return
    }

    this.roomId = roomId
    this.isIntentionalClose = false

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    const wsUrl = `${protocol}//${host}/ws/room?token=${encodeURIComponent(accessToken)}&room_id=${encodeURIComponent(roomId)}`

    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.connectHandlers.forEach((h) => h())
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as RoomWSMessage
        this.messageHandlers.forEach((h) => h(message))
      } catch (error) {
        console.error('Failed to parse room WebSocket message:', error)
      }
    }

    this.ws.onclose = () => {
      this.disconnectHandlers.forEach((h) => h())
      this.attemptReconnect()
    }

    this.ws.onerror = () => {
      // Error handling done in onclose
    }
  }

  disconnect(): void {
    this.isIntentionalClose = true
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
    this.roomId = null
  }

  private attemptReconnect(): void {
    if (this.isIntentionalClose || !this.roomId) return
    if (this.reconnectAttempts >= this.maxReconnectAttempts) return

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    setTimeout(() => {
      if (!this.isIntentionalClose && this.roomId) {
        this.connect(this.roomId)
      }
    }, delay)
  }

  private send(type: RoomWSMessageType, payload: unknown = {}): void {
    if (this.ws?.readyState !== WebSocket.OPEN) return
    this.ws.send(JSON.stringify({ type, payload }))
  }

  sendChat(message: string): void {
    this.send('room_chat', { message })
  }

  sendTyping(isTyping: boolean): void {
    this.send('room_typing', { isTyping })
  }

  sendCancel(botId: string): void {
    this.send('room_cancel', { botId })
  }

  onMessage(handler: MessageHandler): () => void {
    this.messageHandlers.push(handler)
    return () => {
      this.messageHandlers = this.messageHandlers.filter((h) => h !== handler)
    }
  }

  onConnect(handler: ConnectionHandler): () => void {
    this.connectHandlers.push(handler)
    return () => {
      this.connectHandlers = this.connectHandlers.filter((h) => h !== handler)
    }
  }

  onDisconnect(handler: ConnectionHandler): () => void {
    this.disconnectHandlers.push(handler)
    return () => {
      this.disconnectHandlers = this.disconnectHandlers.filter((h) => h !== handler)
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

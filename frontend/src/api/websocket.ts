/**
 * WebSocket Client for Cachibot
 *
 * Handles real-time communication with the agent.
 */

import type { WSMessage, WSMessageType, ToolConfigs, BotCapabilities, BotModels } from '../types'
import { useAuthStore } from '../stores/auth'

type MessageHandler = (message: WSMessage) => void
type ConnectionHandler = () => void
type ErrorHandler = (error: Event) => void

export class WebSocketClient {
  private ws: WebSocket | null = null
  private url: string
  private reconnectAttempts = 0
  private maxReconnectAttempts = 5
  private reconnectDelay = 1000
  private isIntentionalClose = false

  private messageHandlers: MessageHandler[] = []
  private connectHandlers: ConnectionHandler[] = []
  private disconnectHandlers: ConnectionHandler[] = []
  private errorHandlers: ErrorHandler[] = []

  constructor(url?: string) {
    // Default to current host with /ws path
    // In production, use same host. In dev (port 5173), Vite proxies to backend
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.url = url || `${protocol}//${host}/ws`
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return
    }

    // Get auth token
    const { accessToken } = useAuthStore.getState()
    if (!accessToken) {
      console.error('Cannot connect WebSocket: not authenticated')
      return
    }

    this.isIntentionalClose = false
    // Include token as query parameter
    const wsUrl = `${this.url}?token=${encodeURIComponent(accessToken)}`
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.connectHandlers.forEach((handler) => handler())
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as WSMessage
        this.messageHandlers.forEach((handler) => handler(message))
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.ws.onclose = () => {
      this.disconnectHandlers.forEach((handler) => handler())
      this.attemptReconnect()
    }

    this.ws.onerror = (error) => {
      this.errorHandlers.forEach((handler) => handler(error))
    }
  }

  disconnect(): void {
    this.isIntentionalClose = true
    if (this.ws) {
      this.ws.close()
      this.ws = null
    }
  }

  private attemptReconnect(): void {
    if (this.isIntentionalClose) {
      return
    }

    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    setTimeout(() => {
      if (!this.isIntentionalClose) {
        console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`)
        this.connect()
      }
    }, delay)
  }

  send(type: WSMessageType, payload: unknown = {}): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.error('WebSocket is not connected')
      return
    }

    this.ws.send(JSON.stringify({ type, payload }))
  }

  sendChat(
    message: string,
    options?: {
      systemPrompt?: string
      botId?: string
      chatId?: string
      model?: string
      models?: BotModels
      capabilities?: BotCapabilities
      toolConfigs?: ToolConfigs
      enabledSkills?: string[]
      replyToId?: string
    }
  ): void {
    this.send('chat', {
      message,
      systemPrompt: options?.systemPrompt,
      botId: options?.botId,
      chatId: options?.chatId,
      model: options?.model,
      models: options?.models,
      capabilities: options?.capabilities,
      toolConfigs: options?.toolConfigs,
      enabledSkills: options?.enabledSkills,
      replyToId: options?.replyToId,
    })
  }

  sendCancel(): void {
    this.send('cancel')
  }

  sendApproval(id: string, approved: boolean): void {
    this.send('approval', { id, approved })
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

  onError(handler: ErrorHandler): () => void {
    this.errorHandlers.push(handler)
    return () => {
      this.errorHandlers = this.errorHandlers.filter((h) => h !== handler)
    }
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

// Singleton instance
export const wsClient = new WebSocketClient()

/**
 * Base WebSocket client with shared connection lifecycle,
 * reconnection with exponential backoff, and event handler management.
 *
 * Subclasses implement buildUrl() and optionally override hooks.
 */

import { useAuthStore } from '../stores/auth'

export type ConnectionHandler = () => void
export type ErrorHandler = (error: Event) => void

export abstract class BaseWebSocketClient<TMessage> {
  protected ws: WebSocket | null = null
  protected reconnectAttempts = 0
  protected maxReconnectAttempts = 5
  protected reconnectDelay = 1000
  protected isIntentionalClose = false

  private messageHandlers: Array<(message: TMessage) => void> = []
  private connectHandlers: ConnectionHandler[] = []
  private disconnectHandlers: ConnectionHandler[] = []
  private errorHandlers: ErrorHandler[] = []

  // ---------------------------------------------------------------------------
  // Abstract: subclasses define how to build the WebSocket URL
  // ---------------------------------------------------------------------------

  /** Return the full WebSocket URL including auth token query parameter. */
  protected abstract buildUrl(token: string): string

  /** Called after a successful reconnect check but before creating the socket.
   *  Return false to abort the reconnection attempt. Default: true. */
  protected canReconnect(): boolean {
    return true
  }

  // ---------------------------------------------------------------------------
  // Connection lifecycle
  // ---------------------------------------------------------------------------

  protected connectWithToken(): void {
    if (this.ws?.readyState === WebSocket.OPEN || this.ws?.readyState === WebSocket.CONNECTING) {
      return
    }

    const { accessToken } = useAuthStore.getState()
    if (!accessToken) {
      console.error('Cannot connect WebSocket: not authenticated')
      return
    }

    this.isIntentionalClose = false
    const wsUrl = this.buildUrl(accessToken)
    this.ws = new WebSocket(wsUrl)

    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.connectHandlers.forEach((h) => h())
    }

    this.ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data) as TMessage
        this.messageHandlers.forEach((h) => h(message))
      } catch (error) {
        console.error('Failed to parse WebSocket message:', error)
      }
    }

    this.ws.onclose = () => {
      this.disconnectHandlers.forEach((h) => h())
      this.attemptReconnect()
    }

    this.ws.onerror = (error) => {
      this.errorHandlers.forEach((h) => h(error))
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
    if (this.isIntentionalClose) return
    if (!this.canReconnect()) return
    if (this.reconnectAttempts >= this.maxReconnectAttempts) {
      console.error('Max reconnect attempts reached')
      return
    }

    this.reconnectAttempts++
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1)

    setTimeout(() => {
      if (!this.isIntentionalClose && this.canReconnect()) {
        console.log(`Reconnecting... (attempt ${this.reconnectAttempts})`)
        this.doReconnect()
      }
    }, delay)
  }

  /** Override to pass extra state (e.g. roomId) into the reconnect call. */
  protected doReconnect(): void {
    this.connectWithToken()
  }

  // ---------------------------------------------------------------------------
  // Sending
  // ---------------------------------------------------------------------------

  protected sendRaw(data: unknown): void {
    if (this.ws?.readyState !== WebSocket.OPEN) {
      console.error('WebSocket is not connected')
      return
    }
    this.ws.send(JSON.stringify(data))
  }

  // ---------------------------------------------------------------------------
  // Event handler registration
  // ---------------------------------------------------------------------------

  onMessage(handler: (message: TMessage) => void): () => void {
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

  // ---------------------------------------------------------------------------
  // State
  // ---------------------------------------------------------------------------

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN
  }
}

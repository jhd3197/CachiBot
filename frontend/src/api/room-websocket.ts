/**
 * WebSocket client for room communication.
 *
 * NOT a singleton — one instance per active room.
 */

import type { RoomWSMessage, RoomWSMessageType } from '../types'
import { BaseWebSocketClient } from './base-websocket'

export class RoomWebSocketClient extends BaseWebSocketClient<RoomWSMessage> {
  private roomId: string | null = null

  protected buildUrl(token: string): string {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    return `${protocol}//${host}/ws/room?token=${encodeURIComponent(token)}&room_id=${encodeURIComponent(this.roomId!)}`
  }

  protected canReconnect(): boolean {
    return this.roomId !== null
  }

  protected doReconnect(): void {
    if (this.roomId) {
      this.connect(this.roomId)
    }
  }

  connect(roomId: string): void {
    this.roomId = roomId
    this.connectWithToken()
  }

  disconnect(): void {
    super.disconnect()
    this.roomId = null
  }

  private send(type: RoomWSMessageType, payload: unknown = {}): void {
    this.sendRaw({ type, payload })
  }

  sendChat(message: string, messageId?: string): void {
    this.send('room_chat', { message, messageId })
  }

  sendTyping(isTyping: boolean): void {
    this.send('room_typing', { isTyping })
  }

  sendCancel(botId: string): void {
    this.send('room_cancel', { botId })
  }
}

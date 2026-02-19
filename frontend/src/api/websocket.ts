/**
 * WebSocket Client for Cachibot
 *
 * Handles real-time communication with the agent.
 */

import type { WSMessage, WSMessageType, ToolConfigs, BotCapabilities, BotModels } from '../types'
import { BaseWebSocketClient } from './base-websocket'

export class WebSocketClient extends BaseWebSocketClient<WSMessage> {
  private url: string

  constructor(url?: string) {
    super()
    // Default to current host with /ws path
    // In production, use same host. In dev (port 5173), Vite proxies to backend
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const host = window.location.host
    this.url = url || `${protocol}//${host}/ws`
  }

  protected buildUrl(token: string): string {
    return `${this.url}?token=${encodeURIComponent(token)}`
  }

  connect(): void {
    this.connectWithToken()
  }

  send(type: WSMessageType, payload: unknown = {}): void {
    this.sendRaw({ type, payload })
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
}

// Singleton instance
export const wsClient = new WebSocketClient()

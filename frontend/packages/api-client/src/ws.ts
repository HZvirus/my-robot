import type { WSMessage } from './types'

export type WSHandler = (msg: WSMessage) => void

export interface ChatClientOptions {
  /** 完整 ws url，不含 token；token 以 query 附加 */
  url?: string
  token: string
  heartbeatIntervalMs?: number
  reconnectMaxMs?: number
}

/**
 * 聊天 WebSocket 客户端：自动重连 + 心跳 + 事件订阅。
 */
export class ChatClient {
  private ws: WebSocket | null = null
  private handlers = new Set<WSHandler>()
  private closedByUser = false
  private reconnectAttempts = 0
  private heartbeatTimer: number | null = null
  private readonly opts: Required<Omit<ChatClientOptions, 'token'>> & { token: string }

  constructor(opts: ChatClientOptions) {
    const base =
      opts.url ??
      (typeof window !== 'undefined'
        ? `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws/chat`
        : 'ws://localhost:8000/ws/chat')
    this.opts = {
      url: base,
      token: opts.token,
      heartbeatIntervalMs: opts.heartbeatIntervalMs ?? 20000,
      reconnectMaxMs: opts.reconnectMaxMs ?? 15000,
    }
  }

  on(handler: WSHandler): () => void {
    this.handlers.add(handler)
    return () => this.handlers.delete(handler)
  }

  connect(): void {
    this.closedByUser = false
    const url = `${this.opts.url}?token=${encodeURIComponent(this.opts.token)}`
    this.ws = new WebSocket(url)
    this.ws.onopen = () => {
      this.reconnectAttempts = 0
      this.startHeartbeat()
    }
    this.ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data) as WSMessage
        this.handlers.forEach((h) => h(msg))
      } catch {
        // 忽略非 JSON
      }
    }
    this.ws.onclose = () => {
      this.stopHeartbeat()
      if (!this.closedByUser) {
        this.scheduleReconnect()
      }
    }
    this.ws.onerror = () => {
      this.ws?.close()
    }
  }

  sendChat(text: string): void {
    this.send({ type: 'chat', text })
  }

  ping(): void {
    this.send({ type: 'ping' })
  }

  close(): void {
    this.closedByUser = true
    this.stopHeartbeat()
    this.ws?.close()
    this.ws = null
  }

  private send(payload: unknown): void {
    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(payload))
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat()
    this.heartbeatTimer = window.setInterval(() => this.ping(), this.opts.heartbeatIntervalMs)
  }

  private stopHeartbeat(): void {
    if (this.heartbeatTimer !== null) {
      window.clearInterval(this.heartbeatTimer)
      this.heartbeatTimer = null
    }
  }

  private scheduleReconnect(): void {
    this.reconnectAttempts += 1
    const delay = Math.min(this.opts.reconnectMaxMs, 1000 * 2 ** this.reconnectAttempts)
    window.setTimeout(() => {
      if (!this.closedByUser) this.connect()
    }, delay)
  }
}

import { ensureAuth, getDeviceToken } from '@/utils/auth'

/**
 * SSE 流式响应中的单个事件帧：
 * - audio：base64 编码的 MP3 音频片段（可累加拼接）
 * - error：服务端返回的错误信息
 */
export interface SmartTtsStreamEvent {
  audio?: string
  error?: string
}

/** 文本流式合成请求参数（全部可选，缺省由服务端决定） */
export interface SmartTtsStreamTextOptions {
  voice?: string // 音色 ID（见 useSmartTts 的 SMART_TTS_VOICES）
  speed?: number // 语速（0-100）
  volume?: number // 音量（0-100）
  pitch?: number // 音调（0-100）
  sampleRate?: number // 采样率
  oralLevel?: string // 口语化程度
}

/** 流式请求的回调处理器 */
export interface SmartTtsStreamHandlers {
  onEvent: (event: SmartTtsStreamEvent) => void // 每个音频/错误帧到达时触发
  onError: (message: string) => void // 请求或网络出错时触发
  onClose: () => void // 流结束、被 end()/abort() 触发或出错兜底后触发
}

/**
 * 流式合成客户端接口（由 streamSmartTtsText 返回）：
 * - push(text)：增量追加一段待合成文本（即时发送）
 * - end()：标记文本推送完毕（发送结束帧）
 * - abort()：取消请求，立即终止
 * - done：整个请求流程完成的 Promise
 */
export interface SmartTtsTextStreamClient {
  push(text: string): void
  end(): void
  abort(): void
  done: Promise<void>
}


/**
 * 经后端 WebSocket 桥接的流式合成传输层（/api/smart-tts/ws）。
 * 协议：首帧参数，随后 {"text": "..."} 增量推送，{"end": true} 结束；
 * 服务端回 {"audio": "<base64>"}* 与 {"done": true}。
 * 相比旧 POST /stream-text（整段缓冲），WS 桥接实现真正的增量合成。
 */
export function streamSmartTtsText(
  options: SmartTtsStreamTextOptions,
  handlers: SmartTtsStreamHandlers
): SmartTtsTextStreamClient {
  let ws: WebSocket | null = null
  let opened = false
  let ended = false
  let settled = false
  const pending: string[] = []
  let resolveDone!: () => void
  const donePromise = new Promise<void>((resolve) => {
    resolveDone = resolve
  })


  function settle(): void {
    if (settled) return
    settled = true
    resolveDone()
  }

  function cleanup(): void {
    if (!ws) return
    ws.onopen = null
    ws.onmessage = null
    ws.onerror = null
    ws.onclose = null
    try {
      ws.close()
    } catch {
      // already closed
    }
    ws = null
    opened = false
  }

  function sendFrame(frame: Record<string, unknown>): void {
    if (ws && ws.readyState === WebSocket.OPEN) ws.send(JSON.stringify(frame))
  }

  async function connect(): Promise<void> {
    try {
      await ensureAuth()
    } catch {
      // 注册失败继续连接，由后端 4401 触发错误回调
    }
    const proto = window.location.protocol === 'https:' ? 'wss' : 'ws'
    const token = encodeURIComponent(getDeviceToken())
    const socket = new WebSocket(
      proto + '://' + window.location.host + '/api/smart-tts/ws?token=' + token
    )
    ws = socket

    socket.onopen = () => {
      opened = true
      sendFrame({ ...options })
      for (const text of pending.splice(0)) sendFrame({ text })
      if (ended) sendFrame({ end: true })
    }
    socket.onmessage = (ev: MessageEvent<string>) => {
      try {
        const msg = JSON.parse(ev.data) as {
          audio?: string
          error?: string
          done?: boolean
        }
        if (msg.error) {
          handlers.onError(msg.error)
          cleanup()
          handlers.onClose()
          settle()
          return
        }
        if (msg.audio) handlers.onEvent({ audio: msg.audio })
        if (msg.done) {
          cleanup()
          handlers.onClose()
          settle()
        }
      } catch {
        // ignore malformed frames
      }
    }
    socket.onerror = () => {
      if (!settled) handlers.onError('WebSocket 连接出错')
    }
    socket.onclose = () => {
      if (!settled) {
        handlers.onClose()
        settle()
      }
    }
  }

  void connect()


  return {
    /**
     * 增量追加一段待合成文本并立即发送；连接尚未就绪时先缓冲。
     * end() 后调用被忽略。
     */
    push(text: string): void {
      if (ended) return
      if (opened) sendFrame({ text })
      else pending.push(text)
    },
    /** 结束文本推送：发送结束帧，等待收尾音频。 */
    end(): void {
      if (ended) return
      ended = true
      if (opened) sendFrame({ end: true })
    },
    /** 中止请求：关闭连接并收敛 Promise（不重复回调 onClose）。 */
    abort(): void {
      if (settled) return
      ended = true
      cleanup()
      settle()
    },
    /** 暴露请求流程的 Promise，可 await 整次合成完成 */
    get done(): Promise<void> {
      return donePromise
    }
  }
}

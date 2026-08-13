import type {
  SmartTtsStreamEvent,
  SmartTtsStreamHandlers,
  SmartTtsStreamTextOptions,
  SmartTtsTextStreamClient
} from '@/api/smartTts'
import { IFLYTEK_SMART_TTS } from '@/config/smartTts'

/** 签名 WebSocket 地址（含本次会话所需的 app_id） */
interface SmartTtsWsUrl {
  url: string
  app_id: string
}

/** 将 UTF-8 文本编码为 base64（协议要求文本以 base64 传输） */
function textToBase64(text: string): string {
  const bytes = new TextEncoder().encode(text)
  let binary = ''
  const CHUNK = 0x8000
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(binary)
}

/** 将字节数组编码为 base64 */
function bytesToBase64(bytes: Uint8Array): string {
  let binary = ''
  const CHUNK = 0x8000
  for (let i = 0; i < bytes.length; i += CHUNK) {
    binary += String.fromCharCode(...bytes.subarray(i, i + CHUNK))
  }
  return btoa(binary)
}

/** 对字符串做 RFC3986 编码（与后端 urllib.parse.quote 语义对齐） */
function encodeComponent(value: string): string {
  return encodeURIComponent(value)
}

/**
 * 使用 Web Crypto 在浏览器端生成讯飞鉴权方式二的签名 WebSocket URL：
 * 对 "host/date/request-line" 做 HMAC-SHA256，并把 authorization/date/host
 * 拼接到查询参数中，浏览器即可直连。
 */
async function buildSignedWsUrl(): Promise<string> {
  const { baseUrl, apiKey, apiSecret } = IFLYTEK_SMART_TTS
  const u = new URL(baseUrl)
  const host = u.host
  const path = u.pathname
  const date = new Date().toUTCString()
  const signatureOrigin = `host: ${host}\ndate: ${date}\nGET ${path} HTTP/1.1`
  const encoder = new TextEncoder()
  const key = await crypto.subtle.importKey(
    'raw',
    encoder.encode(apiSecret),
    { name: 'HMAC', hash: 'SHA-256' },
    false,
    ['sign']
  )
  const sig = await crypto.subtle.sign('HMAC', key, encoder.encode(signatureOrigin))
  const signature = bytesToBase64(new Uint8Array(sig))
  const authorizationOrigin =
    `api_key="${apiKey}", algorithm="hmac-sha256", ` +
    `headers="host date request-line", signature="${signature}"`
  const authorization = bytesToBase64(encoder.encode(authorizationOrigin))
  const query =
    `authorization=${encodeComponent(authorization)}` +
    `&date=${encodeComponent(date)}&host=${encodeComponent(host)}`
  return `${baseUrl}?${query}`
}

/**
 * 通过 WebSocket 直连讯飞超拟人语音合成接口的流式客户端。
 *
 * 与 streamSmartTtsText（SSE 转发）的差异：
 * 1. 浏览器无法在 WebSocket 握手时附加 `x-api-key` 头，因此必须用
 *    HMAC-SHA256 签名 URL 直连；已配置前端凭据（config/smartTts.ts）时
 *    在浏览器端签名，否则回退到后端 `/api/smart-tts/ws-url` 获取签名地址。
 * 2. push() 的文本会按协议帧（status 0/1/2、递增 seq）增量发送，
 *    音频帧随收随报，无需等整段文本结束。
 * 3. 音频编码使用 lame（MP3），采样率默认 24000。
 */
export function streamSmartTtsWs(
  options: SmartTtsStreamTextOptions,
  handlers: SmartTtsStreamHandlers
): SmartTtsTextStreamClient {
  /** 当前 WebSocket 连接（连接成功前为 null） */
  let ws: WebSocket | null = null
  /** 后端下发的 app_id，构建协议帧时使用 */
  let appId = ''
  /** 是否已 end()/abort()，防止重复发送或重复 push */
  let ended = false
  /** 是否已发出首个非结束帧（用于决定 status 0/1） */
  let started = false
  /** 是否已发出结束帧（status 2） */
  let finalSent = false
  /** 本次请求是否已收敛（onClose 已回调 / done 已 resolve） */
  let settled = false
  /** 文本帧序号，随帧递增 */
  let seq = 0
  /** 连接就绪前 push 进来的文本缓冲 */
  const pending: string[] = []
  /** 用于中止 ws-url 请求的 AbortController */
  const abortCtrl = new AbortController()

  let resolveDone!: () => void
  /** 整个请求流程（获取地址 + WebSocket 收发）完成的 Promise */
  const donePromise = new Promise<void>((resolve) => {
    resolveDone = resolve
  })

  function settle(): void {
    if (settled) return
    settled = true
    resolveDone()
  }

  /** 关闭并解绑 WebSocket，防止重复回调 */
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
  }

  /** 构造并发送一帧文本（文本以 base64 编码，header.status 与 payload.status 一致） */
  function sendFrame(text: string, status: number): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    const frame = {
      header: { app_id: appId, status },
      parameter: {
        tts: {
          vcn: options.voice ?? 'x6_lingxiaoxuan_flow',
          speed: options.speed ?? 50,
          volume: options.volume ?? 50,
          pitch: options.pitch ?? 50,
          bgs: 0,
          reg: 0,
          rdn: 0,
          rhy: 0,
          audio: {
            encoding: 'lame',
            sample_rate: options.sampleRate ?? 24000,
            channels: 1,
            bit_depth: 16,
            frame_size: 0
          }
        }
      },
      payload: {
        text: {
          encoding: 'utf8',
          compress: 'raw',
          format: 'plain',
          status,
          seq: seq++,
          text: textToBase64(text)
        }
      }
    }
    ws.send(JSON.stringify(frame))
  }

  /** 连接就绪后，将缓冲文本按 0/1/2 帧依次发出 */
  function flushPending(): void {
    if (!ws || ws.readyState !== WebSocket.OPEN) return
    while (pending.length > 0) {
      const text = pending.shift() as string
      // 已 end() 时最后一个缓冲片段作为结束帧（status 2）
      const isFinal = ended && pending.length === 0
      if (isFinal) {
        sendFrame(text, 2)
        finalSent = true
      } else {
        sendFrame(text, started ? 1 : 0)
        started = true
      }
    }
    // end() 已调用但缓冲已空（文本此前已按 status 0/1 发完）或从未发过帧：
    // 必须补发一个空结束帧（status 2），否则服务端收不到结束标记，
    // 会一直等待上行数据并在超时后报错（如 26005 No active up data）。
    if (ended && !finalSent) {
      sendFrame('', 2)
      finalSent = true
      started = true
    }
  }

  async function resolveWsUrl(): Promise<SmartTtsWsUrl> {
    // 优先在浏览器端用本地凭据签名直连
    const creds = IFLYTEK_SMART_TTS
    if (creds.appId && creds.apiKey && creds.apiSecret) {
      try {
        const url = await buildSignedWsUrl()
        return { url, app_id: creds.appId }
      } catch (err) {
        console.error('smart tts client-side signing failed:', err)
        // 回退到后端签名
      }
    }
    const resp = await fetch('/api/smart-tts/ws-url', {
      signal: abortCtrl.signal
    })
    if (!resp.ok) {
      throw new Error(`获取WebSocket地址失败 (${resp.status})`)
    }
    return (await resp.json()) as SmartTtsWsUrl
  }

  async function connect(): Promise<void> {
    try {
      const info = await resolveWsUrl()
      appId = info.app_id

      const socket = new WebSocket(info.url)
      ws = socket
      socket.onopen = () => flushPending()
      socket.onmessage = (ev: MessageEvent<string>) => {
        try {
          const msg = JSON.parse(ev.data) as {
            header?: { code?: number; message?: string }
            payload?: { audio?: { audio?: string; status?: number } }
          }
          const code = msg.header?.code ?? 0
          if (code !== 0) {
            handlers.onError(`${msg.header?.message ?? '合成错误'} (${code})`)
            cleanup()
            handlers.onClose()
            settle()
            return
          }
          const audio = msg.payload?.audio
          if (audio?.audio) {
            handlers.onEvent({ audio: audio.audio } satisfies SmartTtsStreamEvent)
          }
          // 服务端返回结束帧（status 2），本次会话完成
          if (audio?.status === 2) {
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
        // 主动关闭（结束帧 / abort）后不再重复回调
        if (!settled) {
          handlers.onClose()
          settle()
        }
      }
    } catch (err) {
      if (abortCtrl.signal.aborted) {
        settle()
        return
      }
      handlers.onError(err instanceof Error ? err.message : '网络错误')
      handlers.onClose()
      settle()
    }
  }

  void connect()

  return {
    /**
     * 增量追加一段待合成文本，立即以文本帧（status 0/1）发送；
     * 连接尚未就绪时先缓冲，onopen 后统一发出。end() 后调用被忽略。
     */
    push(text: string): void {
      if (ended) return
      pending.push(text)
      flushPending()
    },
    /**
     * 结束文本推送：剩余缓冲以结束帧（status 2）发出；
     * 若从未发过文本则补发一个空结束帧。
     */
    end(): void {
      if (ended) return
      ended = true
      flushPending()
    },
    /** 中止请求：取消地址获取并关闭 WebSocket */
    abort(): void {
      if (settled) return
      ended = true
      abortCtrl.abort()
      cleanup()
      settle()
    },
    /** 暴露请求流程的 Promise，可 await 整次合成完成 */
    get done(): Promise<void> {
      return donePromise
    }
  }
}

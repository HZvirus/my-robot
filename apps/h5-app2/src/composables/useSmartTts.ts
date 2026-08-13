import { reactive, ref, watch } from 'vue'
import { cleanTtsText } from '@my-robot/ui'

import { streamSmartTtsText } from '@/api/smartTts'
import type {
  SmartTtsStreamEvent,
  SmartTtsTextStreamClient
} from '@/api/smartTts'

/**
 * 语音合成播放状态：
 * - idle：空闲（无播放任务）
 * - playing：正在播放
 * - paused：已暂停（可继续播放）
 */
export type SpeechState = 'idle' | 'playing' | 'paused'

/**
 * TTS 语音合成参数设置：
 * - autoRead：是否自动朗读（关闭后 pushText 不再触发合成）
 * - voice：音色 ID（见 SMART_TTS_VOICES）
 * - speed：语速（0-100）
 * - volume：音量（0-100）
 * - pitch：音调（0-100）
 */
export interface SpeechSettings {
  autoRead: boolean
  voice: string
  speed: number
  volume: number
  pitch: number
}

/** 可选音色列表（value 为接口参数，label 为展示名称） */
export const SMART_TTS_VOICES: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'x6_lingxiaoyue_pro', label: '聆小玥（女 · 交互聊天）' },
  { value: 'x6_lingfeiyi_pro', label: '聆飞逸（男 · 交互聊天）' },
  { value: 'x6_lingxiaoxuan_pro', label: '聆小璇（女 · 交互聊天）' },
  { value: 'x6_lingyuyan_pro', label: '聆玉言（女 · 交互聊天）' },
  { value: 'x6_lingfeiyi_flow', label: '聆飞逸（男 · 免费）' },
  { value: 'x6_lingxiaoyue_flow', label: '聆小玥（女 · 免费）' }
]

/** 设置持久化到 localStorage 的 key */
const STORAGE_KEY = 'my-robot:tts-settings'

/** 默认合成参数 */
const DEFAULT_SETTINGS: SpeechSettings = {
  autoRead: true,
  voice: 'x6_lingxiaoyue_pro',
  speed: 50,
  volume: 50,
  pitch: 50
}

/**
 * 从 localStorage 读取历史设置；
 * 读取失败或数据缺失时回退到默认设置。
 */
function loadSettings(): SpeechSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<SpeechSettings>) }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

/** 全局响应式设置对象（模块级单例） */
const settings = reactive<SpeechSettings>(loadSettings())

/** 深度监听设置变化，自动写回 localStorage 持久化 */
watch(
  settings,
  (value) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value))
    } catch {
      // storage unavailable, ignore
    }
  },
  { deep: true }
)

/** 当前播放状态 */
const state = ref<SpeechState>('idle')
/** 当前正在播报的内容 ID（用于区分多个播报来源） */
const speakingId = ref<string | null>(null)
/** 最近一次的错误信息（空字符串表示无错误） */
const error = ref('')

// ---------------------------------------------------------------------------
// 播放引擎（复刻共享 useSpeech 组合式的 Web Audio + <audio> 兜底方案）：
// 优先使用 Web Audio API 按时间轴依次排列解码后的音频缓冲区；
// 当浏览器不支持 AudioContext 或解码失败时，降级为 <audio> 元素播放。
// ---------------------------------------------------------------------------

/** 播放引擎类型：webaudio（主方案）/ fallback（<audio> 兜底） */
type Engine = 'webaudio' | 'fallback'

/** 当前使用的播放引擎 */
let engine: Engine = 'webaudio'
/** 全局 AudioContext（惰性创建，首次播放时初始化） */
let audioCtx: AudioContext | null = null
/** 主增益节点，统一控制输出音量 */
let masterGain: GainNode | null = null
/** Web Audio 时间轴的播放进度（秒），用于串联多段音频 */
let playhead = 0
/** 正在播放（未结束）的音频源列表 */
let activeSources: AudioBufferSourceNode[] = []
/** 兜底模式下排队待播的 MP3 片段队列 */
let clipQueue: { url: string }[] = []
/** 兜底模式下当前正在播放的 <audio> 元素 */
let currentAudio: HTMLAudioElement | null = null
/** 兜底模式下当前播放片段的对象 URL */
let currentClipUrl: string | null = null

/**
 * 一次流式合成会话的状态：
 * - id：本次会话对应的内容 ID
 * - consumed：已推入 TTS 流中的字符数（增量推送去重用）
 * - finished：文本是否已全部推送完毕
 * - client：TTS 流式请求客户端（惰性创建）
 * - audioChunks：流式回传的音频数据（base64 解码后累积）
 */
interface FeedSession {
  id: string
  consumed: number // chars already pushed to the TTS stream
  finished: boolean
  client: SmartTtsTextStreamClient | null
  audioChunks: Uint8Array[]
}

/** 当前活跃的合成会话（同一时刻只允许一个） */
let session: FeedSession | null = null
/** 队列是否被暂停（暂停时不继续排播下一段） */
let queuePaused = false

/** base64 字符串解码为字节数组 */
function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

/** 将多个字节数组拼接为一个连续的字节数组 */
function concatBytes(chunks: Uint8Array[]): Uint8Array<ArrayBuffer> {
  let total = 0
  for (const chunk of chunks) total += chunk.byteLength
  const out = new Uint8Array(total)
  let offset = 0
  for (const chunk of chunks) {
    out.set(chunk, offset)
    offset += chunk.byteLength
  }
  return out
}

/** 提取字节数组对应的底层 ArrayBuffer（去除可能的视图偏移） */
function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer
}

/**
 * 兼容新旧 API 的 decodeAudioData 封装：
 * 新版返回 Promise，旧版（webkit）依赖回调。
 */
function decodeAudioData(ctx: AudioContext, data: ArrayBuffer): Promise<AudioBuffer> {
  return new Promise((resolve, reject) => {
    const result = ctx.decodeAudioData(data) as unknown
    if (result && typeof (result as { then?: unknown }).then === 'function') {
      const promise = result as Promise<AudioBuffer>
      promise.then(resolve, reject)
    } else {
      ctx.decodeAudioData(data, resolve, reject)
    }
  })
}

/**
 * 惰性创建 AudioContext（需在用户手势后调用才能自动播放）。
 * 浏览器不支持时降级为 fallback 引擎并返回 null。
 */
function ensureAudioContext(): AudioContext | null {
  if (engine === 'fallback') return null
  if (audioCtx) return audioCtx
  const ctor =
    window.AudioContext ??
    (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext
  if (!ctor) {
    engine = 'fallback'
    return null
  }
  try {
    audioCtx = new ctor()
    masterGain = audioCtx.createGain()
    masterGain.connect(audioCtx.destination)
    return audioCtx
  } catch {
    engine = 'fallback'
    audioCtx = null
    return null
  }
}

/**
 * 切换到 <audio> 兜底引擎：
 * 停止并清理所有 Web Audio 资源。
 */
function switchToFallback(): void {
  if (engine === 'fallback') return
  engine = 'fallback'
  for (const src of activeSources) {
    try {
      src.stop()
    } catch {
      // already stopped
    }
  }
  activeSources = []
  playhead = 0
  if (audioCtx && audioCtx.state !== 'closed') {
    void audioCtx.close()
  }
  audioCtx = null
  masterGain = null
}

/**
 * Web Audio 引擎：将解码后的音频缓冲区追加到播放时间轴。
 * 首次播放时恢复（resume）上下文以满足自动播放策略。
 */
function playBuffer(buffer: AudioBuffer): void {
  const ctx = audioCtx
  if (!ctx || engine === 'fallback') return
  if (!queuePaused && ctx.state !== 'running') {
    void ctx.resume().catch(() => {})
  }
  const src = ctx.createBufferSource()
  src.buffer = buffer
  src.connect(masterGain as GainNode)
  src.start(playhead)
  activeSources.push(src)
  playhead += buffer.duration
  src.onended = () => {
    const index = activeSources.indexOf(src)
    if (index >= 0) activeSources.splice(index, 1)
    maybeEndPlayback()
  }
}

/**
 * fallback 引擎：从队列取出下一段 MP3 并用 <audio> 播放，
 * 播完/出错后清理并继续播下一段。
 */
function playNext(): void {
  if (queuePaused || state.value !== 'playing') return
  if (currentAudio) return
  const clip = clipQueue.shift()
  if (!clip) {
    maybeEndPlayback()
    return
  }
  currentClipUrl = clip.url
  const el = new Audio(clip.url)
  currentAudio = el
  const cleanup = () => {
    if (currentAudio === el) currentAudio = null
    if (currentClipUrl === clip.url) currentClipUrl = null
    URL.revokeObjectURL(clip.url)
  }
  el.onended = () => {
    cleanup()
    playNext()
  }
  el.onerror = () => {
    cleanup()
    playNext()
  }
  void el.play().catch(() => {
    cleanup()
    playNext()
  })
}

/**
 * 播放收尾判断：当前引擎没有剩余待播音频，
 * 且文本已全部推送完毕时，自动结束本次播报。
 */
function maybeEndPlayback(): void {
  if (queuePaused || state.value !== 'playing') return
  if (engine === 'webaudio') {
    if (activeSources.length > 0) return
  } else if (currentAudio || clipQueue.length > 0) {
    return
  }
  if (session && session.finished) stop()
}

/**
 * 将会话累积的音频数据统一播放：
 * 优先 Web Audio 解码播放；解码失败则降级 fallback；
 * fallback 下将数据打包为 MP3 Blob 入队逐段播放。
 */
async function playCollectedAudio(s: FeedSession): Promise<void> {
  if (session !== s) return
  if (s.audioChunks.length === 0) {
    maybeEndPlayback()
    return
  }
  const bytes = concatBytes(s.audioChunks)
  if (engine === 'webaudio') {
    const ctx = ensureAudioContext()
    if (ctx && engine === 'webaudio') {
      try {
        const buffer = await decodeAudioData(ctx, toArrayBuffer(bytes))
        if (session === s) playBuffer(buffer)
        return
      } catch {
        switchToFallback()
      }
    }
  }
  const blob = new Blob([bytes], { type: 'audio/mpeg' })
  clipQueue.push({ url: URL.createObjectURL(blob) })
  playNext()
}

/** 中止当前会话的 TTS 流式请求（取消 fetch） */
function abortStream(): void {
  if (session?.client) {
    session.client.abort()
  }
}

/**
 * 停止播报：中止请求、停止所有音频源、
 * 清理对象 URL 并重置会话状态为 idle。
 */
function stop(): void {
  abortStream()
  if (audioCtx) {
    for (const src of activeSources) {
      try {
        src.stop()
      } catch {
        // already stopped
      }
    }
    activeSources = []
    playhead = 0
  }
  for (const clip of clipQueue) URL.revokeObjectURL(clip.url)
  clipQueue = []
  if (currentAudio) {
    const el = currentAudio
    currentAudio = null
    el.onended = null
    el.onerror = null
    el.pause()
  }
  if (currentClipUrl) {
    URL.revokeObjectURL(currentClipUrl)
    currentClipUrl = null
  }
  session = null
  queuePaused = false
  state.value = 'idle'
  speakingId.value = null
}

// ---------------------------------------------------------------------------
// 流式合成会话：文本被增量推入 TTS 请求体，
// 同一 HTTP 响应中以 SSE 形式流式回传 MP3 音频帧。
// ---------------------------------------------------------------------------

/**
 * 开启一个新的合成会话（会先停止当前会话）。
 * 之后通过 pushText / finish 增量喂入文本。
 */
function startFeed(id: string): void {
  stop()
  state.value = 'playing'
  speakingId.value = id
  error.value = ''
  session = {
    id,
    consumed: 0,
    finished: false,
    client: null,
    audioChunks: []
  }
}

/**
 * 增量推送文本（流式模式）：
 * - autoRead 关闭时直接忽略；
 * - 只推送新增部分，避免重复合成；
 * - 清理文本中的无效字符后再推入；
 * - 客户端惰性创建，首次推送时建立 TTS 流式请求。
 */
function pushText(id: string, content: string): void {
  if (!settings.autoRead) return
  if (!session || session.id !== id) startFeed(id)
  const s = session as FeedSession
  if (content.length <= s.consumed) return
  const fresh = content.slice(s.consumed)
  s.consumed = content.length
  const clean = cleanTtsText(fresh)
  if (!clean) return
  if (!s.client) {
    s.client = streamSmartTtsText(
      {
        voice: settings.voice,
        speed: settings.speed,
        volume: settings.volume,
        pitch: settings.pitch
      },
      {
        onEvent(event: SmartTtsStreamEvent) {
          if (event.error) {
            error.value = event.error
            return
          }
          if (event.audio) s.audioChunks.push(base64ToBytes(event.audio))
        },
        onError(message) {
          error.value = message
        },
        onClose() {
          if (session === s && s.finished) {
            void playCollectedAudio(s)
          }
        }
      }
    )
  }
  s.client.push(clean)
}

/**
 * 标记文本推送完成（流式模式收尾）：
 * 请求结束后若有音频则开始播放；若从未创建请求则直接播放已收集音频。
 */
function finish(id: string): void {
  if (!session || session.id !== id) return
  const s = session
  s.finished = true
  if (s.client) {
    s.client.end()
  } else {
    void playCollectedAudio(s)
  }
}

/**
 * 一次性合成并播放完整文本（非流式）：
 * 直接创建请求、推送全部文本并立即 end，等待音频回传后播放。
 */
function speak(id: string, text: string): void {
  startFeed(id)
  const s = session as FeedSession
  s.finished = true
  const clean = cleanTtsText(text)
  if (clean) {
    s.client = streamSmartTtsText(
      {
        voice: settings.voice,
        speed: settings.speed,
        volume: settings.volume,
        pitch: settings.pitch
      },
      {
        onEvent(event: SmartTtsStreamEvent) {
          if (event.error) {
            error.value = event.error
            return
          }
          if (event.audio) s.audioChunks.push(base64ToBytes(event.audio))
        },
        onError(message) {
          error.value = message
        },
        onClose() {
          if (session === s) void playCollectedAudio(s)
        }
      }
    )
    s.client.push(clean)
    s.client.end()
  } else {
    maybeEndPlayback()
  }
}

/** 暂停播放（Web Audio 挂起上下文，fallback 暂停 <audio>） */
function pause(): void {
  if (state.value !== 'playing') return
  queuePaused = true
  if (engine === 'webaudio' && audioCtx && audioCtx.state === 'running') {
    void audioCtx.suspend()
  }
  if (currentAudio) currentAudio.pause()
  state.value = 'paused'
}

/** 恢复播放（恢复上下文 / 继续 <audio> / 继续播队列下一段） */
function resume(): void {
  if (state.value !== 'paused') return
  queuePaused = false
  state.value = 'playing'
  if (engine === 'webaudio' && audioCtx && audioCtx.state !== 'running') {
    void audioCtx.resume().catch(() => {})
  }
  if (currentAudio) {
    void currentAudio.play().catch(() => {})
    return
  }
  playNext()
}

/**
 * 播报开关（供 UI 按钮使用）：
 * - 空闲或来源不同：开始播放；
 * - 播放中：暂停；
 * - 已暂停：恢复。
 */
function toggle(id: string, text: string): void {
  if (state.value === 'idle' || speakingId.value !== id) {
    speak(id, text)
    return
  }
  if (state.value === 'playing') {
    pause()
    return
  }
  resume()
}

/** 该 ID 当前是否有活跃播报（播放中或暂停） */
function isActive(id: string): boolean {
  return state.value !== 'idle' && speakingId.value === id
}

/** 该 ID 当前是否正在播放（非暂停） */
function isPlaying(id: string): boolean {
  return state.value === 'playing' && speakingId.value === id
}

/** 组合式函数入口：对外暴露状态与操作方法 */
export function useSmartTts() {
  return {
    state,
    speakingId,
    error,
    settings,
    voices: SMART_TTS_VOICES,
    toggle,
    speak,
    pushText,
    finish,
    pause,
    resume,
    stop,
    isActive,
    isPlaying
  }
}

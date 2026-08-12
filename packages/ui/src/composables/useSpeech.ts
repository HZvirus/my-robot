import { reactive, ref, watch } from 'vue'

export type SpeechState = 'idle' | 'playing' | 'paused'

export interface SpeechSettings {
  autoRead: boolean
  voice: string
  speed: number
  volume: number
  pitch: number
}

interface TtsStreamRequest {
  text: string
  voice?: string
  speed?: number
  volume?: number
  pitch?: number
}

interface TtsStreamEvent {
  audio?: string
  error?: string
}

export const TTS_VOICES: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'xiaoyan', label: '小燕（女 · 通用）' },
  { value: 'aisjiuxu', label: '许久（男 · 沉稳）' },
  { value: 'aisxping', label: '小萍（女 · 温柔）' },
  { value: 'aisjinger', label: '小婧（女 · 亲切）' },
  { value: 'aisbabyxu', label: '许小宝（童声）' },
  { value: 'x4_lingfei_oral', label: '聆飞（男 · 英语）' }
]

const STORAGE_KEY = 'my-robot:tts-settings'

const DEFAULT_SETTINGS: SpeechSettings = {
  autoRead: false,
  voice: 'xiaoyan',
  speed: 50,
  volume: 50,
  pitch: 50
}

function loadSettings(): SpeechSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return { ...DEFAULT_SETTINGS }
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(raw) as Partial<SpeechSettings>) }
  } catch {
    return { ...DEFAULT_SETTINGS }
  }
}

const settings = reactive<SpeechSettings>(loadSettings())

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

const state = ref<SpeechState>('idle')
const speakingId = ref<string | null>(null)
const error = ref('')

let generation = 0
let abortCtrl: AbortController | null = null
let audioEl: HTMLAudioElement | null = null
let objectUrl: string | null = null

export function cleanTtsText(text: string): string {
  return text
    .replace(/```[\s\S]*?```/g, ' ')
    .replace(/`([^`]*)`/g, '$1')
    .replace(/[#>*_~[\]]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function base64ToBytes(b64: string): Uint8Array<ArrayBuffer> {
  const bin = atob(b64)
  const bytes = new Uint8Array(bin.length)
  for (let i = 0; i < bin.length; i++) bytes[i] = bin.charCodeAt(i)
  return bytes
}

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

function stopAudio(): void {
  if (audioEl) {
    audioEl.onended = null
    audioEl.onerror = null
    audioEl.pause()
    audioEl = null
  }
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl)
    objectUrl = null
  }
}

function abortStream(): void {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
}

function stop(): void {
  generation += 1
  abortStream()
  stopAudio()
  state.value = 'idle'
  speakingId.value = null
}

function playBlob(chunks: Uint8Array[]): void {
  const blob = new Blob([concatBytes(chunks)], { type: 'audio/mpeg' })
  objectUrl = URL.createObjectURL(blob)
  const el = new Audio(objectUrl)
  audioEl = el
  const finish = () => {
    if (audioEl !== el) return
    stopAudio()
    state.value = 'idle'
    speakingId.value = null
  }
  el.onended = finish
  el.onerror = finish
  void el.play().catch(() => {
    /* autoplay blocked: keep idle so the user can retry */
  })
}

async function fetchSse(
  url: string,
  body: TtsStreamRequest,
  signal: AbortSignal,
  handlers: {
    onEvent: (event: TtsStreamEvent) => void
    onError: (message: string) => void
    onClose: () => void
  }
): Promise<void> {
  const { onEvent, onError, onClose } = handlers
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal
    })
    if (!resp.ok) {
      onError(`请求失败 (${resp.status})`)
      onClose()
      return
    }
    if (!resp.body) {
      onError('浏览器不支持流式响应')
      onClose()
      return
    }
    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const payload = trimmed.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try {
          onEvent(JSON.parse(payload) as TtsStreamEvent)
        } catch {
          // ignore malformed frames
        }
      }
    }
    onClose()
  } catch (err) {
    if (signal.aborted) return
    onError(err instanceof Error ? err.message : '网络错误')
    onClose()
  }
}

async function speak(id: string, text: string): Promise<void> {
  stop()
  const clean = cleanTtsText(text)
  if (!clean) return

  const myGen = generation
  state.value = 'playing'
  speakingId.value = id
  error.value = ''

  const chunks: Uint8Array[] = []
  const ctrl = new AbortController()
  abortCtrl = ctrl

  const handleError = (message: string) => {
    if (generation !== myGen) return
    error.value = message
    state.value = 'idle'
    speakingId.value = null
  }

  await fetchSse(
    '/api/tts/stream',
    {
      text: clean,
      voice: settings.voice,
      speed: settings.speed,
      volume: settings.volume,
      pitch: settings.pitch
    },
    ctrl.signal,
    {
      onEvent(event) {
        if (generation !== myGen) return
        if (event.error) {
          handleError(event.error)
          return
        }
        if (event.audio) chunks.push(base64ToBytes(event.audio))
      },
      onError(message) {
        handleError(message)
      },
      onClose() {
        if (generation !== myGen) return
        abortCtrl = null
        if (chunks.length === 0) {
          handleError('未获取到语音')
          return
        }
        playBlob(chunks)
      }
    }
  )
}

function pause(): void {
  if (state.value !== 'playing') return
  if (audioEl) {
    audioEl.pause()
    state.value = 'paused'
  }
}

function resume(): void {
  if (state.value !== 'paused' || !audioEl) return
  void audioEl.play().catch(() => {})
  state.value = 'playing'
}

function toggle(id: string, text: string): void {
  if (state.value === 'idle' || speakingId.value !== id) {
    void speak(id, text)
    return
  }
  if (state.value === 'playing') {
    pause()
    return
  }
  resume()
}

function isActive(id: string): boolean {
  return state.value !== 'idle' && speakingId.value === id
}

function isPlaying(id: string): boolean {
  return state.value === 'playing' && speakingId.value === id
}

export function useSpeech() {
  return {
    state,
    speakingId,
    error,
    settings,
    toggle,
    speak,
    pause,
    resume,
    stop,
    isActive,
    isPlaying
  }
}

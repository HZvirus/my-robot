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
  autoRead: true,
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

// ---------------------------------------------------------------------------
// Playback engines.
//
// Primary (route C): Web Audio. Each MP3 frame is decoded as it arrives and
// scheduled on a running playhead, so audio starts within a sentence while
// synthesis is still producing frames.
//
// Fallback: when `AudioContext`/`decodeAudioData` is missing or rejects MP3
// (known Safari/iOS issues), every sentence is buffered and replayed through
// chained <audio> elements. Frames keep streaming but playback waits for the
// sentence clip, preserving reliability across browsers.
// ---------------------------------------------------------------------------

type Engine = 'webaudio' | 'fallback'

const SENTENCE_END = /[。！？…；;!?]/

// Utterance batching: the first sentence is synthesized immediately for a fast
// first word; subsequent sentences are grouped into utterances and sent in one
// request (fewer connections). A buffer flushes when it has enough sentences,
// grows too large, or has been waiting too long.
const UTTERANCE_MIN_SENTENCES = 2
const UTTERANCE_MAX_BYTES = 400
const UTTERANCE_MAX_WAIT_MS = 1000

function byteLength(text: string): number {
  return new TextEncoder().encode(text).length
}

let engine: Engine = 'webaudio'
let audioCtx: AudioContext | null = null
let masterGain: GainNode | null = null
let playhead = 0
let activeSources: AudioBufferSourceNode[] = []

interface Clip {
  url: string
}

let clipQueue: Clip[] = []
let currentAudio: HTMLAudioElement | null = null
let currentClipUrl: string | null = null

// ---------------------------------------------------------------------------
// Streaming session: text is fed incrementally (chat SSE deltas); completed
// sentences are synthesized immediately and their audio frames are queued for
// playback, so speech follows the typewriter instead of waiting for the end.
// ---------------------------------------------------------------------------

interface FeedSession {
  id: string
  consumed: number // chars already consumed from the full content
  buffer: string // pending text not yet split into sentences
  finished: boolean
  chain: Promise<void> // serializes synthesis so clips keep sentence order
  sentFirst: boolean // first sentence was already synthesized immediately
  utterance: string // buffered sentences waiting to be sent as one request
  utteranceSentences: number
  utteranceStart: number // ms timestamp when the current utterance began
}

let session: FeedSession | null = null
let abortCtrl: AbortController | null = null
let queuePaused = false
let pendingSynth = 0

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

function toArrayBuffer(bytes: Uint8Array): ArrayBuffer {
  return bytes.buffer.slice(
    bytes.byteOffset,
    bytes.byteOffset + bytes.byteLength
  ) as ArrayBuffer
}

function extractSentences(buf: string): { sentences: string[]; rest: string } {
  let lastEnd = -1
  for (let i = 0; i < buf.length; i++) {
    if (SENTENCE_END.test(buf[i])) lastEnd = i
  }
  if (lastEnd < 0) return { sentences: [], rest: buf }
  const complete = buf.slice(0, lastEnd + 1)
  const rest = buf.slice(lastEnd + 1)
  const sentences = complete
    .split(/[。！？…；;!?]+/)
    .map((s) => s.trim())
    .filter(Boolean)
  return { sentences, rest }
}

/** Promise-based decodeAudioData that also supports the legacy callback API. */
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

/** Silence the Web Audio pipeline and switch all playback to <audio> clips. */
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

/** Schedule an already-decoded buffer at the running playhead (gapless). */
function playBuffer(buffer: AudioBuffer): void {
  const ctx = audioCtx
  if (!ctx || engine === 'fallback') return
  if (!queuePaused && ctx.state !== 'running') {
    // iOS creates the context suspended; resume it so audio can play.
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

function abortStream(): void {
  if (abortCtrl) {
    abortCtrl.abort()
    abortCtrl = null
  }
}

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

function startFeed(id: string): void {
  stop()
  state.value = 'playing'
  speakingId.value = id
  error.value = ''
  session = {
    id,
    consumed: 0,
    buffer: '',
    finished: false,
    chain: Promise.resolve(),
    sentFirst: false,
    utterance: '',
    utteranceSentences: 0,
    utteranceStart: 0
  }
}

function pushSynth(s: FeedSession, text: string): void {
  if (!text) return
  pendingSynth += 1
  s.chain = s.chain.then(async () => {
    try {
      if (session !== s) return
      await streamSentence(text)
    } catch {
      // per-clip failure is handled inside streamSentence
    } finally {
      pendingSynth -= 1
      maybeEndPlayback()
    }
  })
}

/**
 * Synthesize one text chunk via the v2 TTS service (/api/tts/stream). The
 * whole MP3 is buffered, decoded once and played — a gapless one-shot replay.
 */
async function streamSentence(text: string): Promise<void> {
  const chunks: Uint8Array[] = []
  const ctrl = new AbortController()
  abortCtrl = ctrl
  let failed = false

  await fetchSse(
    '/api/tts/stream',
    {
      text,
      voice: settings.voice,
      speed: settings.speed,
      volume: settings.volume,
      pitch: settings.pitch
    },
    ctrl.signal,
    {
      onEvent(event) {
        if (event.error) {
          error.value = event.error
          failed = true
          return
        }
        if (event.audio) chunks.push(base64ToBytes(event.audio))
      },
      onError(message) {
        error.value = message
        failed = true
      },
      onClose() {
        // all frames received
      }
    }
  )

  if (failed || chunks.length === 0) return
  const bytes = concatBytes(chunks)
  if (engine === 'webaudio') {
    const ctx = ensureAudioContext()
    if (ctx && engine === 'webaudio') {
      try {
        const buffer = await decodeAudioData(ctx, toArrayBuffer(bytes))
        if (session) playBuffer(buffer)
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

function maybeEndPlayback(): void {
  if (pendingSynth > 0 || queuePaused || state.value !== 'playing') return
  if (engine === 'webaudio') {
    if (activeSources.length > 0) return
  } else if (currentAudio || clipQueue.length > 0) {
    return
  }
  if (session && session.finished) stop()
}

/** Feed newly arrived text for `id`; the first sentence is synthesized right
 * away, later sentences are grouped into utterances and flushed in batches. */
function pushText(id: string, content: string): void {
  if (!settings.autoRead) return
  if (!session || session.id !== id) startFeed(id)
  const s = session as FeedSession
  if (content.length <= s.consumed) return
  const fresh = content.slice(s.consumed)
  s.consumed = content.length
  s.buffer += fresh
  const { sentences, rest } = extractSentences(s.buffer)
  s.buffer = rest
  for (const sentence of sentences) {
    const clean = cleanTtsText(sentence)
    if (!clean) continue
    if (!s.sentFirst) {
      s.sentFirst = true
      pushSynth(s, clean)
      continue
    }
    if (s.utteranceSentences === 0) s.utteranceStart = Date.now()
    s.utterance += clean
    s.utteranceSentences += 1
    if (shouldFlushUtterance(s)) flushUtterance(s)
  }
}

function shouldFlushUtterance(s: FeedSession): boolean {
  if (s.utteranceSentences >= UTTERANCE_MIN_SENTENCES) return true
  if (byteLength(s.utterance) >= UTTERANCE_MAX_BYTES) return true
  return (
    s.utteranceStart > 0 &&
    Date.now() - s.utteranceStart >= UTTERANCE_MAX_WAIT_MS
  )
}

function flushUtterance(s: FeedSession): void {
  if (!s.utterance) return
  pushSynth(s, s.utterance)
  s.utterance = ''
  s.utteranceSentences = 0
  s.utteranceStart = 0
}

/** Flush the trailing partial text once the reply is complete. */
function finish(id: string): void {
  if (!session || session.id !== id) return
  const s = session
  s.finished = true
  const rest = cleanTtsText(s.buffer)
  s.buffer = ''
  if (rest) {
    if (!s.sentFirst) {
      s.sentFirst = true
      pushSynth(s, rest)
    } else {
      s.utterance += rest
      s.utteranceSentences += 1
    }
  }
  flushUtterance(s)
  maybeEndPlayback()
}

/** Manual read-aloud of a whole message (plays frames as soon as they arrive). */
function speak(id: string, text: string): void {
  startFeed(id)
  const s = session as FeedSession
  s.finished = true
  pushSynth(s, cleanTtsText(text))
  maybeEndPlayback()
}

function pause(): void {
  if (state.value !== 'playing') return
  queuePaused = true
  if (engine === 'webaudio' && audioCtx && audioCtx.state === 'running') {
    void audioCtx.suspend()
  }
  if (currentAudio) currentAudio.pause()
  state.value = 'paused'
}

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
    pushText,
    finish,
    pause,
    resume,
    stop,
    isActive,
    isPlaying
  }
}

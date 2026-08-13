import { reactive, ref, watch } from 'vue'
import { cleanTtsText } from '@my-robot/ui'

import { streamSmartTtsText } from '@/api/smartTts'
import type {
  SmartTtsStreamEvent,
  SmartTtsTextStreamClient
} from '@/api/smartTts'

export type SpeechState = 'idle' | 'playing' | 'paused'

export interface SpeechSettings {
  autoRead: boolean
  voice: string
  speed: number
  volume: number
  pitch: number
}

export const SMART_TTS_VOICES: ReadonlyArray<{ value: string; label: string }> = [
  { value: 'x6_lingxiaoyue_pro', label: '聆小玥（女 · 交互聊天）' },
  { value: 'x6_lingfeiyi_pro', label: '聆飞逸（男 · 交互聊天）' },
  { value: 'x6_lingxiaoxuan_pro', label: '聆小璇（女 · 交互聊天）' },
  { value: 'x6_lingyuyan_pro', label: '聆玉言（女 · 交互聊天）' },
  { value: 'x6_lingfeiyi_flow', label: '聆飞逸（男 · 免费）' },
  { value: 'x6_lingxiaoyue_flow', label: '聆小玥（女 · 免费）' }
]

const STORAGE_KEY = 'my-robot:tts-settings'

const DEFAULT_SETTINGS: SpeechSettings = {
  autoRead: true,
  voice: 'x6_lingxiaoyue_pro',
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
// Playback engine (mirrors the Web Audio + <audio> fallback approach used by
// the shared `useSpeech` composable).
// ---------------------------------------------------------------------------

type Engine = 'webaudio' | 'fallback'

let engine: Engine = 'webaudio'
let audioCtx: AudioContext | null = null
let masterGain: GainNode | null = null
let playhead = 0
let activeSources: AudioBufferSourceNode[] = []
let clipQueue: { url: string }[] = []
let currentAudio: HTMLAudioElement | null = null
let currentClipUrl: string | null = null

interface FeedSession {
  id: string
  consumed: number // chars already pushed to the TTS stream
  finished: boolean
  client: SmartTtsTextStreamClient | null
  audioChunks: Uint8Array[]
}

let session: FeedSession | null = null
let queuePaused = false

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
  if (queuePaused || state.value !== 'playing') return
  if (engine === 'webaudio') {
    if (activeSources.length > 0) return
  } else if (currentAudio || clipQueue.length > 0) {
    return
  }
  if (session && session.finished) stop()
}

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

function abortStream(): void {
  if (session?.client) {
    session.client.abort()
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

// ---------------------------------------------------------------------------
// Streaming session: text is pushed into the TTS request body incrementally
// while MP3 frames stream back over the same HTTP response.
// ---------------------------------------------------------------------------

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

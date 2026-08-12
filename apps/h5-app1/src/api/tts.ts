import type {
  TtsStreamEvent,
  TtsStreamRequest
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'

export function streamTts(
  req: TtsStreamRequest,
  handlers: SseHandlers<TtsStreamEvent>
): Promise<void> {
  return readSse('/api/tts/stream', req, handlers)
}

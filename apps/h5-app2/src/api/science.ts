import type {
  ScienceRequest,
  ScienceStreamEvent
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'

export function streamScience(
  req: ScienceRequest,
  handlers: SseHandlers<ScienceStreamEvent>
): Promise<void> {
  return readSse('/api/science/chat', req, handlers)
}

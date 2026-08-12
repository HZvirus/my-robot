import type {
  CompanionRequest,
  CompanionStreamEvent
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'

export function streamCompanion(
  req: CompanionRequest,
  handlers: SseHandlers<CompanionStreamEvent>
): Promise<void> {
  return readSse('/api/companion/chat', req, handlers)
}

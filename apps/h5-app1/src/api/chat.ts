import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'
import { authFetch } from '@/utils/auth'

export function chat(req: ChatRequest): Promise<ChatResponse> {
  return authFetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req)
  }).then(async (resp) => {
    if (!resp.ok) throw new Error('请求失败 (' + resp.status + ')')
    return (await resp.json()) as ChatResponse
  })
}

export function streamChat(
  req: ChatRequest,
  handlers: SseHandlers<ChatStreamEvent>
): Promise<void> {
  return readSse('/api/chat/stream', req, handlers)
}

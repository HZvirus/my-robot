import axios from 'axios'
import type {
  ChatRequest,
  ChatResponse,
  ChatStreamEvent
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'

const http = axios.create({ baseURL: '/api' })

export function chat(req: ChatRequest): Promise<ChatResponse> {
  return http.post<ChatResponse>('/chat', req).then((r) => r.data)
}

export function streamChat(
  req: ChatRequest,
  handlers: SseHandlers<ChatStreamEvent>
): Promise<void> {
  return readSse('/api/chat/stream', req, handlers)
}

import type {
  Department,
  TriageRequest,
  TriageStreamEvent
} from '@my-robot/shared-types'
import { readSse } from '@/utils/sse'
import type { SseHandlers } from '@/utils/sse'

export function streamTriage(
  req: TriageRequest,
  handlers: SseHandlers<TriageStreamEvent>
): Promise<void> {
  return readSse('/api/triage/chat', req, handlers)
}

export async function fetchDepartments(): Promise<Department[]> {
  const resp = await fetch('/api/triage/departments')
  if (!resp.ok) return []
  return (await resp.json()) as Department[]
}

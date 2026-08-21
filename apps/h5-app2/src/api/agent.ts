import type { AgentRunRequest, AgentRunResponse } from '@my-robot/shared-types'
import { authFetch } from '@/utils/auth'

export async function runAgent(req: AgentRunRequest): Promise<AgentRunResponse> {
  const resp = await authFetch('/api/agent/run', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message: req.message, conversationId: req.conversationId })
  })
  if (!resp.ok) {
    let detail = `请求失败 (${resp.status})`
    try {
      const data = (await resp.json()) as { detail?: string }
      if (data.detail) detail = data.detail
    } catch {
      // 保留默认错误信息
    }
    throw new Error(detail)
  }
  return (await resp.json()) as AgentRunResponse
}

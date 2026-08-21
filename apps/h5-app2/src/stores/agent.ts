import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import type { AgentChatMessage } from '@my-robot/shared-types'
import { runAgent } from '@/api/agent'

/**
 * Agent 对话 Store：管理当前会话的消息列表、
 * 会话 ID、非流式运行状态与错误信息。
 */
export const useAgentStore = defineStore('agent', () => {
  const messages = ref<AgentChatMessage[]>([])
  const conversationId = ref<string | null>(null)
  const running = ref(false)
  const error = ref('')

  function makeMessage(role: 'user' | 'assistant', content: string): AgentChatMessage {
    return reactive({
      id: Date.now() + '-' + Math.random().toString(36).slice(2, 8),
      role,
      content,
      steps: [],
      createdAt: new Date().toISOString()
    })
  }

  /**
   * 发送一条消息并等待 Agent 完整回答：
   * 1. 校验输入与并发状态；
   * 2. 追加用户消息，并预先占位一条空的助手消息；
   * 3. 调用 /agent/run，回填最终答案与推理足迹（steps）；
   * 4. 无论成功与否，finally 中复位 running。
   */
  async function send(text: string): Promise<void> {
    const content = text.trim()
    if (!content || running.value) return

    running.value = true
    error.value = ''
    messages.value.push(makeMessage('user', content))

    const assistant = makeMessage('assistant', '')
    messages.value.push(assistant)

    try {
      const resp = await runAgent({
        message: content,
        conversationId: conversationId.value ?? undefined
      })
      conversationId.value = resp.conversationId
      assistant.content = resp.answer
      assistant.steps = resp.steps
    } catch (err) {
      error.value = err instanceof Error ? err.message : '请求失败'
      assistant.content = ''
    } finally {
      running.value = false
    }
  }

  /** 重置会话状态：清空消息、会话 ID 与错误信息 */
  function reset() {
    messages.value = []
    conversationId.value = null
    error.value = ''
    running.value = false
  }

  return {
    messages,
    conversationId,
    running,
    error,
    send,
    reset
  }
})

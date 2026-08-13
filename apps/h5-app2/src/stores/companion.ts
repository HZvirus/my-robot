import { defineStore } from 'pinia'
import { reactive, ref } from 'vue'
import type {
  CompanionConversation,
  CompanionMessage
} from '@my-robot/shared-types'
import { useSmartTts } from '@/composables/useSmartTts'
import { streamCompanion } from '@/api/companion'

/**
 * 全局 TTS 播报实例（模块级单例，供消息朗读使用）。
 * 每次发送新消息前调用 speech.stop()，避免新旧播报互相叠加。
 */
const speech = useSmartTts()

/**
 * 陪伴对话 Store：管理当前会话的消息列表、
 * 会话 ID、流式生成状态与错误信息。
 *
 * 使用组合式（setup）风格的 Pinia store 定义。
 */
export const useCompanionStore = defineStore('companion', () => {
  /** 当前会话的消息列表（含用户消息与助手回复） */
  const messages = ref<CompanionMessage[]>([])
  /** 当前会话的 ID（由后端在首个事件中返回，用于续聊） */
  const conversationId = ref<string | null>(null)
  /** 是否正在流式生成回复（期间禁止重复发送） */
  const streaming = ref(false)
  /** 最近一次的错误信息（空字符串表示无错误） */
  const error = ref('')

  /**
   * 创建一条消息对象：
   * - id 由时间戳 + 随机串生成，保证同一会话内唯一；
   * - interrupted 标记消息是否被中断（失败/流异常/空回复）；
   * - createdAt 为 ISO 时间字符串。
   */
  function makeMessage(role: 'user' | 'assistant', content: string): CompanionMessage {
    return reactive({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      interrupted: false,
      createdAt: new Date().toISOString()
    })
  }

  /**
   * 发送一条用户消息并流式接收助手回复：
   * 1. 校验输入与并发状态，空文本或已在流式生成时直接返回；
   * 2. 停止当前 TTS 播报，追加用户消息，并预先占位一条空的助手消息；
   * 3. 调用 streamCompanion 消费 SSE 流：
   *    - 首个事件携带 conversationId，用于保存/续聊；
   *    - 每收到 delta 就追加到助手消息内容，并增量推入 TTS 播报；
   * 4. 无论成功与否，finally 中复位 streaming。
   */
  async function send(text: string): Promise<void> {
    const content = text.trim()
    if (!content || streaming.value) return

    speech.stop()
    streaming.value = true
    error.value = ''
    messages.value.push(makeMessage('user', content))

    const assistant = makeMessage('assistant', '')
    messages.value.push(assistant)

    try {
      await streamCompanion(
        { message: content, conversationId: conversationId.value ?? undefined },
        {
          onEvent(event) {
            // 记录服务端下发的会话 ID（首个事件出现一次）
            if (event.conversationId) conversationId.value = event.conversationId
            // 增量文本：累加内容并同步驱动 TTS 流式播报
            if (event.delta) {
              assistant.content += event.delta
              speech.pushText(assistant.id, assistant.content)
            }
            if (event.error) error.value = event.error
          },
          onError(message) {
            error.value = message
            // 出错视为该条回复被中断
            assistant.interrupted = true
          },
          onClose() {
            // 无任何内容且无错误：视为被中断（如空回复）
            if (assistant.content === '' && !error.value) {
              assistant.interrupted = true
            }
            // 若开启自动朗读，告知 TTS 文本推送完毕，触发收尾播报
            if (speech.settings.autoRead) speech.finish(assistant.id)
          }
        }
      )
    } finally {
      streaming.value = false
    }
  }

  /**
   * 按会话 ID 加载历史消息，恢复本地聊天视图。
   * 请求失败时静默返回（保持现状）。
   */
  async function loadHistory(id: string): Promise<void> {
    const resp = await fetch(`/api/companion/history/${encodeURIComponent(id)}`)
    if (!resp.ok) return
    const data = (await resp.json()) as {
      conversationId: string
      messages: CompanionMessage[]
    }
    conversationId.value = data.conversationId
    messages.value = data.messages
  }

  /** 拉取历史会话列表（侧边栏展示用），失败时返回空数组 */
  async function loadConversations(): Promise<CompanionConversation[]> {
    const resp = await fetch('/api/companion/conversations')
    if (!resp.ok) return []
    return (await resp.json()) as CompanionConversation[]
  }

  /**
   * 重置会话状态：停止播报、清空消息与会话 ID，
   * 复位流式状态和错误信息。
   */
  function reset() {
    speech.stop()
    messages.value = []
    conversationId.value = null
    error.value = ''
    streaming.value = false
  }

  return {
    messages,
    conversationId,
    streaming,
    error,
    send,
    loadHistory,
    loadConversations,
    reset
  }
})

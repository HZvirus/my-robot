import { reactive, ref } from 'vue'
import {
  ChatClient,
  type ChatMessage,
  type WSMessage,
  getToken,
  setToken,
  clearToken,
  sendFeedback as apiFeedback,
} from '@my-robot/api-client'

interface StreamingState {
  active: boolean
  text: string
  messageId: string | null
}

export function useChat() {
  const messages = ref<ChatMessage[]>([])
  const connected = ref(false)
  const sessionId = ref<string | null>(null)
  const scene = ref<string>('hospital')
  const streaming = reactive<StreamingState>({ active: false, text: '', messageId: null })
  const error = ref<string | null>(null)
  let client: ChatClient | null = null

  function pushUser(text: string) {
    messages.value.push({
      id: crypto.randomUUID(),
      role: 'user',
      text,
    })
  }

  function startAssistant(): ChatMessage {
    const id = crypto.randomUUID()
    const msg: ChatMessage = { id, role: 'assistant', text: '', action: null, feedback: null }
    messages.value.push(msg)
    streaming.active = true
    streaming.text = ''
    streaming.messageId = null
    return msg
  }

  function handle(msg: WSMessage) {
    if (msg.type === 'status') {
      const p = msg.payload || {}
      if (p.state === 'connected') {
        connected.value = true
        sessionId.value = p.session_id ?? sessionId.value
      } else if (p.state === 'awaiting_input') {
        streaming.active = false
      } else if (p.event === 'escalate' || p.event === 'soothe') {
        error.value = p.message
      }
      return
    }
    if (msg.type === 'token') {
      streaming.text += msg.payload?.delta ?? ''
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') last.text = streaming.text
      return
    }
    if (msg.type === 'action') {
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') {
        last.action = msg.payload
      }
      return
    }
    if (msg.type === 'message') {
      streaming.active = false
      streaming.messageId = msg.payload?.message_id ?? null
      const last = messages.value[messages.value.length - 1]
      if (last && last.role === 'assistant') {
        last.text = msg.payload?.text ?? streaming.text
        last.scene = msg.payload?.scene
        last.id = msg.payload?.message_id ?? last.id
      }
      return
    }
    if (msg.type === 'error') {
      error.value = msg.payload?.message ?? '发生错误'
      streaming.active = false
    }
  }

  function connect(token: string, sceneName: string) {
    scene.value = sceneName
    if (client) client.close()
    client = new ChatClient({ token })
    client.on(handle)
    client.connect()
  }

  function send(text: string) {
    if (!text.trim() || !client) return
    pushUser(text)
    startAssistant()
    error.value = null
    client.sendChat(text)
  }

  async function feedback(message: ChatMessage, score: 1 | -1) {
    if (message.feedback === score) return
    message.feedback = score
    try {
      await apiFeedback({
        session_id: sessionId.value ?? '',
        message_id: message.id,
        score,
      })
    } catch {
      // 静默失败，骨架阶段不阻塞 UI
    }
  }

  function disconnect() {
    client?.close()
    client = null
    connected.value = false
  }

  return {
    messages,
    connected,
    sessionId,
    scene,
    streaming,
    error,
    connect,
    send,
    feedback,
    disconnect,
    getToken,
    setToken,
    clearToken,
  }
}

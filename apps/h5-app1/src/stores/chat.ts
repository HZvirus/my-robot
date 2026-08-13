import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { ChatConversation, ChatMessage } from '@my-robot/shared-types'
import { useSpeech } from '@my-robot/ui'
import { streamChat } from '@/api/chat'

const speech = useSpeech()

export const useChatStore = defineStore('chat', () => {
  const messages = ref<ChatMessage[]>([])
  const conversationId = ref<string | null>(null)
  const streaming = ref(false)
  const error = ref('')

  function makeMessage(role: 'user' | 'assistant', content: string): ChatMessage {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      createdAt: new Date().toISOString()
    }
  }

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
      await streamChat(
        { message: content, conversationId: conversationId.value ?? undefined },
        {
          onEvent(event) {
            if (event.conversationId) conversationId.value = event.conversationId
            if (event.delta) {
              assistant.content += event.delta
              speech.pushText(assistant.id, assistant.content)
            }
            if (event.error) error.value = event.error
          },
          onError(message) {
            error.value = message
            assistant.interrupted = true
          },
          onClose() {
            if (assistant.content === '' && !error.value) {
              assistant.interrupted = true
            }
            if (speech.settings.autoRead) speech.finish(assistant.id)
          }
        }
      )
    } finally {
      streaming.value = false
    }
  }

  async function loadHistory(id: string): Promise<void> {
    const resp = await fetch(`/api/chat/history/${encodeURIComponent(id)}`)
    if (!resp.ok) return
    const data = (await resp.json()) as {
      conversationId: string
      messages: ChatMessage[]
    }
    conversationId.value = data.conversationId
    messages.value = data.messages
  }

  async function loadConversations(): Promise<ChatConversation[]> {
    const resp = await fetch('/api/chat/conversations')
    if (!resp.ok) return []
    return (await resp.json()) as ChatConversation[]
  }

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

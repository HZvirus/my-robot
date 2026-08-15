import { defineStore } from 'pinia'
import { ref } from 'vue'
import type {
  Department,
  TriageConversation,
  TriageMessage,
  TriageSource
} from '@my-robot/shared-types'
import { fetchDepartments, streamTriage } from '@/api/triage'
import { authFetch } from '@/utils/auth'

export const useTriageStore = defineStore('triage', () => {
  const messages = ref<TriageMessage[]>([])
  const conversationId = ref<string | null>(null)
  const streaming = ref(false)
  const sources = ref<TriageSource[]>([])
  const error = ref('')
  const departments = ref<Department[]>([])
  const primaryDepartment = ref<Department | null>(null)
  const recommendedDepartments = ref<Department[]>([])

  function makeMessage(role: 'user' | 'assistant', content: string): TriageMessage {
    return {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      role,
      content,
      interrupted: false,
      createdAt: new Date().toISOString()
    }
  }

  async function ensureDepartments(): Promise<void> {
    if (departments.value.length) return
    departments.value = await fetchDepartments()
  }

  function departmentsFor(text: string): Department[] {
    if (!text) return []
    const found = departments.value.filter((d) => text.includes(d.name))
    return found.sort((a, b) => text.indexOf(a.name) - text.indexOf(b.name))
  }

  async function send(text: string): Promise<void> {
    const content = text.trim()
    if (!content || streaming.value) return

    streaming.value = true
    error.value = ''
    sources.value = []
    primaryDepartment.value = null
    recommendedDepartments.value = []
    messages.value.push(makeMessage('user', content))

    const assistant = makeMessage('assistant', '')
    messages.value.push(assistant)

    try {
      await streamTriage(
        { message: content, conversationId: conversationId.value ?? undefined },
        {
          onEvent(event) {
            if (event.conversationId) conversationId.value = event.conversationId
            if (event.delta) assistant.content += event.delta
            if (event.sources) sources.value = event.sources
            if (event.error) error.value = event.error
            if (event.department) primaryDepartment.value = event.department
            if (event.matchedDepartments) {
              recommendedDepartments.value = event.matchedDepartments
            }
          },
          onError(message) {
            error.value = message
            assistant.interrupted = true
          },
          onClose() {
            assistant.interrupted = assistant.content === ''
            if (!recommendedDepartments.value.length) {
              void ensureDepartments().then(() => {
                recommendedDepartments.value = departmentsFor(assistant.content)
              })
            }
          }
        }
      )
    } finally {
      streaming.value = false
    }
  }

  async function loadHistory(id: string): Promise<void> {
    const resp = await authFetch('/api/triage/history/' + encodeURIComponent(id))
    if (!resp.ok) return
    const data = (await resp.json()) as {
      conversationId: string
      messages: TriageMessage[]
    }
    conversationId.value = data.conversationId
    messages.value = data.messages
    const last = [...data.messages].reverse().find((m) => m.role === 'assistant')
    sources.value = last?.sources ?? []
    await ensureDepartments()
    recommendedDepartments.value = departmentsFor(last?.content ?? '')
  }

  async function loadConversations(): Promise<TriageConversation[]> {
    const resp = await authFetch('/api/triage/conversations')
    if (!resp.ok) return []
    return (await resp.json()) as TriageConversation[]
  }

  function reset() {
    messages.value = []
    conversationId.value = null
    sources.value = []
    error.value = ''
    streaming.value = false
    primaryDepartment.value = null
    recommendedDepartments.value = []
  }

  return {
    messages,
    conversationId,
    streaming,
    sources,
    error,
    departments,
    primaryDepartment,
    recommendedDepartments,
    send,
    loadHistory,
    loadConversations,
    ensureDepartments,
    departmentsFor,
    reset
  }
})

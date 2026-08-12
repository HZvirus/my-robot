export interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'system'
  content: string
  interrupted?: boolean
  createdAt: string
}

export interface ChatRequest {
  message: string
  conversationId?: string
}

export interface ChatResponse {
  reply: string
  conversationId: string
}

export interface ChatStreamEvent {
  conversationId?: string
  delta?: string
  done?: boolean
  error?: string
}

export interface ChatHistoryResponse {
  conversationId: string
  messages: ChatMessage[]
}

export interface ChatConversation {
  id: string
  createdAt: string
  preview: string
}

export interface ApiResult<T> {
  code: number
  data: T
  message: string
}

export interface TriageSource {
  file: string
  text: string
}

export interface Department {
  id: string
  name: string
  category: string
  description: string
}

export interface TriageStreamEvent {
  conversationId?: string
  delta?: string
  sources?: TriageSource[]
  department?: Department | null
  matchedDepartments?: Department[]
  done?: boolean
  error?: string
}

export interface TriageRequest {
  message: string
  conversationId?: string
}

export interface TriageMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  sources?: TriageSource[] | null
  interrupted: boolean
  createdAt: string
}

export interface TriageHistoryResponse {
  conversationId: string
  messages: TriageMessage[]
}

export interface TriageConversation {
  id: string
  createdAt: string
  preview: string
}

export interface CompanionRequest {
  message: string
  conversationId?: string
}

export interface CompanionStreamEvent {
  conversationId?: string
  delta?: string
  done?: boolean
  error?: string
}

export interface CompanionMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  interrupted: boolean
  createdAt: string
}

export interface CompanionHistoryResponse {
  conversationId: string
  messages: CompanionMessage[]
}

export interface CompanionConversation {
  id: string
  createdAt: string
  preview: string
}

export interface TtsStreamRequest {
  text: string
  voice?: string
  speed?: number
  volume?: number
  pitch?: number
}

export interface TtsStreamEvent {
  audio?: string
  error?: string
}

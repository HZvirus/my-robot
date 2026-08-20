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

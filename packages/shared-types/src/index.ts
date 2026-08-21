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

export interface AgentRunRequest {
  message: string
  conversationId?: string
}

export interface AgentStep {
  stepNo: number
  thought: string
  action: string
  observation: string
  status: string
}

export interface AgentRunResponse {
  conversationId: string
  answer: string
  steps: AgentStep[]
}

export interface AgentChatMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  steps: AgentStep[]
  createdAt: string
}

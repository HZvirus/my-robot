export type Scene = 'hospital' | 'home'

export interface Tenant {
  id: string
  name: string
  scene: Scene
  config: Record<string, unknown>
}

export interface User {
  id: string
  tenant_id: string
  name: string
  phone: string
  role: string
}

export interface LoginResp {
  access_token: string
  token_type: string
  expires_in: number
  user: User
  tenant: Tenant
}

export interface LoginReq {
  phone: string
  password: string
  tenant_id?: string
}

export interface FeedbackReq {
  session_id: string
  message_id: string
  score: 1 | -1
}

export type WSMessageType = 'token' | 'message' | 'action' | 'status' | 'error'

export interface WSMessage {
  type: WSMessageType
  session_id?: string
  payload: any
}

export interface ActionPayload {
  id: string
  type: string
  params: Record<string, any>
  status: string
}

export interface ChatMessage {
  id: string
  role: 'user' | 'assistant'
  text: string
  scene?: Scene
  action?: ActionPayload | null
  feedback?: 1 | -1 | null
}

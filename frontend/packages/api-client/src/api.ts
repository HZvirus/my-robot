import { http } from './http'
import type { FeedbackReq, LoginReq, LoginResp, User } from './types'

export async function login(req: LoginReq): Promise<LoginResp> {
  const { data } = await http.post<LoginResp>('/auth/login', req)
  return data
}

export async function refresh(): Promise<LoginResp> {
  const { data } = await http.post<LoginResp>('/auth/refresh')
  return data
}

export async function getMe(): Promise<User> {
  const { data } = await http.get<User>('/users/me')
  return data
}

export async function listTenants() {
  const { data } = await http.get('/tenants')
  return data
}

export async function sendFeedback(req: FeedbackReq): Promise<{ ok: boolean; id: string }> {
  const { data } = await http.post('/feedback', req)
  return data
}

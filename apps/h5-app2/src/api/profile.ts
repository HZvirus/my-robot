import axios from 'axios'
import type { ApiResult } from '@my-robot/shared-types'

const http = axios.create({ baseURL: '/api' })

interface Profile {
  nickname: string
}

export function getProfile(): Promise<ApiResult<Profile>> {
  return http.get<ApiResult<Profile>>('/profile').then((r) => r.data)
}

export function updateProfile(payload: Profile): Promise<ApiResult<Profile>> {
  return http.put<ApiResult<Profile>>('/profile', payload).then((r) => r.data)
}

import axios, { type AxiosInstance } from 'axios'

const TOKEN_KEY = 'robot_token'

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token)
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY)
}

export function createHttp(baseURL = '/api'): AxiosInstance {
  const http = axios.create({
    baseURL,
    timeout: 15000,
  })

  http.interceptors.request.use((config) => {
    const token = getToken()
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  http.interceptors.response.use(
    (resp) => resp,
    (error) => {
      if (error?.response?.status === 401) {
        clearToken()
        window.dispatchEvent(new CustomEvent('robot:unauthorized'))
      }
      return Promise.reject(error)
    },
  )

  return http
}

export const http = createHttp(
  (import.meta.env.VITE_API_BASE as string | undefined) ?? '/api',
)

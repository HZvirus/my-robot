/**
 * 匿名设备鉴权：首次使用生成设备令牌并到后端换取 user id，
 * 之后所有需鉴权请求带 Authorization: Bearer <token>。
 * 令牌仅保存在本机 localStorage，后端只存其 SHA-256 哈希。
 */
const TOKEN_KEY = 'my-robot:device-token'
const USER_KEY = 'my-robot:user-id'

let registerPromise: Promise<void> | null = null

function generateToken(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID() + '-' + Math.random().toString(36).slice(2, 10)
  }
  return (
    Date.now().toString(36) +
    '-' +
    Math.random().toString(36).slice(2, 10) +
    Math.random().toString(36).slice(2, 10)
  )
}

export function getDeviceToken(): string {
  let token = localStorage.getItem(TOKEN_KEY)
  if (!token) {
    token = generateToken()
    localStorage.setItem(TOKEN_KEY, token)
  }
  return token
}

/** 确保设备已在后端注册（幂等；失败后允许下次重试） */
export async function ensureAuth(): Promise<void> {
  if (localStorage.getItem(USER_KEY)) return
  if (!registerPromise) {
    registerPromise = (async () => {
      try {
        const resp = await fetch('/api/auth/device', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ deviceId: getDeviceToken() })
        })
        if (!resp.ok) throw new Error('register failed: ' + resp.status)
        const data = (await resp.json()) as { userId: string }
        localStorage.setItem(USER_KEY, data.userId)
      } finally {
        registerPromise = null
      }
    })()
  }
  await registerPromise
}

/** 带鉴权头的 fetch：自动先完成设备注册，再附加 Bearer 令牌 */
export async function authFetch(url: string, init: RequestInit = {}): Promise<Response> {
  try {
    await ensureAuth()
  } catch {
    // 注册失败仍发起请求，由后端 401 触发上层错误提示
  }
  const headers = new Headers(init.headers)
  headers.set('Authorization', 'Bearer ' + getDeviceToken())
  return fetch(url, { ...init, headers })
}

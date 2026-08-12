export interface SseHandlers<T> {
  onEvent: (event: T) => void
  onError: (message: string) => void
  onClose: () => void
}

/**
 * POST a JSON body and consume the SSE response via fetch + ReadableStream.
 * EventSource cannot be used: it is GET-only and cannot send a request body.
 */
export async function readSse<T>(
  url: string,
  body: unknown,
  handlers: SseHandlers<T>
): Promise<void> {
  const { onEvent, onError, onClose } = handlers
  try {
    const resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    })

    if (!resp.ok) {
      onError(`请求失败 (${resp.status})`)
      onClose()
      return
    }

    if (!resp.body) {
      onError('浏览器不支持流式响应')
      onClose()
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''

    for (;;) {
      const { done, value } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() ?? ''
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed.startsWith('data:')) continue
        const payload = trimmed.slice(5).trim()
        if (!payload || payload === '[DONE]') continue
        try {
          onEvent(JSON.parse(payload) as T)
        } catch {
          // ignore malformed frames
        }
      }
    }
    onClose()
  } catch (err) {
    onError(err instanceof Error ? err.message : '网络错误')
    onClose()
  }
}

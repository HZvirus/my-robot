# 05 · 前端流式处理

## 1. 为什么用 `fetch` + `ReadableStream`，而不是 `EventSource`

`EventSource` 只能 GET，无法携带 POST body，因此所有流式接口都用 **POST + SSE**。前端统一封装 `readSse()`（`apps/h5-app2/src/utils/sse.ts`），内部用 `fetch` + `response.body.getReader()` 按行解析：

```ts
export async function readSse<T>(
  url: string,
  body: unknown,
  handlers: SseHandlers<T>
): Promise<void> {
  const resp = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body)
  })
  const reader = resp.body!.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  for (;;) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() ?? ''                 // 半行留在 buffer，下个分片再接
    for (const line of lines) {
      const trimmed = line.trim()
      if (!trimmed.startsWith('data:')) continue
      const payload = trimmed.slice(5).trim()
      if (!payload || payload === '[DONE]') continue
      try {
        onEvent(JSON.parse(payload) as T)
      } catch {
        // 忽略损坏帧
      }
    }
  }
  onClose()
}
```

要点：

- `TextDecoder(..., { stream: true })` 正确处理多字节 UTF-8 跨分片（中文）。
- 每次 `read()` 后按 `\n` 切行，尾部残行留到下一轮，防止 JSON 被截断。
- `onEvent / onError / onClose` 三个回调与后端 SSE 事件一一对应。

## 2. 数据流（前端视角）

```
用户输入
  → store.send(text) 压入 user 气泡 + 空 assistant 气泡
  → streamCompanion() / streamScience()
  → onEvent:
      conversationId → 记录会话
      delta          → assistant.content += delta（TypewriterText 逐字渲染）
      error          → 展示错误
  → onClose: 若内容为空置 interrupted，结束朗读
```

### 会话状态（Pinia）

- `apps/h5-app2/src/stores/companion.ts`：管理陪伴聊天的消息流（`reactive` 保持增量可响应），`send()` 负责组装 SSE 请求并驱动增量。
- `apps/h5-app2/src/stores/science.ts`：同 companion，纯文本科普助手（无 TTS/语音）。

### API 层

- `src/api/companion.ts`：`streamCompanion`（`/api/companion/chat`）。
- `src/api/science.ts`：`streamScience`（`/api/science/chat`）。

## 3. 逐字渲染：`TypewriterText`

`packages/ui/src/components/TypewriterText.vue`：

- `active` 期间按 16ms 定时器分步截取文本（每步至少 1 字符，最多补足剩余 1/6），制造「打字机」效果并带 `▌` 光标。
- 结束（`active=false`）时直接显示全文，避免闪烁。

```html
<TypewriterText
  v-if="m.role === 'assistant'"
  :text="m.content"
  :active="m.id === activeAssistantId"
/>
```

`activeAssistantId` 由 view 计算：`store.streaming` 时取最后一条 assistant 消息。

## 4. 语音朗读：`useSpeech`

见 `packages/ui/src/composables/useSpeech.ts`，配合讯飞 TTS（[03-iflytek-tts.md](./03-iflytek-tts.md)）：

- **边聊边读**：`pushText(id, content)` 接收 SSE 增量，按句号/问号等切句，第一句立即合成，后续攒批（≥2 句 / ≥400 字节 / ≥1 秒）再合成，减少请求数。
- **播放引擎**：
  - Web Audio：MP3 帧到达即 `decodeAudioData`，按累计 `playhead` `bufferSource.start()` 无缝排程，音频随打字机一起推进。
  - 回退：`decodeAudioData` 失败或 Safari/iOS 缺 `AudioContext` 时，整句缓冲后走链式 `<audio>` 播放。
- **文本清洗**：`cleanTtsText()` 剥掉代码块/行内代码/Markdown 标记再送去合成。
- **设置**：`autoRead/voice/speed/volume/pitch` 存在 `localStorage`；`SpeechButton` 提供手动「朗读/暂停/继续」。

## 5. 开发联调

- `vite.config.ts` 已把 `/api` 代理到 `http://localhost:8000`（h5-app2:5174），前端无需处理跨域。
- 后端 CORS 白名单默认包含 5174。
- 手动验证流式：`curl -N -X POST http://localhost:8000/api/companion/chat -H "Content-Type: application/json" -d '{"message":"你好"}'`

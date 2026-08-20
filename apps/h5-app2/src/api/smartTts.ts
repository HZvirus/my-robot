/**
 * SSE/WSS 流式响应中的单个事件帧：
 * - audio：base64 编码的 MP3 音频片段（可累加拼接）
 * - error：服务端返回的错误信息
 */
export interface SmartTtsStreamEvent {
  audio?: string
  error?: string
}

/** 文本流式合成请求参数（全部可选，缺省由服务端决定） */
export interface SmartTtsStreamTextOptions {
  voice?: string // 音色 ID（见 useSmartTts 的 SMART_TTS_VOICES）
  speed?: number // 语速（0-100）
  volume?: number // 音量（0-100）
  pitch?: number // 音调（0-100）
  sampleRate?: number // 采样率
  oralLevel?: string // 口语化程度
}

/** 流式请求的回调处理器 */
export interface SmartTtsStreamHandlers {
  onEvent: (event: SmartTtsStreamEvent) => void // 每个音频/错误帧到达时触发
  onError: (message: string) => void // 请求或网络出错时触发
  onClose: () => void // 流结束、被 end()/abort() 触发或出错兜底后触发
}

/**
 * 流式合成客户端接口（由 streamSmartTtsWs 返回）：
 * - push(text)：增量追加一段待合成文本（即时发送）
 * - end()：标记文本推送完毕（发送结束帧）
 * - abort()：取消请求，立即终止
 * - done：整个请求流程完成的 Promise
 */
export interface SmartTtsTextStreamClient {
  push(text: string): void
  end(): void
  abort(): void
  done: Promise<void>
}

/**
 * SSE 流式响应中的单个事件帧：
 * - audio：base64 编码的 MP3 音频片段（可累加拼接）
 * - error：服务端返回的错误信息
 */
export interface SmartTtsStreamEvent {
  audio?: string;
  error?: string;
}

/** 文本流式合成请求参数（全部可选，缺省由服务端决定） */
export interface SmartTtsStreamTextOptions {
  voice?: string; // 音色 ID（见 useSmartTts 的 SMART_TTS_VOICES）
  speed?: number; // 语速（0-100）
  volume?: number; // 音量（0-100）
  pitch?: number; // 音调（0-100）
  sampleRate?: number; // 采样率
  oralLevel?: string; // 口语化程度
}

/** 流式请求的回调处理器 */
export interface SmartTtsStreamHandlers {
  onEvent: (event: SmartTtsStreamEvent) => void; // 每个 SSE 音频/错误帧到达时触发
  onError: (message: string) => void; // 请求或网络出错时触发
  onClose: () => void; // 流正常结束、被 end()/abort() 触发或出错兜底后触发
}

/**
 * 流式合成客户端接口（由 streamSmartTtsText 返回）：
 * - push(text)：增量追加一段待合成文本（本地缓冲，end 时才真正发出）
 * - end()：标记文本推送完毕，触发单次 POST 请求并开始消费 SSE 音频
 * - abort()：取消请求，立即终止
 * - done：整个请求流程（fetch + 读取完 SSE）完成的 Promise
 */
export interface SmartTtsTextStreamClient {
  push(text: string): void;
  end(): void;
  abort(): void;
  done: Promise<void>;
}

/**
 * 向 `/api/smart-tts/stream-text` 发起文本流式合成请求。
 *
 * 请求体为 NDJSON：每行一个 JSON 编码的文本片段（{"text":"..."}）；
 * 响应为 SSE 格式，通过 data: 行逐帧回传 MP3 音频。
 *
 * 设计要点：
 * 1. 所有 push() 的文本先缓存在本地，end() 时才拼接为单个 POST 请求体发送：
 *    - 后端在回传音频前会先缓冲整个请求体；
 *    - Chrome 对 HTTP/1.1 下的流式（ReadableStream）请求体会报
 *      ERR_ALPN_NEGOTIATION_FAILED，所以不能边推边传。
 * 2. SSE 按行解析，行可能被 TCP 分片拆开，因此用 buffer 暂存半个行。
 */
export function streamSmartTtsText(
  options: SmartTtsStreamTextOptions,
  handlers: SmartTtsStreamHandlers,
): SmartTtsTextStreamClient {
  /** 用于中止 fetch 请求的 AbortController */
  const abortCtrl = new AbortController();
  /** 已 push 的文本行缓冲（每行一个 JSON 片段） */
  const lines: string[] = [];
  /** 是否已 end()/abort()，防止重复发送或重复 push */
  let ended = false;
  /** 整个请求流程完成的 Promise（abort/出错也会 resolve） */
  let donePromise: Promise<void> = Promise.resolve();

  /**
   * 发起单次 POST 请求并消费 SSE 响应流。
   * 结果挂到 donePromise 上，供外部 await。
   */
  function send(): void {
    donePromise = (async () => {
      try {
        const resp = await fetch("/api/smart-tts/stream-text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: lines.join(""),
          signal: abortCtrl.signal,
        });
        // HTTP 层失败：直接回报错误并关闭
        if (!resp.ok) {
          handlers.onError(`请求失败 (${resp.status})`);
          handlers.onClose();
          return;
        }
        // 浏览器不支持流式响应体
        if (!resp.body) {
          handlers.onError("浏览器不支持流式响应");
          handlers.onClose();
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        // buffer 暂存未成行的残留数据，应对 SSE 帧被 TCP 拆包的情况
        let buffer = "";
        for (;;) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;
          buffer += decoder.decode(value, { stream: true });
          const sseLines = buffer.split("\n");
          // 最后一段可能是不完整行，留在 buffer 等下一块数据补齐
          buffer = sseLines.pop() ?? "";
          for (const line of sseLines) {
            const trimmed = line.trim();
            // 仅处理 data: 开头的 SSE 数据行
            if (!trimmed.startsWith("data:")) continue;
            const payload = trimmed.slice(5).trim();
            // 跳过空行与结束标记
            if (!payload || payload === "[DONE]") continue;
            try {
              handlers.onEvent(JSON.parse(payload) as SmartTtsStreamEvent);
            } catch {
              // ignore malformed frames
            }
          }
        }
        // 读取完整个响应流，通知关闭
        handlers.onClose();
      } catch (err) {
        console.error("Error in streamSmartTtsText:", err);
        // 主动 abort 触发的异常属于预期行为，不再重复报错
        if (abortCtrl.signal.aborted) return;
        handlers.onError(err instanceof Error ? err.message : "网络错误");
        handlers.onClose();
      }
    })();
  }

  return {
    /**
     * 增量追加一段待合成文本。
     * 仅本地缓冲为一行 JSON，不触发网络请求；end() 后调用被忽略。
     */
    push(text: string): void {
      if (ended) return;
      lines.push(JSON.stringify({ text }) + "\n");
    },
    /**
     * 结束文本推送并触发实际请求。
     * 无任何文本时不会发请求，直接回调 onClose()。
     */
    end(): void {
      if (ended) return;
      ended = true;
      if (lines.length === 0) {
        handlers.onClose();
        return;
      }
      send();
    },
    /** 中止请求：标记结束并 abort 底层 fetch */
    abort(): void {
      ended = true;
      abortCtrl.abort();
    },
    /** 暴露请求流程的 Promise，可 await 整次合成完成 */
    get done(): Promise<void> {
      return donePromise;
    },
  };
}

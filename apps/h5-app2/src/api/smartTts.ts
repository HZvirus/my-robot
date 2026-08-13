export interface SmartTtsStreamEvent {
  audio?: string;
  error?: string;
}

export interface SmartTtsStreamTextOptions {
  voice?: string;
  speed?: number;
  volume?: number;
  pitch?: number;
  sampleRate?: number;
  oralLevel?: string;
}

export interface SmartTtsStreamHandlers {
  onEvent: (event: SmartTtsStreamEvent) => void;
  onError: (message: string) => void;
  onClose: () => void;
}

export interface SmartTtsTextStreamClient {
  push(text: string): void;
  end(): void;
  abort(): void;
  done: Promise<void>;
}

/**
 * POST to `/api/smart-tts/stream-text` with an NDJSON request body (one
 * JSON-encoded text piece per line) and consume the SSE audio response.
 *
 * Text pieces are buffered locally and sent in a single POST on `end()`: the
 * backend buffers the body before streaming audio back anyway, and Chrome
 * rejects streaming (ReadableStream) request bodies over HTTP/1.1 with
 * ERR_ALPN_NEGOTIATION_FAILED.
 */
export function streamSmartTtsText(
  options: SmartTtsStreamTextOptions,
  handlers: SmartTtsStreamHandlers,
): SmartTtsTextStreamClient {
  const abortCtrl = new AbortController();
  const lines: string[] = [];
  let ended = false;
  let donePromise: Promise<void> = Promise.resolve();

  function send(): void {
    donePromise = (async () => {
      try {
        const resp = await fetch("/api/smart-tts/stream-text", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: lines.join(""),
          signal: abortCtrl.signal,
        });
        if (!resp.ok) {
          handlers.onError(`请求失败 (${resp.status})`);
          handlers.onClose();
          return;
        }
        if (!resp.body) {
          handlers.onError("浏览器不支持流式响应");
          handlers.onClose();
          return;
        }
        const reader = resp.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done: streamDone, value } = await reader.read();
          if (streamDone) break;
          buffer += decoder.decode(value, { stream: true });
          const sseLines = buffer.split("\n");
          buffer = sseLines.pop() ?? "";
          for (const line of sseLines) {
            const trimmed = line.trim();
            if (!trimmed.startsWith("data:")) continue;
            const payload = trimmed.slice(5).trim();
            if (!payload || payload === "[DONE]") continue;
            try {
              handlers.onEvent(JSON.parse(payload) as SmartTtsStreamEvent);
            } catch {
              // ignore malformed frames
            }
          }
        }
        handlers.onClose();
      } catch (err) {
        console.error("Error in streamSmartTtsText:", err);
        if (abortCtrl.signal.aborted) return;
        handlers.onError(err instanceof Error ? err.message : "网络错误");
        handlers.onClose();
      }
    })();
  }

  return {
    push(text: string): void {
      if (ended) return;
      lines.push(JSON.stringify({ text }) + "\n");
    },
    end(): void {
      if (ended) return;
      ended = true;
      if (lines.length === 0) {
        handlers.onClose();
        return;
      }
      send();
    },
    abort(): void {
      ended = true;
      abortCtrl.abort();
    },
    get done(): Promise<void> {
      return donePromise;
    },
  };
}

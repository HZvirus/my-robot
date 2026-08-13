# 07 · 超拟人 TTS 流式合成与播放（小安快速版）

本文档总结「健康陪伴快速版」（`apps/h5-app2`）的语音方案：基于**讯飞超拟人（Super Smart TTS，x6 系列音色）**的增量流式合成与浏览器端低延迟播放。

与 [03-iflytek-tts.md](./03-iflytek-tts.md) 的差异：

| | 03 · 讯飞 v2 TTS | 07 · 超拟人 TTS |
| --- | --- | --- |
| 文本发送 | 整段一帧（`status=2`） | 双向流式，文本分帧 0/1/2 增量发送 |
| 传输链路 | 后端 WS → SSE 转发 | 后端 SSE 转发 **或** 浏览器 WebSocket 直连 |
| 前端路径 | `packages/ui/useSpeech.ts` | `apps/h5-app2` 的 `useSmartTts*` |
| 目标 | 智能助手 / 智能导诊 | 健康陪伴快速版（小安） |

## 1. 代码位置

**后端（`apps/ai-service/app/`）**

- 路由：`api/routes/smart_tts.py`
  - `POST /api/smart-tts/stream`：整段文本 → 音频（SSE）
  - `POST /api/smart-tts/stream-text`：增量文本帧 → 音频（SSE，请求体为 NDJSON）
  - `GET /api/smart-tts/ws-url`：后端签名下发 WebSocket 直连地址（供前端直连）
- 服务：`services/smart_tts_service.py`
  - `synthesize()`：单帧（status 2）合成，整段文本一次发送
  - `synthesize_stream()`：文本分帧（status 0/1 → 2）发送，音频同会话流回
  - `build_url()`：HMAC-SHA256 签名 URL（鉴权方式二，供 ws-url 接口使用）
  - `_build_frame()` / `_recv_audio()`：协议帧构造与音频接收
- 配置：`app/core/config.py` 的 `IFLYTEK_SMART_TTS_*`
- 测试：`tests/test_smart_tts.py`

**前端（`apps/h5-app2/src/`）**

- 视图：`views/CompanionFastView.vue`（入口页，切到 WebSocket 直连传输层）
- 合成 API：`api/smartTts.ts`（SSE 传输层）、`api/smartTtsWs.ts`（WS 直连传输层）
- 播放引擎：`composables/useSmartTts.ts`（MSE 主 / Web Audio 兜底）
- 传输层切换：`composables/useSmartTtsWs.ts`（模块级单例，页面卸载时用 `useSmartTts()` 恢复）
- 会话状态：`stores/companion.ts`（`send()` 内 `pushText`/`finish` 驱动播报）
- 前端**不持有**任何讯飞凭据

## 2. 传输层

播放引擎与传输层解耦：`useSmartTts.ts` 通过模块级 `smartTtsTransport` 注入传输实现，统一使用同一套播放引擎与设置。

### 2.1 SSE 转发（默认，`api/smartTts.ts`）

`streamSmartTtsText()`：`push()` 的文本本地缓冲为 NDJSON 行，`end()` 时单次 POST 到 `/api/smart-tts/stream-text`，按行解析 SSE `data:` 帧回传音频。实现要点：

- Chrome 对 HTTP/1.1 下流式请求体会报 `ERR_ALPN_NEGOTIATION_FAILED`，因此**不能边推边传**，必须 end 时整体发出；
- SSE 行可能被 TCP 拆包，用 `buffer` 暂存半个行再按 `\n` 切分。

### 2.2 WebSocket 直连（快速版，`api/smartTtsWs.ts`）

`streamSmartTtsWs()`：`push()` 的文本按协议帧（`header.status`/`payload.status` 0/1/2、递增 `seq`）**随到随发**，音频帧 `onEvent` 随收随报，跳过服务端 SSE 转发，进一步降低首响延迟。

- **鉴权（统一走后端签名）**：浏览器 WebSocket 握手无法附加 `x-api-key` 头，因此直连只能使用鉴权方式二（HMAC-SHA256 签名 URL）。签名统一由后端完成：前端先请求 `GET /api/smart-tts/ws-url` 获取 `{url, app_id}` 再建立连接，**前端不持有任何讯飞凭据**。后端要求 `IFLYTEK_SMART_TTS_AUTH_METHOD=2` 并配置 `IFLYTEK_SMART_TTS_API_KEY` / `IFLYTEK_SMART_TTS_API_SECRET`；SSE 转发路径两种鉴权方式均可用。
- **文本帧状态**：首帧 `status=0`、中间 `1`、末帧 `2`；`end()` 时剩余缓冲以 `status=2` 发出，若从未发过帧则补发一个空结束帧。
- **音频**：`lame`（MP3），默认 `sample_rate=24000`，`channels=1`，`bit_depth=16`。

## 3. 播放引擎（`composables/useSmartTts.ts`）

音频数据统一走 `enqueueAudioChunk()` 路由到三类引擎（`startFeed` 时按浏览器能力选择）：

1. **MediaSource (MSE，首选)**：`audio/mpeg` SourceBuffer 逐帧 `appendBuffer`，浏览器解码器跨 chunk 保持连续状态，帧与帧之间无缝衔接，彻底避免块边界卡顿。
   - 写入背压：`drainMseQueue()` 在 `updating` 期间排队；
   - 内存控制：`trimMseBuffer()` 定期移除当前播放点 5s 之前的已播区间；
   - 首个缓冲就绪即 `ensureMsePlaying()` 启动播放；
   - 流结束：`endMse()` → 队列写空后 `endOfStream()`，`<audio>` `ended` 事件触发收尾。
2. **Web Audio（MSE 不支持时的兜底）**：攒够约 3 帧 / 12KB 才 `concatBytes` 整体 `decodeAudioData` 一次，段首 40ms 淡入掩盖批边界解码器毛刺；流关闭时 `flushWebAudioBatch` 冲刷尾部。
3. **`<audio>`（fallback，最终兜底）**：MP3 打包 Blob 入队逐段播放。

## 4. 数据流（一次完整对话）

```
CompanionFastView.send()
  → store.send()                    // stores/companion.ts
      speech.stop()                 // 停旧播报
      streamCompanion(SSE)          // LLM 增量文本
        onEvent(delta) → assistant.content += delta
                       → speech.pushText(id, content)   // 增量推文本
      onClose → speech.finish(id)   // 发送文本结束帧(status 2)
  → useSmartTts.pushText()
      → smartTtsTransport(...)      // WS 直连 或 SSE 转发
      → [WS 直连] GET /api/smart-tts/ws-url（后端签名）→ new WebSocket(url)
      → 音频帧 onEvent → enqueueAudioChunk()
        → MSE appendBuffer  / Web Audio 攒批解码
      → onClose → endMse() / flushWebAudioBatch() → 播完收尾
```

## 5. 关键问题与修复

### 5.1 26005 超时（`No active up data within 14000 ms`）

**原因**：`flushPending()` 在 `end()` 时若文本此前已全部按 status 0/1 发完（`pending` 为空），不会补发 `status=2` 结束帧；服务端 14s 收不到上行数据即报 `code: 26005`。

**修复**（`api/smartTtsWs.ts`）：新增 `finalSent` 标记，`end()` 后无论缓冲是否为空都保证发一个结束帧（空文本 `status=2`），与后端 `synthesize_stream()` 的 `pending or ""` 行为对齐。

### 5.2 逐帧解码卡顿

**原因**：每帧独立 `decodeAudioData` 播放会产生块边界瑕疵——MPEG Layer III 比特水库（bit reservoir）让每块开头的帧冷启动解码出现瞬时劣化/静音，且解码器只在流头有 Xing/LAME 头时正确裁剪 priming delay。

**修复**：采用 **MSE** 连续解码；不支持的浏览器退回 **攒批整体解码 + 淡入**。

### 5.3 首响延迟

原实现把全部音频累积到流结束才播放。现在音频帧**边收边播**：MSE 下首个音频帧到达即开始播放，Web Audio 兜底下约 1~2s（攒批阈值）后开始。

## 6. 注意事项

- **iOS Safari 不支持 `audio/mpeg` 的 MSE**（`MediaSource.isTypeSupported` 返回 false），自动走 Web Audio 兜底路径；Android Chrome / 微信 X5（Blink）支持 MSE。
- **自动播放策略**：依赖用户点击「发送」产生的 sticky activation；`<audio>`/`AudioContext` 在首次有数据时才 `play()`/`resume()`。
- **凭据安全**：凭据仅存在于后端（`.env`），前端不持有；`ws-url` 返回的签名 URL 含当前 `date`，属短期有效。
- **生命周期**：传输层与播放引擎为模块级单例；离开 `CompanionFastView` 时需 `useSmartTts()` 恢复 SSE 传输层并 `speech.stop()`。

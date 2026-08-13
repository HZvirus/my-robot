# 03 · 使用讯飞（语音合成 TTS）

智能助手 / 健康陪伴的回复支持语音朗读，语音由**讯飞开放平台**的 WebSocket TTS 接口合成。后端 `/api/tts/stream` 把 MP3 音频分块以 SSE 推给前端，前端实时解码播放（见 [05-frontend-streaming.md](./05-frontend-streaming.md) 的「语音朗读」小节）。

## 1. 配置（`.env`）

```ini
IFLYTEK_APP_ID=...
IFLYTEK_API_KEY=...
IFLYTEK_API_SECRET=...
IFLYTEK_TTS_URL=wss://tts-api.xfyun.cn/v2/tts
IFLYTEK_TTS_VOICE=xiaoyan
IFLYTEK_TTS_SPEED=50
IFLYTEK_TTS_VOLUME=50
IFLYTEK_TTS_PITCH=50
IFLYTEK_TTS_MAX_BYTES=8000
```

三个密钥缺一不可；未配置时 `synthesize()` 抛 `RuntimeError("iFlytek TTS is not configured")`，路由会把错误以 SSE `error` 事件返回。

## 2. 接口

- `POST /api/tts/stream`，请求体：`{text, voice?, speed?, volume?, pitch?}`
- 响应为 SSE：`data: {"audio":"<base64 MP3 分块>"}`，结束 `data: [DONE]`；失败 `data: {"error":"..."}`。

```bash
curl -N -X POST http://localhost:8000/api/tts/stream \
  -H "Content-Type: application/json" \
  -d '{"text":"你好，欢迎来到示例医院"}'
```

## 3. 实现（`app/services/tts_service.py`）

### 3.1 WebSocket 鉴权（HMAC-SHA256）

讯飞 v2 TTS 要求每次握手对 URL 做签名，签名串为三行：

```
host: tts-api.xfyun.cn
date: <RFC 1123 GMT 时间>
GET /v2/tts HTTP/1.1
```

用 `api_secret` 做 HMAC-SHA256，拼出 `authorization`，再整体 base64 后拼入 query 参数：

```python
signature = base64.b64encode(
    hmac.new(api_secret, signature_origin, digestmod=hashlib.sha256).digest()
).decode()
authorization = base64.b64encode(
    f'api_key="{api_key}", algorithm="hmac-sha256", '
    f'headers="host date request-line", signature="{signature}"'
).decode()
url = f"{base_url}?authorization={quote(authorization)}&date={quote(date)}&host={host}"
```

`date` 每次请求都取当前 GMT 时间，不可缓存。

### 3.2 协议要点

- **整段文本一帧发送**：v2 接口不支持分帧增量文本，`data.status = 2` 表示最后一帧（也是唯一一帧），文本 `base64(UTF-8)`。
- **音频格式**：`aue = "lame"` 输出 MP3（配合 `sfl=1`、`tte="UTF8"`）。
- **发音人 `vcn`**：默认 `xiaoyan`，可传 `voice` 覆盖（前端可选值见 `useSpeech.ts` 的 `TTS_VOICES`）。
- **超长文本**：超过 `IFLYTEK_TTS_MAX_BYTES`（8000 字节）时按 UTF-8 字节边界截断（`_truncate_to_bytes`），避免接口报错。

### 3.3 音频流式返回

```python
async with websockets.connect(url) as ws:
    await ws.send(json.dumps(request, ensure_ascii=False))
    while True:
        message = json.loads(await ws.recv())
        if message.get("code") != 0:
            raise RuntimeError(f"iFlytek TTS error {code}: {msg} sid={sid}")
        audio = message.get("data", {}).get("audio")
        if audio:
            yield base64.b64decode(audio)     # 每帧 MP3 直接产出
        if message.get("data", {}).get("status") == 2:
            break                              # 服务端结束
```

路由把每个 `bytes` 帧 base64 后包装成 SSE 事件，前端可边收边播。

## 4. 前端

前端朗读能力封装在 `packages/ui/src/composables/useSpeech.ts`（`useSpeech()`）：

- **设置持久化**：`autoRead/voice/speed/volume/pitch` 存于 `localStorage`（`my-robot:tts-settings`）。
- **边聊边读**：聊天 SSE 的 `delta` 累积到完整句子后立即调 `/api/tts/stream` 合成该句（`pushText`）；第一句立即合成，后续句子按「≥2 句 / ≥400 字节 / ≥1 秒」攒批（utterance）减少连接数。
- **播放引擎**：优先 Web Audio（MP3 解码后按播放游标无缝排程）；`decodeAudioData` 失败或 Safari/iOS 不支持时，自动降级为链式 `<audio>` 元素回放。
- **文本清洗**：合成前用 `cleanTtsText` 去掉代码块、行内代码、Markdown 标记，避免读出 `#`、反引号等。

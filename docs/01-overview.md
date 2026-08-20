# 01 · 导诊与聊天总体架构

## 1. 模块划分

后端（`apps/ai-service`，FastAPI）提供三类「对话」能力，共享同一套 SQLite 会话持久化与 SSE 流式传输：

| 能力 | 服务类 | 路由 | 特点 |
| --- | --- | --- | --- |
| 通用聊天 | `ChatService`（`services/chat_service.py`） | `/api/chat/stream` | 通用系统提示词，仅带历史上下文 |
| 健康陪伴 | `CompanionService`（`services/companion_service.py`） | `/api/companion/chat` | 暖心理人设「小安」，含急重症提醒 |
| 科普百科 | `ScienceService`（`services/science_service.py`） | `/api/science/chat` | 人设「小科」，通俗科普讲解，纯文本无语音 |
| 智能导诊 | `TriageService`（`services/triage_service.py`） | `/api/triage/chat` | RAG：检索知识库 → 注入上下文 → 推荐科室 |

四个服务结构高度一致：`stream_answer()` 均为异步生成器，按固定顺序产出 SSE 事件 dict，流结束后把「用户 + 助手」两条消息落库。

此外还有：

- `POST /api/chat`：旧的**非流式**聊天，同样走本地 Ollama（`services/ai_service.py`），响应为普通 JSON（snake_case 字段，历史遗留）。
- `POST /api/tts/stream`：讯飞 TTS，见 [03-iflytek-tts.md](./03-iflytek-tts.md)。

## 2. 目录结构

```
apps/ai-service/
├── app/
│   ├── main.py                 # FastAPI 入口：lifespan 建表、挂载路由、CORS
│   ├── api/routes/             # chat / companion / science / triage / tts / profile
│   ├── services/               # 业务与 AI 逻辑（见上表）
│   ├── models/                 # Pydantic DTO（camelCase 别名）
│   ├── db/
│   │   ├── session.py          # engine / SessionLocal / Base / get_db
│   │   └── models.py           # Conversation、Message ORM
│   └── core/                   # config（Settings）、logger
├── scripts/ingest_kb.py        # 知识库入库 CLI
├── knowledge/*.md              # 医院知识库（科室、症状、挂号等）
└── tests/
```

前端：

- `apps/h5-app2`：健康陪伴（`/`、`/companion`、`/companion/smart`、`/companion/fast`）、科普百科（`/science`）、设置（`/settings`）。
- 共享 `packages/ui` 提供 `TypewriterText`（逐字渲染）、`SpeechButton`、`useSpeech`（语音朗读）。

## 3. 配置项（`app/core/config.py` 与 `.env`）

```ini
# 通用聊天 / 健康陪伴 / 科普百科的历史条数上限
CHAT_MAX_HISTORY=10
COMPANION_MAX_HISTORY=12
SCIENCE_MAX_HISTORY=12

# 讯飞 TTS
IFLYTEK_APP_ID=...
IFLYTEK_API_KEY=...
IFLYTEK_API_SECRET=...
IFLYTEK_TTS_URL=wss://tts-api.xfyun.cn/v2/tts
IFLYTEK_TTS_VOICE=xiaoyan
IFLYTEK_TTS_SPEED=50
IFLYTEK_TTS_VOLUME=50
IFLYTEK_TTS_PITCH=50
IFLYTEK_TTS_MAX_BYTES=8000

# 本地 Ollama + RAG
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_LLM_MODEL=qwen2.5:7b
OLLAMA_EMBED_MODEL=bge-m3
OLLAMA_TIMEOUT=120.0
EMBEDDING_DIM=1024
CHROMA_PERSIST_DIR=./data/chroma
CHROMA_COLLECTION=hospital_kb
KB_DIR=./knowledge
TRIAGE_TOP_K=4
TRIAGE_MAX_HISTORY=6
TRIAGE_CHUNK_SIZE=500
TRIAGE_CHUNK_OVERLAP=80
```

## 4. SSE 事件协议

所有流式接口（chat/companion/science/triage/tts）统一用 **POST + SSE** 返回，浏览器端不能用 `EventSource`（GET-only），改用 `fetch` + `ReadableStream` 解析（见 [05-frontend-streaming.md](./05-frontend-streaming.md)）。

帧格式：`data: {json}\n\n`，结束帧 `data: [DONE]\n\n`。

### 通用聊天 / 健康陪伴事件序列

```
data: {"conversationId":"..."}     # 首帧，后端生成或沿用
data: {"delta":"..."}              # 若干次，逐字增量
data: {"done":true}                # 正常结束
data: [DONE]
```

### 导诊事件序列（多了检索结果与科室推荐）

```
data: {"conversationId":"..."}
data: {"sources":[{"file","text"},...]}   # 引用的知识库片段
data: {"delta":"..."}
data: {"department":{...},"matchedDepartments":[...]}  # 流结束后解析出的推荐科室
data: {"done":true}
data: [DONE]
```

### 错误与中断

- 服务端异常：在生成器内捕获并输出 `data: {"error":"..."}`，随后正常收尾（`done` 或 `[DONE]`），HTTP 仍是 200。
- 客户端断开：服务端收到 `asyncio.CancelledError`，把已生成的部分文本落库并标记 `interrupted=true`，然后 `raise` 结束流。

## 5. 会话持久化

`Conversation`（id、created_at）与 `Message`（id、conversation_id、role、content、sources JSON、interrupted、created_at）共用同一张表：

- 每轮结束时写入 user + assistant 两条记录；导诊的 `sources` 会随 assistant 记录一起保存。
- 历史按 `created_at` 倒序取最近 N 条（`TRIAGE_MAX_HISTORY` / `CHAT_MAX_HISTORY` / `COMPANION_MAX_HISTORY` / `SCIENCE_MAX_HISTORY`），再反转为正序拼入上下文。
- 同一轮 user/assistant 的 `created_at` 相差 1 微秒，保证取历史时顺序稳定。
- 表结构在应用启动时由 `Base.metadata.create_all(bind=engine)` 创建（`main.py` lifespan）。
